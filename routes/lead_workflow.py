"""API REST del workflow multiagente de leads."""

import os

from flask import Blueprint, current_app, jsonify, render_template, request

from agents.lead_workflow.orchestrator import LeadWorkflowOrchestrator
from agents.lead_workflow.state_store import LeadWorkflowStateStore
from agents.lead_workflow.tasks import run_workflow_async
from agents.lead_workflow.workflow_catalog import get_workflow_catalog
from utils.security import login_required, role_required, ROLE_ADMIN, ROLE_GERENTE, ROLE_ASESOR

lead_workflow_bp = Blueprint("lead_workflow", __name__, url_prefix="/lead_workflow")
orchestrator = LeadWorkflowOrchestrator()

MANAGEMENT_ROLES = (ROLE_ADMIN, ROLE_GERENTE)
WORKFLOW_ROLES = (ROLE_ADMIN, ROLE_GERENTE, ROLE_ASESOR)


def _codigo_from_request():
    """Obtiene codigo desde JSON body, query o form."""
    data = request.get_json(silent=True) or {}
    codigo = (
        data.get("codigo")
        or request.args.get("codigo")
        or request.form.get("codigo")
        or ""
    )
    return LeadWorkflowStateStore.normalize_codigo(codigo)


def _resolve_codigo(codigo_raw):
    row, err = orchestrator.store.resolve_lead(codigo_raw)
    if err:
        return None, None, err
    return int(row["id"]), row, None


def _enrich_codigo(result, lead_row=None):
    if not isinstance(result, dict):
        return result
    codigo = (lead_row or {}).get("codigo")
    if not codigo and result.get("lead_id"):
        row = orchestrator.store.fetch_lead(result["lead_id"])
        codigo = (row or {}).get("codigo")
    if codigo:
        result["codigo"] = codigo
    return result


def trigger_workflow_for_new_lead(app, lead_id, *, auto_advance=True):
    """
    WORKFLOW MULTIAGENTE · INICIO al crear un lead.
    Comunicación entre agentes vía orquestador + tablas MySQL (no Socket.IO).
    Ver agents/lead_workflow/orchestrator.py → process_lead()
    """
    run_workflow_async(app, int(lead_id), orchestrator, auto_advance=auto_advance)


# ═══════════════════════════════════════════════════════════════════════════════
# WORKFLOW LEADS · MAPA — COMUNICACIÓN MULTIAGENTE (al crear/process lead)
# ───────────────────────────────────────────────────────────────────────────────
# INICIO  routes/lead.py create_lead() → trigger_workflow_for_new_lead()
#         o POST /lead_workflow/process
# NÚCLEO  agents/lead_workflow/orchestrator.py → process_lead()
#         scoring → assignment → commercial → recovery → closing (secuencial)
# PERSIST agents/lead_workflow/state_store.py → lead_agent_state, agent_interactions
# FIN     nodo completed | dead | awaiting_response (espera webhook/manual)
# NO usa Socket.IO — ver Monitor en /lead_workflow/monitor y trace API
# ═══════════════════════════════════════════════════════════════════════════════


@lead_workflow_bp.route("/process", methods=["POST"])
@login_required
@role_required(*WORKFLOW_ROLES)
def process_lead():
    """
    Inicia o continúa el workflow multiagente para un lead.
    Body JSON: { "codigo": "LED-4878", "async": true, "auto_advance": true }
    """
    payload = request.get_json(silent=True) or {}
    lead_id, lead_row, err = _resolve_codigo(payload.get("codigo"))
    if err:
        return jsonify({"ok": False, "error": err}), 400

    auto_advance = payload.get("auto_advance", True)
    run_async = payload.get("async", True)
    codigo = lead_row.get("codigo")

    if run_async:
        run_workflow_async(
            current_app._get_current_object(), lead_id, orchestrator, auto_advance=auto_advance
        )
        return jsonify(
            {
                "ok": True,
                "codigo": codigo,
                "status": "processing",
                "message": f"Workflow iniciado. Consulte /lead_workflow/status/{codigo}.",
            }
        )

    result = orchestrator.process_lead(lead_id, auto_advance=auto_advance)
    result = _enrich_codigo(result, lead_row)
    status_code = 200 if result.get("ok") else 400
    return jsonify(result), status_code


@lead_workflow_bp.route("/status/<codigo>", methods=["GET"])
@login_required
@role_required(*WORKFLOW_ROLES)
def workflow_status(codigo):
    lead_id, lead_row, err = _resolve_codigo(codigo)
    if err:
        return jsonify({"ok": False, "error": err}), 404
    result = _enrich_codigo(orchestrator.get_status(lead_id), lead_row)
    status_code = 200 if result.get("ok") else 404
    return jsonify(result), status_code


