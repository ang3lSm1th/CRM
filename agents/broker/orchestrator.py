import os
import re
import json
import time
from datetime import datetime
from uuid import uuid4
from collections import deque

import MySQLdb.cursors

from agents.core.db_agent import DBAgent
from agents.core.marketing_agent import MarketingAgent
from agents.core.llm_agent import LLMAgent
from agents.core.prediccion_agente import PrediccionCompraAgente
from agents.core.reportes_agente import ReportesAgente
from agents.core.retencion_agente import RetencionAbandonoAgente
from extensions import mysql, socketio
from models.agent_models.memory_models import AgentMemory, AgentStats
from models.user import User
from utils.text_normalizer import normalize_user_text


class AgentOrchestrator:
    def __init__(self):
        self.db_agent = DBAgent()
        self.marketing_agent = MarketingAgent()
        self.llm_agent = LLMAgent()
        self.prediccion_agente = PrediccionCompraAgente()
        self.reportes_agente = ReportesAgente()
        self.retencion_agente = RetencionAbandonoAgente()
        self.memory_size = int(os.getenv("AGENT_MEMORY_SIZE", "10"))
        self.allow_llm_fallback_for_data = (
            os.getenv("ALLOW_LLM_FALLBACK_FOR_DATA", "0") == "1"
        )
        self.agent_catalog = self._build_agent_catalog()
        self.agents = {
            "database": self.db_agent,
            "marketing": self.marketing_agent,
            "llm": self.llm_agent,
            "prediccion": self.prediccion_agente,
            "reportes": self.reportes_agente,
            "retencion_abandono": self.retencion_agente,
        }
        self.routing_patterns = {
            "prediccion": [
                r"\b(probabilidad|prediccion|predicción|comprar|compra)\b.*\blead\b",
                r"\blead\b.*\b(probabilidad|prediccion|predicción)\b",
            ],
            "reportes": [
                r"\b(tendencia|embudo|conversion|conversión|funnel|producto mas vendido|producto más vendido)\b",
                r"\breporte\b.*\b(ventas|conversion|conversión|producto)\b",
                r"\b(reporte|reportes|informe|resumen)\b",
            ],
            "retencion_abandono": [
                r"\b(retencion|retención|recurrentes|abandono|inactivos|inactividad|churn)\b",
                r"\bleads?\b.*\b(riesgo|abandono|inactivo)\b",
            ],
            "marketing": [
                r"\b(campana|campaña|campanas|campañas|marketing|feria|ferias|inventario|stock|mercaderia|mercadería|impresiones|alcance|cpc)\b"
            ],
            "database": [
                r"\b(lead|leads|venta|ventas|pipeline|embudo|estado de leads|clientes|cerrados|cotizados|cuantos|cuántos|cuanto|cuánto|total|mes|enero|febrero|marzo|abril|mayo|junio|julio|agosto|septiembre|octubre|noviembre|diciembre|ultimos|últimos|dias|estado|nuevo|nuevos|pendiente|pendientes|seguimiento|seguimientos|gestion|gestión)\b"
            ],
        }
        self._communications = deque(maxlen=500)
        self._traces = deque(maxlen=1500)

    def _build_agent_catalog(self):
        return {
            "database": {
                "agent_id": "db_agent",
                "intent": "database",
                "role": "Analista SQL de CRM",
                "goal": "Responder consultas de leads y ventas con datos reales del sistema.",
                "tools": [
                    {
                        "name": "natural_to_sql",
                        "description": "Convierte lenguaje natural en SQL controlado.",
                    },
                    {
                        "name": "sql_scalar_query",
                        "description": "Ejecuta consultas agregadas seguras (COUNT/SUM).",
                    },
                    {
                        "name": "schema_guard",
                        "description": "Valida existencia de tablas y columnas antes de consultar.",
                    },
                ],
            },
            "marketing": {
                "agent_id": "marketing_agent",
                "intent": "marketing",
                "role": "Analista de Marketing CRM",
                "goal": "Reportar estado de campanas, inventario y ferias con tablas internas.",
                "tools": [
                    {
                        "name": "campaign_status_tool",
                        "description": "Resume campanas activas/finalizadas.",
                    },
                    {
                        "name": "inventory_snapshot_tool",
                        "description": "Consulta stock e inventario de marketing.",
                    },
                    {
                        "name": "ferias_metrics_tool",
                        "description": "Calcula indicadores de ferias y leads.",
                    },
                ],
            },
            "prediccion": {
                "agent_id": "prediccion_compra",
                "intent": "prediccion",
                "role": "Especialista ML de Probabilidad de Compra",
                "goal": "Predecir conversion de un lead usando modelo entrenado y variables reales.",
                "tools": [
                    {
                        "name": "lead_feature_builder",
                        "description": "Construye features del lead desde BD.",
                    },
                    {
                        "name": "ml_inference_tool",
                        "description": "Ejecuta predict_proba sobre el modelo cargado.",
                    },
                    {
                        "name": "prediction_cache_tool",
                        "description": "Guarda predicciones en historial ML.",
                    },
                ],
            },
            "reportes": {
                "agent_id": "reportes_agente",
                "intent": "reportes",
                "role": "Analista de Reporteria Comercial",
                "goal": "Entregar reportes de tendencia, embudo y top producto con datos historicos.",
                "tools": [
                    {
                        "name": "ventas_tendencia_tool",
                        "description": "Serie mensual de ventas recientes.",
                    },
                    {
                        "name": "embudo_conversion_tool",
                        "description": "Calcula contacto y cierre de embudo.",
                    },
                    {
                        "name": "top_producto_tool",
                        "description": "Detecta producto mas vendido por volumen.",
                    },
                ],
            },
            "retencion_abandono": {
                "agent_id": "retencion_abandono",
                "intent": "retencion_abandono",
                "role": "Analista de Retencion y Churn",
                "goal": "Estimar retencion y detectar leads con riesgo de abandono.",
                "tools": [
                    {
                        "name": "retention_rate_tool",
                        "description": "Calcula clientes recurrentes sobre compradores.",
                    },
                    {
                        "name": "churn_risk_tool",
                        "description": "Lista leads inactivos y dias de inactividad.",
                    },
                ],
            },
            "llm": {
                "agent_id": "llm_agent",
                "intent": "llm",
                "role": "Asistente General Controlado",
                "goal": "Atender consultas no estructuradas cuando no existe mapping de datos.",
                "tools": [
                    {
                        "name": "openai_chat_tool",
                        "description": "Generacion con proveedor OpenAI si esta disponible.",
                    },
                    {
                        "name": "groq_fallback_tool",
                        "description": "Fallback via LiteLLM para continuidad del servicio.",
                    },
                ],
            },
        }

    def get_agent_registry(self):
        return list(self.agent_catalog.values())

    def _emit_trace(
        self,
        trace_id,
        session_id,
        question,
        step,
        component,
        action,
        intent=None,
        selected_agent=None,
        tool=None,
        ok=None,
        detail=None,
    ):
        event = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "trace_id": trace_id,
            "session_id": session_id,
            "question": question,
            "step": step,
            "component": component,
            "action": action,
            "intent": intent,
            "selected_agent": selected_agent,
            "tool": tool,
            "ok": ok,
            "detail": detail,
        }
        self._traces.appendleft(event)
        try:
            socketio.emit("debug_trace", event)
            socketio.emit(
                "agent_socket_event",
                {
                    "event": "debug_trace",
                    "direction": "orquestador → monitor",
                    "timestamp": event["timestamp"],
                    "step": step,
                    "component": component,
                    "action": action,
                    "intent": intent,
                    "selected_agent": selected_agent,
                    "trace_id": trace_id,
                },
            )
        except Exception:
            pass

    def get_recent_traces(self, limit=40):
        safe_limit = max(1, min(int(limit or 40), 300))
        return list(self._traces)[:safe_limit]

    def _infer_tools_used(self, intent, result):
        tools = []
        if result.get("sql"):
            tools.append("sql_query")
        if intent == "prediccion":
            tools.extend(["lead_feature_builder", "ml_inference_tool"])
        if intent == "reportes":
            tools.append("analytics_query")
        if intent == "marketing":
            tools.append("marketing_query")
        if intent == "retencion_abandono":
            tools.append("retention_query")
        if intent == "llm":
            tools.append(result.get("provider") or "llm_completion")
        if not tools:
            tools.append("internal_handler")
        return tools

    def _classify_intent(self, question):
        q = normalize_user_text(question)

        # Si la consulta pide leads o ventas, la fuente correcta es SQL/BD.
        if re.search(
            r"\bleads?\b|\bventas?\b|\bpipeline\b|\bembudo\b|\bcotizad[oa]s?\b",
            q,
            re.IGNORECASE,
        ):
            return "database"

        for intent, patterns in self.routing_patterns.items():
            for pattern in patterns:
                if re.search(pattern, q):
                    return intent
        # LLM desactivado: cualquier consulta sin match va a db_agent
        return "database"

    def _routing_confidence(self, question, intent):
        q = normalize_user_text(question)
        for pattern in self.routing_patterns.get(intent, []):
            if re.search(pattern, q):
                return 0.9
        return 0.55 if intent == "llm" else 0.7

    def _is_greeting(self, q):
        return bool(
            re.search(
                r"^(hola|buenos dias|buenas tardes|buenas noches|hey|saludos)\b|\b(hola|buenos dias|buenas tardes|buenas noches)\b",
                q,
                re.IGNORECASE,
            )
        )

    def _is_name_question(self, q):
        return bool(
            re.search(
                r"\b(como me llamo|como me llamo\?|mi nombre|quien soy|como me dicen|tu nombre)\b",
                q,
                re.IGNORECASE,
            )
        )

    def _is_thanks(self, q):
        return bool(
            re.search(
                r"\b(gracias|muchas gracias|te agradezco|ok gracias|perfecto gracias)\b",
                q,
                re.IGNORECASE,
            )
        )

    def _is_error_correction(self, q):
        return bool(
            re.search(
                r"\b(no|mal|incorrecto|eso no|esta mal|está mal|no es eso|corrige|corregir|equivocado|error)\b",
                q,
                re.IGNORECASE,
            )
        )

    def _smalltalk_reply(self, usuario_id, question):
        q = normalize_user_text(question)
        user = User.get_by_id(usuario_id)
        user_name = (getattr(user, "nombre", None) or "").strip()
        first_name = user_name.split()[0] if user_name else ""

        if self._is_greeting(q):
            answer = f"Hola{', ' + first_name if first_name else ''}. Soy tu asistente multiagente. Puedo consultar leads, ventas, marketing y reportes de Orbes desde la base de datos."
            return {
                "ok": True,
                "session_id": None,
                "intent": "smalltalk",
                "agent": "conversation_agent",
                "answer": answer,
                "confidence": 0.98,
                "tools_used": ["conversation_policy"],
            }

        if self._is_name_question(q):
            if user_name:
                answer = f"Tu nombre registrado es {user_name}. Si quieres, también puedo usar solo {first_name or user_name} en las respuestas."
            else:
                answer = "Aún no tengo tu nombre registrado en sesión. Si lo deseas, puedo recordarlo si lo envías o si lo tomamos del perfil."
            return {
                "ok": True,
                "session_id": None,
                "intent": "smalltalk",
                "agent": "conversation_agent",
                "answer": answer,
                "confidence": 0.97,
                "tools_used": ["conversation_policy"],
            }

        if self._is_thanks(q):
            return {
                "ok": True,
                "session_id": None,
                "intent": "smalltalk",
                "agent": "conversation_agent",
                "answer": "De nada. Si quieres, sigo con consultas de Orbes y te respondo solo con datos de tu BD.",
                "confidence": 0.96,
                "tools_used": ["conversation_policy"],
            }

        return None

    def _learn_correction(
        self,
        usuario_id,
        session_id,
        question,
        correction_text,
        intent=None,
        agent_used=None,
    ):
        last = AgentMemory.get_last_assistant_message(usuario_id, session_id)
        if not last:
            return None
        cleaned_correction = (correction_text or "").strip()
        if not cleaned_correction or cleaned_correction.lower() in {
            "no",
            "nop",
            "nope",
            "mal",
            "incorrecto",
            "esta mal",
            "está mal",
        }:
            cleaned_correction = "Corrección pendiente: el usuario indicó que la respuesta anterior era incorrecta."
        correction_id = AgentMemory.save_correction(
            usuario_id=usuario_id,
            session_id=session_id,
            pregunta_orig=question,
            respuesta_mala=last.get("content"),
            respuesta_buena=cleaned_correction,
            intent=intent or last.get("intent"),
            agent_used=agent_used or last.get("agent_used"),
            reportado_por=usuario_id,
        )
        return correction_id

    def _json_to_text(self, payload):
        if payload is None:
            return ""

        if isinstance(payload, str):
            return payload.strip()

        if isinstance(payload, list):
            chunks = []
            for item in payload[:8]:
                piece = self._json_to_text(item)
                if piece:
                    chunks.append(piece)
            return "; ".join(chunks)

        if isinstance(payload, dict):
            preferred_keys = (
                "message",
                "query",
                "question",
                "text",
                "prompt",
                "consulta",
                "instruction",
            )

            for key in preferred_keys:
                val = payload.get(key)
                if isinstance(val, str) and val.strip():
                    return val.strip()
                if isinstance(val, (dict, list)):
                    nested = self._json_to_text(val)
                    if nested:
                        return nested

            chunks = []
            for key, val in payload.items():
                if key in {"session_id", "intent", "target_agent", "route", "meta"}:
                    continue
                if isinstance(val, (str, int, float, bool)):
                    chunks.append(f"{key}: {val}")
                elif isinstance(val, (list, dict)):
                    inner = self._json_to_text(val)
                    if inner:
                        chunks.append(f"{key}: {inner}")
                if len(chunks) >= 8:
                    break
            return "; ".join(chunks)

        return str(payload).strip()

    def _normalize_message_input(self, raw_input):
        forced_intent = None
        parsed_payload = None

        if isinstance(raw_input, (dict, list)):
            parsed_payload = raw_input
        elif isinstance(raw_input, str):
            text = raw_input.strip()
            if text and text[0] in "[{":
                try:
                    parsed_payload = json.loads(text)
                except Exception:
                    parsed_payload = None

        if isinstance(parsed_payload, dict):
            candidate_intent = (
                parsed_payload.get("intent")
                or parsed_payload.get("route_intent")
                or parsed_payload.get("target_intent")
            )
            if isinstance(candidate_intent, str):
                candidate_intent = candidate_intent.strip().lower()
                if candidate_intent in self.agents:
                    forced_intent = candidate_intent

        normalized_question = self._json_to_text(
            parsed_payload if parsed_payload is not None else raw_input
        )

        return {
            "question": (normalized_question or "").strip(),
            "forced_intent": forced_intent,
            "is_json": parsed_payload is not None,
        }

    def _log_communication(
        self,
        question,
        intent,
        agent,
        answer,
        elapsed_ms,
        confidence,
        ok,
        session_id=None,
        trace_id=None,
        tools_used=None,
        route=None,
        error=None,
    ):
        event = {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "question": question,
            "intent": intent,
            "agent": agent,
            "answer": answer,
            "response_time_ms": int(elapsed_ms),
            "confidence": float(confidence or 0),
            "ok": bool(ok),
            "session_id": session_id,
            "trace_id": trace_id,
            "tools_used": tools_used or [],
            "route": route or "broker->orchestrator->agent",
            "error": error,
        }
        self._communications.appendleft(event)
        try:
            socketio.emit("debug_route", event)
            socketio.emit(
                "agent_socket_event",
                {
                    "event": "debug_route",
                    "direction": "broker → monitor",
                    "timestamp": event["timestamp"],
                    "intent": intent,
                    "agent": agent,
                    "trace_id": trace_id,
                    "ok": bool(ok),
                    "response_time_ms": int(elapsed_ms),
                },
            )
        except Exception:
            pass

    def get_recent_communications(self, limit=20):
        safe_limit = max(1, min(int(limit or 20), 200))
        return list(self._communications)[:safe_limit]

    def _find_similar_answer(self, usuario_id, question):
        similar_questions = AgentMemory.get_similar_questions(
            usuario_id=usuario_id,
            question_text=question,
            limit=self.memory_size,
        )
        if not similar_questions:
            return None

        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            for item in similar_questions:
                sql = """
                    SELECT id, content
                    FROM agent_memory
                    WHERE session_id = %s
                      AND role = 'assistant'
                      AND id > %s
                    ORDER BY id ASC
                    LIMIT 1
                """
                cur.execute(sql, (item.get("session_id"), item.get("id")))
                ans = cur.fetchone()
                if ans and ans.get("content"):
                    return {
                        "answer": ans.get("content"),
                        "source_memory_id": int(ans.get("id")),
                    }
            return None
        finally:
            cur.close()

    def process_message(self, usuario_id, question, session_id=None):
        started_at = time.perf_counter()
        session_id = session_id or str(uuid4())
        trace_id = str(uuid4())
        normalized = self._normalize_message_input(question)
        question = normalized.get("question", "")
        forced_intent = normalized.get("forced_intent")
        if not question:
            return {
                "ok": False,
                "error": "Debes enviar un mensaje.",
                "session_id": session_id,
            }

        self._emit_trace(
            trace_id=trace_id,
            session_id=session_id,
            question=question,
            step=1,
            component="broker",
            action="message_received",
            detail="Mensaje recibido desde chat",
            ok=True,
        )

        smalltalk = self._smalltalk_reply(usuario_id, question)
        if smalltalk:
            AgentMemory.save_interaction(
                usuario_id=usuario_id,
                session_id=session_id,
                role="user",
                content=question,
                intent="smalltalk",
                agent_used="conversation_agent",
            )
            memory_id = AgentMemory.save_interaction(
                usuario_id=usuario_id,
                session_id=session_id,
                role="assistant",
                content=smalltalk["answer"],
                intent="smalltalk",
                agent_used="conversation_agent",
            )
            smalltalk.update(
                {
                    "ok": True,
                    "session_id": session_id,
                    "memory_id": memory_id,
                    "response_time_ms": int((time.perf_counter() - started_at) * 1000),
                    "trace_id": trace_id,
                    "source": "conversation_policy",
                }
            )
            self._log_communication(
                question=question,
                intent="smalltalk",
                agent="conversation_agent",
                answer=smalltalk["answer"],
                elapsed_ms=smalltalk["response_time_ms"],
                confidence=smalltalk["confidence"],
                ok=True,
                session_id=session_id,
                trace_id=trace_id,
                tools_used=smalltalk["tools_used"],
                route="broker->conversation_policy",
            )
            return smalltalk

        if self._is_error_correction(question):
            correction_id = self._learn_correction(
                usuario_id=usuario_id,
                session_id=session_id,
                question=question,
                correction_text=question,
            )
            if correction_id:
                answer = "Listo, guardé tu corrección para aprender de este caso. Si quieres, dime la corrección exacta y te respondo con la versión correcta."
            else:
                answer = "Entiendo que hubo un error, pero no encontré una respuesta previa para corregir en esta conversación."
            AgentMemory.save_interaction(
                usuario_id=usuario_id,
                session_id=session_id,
                role="user",
                content=question,
                intent="correction",
                agent_used="conversation_agent",
            )
            memory_id = AgentMemory.save_interaction(
                usuario_id=usuario_id,
                session_id=session_id,
                role="assistant",
                content=answer,
                intent="correction",
                agent_used="conversation_agent",
            )
            return {
                "ok": True,
                "session_id": session_id,
                "intent": "correction",
                "agent": "conversation_agent",
                "memory_id": memory_id,
                "answer": answer,
                "correction_id": correction_id,
                "response_time_ms": int((time.perf_counter() - started_at) * 1000),
                "confidence": 0.95,
                "trace_id": trace_id,
                "tools_used": ["correction_memory"],
                "source": "conversation_policy",
            }

        intent = forced_intent or self._classify_intent(question)
        selected_profile = self.agent_catalog.get(
            intent, self.agent_catalog.get("llm", {})
        )
        selected_agent_name = selected_profile.get("agent_id", "llm_agent")

        self._emit_trace(
            trace_id=trace_id,
            session_id=session_id,
            question=question,
            step=2,
            component="orchestrator",
            action="intent_classified",
            intent=intent,
            selected_agent=selected_agent_name,
            detail="Intent clasificado por patrones de enrutamiento",
            ok=True,
        )

        AgentMemory.save_interaction(
            usuario_id=usuario_id,
            session_id=session_id,
            role="user",
            content=question,
            intent=intent,
            agent_used="orchestrator",
        )

        # Memory hit desactivado para todos los intents (datos siempre frescos)
        memory_hit = None
        if memory_hit:
            self._emit_trace(
                trace_id=trace_id,
                session_id=session_id,
                question=question,
                step=3,
                component="orchestrator",
                action="memory_hit",
                intent=intent,
                selected_agent="memory_hit",
                tool="semantic_memory",
                detail="Se reutiliza respuesta previa similar",
                ok=True,
            )
            answer = memory_hit["answer"]
            memory_id = AgentMemory.save_interaction(
                usuario_id=usuario_id,
                session_id=session_id,
                role="assistant",
                content=answer,
                intent=intent,
                agent_used="memory_hit",
            )
            AgentStats.update_stats(
                agent_type="memory_hit", error=False, feedback=None, tokens=0
            )
            elapsed_ms = (time.perf_counter() - started_at) * 1000
            self._log_communication(
                question=question,
                intent=intent,
                agent="memory_hit",
                answer=answer,
                elapsed_ms=elapsed_ms,
                confidence=0.99,
                ok=True,
                session_id=session_id,
                trace_id=trace_id,
                tools_used=["semantic_memory"],
                route="broker->orchestrator->memory",
            )
            return {
                "ok": True,
                "session_id": session_id,
                "intent": intent,
                "agent": "memory_hit",
                "memory_id": memory_id,
                "answer": answer,
                "from_memory": True,
                "response_time_ms": int(elapsed_ms),
                "confidence": 0.99,
                "trace_id": trace_id,
            }

        selected_agent = self.agents.get(intent, self.llm_agent)
        routing_confidence = self._routing_confidence(question, intent)

        self._emit_trace(
            trace_id=trace_id,
            session_id=session_id,
            question=question,
            step=3,
            component="orchestrator",
            action="dispatch_agent",
            intent=intent,
            selected_agent=selected_agent_name,
            detail="Despacho de consulta al agente seleccionado",
            ok=True,
        )

        result = selected_agent.handle(question)
        self._emit_trace(
            trace_id=trace_id,
            session_id=session_id,
            question=question,
            step=4,
            component=selected_agent_name,
            action="agent_result",
            intent=intent,
            selected_agent=selected_agent_name,
            tool=", ".join(self._infer_tools_used(intent, result)),
            detail=(result.get("error") or "Respuesta generada"),
            ok=bool(result.get("ok")),
        )

        # Optional fallback to LLM when a specialized agent fails.
        if (
            not result.get("ok")
            and intent
            in {
                "database",
                "marketing",
                "prediccion",
                "reportes",
                "retencion_abandono",
            }
            and self.allow_llm_fallback_for_data
        ):
            llm_result = self.llm_agent.handle(question)
            if llm_result.get("ok"):
                self._emit_trace(
                    trace_id=trace_id,
                    session_id=session_id,
                    question=question,
                    step=5,
                    component="orchestrator",
                    action="fallback_llm_applied",
                    intent="llm",
                    selected_agent="llm_agent",
                    tool=(llm_result.get("provider") or "llm_completion"),
                    detail="Fallback de agente especializado hacia LLM",
                    ok=True,
                )
                result = llm_result

        ok = bool(result.get("ok"))
        answer = (
            result.get("answer")
            if ok
            else "No pude resolver tu consulta en este momento."
        )
        agent_used = result.get("agent", "unknown")
        tokens = int(result.get("tokens") or 0)
        confidence = float(result.get("confidence") or routing_confidence)
        elapsed_ms = (time.perf_counter() - started_at) * 1000
        tools_used = self._infer_tools_used(intent, result)

        memory_id = AgentMemory.save_interaction(
            usuario_id=usuario_id,
            session_id=session_id,
            role="assistant",
            content=answer,
            intent=intent,
            agent_used=agent_used,
            tokens_used=tokens,
        )
        AgentStats.update_stats(
            agent_type=agent_used, error=(not ok), feedback=None, tokens=tokens
        )
        self._log_communication(
            question=question,
            intent=intent,
            agent=agent_used,
            answer=answer,
            elapsed_ms=elapsed_ms,
            confidence=confidence,
            ok=ok,
            session_id=session_id,
            trace_id=trace_id,
            tools_used=tools_used,
            route="broker->orchestrator->agent",
            error=result.get("error"),
        )

        self._emit_trace(
            trace_id=trace_id,
            session_id=session_id,
            question=question,
            step=6,
            component="broker",
            action="response_emitted",
            intent=intent,
            selected_agent=agent_used,
            tool=", ".join(tools_used),
            detail="Respuesta enviada al cliente",
            ok=ok,
        )

        return {
            "ok": ok,
            "session_id": session_id,
            "intent": intent,
            "agent": agent_used,
            "memory_id": memory_id,
            "answer": answer,
            "error": result.get("error"),
            "from_memory": False,
            "response_time_ms": int(elapsed_ms),
            "confidence": confidence,
            "trace_id": trace_id,
            "tools_used": tools_used,
            "agent_profile": self.agent_catalog.get(intent),
        }
