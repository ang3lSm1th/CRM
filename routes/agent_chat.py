from flask import Blueprint, jsonify, render_template, request, session
from flask_socketio import emit
import MySQLdb.cursors
from uuid import uuid4

from agents.broker.orchestrator import AgentOrchestrator
from extensions import mysql, socketio
from models.agent_models.memory_models import AgentMemory, AgentStats
from utils.security import login_required, role_required

agent_chat_bp = Blueprint("agent_chat", __name__)
orchestrator = AgentOrchestrator()


def _extract_message_input(payload):
    if payload is None:
        return ""
    if isinstance(payload, str):
        return payload
    if isinstance(payload, dict):
        for key in ("message", "query", "question", "text", "payload", "data"):
            if key in payload:
                return payload.get(key)
        return payload
    return payload


@agent_chat_bp.route("/agent", methods=["GET"])
@login_required
def agent_chat_home():
    if not session.get("agent_session_id"):
        session["agent_session_id"] = str(uuid4())
    return render_template("agents/chat.html")


@agent_chat_bp.route("/agent/session", methods=["GET"])
@login_required
def agent_chat_session_get():
    session_id = session.get("agent_session_id")
    if not session_id:
        session_id = str(uuid4())
        session["agent_session_id"] = session_id
    return jsonify({"ok": True, "session_id": session_id})


@agent_chat_bp.route("/agent/session/new", methods=["POST"])
@login_required
def agent_chat_session_new():
    session["agent_session_id"] = str(uuid4())
    return jsonify({"ok": True, "session_id": session["agent_session_id"]})


@agent_chat_bp.route("/agent/session/select", methods=["POST"])
@login_required
def agent_chat_session_select():
    """Pins a selected session_id as current for this web session."""
    payload = request.get_json(silent=True) or {}
    selected = str(payload.get("session_id") or "").strip()
    if not selected:
        return jsonify({"ok": False, "error": "session_id es obligatorio"}), 400

    session["agent_session_id"] = selected
    return jsonify({"ok": True, "session_id": selected})


@agent_chat_bp.route("/agent/interact", methods=["POST"])
@login_required
def agent_chat_interact():
    """Endpoint REST que acepta texto o JSON para el orquestador multiagente."""
    payload = request.get_json(silent=True)
    if payload is None:
        payload = (
            request.form.to_dict()
            if request.form
            else (request.data.decode("utf-8", errors="ignore") if request.data else "")
        )

    usuario_id = session.get("user_id")
    if not usuario_id:
        return jsonify({"ok": False, "error": "Sesion no autenticada"}), 401

    incoming = _extract_message_input(payload)
    session_id = None
    if isinstance(payload, dict):
        session_id = payload.get("session_id")
    session_id = session_id or session.get("agent_session_id")

    result = orchestrator.process_message(
        usuario_id=usuario_id,
        question=incoming,
        session_id=session_id,
    )

    if result.get("session_id") and not (
        isinstance(payload, dict) and payload.get("session_id")
    ):
        session["agent_session_id"] = result["session_id"]

    code = 200 if result.get("ok") else 400
    return jsonify(result), code


@agent_chat_bp.route("/agent/history", methods=["GET"])
@login_required
def agent_chat_history():
    AgentMemory.ensure_schema()
    usuario_id = session.get("user_id")
    try:
        limit = int(request.args.get("limit", 60))
    except Exception:
        limit = 60
    limit = max(1, min(limit, 200))
    session_id = request.args.get("session_id") or session.get("agent_session_id")
    all_sessions = str(request.args.get("all", "0")) == "1"

    if not usuario_id:
        return jsonify({"ok": False, "error": "Sesion no autenticada"}), 401
    if not all_sessions and not session_id:
        return jsonify({"ok": False, "error": "session_id es obligatorio"}), 400

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        if all_sessions:
            cur.execute(
                """
                SELECT id, session_id, role, content, intent, agent_used, feedback, created_at
                FROM agent_memory
                WHERE usuario_id = %s
                ORDER BY id DESC
                LIMIT %s
                """,
                (usuario_id, limit),
            )
        else:
            cur.execute(
                """
                SELECT id, session_id, role, content, intent, agent_used, feedback, created_at
                FROM agent_memory
                WHERE usuario_id = %s
                  AND session_id = %s
                ORDER BY id DESC
                LIMIT %s
                """,
                (usuario_id, session_id, limit),
            )
        rows = list(cur.fetchall() or [])
        rows.reverse()
        return jsonify({"ok": True, "items": rows, "session_id": session_id})
    except Exception as exc:
        return (
            jsonify(
                {"ok": False, "items": [], "session_id": session_id, "error": str(exc)}
            ),
            500,
        )
    finally:
        cur.close()