@lead_workflow_bp.route("/manual", methods=["POST"])
@login_required
@role_required(*WORKFLOW_ROLES)
def manual_action():
    """
    Acciones manuales sobre el workflow.
    Body: { "codigo": "LED-4878", "action": "...", "payload": {} }
    """
    data = request.get_json(silent=True) or {}
    action = (data.get("action") or "").strip()
    lead_id, lead_row, err = _resolve_codigo(data.get("codigo"))
    if err:
        return jsonify({"ok": False, "error": err}), 400
    if not action:
        return jsonify({"ok": False, "error": "action es obligatorio"}), 400

    result = _enrich_codigo(
        orchestrator.manual_action(
            lead_id, action, data.get("payload") or {}, lead_row=lead_row
        ),
        lead_row,
    )
    status_code = 200 if result.get("ok") else 400
    return jsonify(result), status_code


@lead_workflow_bp.route("/webhook", methods=["POST"])
def workflow_webhook():
    """
    Webhook para respuestas del lead.
    Body: { "codigo": "LED-4878", "responded": true, ... }
    """
    data = request.get_json(silent=True) or {}
    webhook_secret = os.getenv("LEAD_WORKFLOW_WEBHOOK_SECRET", "")
    if webhook_secret:
        provided = request.headers.get("X-Webhook-Secret") or data.get("secret")
        if provided != webhook_secret:
            return jsonify({"ok": False, "error": "Webhook no autorizado"}), 401

    lead_id, lead_row, err = _resolve_codigo(data.get("codigo"))
    if err:
        return jsonify({"ok": False, "error": err}), 400

    result = _enrich_codigo(
        orchestrator.handle_lead_response(
            lead_id,
            responded=bool(data.get("responded", True)),
            response_content=data.get("response_content"),
            sale_won=data.get("sale_won"),
            monto=data.get("monto", 0),
            motivo_no_venta=data.get("motivo_no_venta"),
            lead_row=lead_row,
        ),
        lead_row,
    )
    status_code = 200 if result.get("ok") else 400
    return jsonify(result), status_code


@lead_workflow_bp.route("/monitor", methods=["GET"])
@login_required
@role_required(*WORKFLOW_ROLES)
def workflow_monitor_home():
    """Panel visual del workflow multiagente de leads."""
    return render_template("agents/workflow_monitor.html")


@lead_workflow_bp.route("/recent", methods=["GET"])
@login_required
@role_required(*WORKFLOW_ROLES)
def workflow_recent():
    """Interacciones y estados recientes del workflow (para el panel visual)."""
    limit = request.args.get("limit", 50, type=int)
    limit = max(1, min(limit, 200))
    workflows = orchestrator.store.list_active_workflows(limit=limit)
    for wf in workflows:
        wf["codigo"] = wf.get("lead_codigo")
    interactions = orchestrator.store.list_recent_interactions(limit=limit)
    for it in interactions:
        it["codigo"] = it.get("lead_codigo")
    return jsonify(
        {
            "ok": True,
            "workflows": workflows,
            "interactions": interactions,
        }
    )


@lead_workflow_bp.route("/trace/<codigo>", methods=["GET"])
@login_required
@role_required(*WORKFLOW_ROLES)
def workflow_trace(codigo):
    """Trazabilidad del lead por codigo: pipeline, agentes, herramientas."""
    lead_id, lead_row, err = _resolve_codigo(codigo)
    if err:
        return jsonify({"ok": False, "error": err}), 404
    result = orchestrator.get_lead_trace(lead_id)
    if result.get("ok"):
        result["codigo"] = lead_row.get("codigo")
        if result.get("orchestrator_flow"):
            result["orchestrator_flow"]["codigo"] = lead_row.get("codigo")
        if result.get("lead"):
            result["lead"]["codigo"] = lead_row.get("codigo")
    status_code = 200 if result.get("ok") else 404
    return jsonify(result), status_code


@lead_workflow_bp.route("/catalog", methods=["GET"])
@login_required
@role_required(*WORKFLOW_ROLES)
def workflow_catalog_route():
    """Catálogo estático del grafo multiagente (nodos y herramientas)."""
    return jsonify({"ok": True, **get_workflow_catalog()})


@lead_workflow_bp.route("/management/dashboard", methods=["GET"])
@login_required
@role_required(*MANAGEMENT_ROLES)
def management_dashboard():
    """KPIs ejecutivos: CAC, adquisición, retención, score promedio (Gerencia)."""
    result = orchestrator.get_management_dashboard()
    return jsonify(result)


@lead_workflow_bp.route("/analyze/<codigo>", methods=["GET"])
@login_required
@role_required(*WORKFLOW_ROLES)
def analyze_lead_only(codigo):
    """Solo ejecuta los 4 agentes de análisis + score global, sin avanzar el workflow."""
    from agents.lead_workflow.lead_scoring import LeadScoringAgent

    lead_id, lead_row, err = _resolve_codigo(codigo)
    if err:
        return jsonify({"ok": False, "error": err}), 404

    scoring = LeadScoringAgent()
    result = scoring.analyze(lead_row)
    return jsonify(
        {
            "ok": True,
            "codigo": lead_row.get("codigo"),
            "analysis": result,
        }
    )
