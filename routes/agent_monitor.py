from flask import Blueprint, jsonify, render_template
import MySQLdb.cursors

from extensions import mysql
from routes.agent_chat import orchestrator
from utils.security import login_required, role_required

monitor_bp = Blueprint("agent_monitor", __name__)


@monitor_bp.route("/agent/monitor", methods=["GET"])
@login_required
@role_required("administrador")
def monitor_home():
    architecture_text = "Broker -> Orquestador(intent+reglas) -> Agente Especializado -> Herramienta -> BD CRM -> Respuesta"
    return render_template("agents/monitor.html", architecture_text=architecture_text)


@monitor_bp.route("/agent/monitor/comunicacion", methods=["GET"])
@login_required
@role_required("administrador")
def monitor_comunicacion():
    items = orchestrator.get_recent_communications(limit=20)
    return jsonify({"ok": True, "items": items})


@monitor_bp.route("/agent/monitor/registry", methods=["GET"])
@login_required
@role_required("administrador")
def monitor_registry():
    items = orchestrator.get_agent_registry()
    return jsonify({"ok": True, "items": items})


@monitor_bp.route("/agent/monitor/traces", methods=["GET"])
@login_required
@role_required("administrador")
def monitor_traces():
    items = orchestrator.get_recent_traces(limit=60)
    return jsonify({"ok": True, "items": items})


@monitor_bp.route("/agent/monitor/estadisticas", methods=["GET"])
@login_required
@role_required("administrador")
def monitor_estadisticas():
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        cur.execute("""
            SELECT
                agent_type,
                SUM(total_calls) AS total_calls,
                SUM(total_errors) AS total_errors,
                ROUND(AVG(avg_feedback), 2) AS avg_feedback,
                SUM(tokens_total) AS tokens_total
            FROM agent_stats
            GROUP BY agent_type
            ORDER BY total_calls DESC, agent_type ASC
            """)
        rows = cur.fetchall() or []
        return jsonify({"ok": True, "items": rows})
    finally:
        cur.close()
