"""
Orquestador del workflow multiagente de leads (diagrama TO-BE).

# ═══ WORKFLOW LEADS · MAPA DE COMUNICACIÓN MULTIAGENTE (MySQL, no Socket.IO) ═══
# INICIO   routes/lead.py → trigger_workflow_for_new_lead() al crear lead
#          routes/lead_workflow.py → POST /lead_workflow/process
#
# PASO 1   _run_scoring()        → lead_scoring.py (+ 4 sub-agentes de análisis)
# PASO 2   _run_assignment()     → commercial_assistant.assign_advisor()
# PASO 3   _run_commercial_contact() → commercial_assistant.contact() [máx. 2 intentos]
# PASO 4   _run_recovery_contact()  → recovery_agent [si no responde]
# PASO 5   _run_closing()        → closing_agent [si responde / venta]
# FIN      nodo completed | dead | awaiting_response (espera webhook/manual)
#
# Cada paso registra en state_store.log_interaction() → tabla agent_interactions
# ═══════════════════════════════════════════════════════════════════════════════

Flujo:
  scoring (4 agentes) → assignment → commercial (2 intentos)
  → recovery (2 intentos) | closing | dead | completed

Implementa un grafo de estados explícito (patrón LangGraph) sin dependencia externa,
compatible con el broker existente en agents/broker/orchestrator.py.
"""

import logging
from datetime import datetime

from agents.lead_workflow.state_store import LeadWorkflowStateStore
from agents.lead_workflow.lead_scoring import LeadScoringAgent
from agents.lead_workflow.commercial_assistant import CommercialAssistantAgent
from agents.lead_workflow.recovery_agent import RecoveryAgent
from agents.lead_workflow.closing_agent import ClosingAgent
from agents.lead_workflow.management_agent import ManagementAgent
from agents.lead_workflow.workflow_catalog import (
    AGENT_TO_NODE,
    NODE_INDEX,
    enrich_scoring_step,
    get_node_catalog,
    get_workflow_catalog,
)

logger = logging.getLogger(__name__)