@agent_chat_bp.route("/agent/history", methods=["DELETE"])
@login_required
def agent_chat_history_delete():
    AgentMemory.ensure_schema()
    usuario_id = session.get("user_id")
    payload = request.get_json(silent=True) or {}
    delete_all = bool(payload.get("all"))
    session_id = payload.get("session_id") or session.get("agent_session_id")

    deleted = AgentMemory.delete_history(
        usuario_id=usuario_id,
        session_id=None if delete_all else session_id,
    )

    # Al borrar chat actual, crear uno nuevo automaticamente.
    if not delete_all:
        session["agent_session_id"] = str(uuid4())

    return jsonify(
        {
            "ok": True,
            "deleted": deleted,
            "session_id": session.get("agent_session_id"),
        }
    )


@agent_chat_bp.route("/agent/feedback", methods=["POST"])
@login_required
def agent_chat_feedback():
    AgentMemory.ensure_schema()
    payload = request.get_json(silent=True) or {}
    memory_id = payload.get("memory_id")
    stars = payload.get("stars")
    session_id = payload.get("session_id") or session.get("agent_session_id")

    if not memory_id or not stars:
        return (
            jsonify({"ok": False, "error": "memory_id y stars son obligatorios"}),
            400,
        )

    ok = AgentMemory.update_feedback(memory_id=memory_id, stars=stars)
    if not ok:
        return jsonify({"ok": False, "error": "Interacción no encontrada"}), 404

    # Actualiza promedio diario de feedback con el agente que respondió.
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        cur.execute("SELECT agent_used FROM agent_memory WHERE id = %s", (memory_id,))
        row = cur.fetchone() or {}
        agent_used = row.get("agent_used") or "unknown"
    finally:
        cur.close()

    if int(stars) <= 2 and session_id:
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            cur.execute(
                """
                SELECT content, intent, agent_used
                FROM agent_memory
                WHERE id = %s
                """,
                (memory_id,),
            )
            assistant_row = cur.fetchone() or {}
        finally:
            cur.close()

        AgentMemory.save_correction(
            usuario_id=session.get("user_id"),
            session_id=session_id,
            pregunta_orig="Feedback de baja calificación",
            respuesta_mala=assistant_row.get("content"),
            respuesta_buena="El usuario marcó esta respuesta como incorrecta o poco útil.",
            intent=assistant_row.get("intent"),
            agent_used=assistant_row.get("agent_used") or agent_used,
            reportado_por=session.get("user_id"),
        )

    AgentStats.update_stats(
        agent_type=agent_used, error=False, feedback=float(stars), tokens=0
    )
    return jsonify({"ok": True})


@agent_chat_bp.route("/agent/stats", methods=["GET"])
@login_required
@role_required("administrador", "gerente", "rrhh")
def agent_chat_stats():
    AgentMemory.ensure_schema()
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        cur.execute("""
            SELECT fecha, agent_type, total_calls, total_errors, avg_feedback, tokens_total
            FROM agent_stats
            ORDER BY fecha DESC, agent_type ASC
            LIMIT 120
            """)
        rows = cur.fetchall()
        return jsonify({"ok": True, "items": rows})
    finally:
        cur.close()


@agent_chat_bp.route("/agent/sessions", methods=["GET"])
@login_required
def agent_chat_sessions_list():
    """Returns list of distinct chat sessions for the current user, newest first."""
    AgentMemory.ensure_schema()
    usuario_id = session.get("user_id")
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        cur.execute(
            """
            SELECT
                am.session_id,
                MIN(am.created_at) AS started_at,
                MAX(am.created_at) AS last_at,
                COUNT(*) AS total_msgs,
                (
                    SELECT content
                    FROM agent_memory am2
                    WHERE am2.session_id = am.session_id
                      AND am2.usuario_id = %s
                      AND am2.role = 'user'
                    ORDER BY am2.id ASC
                    LIMIT 1
                ) AS preview
            FROM agent_memory am
            WHERE am.usuario_id = %s
                            AND am.session_id IS NOT NULL
                            AND am.session_id <> ''
            GROUP BY am.session_id
            ORDER BY last_at DESC
            LIMIT 60
            """,
            (usuario_id, usuario_id),
        )
        rows = cur.fetchall() or []
        return jsonify({"ok": True, "sessions": rows})
    except Exception as exc:
        return jsonify({"ok": True, "sessions": [], "warning": str(exc)})
    finally:
        cur.close()


@socketio.on("user_message")
def socket_user_message(payload):
    usuario_id = session.get("user_id")
    if not usuario_id:
        emit("agent_response", {"ok": False, "error": "Sesión no autenticada."})
        return

    payload = payload or {}
    incoming = _extract_message_input(payload)
    request_session_id = (
        payload.get("session_id") if isinstance(payload, dict) else None
    )
    session_id = request_session_id or session.get("agent_session_id")

    emit("agent_typing", {"typing": True})
    try:
        result = orchestrator.process_message(
            usuario_id=usuario_id,
            question=incoming,
            session_id=session_id,
        )
    except Exception as exc:
        emit(
            "agent_response", {"ok": False, "error": f"Error interno del agente: {exc}"}
        )
        return

    # Evita que una pestaña pise el chat activo de otra si ya vino session_id en payload.
    if result.get("session_id") and not request_session_id:
        session["agent_session_id"] = result["session_id"]

    emit("agent_response", result)