class LeadWorkflowOrchestrator:
    COMMERCIAL_MAX = CommercialAssistantAgent.MAX_COMMERCIAL_ATTEMPTS
    RECOVERY_MAX = RecoveryAgent.MAX_RECOVERY_ATTEMPTS

    def __init__(self):
        self.store = LeadWorkflowStateStore()
        self.scoring = LeadScoringAgent()
        self.commercial = CommercialAssistantAgent()
        self.recovery = RecoveryAgent()
        self.closing = ClosingAgent()
        self.management = ManagementAgent()

    def _score_data_from_state(self, state):
        data = state.get("data") or {}
        if isinstance(data, str):
            import json

            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                data = {}
        return {
            "global_score": state.get("score", 0),
            "priority_label": state.get("priority_label"),
            "agent_outputs": data.get("agent_outputs", {}),
        }

    def _wrap_step(self, node, result, state, **extra):
        catalog = get_node_catalog(node) or {}
        step = {
            "node": node,
            "agent": catalog.get("agent") or extra.get("agent"),
            "label": catalog.get("label", node),
            "description": catalog.get("description", ""),
            "tools": catalog.get("tools", []),
            "sub_agents": catalog.get("sub_agents", []),
            "result": result,
            "state": state,
        }
        if node == "scoring" and isinstance(result, dict):
            step["sub_agent_results"] = enrich_scoring_step(result)
        step.update(extra)
        return step

    def _run_scoring(self, lead_row):
        # ═══ WORKFLOW · PASO 1/5 · Scoring (4 sub-agentes) → ver lead_scoring.py ═══
        result = self.scoring.analyze(lead_row)
        self.store.log_interaction(
            lead_row["id"],
            "lead_scoring",
            content=result.get("recommendation"),
            metadata={"global_score": result.get("global_score")},
        )
        state = self.store.upsert_state(
            lead_row["id"],
            current_node="assignment",
            score=result["global_score"],
            priority_label=result["priority_label"],
            recommendation=result["recommendation"],
            data={"agent_outputs": result["agent_outputs"], "scoring": result},
        )
        return self._wrap_step("scoring", result, state)

    def _run_assignment(self, lead_row, state):
        # ═══ WORKFLOW · PASO 2/5 · Asignación de asesor → commercial_assistant.py ═══
        score_data = self._score_data_from_state(state)
        assignment = self.commercial.assign_advisor(lead_row, score_data)
        self.store.log_interaction(
            lead_row["id"],
            "commercial_assistant",
            content=f"Asignado a asesor {assignment.get('assigned_to')}",
            metadata=assignment,
        )
        state = self.store.upsert_state(
            lead_row["id"],
            current_node="commercial",
            assigned_to=assignment.get("assigned_to"),
            data={"assignment": assignment},
        )
        return self._wrap_step("assignment", assignment, state)

    def _run_commercial_contact(self, lead_row, state, attempt=None):
        # ═══ WORKFLOW · PASO 3/5 · Contacto comercial (1er/2do intento) ═══
        score_data = self._score_data_from_state(state)
        current_attempts = int(state.get("attempts") or 0)
        attempt = attempt or (current_attempts + 1)

        if attempt > self.COMMERCIAL_MAX:
            state = self.store.upsert_state(
                lead_row["id"],
                current_node="recovery",
                attempts=current_attempts,
            )
            return self._run_recovery_contact(lead_row, self.store.get_state(lead_row["id"]))

        contact = self.commercial.contact(lead_row, attempt, score_data)
        self.store.log_interaction(
            lead_row["id"],
            "commercial_assistant",
            interaction_type=contact["channel"],
            content=contact["message"],
            metadata={"attempt": attempt},
        )
        state = self.store.upsert_state(
            lead_row["id"],
            current_node="commercial",
            attempts=attempt,
            next_action_date=contact.get("next_followup"),
            data={"last_contact": contact},
            workflow_status="active",
        )
        return self._wrap_step(
            "commercial",
            contact,
            state,
            awaiting_response=True,
        )

    def _run_recovery_contact(self, lead_row, state):
        # ═══ WORKFLOW · PASO 4/5 · Recuperación (si no hubo respuesta comercial) ═══
        data = state.get("data") or {}
        if isinstance(data, str):
            import json

            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                data = {}

        recovery_attempts = int(data.get("recovery_attempts") or 0) + 1
        if recovery_attempts > self.RECOVERY_MAX:
            dead = self.recovery.mark_dead_lead(lead_row["id"])
            self.store.log_interaction(
                lead_row["id"],
                "recovery_agent",
                content=dead["reason"],
                metadata=dead,
            )
            state = self.store.upsert_state(
                lead_row["id"],
                current_node="dead",
                workflow_status="dead",
                data={"recovery_attempts": recovery_attempts, "dead": dead},
            )
            return self._wrap_step("dead", dead, state)

        contact = self.recovery.run_attempt(lead_row, recovery_attempts)
        self.store.log_interaction(
            lead_row["id"],
            "recovery_agent",
            interaction_type=contact["channel"],
            content=contact["message"],
            metadata={"recovery_attempt": recovery_attempts},
        )
        state = self.store.upsert_state(
            lead_row["id"],
            current_node="recovery",
            next_action_date=contact.get("next_followup"),
            data={"recovery_attempts": recovery_attempts, "last_recovery": contact},
        )
        return self._wrap_step(
            "recovery",
            contact,
            state,
            awaiting_response=True,
        )

    def _run_closing(self, lead_row, state, *, sale_won=True, monto=0, motivo_no_venta=None):
        # ═══ WORKFLOW · PASO 5/5 · Cierre y registro venta/no venta → closing_agent.py ═══
        score_data = self._score_data_from_state(state)
        proposal = self.closing.prepare_proposal(lead_row, score_data)
        registration = self.closing.register_sale(
            lead_row["id"],
            sale_won=sale_won,
            monto=monto,
            motivo_no_venta=motivo_no_venta,
        )
        self.store.log_interaction(
            lead_row["id"],
            "closing_agent",
            content=proposal["summary"],
            response_received=True,
            response_content=str(registration),
            metadata={"sale_won": sale_won},
        )
        state = self.store.upsert_state(
            lead_row["id"],
            current_node="completed",
            workflow_status="completed",
            data={"proposal": proposal, "registration": registration},
        )
        closing_result = {"proposal": proposal, "registration": registration}
        return self._wrap_step("completed", closing_result, state)

    def ensure_workflow_started(self, lead_id, lead_row=None, *, auto_advance=True):
        """Crea estado inicial si el lead aún no tiene workflow."""
        if not self.store.ensure_tables():
            return {
                "ok": False,
                "error": (
                    "Tablas de workflow no encontradas. "
                    "Ejecute db/migrations/2026_05_25_create_lead_workflow_tables.sql"
                ),
            }

        lead_row = lead_row or self.store.fetch_lead(lead_id)
        if not lead_row:
            return {"ok": False, "error": f"Lead no encontrado (id={lead_id})."}

        if self.store.get_state(lead_id):
            return {
                "ok": True,
                "started": False,
                "lead_id": lead_id,
                "codigo": lead_row.get("codigo"),
                "state": self.store.get_state(lead_id),
            }

        result = self.process_lead(lead_id, auto_advance=auto_advance)
        if result.get("ok"):
            result["started"] = True
        return result

    def process_lead(self, lead_id, *, auto_advance=True):
        """
        WORKFLOW MULTIAGENTE · NÚCLEO — aquí se encadenan los agentes de lead.
        Comunicación: llamadas Python + registros en agent_interactions (MySQL).
        NO usa Socket.IO (eso es solo el Chat IA en agents/broker/).
        """
        try:
            return self._process_lead_impl(lead_id, auto_advance=auto_advance)
        except Exception as exc:
            logger.exception("Error procesando workflow lead_id=%s", lead_id)
            return {"ok": False, "error": f"Error al procesar workflow: {exc}"}

    def _process_lead_impl(self, lead_id, *, auto_advance=True):
        """Ejecuta el workflow desde el nodo actual hasta un punto de espera o fin."""
        # ═══ WORKFLOW LEADS · INICIO comunicación multiagente (este lead) ═══
        if not self.store.ensure_tables():
            return {
                "ok": False,
                "error": (
                    "Tablas de workflow no encontradas. "
                    "Ejecute db/migrations/2026_05_25_create_lead_workflow_tables.sql"
                ),
            }

        lead_row = self.store.fetch_lead(lead_id)
        if not lead_row:
            return {"ok": False, "error": f"Lead no encontrado (id={lead_id})."}

        state = self.store.get_state(lead_id)
        if not state:
            step = self._run_scoring(lead_row)
            state = step["state"]
            if not auto_advance:
                return {"ok": True, "lead_id": lead_id, "steps": [step], "state": state}

        steps = []
        node = state.get("current_node", "scoring")

        while auto_advance:
            if node == "scoring":
                step = self._run_scoring(lead_row)           # PASO 1
            elif node == "assignment":
                step = self._run_assignment(lead_row, state)  # PASO 2
            elif node == "commercial":
                step = self._run_commercial_contact(lead_row, state)  # PASO 3
                steps.append(step)
                break
            elif node == "recovery":
                step = self._run_recovery_contact(lead_row, state)  # PASO 4
                steps.append(step)
                break
            elif node in ("closing", "completed", "dead"):
                break
            else:
                break

            steps.append(step)
            state = step.get("state") or state
            node = state.get("current_node", node)

            if step.get("awaiting_response"):
                break
            if node in ("dead", "completed"):
                break

        # ═══ WORKFLOW LEADS · FIN (retorna estado + interacciones registradas) ═══
        return {
            "ok": True,
            "lead_id": lead_id,
            "codigo": lead_row.get("codigo"),
            "steps": steps,
            "state": self.store.get_state(lead_id),
            "interactions": self.store.get_interactions(lead_id, limit=10),
        }

    def handle_lead_response(
        self,
        lead_id,
        *,
        responded=True,
        response_content=None,
        sale_won=None,
        monto=0,
        motivo_no_venta=None,
        lead_row=None,
    ):
        """Webhook/evento: el lead respondió (o no) a un contacto."""
        lead_row = lead_row or self.store.fetch_lead(lead_id)
        if not lead_row:
            return {"ok": False, "error": "Lead no encontrado."}

        state = self.store.get_state(lead_id)
        if not state:
            ensured = self.ensure_workflow_started(lead_id, lead_row)
            if not ensured.get("ok"):
                return ensured
            state = self.store.get_state(lead_id)
        if not state:
            return {"ok": False, "error": "No se pudo iniciar el workflow para este lead."}

        node = state.get("current_node")
        self.store.log_interaction(
            lead_id,
            node or "workflow",
            direction="inbound",
            content=response_content,
            response_received=responded,
            response_content=response_content,
        )

        if responded:
            if sale_won is None:
                sale_won = True
            step = self._run_closing(
                lead_row,
                state,
                sale_won=sale_won,
                monto=monto,
                motivo_no_venta=motivo_no_venta,
            )
            return {"ok": True, "lead_id": lead_id, "codigo": lead_row.get("codigo"), "steps": [step], "state": step["state"]}

        attempts = int(state.get("attempts") or 0)
        data = state.get("data") or {}
        if isinstance(data, str):
            import json

            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                data = {}

        if node == "commercial" and attempts < self.COMMERCIAL_MAX:
            step = self._run_commercial_contact(lead_row, state, attempt=attempts + 1)
        elif node == "commercial":
            state = self.store.upsert_state(lead_id, current_node="recovery")
            step = self._run_recovery_contact(lead_row, state)
        elif node == "recovery":
            step = self._run_recovery_contact(lead_row, state)
        else:
            return {"ok": False, "error": f"Nodo '{node}' no admite respuesta automática."}

        return {"ok": True, "lead_id": lead_id, "codigo": lead_row.get("codigo"), "steps": [step], "state": step["state"]}

    def manual_action(self, lead_id, action, payload=None, lead_row=None):
        """Acciones manuales: reintentar, forzar nodo, cambiar score, registrar venta."""
        payload = payload or {}
        lead_row = lead_row or self.store.fetch_lead(lead_id)
        if not lead_row:
            return {"ok": False, "error": f"Lead no encontrado (id={lead_id})."}

        state = self.store.get_state(lead_id)

        if action in ("simulate_response", "simulate_no_response", "register_sale"):
            ensured = self.ensure_workflow_started(lead_id, lead_row)
            if not ensured.get("ok"):
                return ensured
            state = self.store.get_state(lead_id)

        if action == "restart":
            self.store.upsert_state(
                lead_id,
                current_node="scoring",
                attempts=0,
                workflow_status="active",
                data={},
            )
            return self.process_lead(lead_id, auto_advance=payload.get("auto_advance", True))

        if action == "force_node":
            node = payload.get("node")
            if node not in LeadWorkflowStateStore.WORKFLOW_NODES:
                return {"ok": False, "error": f"Nodo inválido: {node}"}
            self.store.upsert_state(lead_id, current_node=node)
            return {"ok": True, "state": self.store.get_state(lead_id)}

        if action == "set_score":
            score = int(payload.get("score", 0))
            priority = payload.get("priority_label")
            if not priority:
                priority = "Alta" if score >= 75 else "Media" if score >= 50 else "Baja"
            self.store.upsert_state(
                lead_id,
                score=score,
                priority_label=priority,
                recommendation=payload.get("recommendation"),
            )
            return {"ok": True, "state": self.store.get_state(lead_id)}

        if action == "register_sale":
            if not state:
                return {"ok": False, "error": "El lead no tiene workflow iniciado."}
            step = self._run_closing(
                lead_row,
                state,
                sale_won=payload.get("sale_won", True),
                monto=payload.get("monto", 0),
                motivo_no_venta=payload.get("motivo_no_venta"),
            )
            return {"ok": True, "steps": [step], "state": step["state"]}

        if action == "simulate_no_response":
            return self.handle_lead_response(lead_id, responded=False)

        if action == "simulate_response":
            return self.handle_lead_response(
                lead_id,
                responded=True,
                response_content=payload.get("response_content"),
                sale_won=payload.get("sale_won", True),
                monto=payload.get("monto", 0),
            )

        return {"ok": False, "error": f"Acción desconocida: {action}"}

    def get_status(self, lead_id):
        lead_row = self.store.fetch_lead(lead_id)
        state = self.store.get_state(lead_id)
        if not state:
            return {
                "ok": False,
                "error": "Workflow no iniciado para este lead.",
                "codigo": (lead_row or {}).get("codigo"),
                "hint": "Use POST /lead_workflow/process con el codigo del lead.",
            }
        return {
            "ok": True,
            "lead_id": lead_id,
            "codigo": (lead_row or {}).get("codigo"),
            "state": state,
            "interactions": self.store.get_interactions(lead_id),
        }

    def get_lead_trace(self, lead_id):
        """Trazabilidad completa: pipeline, nodo actual, interacciones y herramientas."""
        lead_row = self.store.fetch_lead(lead_id)
        if not lead_row:
            return {"ok": False, "error": "Lead no encontrado."}

        codigo = lead_row.get("codigo")
        state = self.store.get_state(lead_id)
        if not state:
            pipeline_status = [
                {**item, "status": "pending"} for item in get_workflow_catalog()["pipeline"]
            ]
            return {
                "ok": True,
                "workflow_started": False,
                "lead_id": lead_id,
                "codigo": codigo,
                "lead": {"id": lead_id, "codigo": codigo, "nombre": lead_row.get("nombre")},
                "state": None,
                "current_node": None,
                "pipeline": pipeline_status,
                "timeline": [],
                "scoring_detail": None,
                "orchestrator_flow": {
                    "orchestrator": "LeadWorkflowOrchestrator",
                    "codigo": codigo,
                    "workflow_started": False,
                    "message": "Workflow no iniciado. Pulse 'Iniciar workflow' o POST /lead_workflow/process.",
                    "steps": [],
                },
                "catalog": get_workflow_catalog(),
            }
        interactions = self.store.get_interactions(lead_id) or []
        interactions = list(reversed(interactions))
        current_node = state.get("current_node", "scoring")
        current_idx = NODE_INDEX.get(current_node, 0)

        pipeline_status = []
        for item in get_workflow_catalog()["pipeline"]:
            idx = NODE_INDEX.get(item["node"], -1)
            if item["node"] in ("dead", "completed"):
                status = "completed" if current_node == item["node"] else "pending"
            elif idx < current_idx:
                status = "completed"
            elif idx == current_idx:
                status = "active"
            else:
                status = "pending"
            pipeline_status.append({**item, "status": status})

        timeline = []
        for i, it in enumerate(interactions):
            agent = it.get("agent_name") or "workflow"
            meta = it.get("metadata")
            if isinstance(meta, str):
                try:
                    import json

                    meta = json.loads(meta)
                except json.JSONDecodeError:
                    meta = {}
            if not isinstance(meta, dict):
                meta = {}

            if agent == "commercial_assistant" and meta.get("attempt"):
                node = "commercial"
            elif agent == "commercial_assistant":
                node = "assignment"
            elif agent == "recovery_agent" and meta.get("recovery_attempt"):
                node = "recovery"
            elif agent == "closing_agent":
                node = "completed" if state.get("current_node") == "completed" else "closing"
            else:
                node = AGENT_TO_NODE.get(agent, state.get("current_node"))
            catalog = get_node_catalog(node) or {}
            timeline.append(
                {
                    "order": i + 1,
                    "node": node,
                    "agent": agent,
                    "label": catalog.get("label", agent),
                    "tools": catalog.get("tools", []),
                    "sub_agents": catalog.get("sub_agents", []),
                    "interaction_type": it.get("interaction_type"),
                    "direction": it.get("direction"),
                    "content": it.get("content"),
                    "response_received": it.get("response_received"),
                    "created_at": str(it.get("created_at") or ""),
                    "metadata": meta,
                }
            )

        data = state.get("data") or {}
        if isinstance(data, str):
            import json

            try:
                data = json.loads(data)
            except json.JSONDecodeError:
                data = {}

        scoring_block = None
        if data.get("agent_outputs") or data.get("scoring"):
            scoring_src = data.get("scoring") or {}
            scoring_block = {
                "global_score": state.get("score"),
                "priority_label": state.get("priority_label"),
                "recommendation": state.get("recommendation"),
                "weights": scoring_src.get("weights"),
                "sub_agent_results": enrich_scoring_step(
                    scoring_src
                    if scoring_src.get("agent_outputs")
                    else {"agent_outputs": data.get("agent_outputs")}
                ),
            }
            for step in timeline:
                if step.get("agent") == "lead_scoring":
                    step["sub_agent_results"] = scoring_block["sub_agent_results"]

        orchestrator_flow = self._build_orchestrator_flow(
            lead_id,
            (lead_row or {}).get("codigo"),
            state,
            timeline,
            scoring_block,
            pipeline_status,
        )

        return {
            "ok": True,
            "workflow_started": True,
            "lead_id": lead_id,
            "codigo": (lead_row or {}).get("codigo"),
            "lead": {
                "id": lead_id,
                "codigo": (lead_row or {}).get("codigo"),
                "nombre": (lead_row or {}).get("nombre"),
            },
            "state": state,
            "current_node": current_node,
            "pipeline": pipeline_status,
            "timeline": timeline,
            "scoring_detail": scoring_block,
            "orchestrator_flow": orchestrator_flow,
            "catalog": get_workflow_catalog(),
        }

    def _build_orchestrator_flow(
        self, lead_id, codigo, state, timeline, scoring_block, pipeline
    ):
        """JSON estructurado: paso a paso del orquestador con agentes y herramientas."""
        flow = []
        order = 0

        for item in pipeline:
            if item.get("status") == "pending" and order > 0:
                continue
            order += 1
            step = {
                "step": order,
                "node": item.get("node"),
                "label": item.get("label"),
                "agent": item.get("agent"),
                "status": item.get("status"),
                "tools": item.get("tools", []),
                "sub_agents": item.get("sub_agents", []),
            }
            if item.get("node") == "scoring" and scoring_block:
                step["output"] = {
                    "global_score": scoring_block.get("global_score"),
                    "priority_label": scoring_block.get("priority_label"),
                    "recommendation": scoring_block.get("recommendation"),
                    "sub_agent_results": scoring_block.get("sub_agent_results"),
                }
            flow.append(step)

        for t in timeline:
            order += 1
            flow.append(
                {
                    "step": order,
                    "event": "agent_execution",
                    "node": t.get("node"),
                    "label": t.get("label"),
                    "agent": t.get("agent"),
                    "tools": t.get("tools", []),
                    "sub_agents": t.get("sub_agents", []),
                    "sub_agent_results": t.get("sub_agent_results"),
                    "interaction": {
                        "type": t.get("interaction_type"),
                        "direction": t.get("direction"),
                        "content": t.get("content"),
                        "metadata": t.get("metadata"),
                        "at": t.get("created_at"),
                    },
                }
            )

        return {
            "orchestrator": "LeadWorkflowOrchestrator",
            "codigo": codigo,
            "lead_id": lead_id,
            "current_node": state.get("current_node"),
            "workflow_status": state.get("workflow_status"),
            "steps": flow,
        }

    def get_management_dashboard(self):
        return {"ok": True, "kpis": self.management.compute_dashboard_kpis()}
