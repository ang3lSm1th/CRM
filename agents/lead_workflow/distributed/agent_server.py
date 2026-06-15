"""Microservicio HTTP de agentes — endpoints REST invocados por el orquestador."""

import os

from flask import Blueprint, jsonify, request

from agents.lead_workflow.agents.closing_agent import ClosingAgent
from agents.lead_workflow.agents.commercial_assistant import CommercialAssistantAgent
from agents.lead_workflow.agents.lead_scoring import LeadScoringAgent
from agents.lead_workflow.agents.recovery_agent import RecoveryAgent
from agents.lead_workflow.state_store import LeadWorkflowStateStore

agent_services_bp = Blueprint("agent_services", __name__)

_scoring = LeadScoringAgent()
_commercial = CommercialAssistantAgent()
_recovery = RecoveryAgent()
_closing = ClosingAgent()
_store = LeadWorkflowStateStore()


def _check_internal_auth():
    secret = os.getenv("INTERNAL_SERVICE_SECRET", "").strip()
    if not secret:
        return None
    provided = request.headers.get("X-Internal-Secret") or ""
    if provided != secret:
        return jsonify({"ok": False, "error": "No autorizado"}), 401
    return None


def _lead_or_error(lead_id):
    row = _store.fetch_lead(int(lead_id))
    if not row:
        return None, (jsonify({"ok": False, "error": f"Lead no encontrado (id={lead_id})"}), 404)
    return row, None


@agent_services_bp.route("/healthz", methods=["GET"])
def healthz():
    return jsonify({"status": "ok", "service": "agent-services"}), 200


@agent_services_bp.route("/scoring/analyze", methods=["POST"])
def scoring_analyze():
    auth_err = _check_internal_auth()
    if auth_err:
        return auth_err
    payload = request.get_json(silent=True) or {}
    lead_id = payload.get("lead_id")
    if not lead_id:
        return jsonify({"ok": False, "error": "lead_id es obligatorio"}), 400
    lead_row, err = _lead_or_error(lead_id)
    if err:
        return err
    result = _scoring.analyze(lead_row)
    return jsonify({"ok": True, "result": result})


@agent_services_bp.route("/commercial/assign", methods=["POST"])
def commercial_assign():
    auth_err = _check_internal_auth()
    if auth_err:
        return auth_err
    payload = request.get_json(silent=True) or {}
    lead_id = payload.get("lead_id")
    score_data = payload.get("score_data") or {}
    if not lead_id:
        return jsonify({"ok": False, "error": "lead_id es obligatorio"}), 400
    lead_row, err = _lead_or_error(lead_id)
    if err:
        return err
    result = _commercial.assign_advisor(lead_row, score_data)
    return jsonify({"ok": True, "result": result})


@agent_services_bp.route("/commercial/contact", methods=["POST"])
def commercial_contact():
    auth_err = _check_internal_auth()
    if auth_err:
        return auth_err
    payload = request.get_json(silent=True) or {}
    lead_id = payload.get("lead_id")
    attempt = int(payload.get("attempt") or 1)
    score_data = payload.get("score_data") or {}
    if not lead_id:
        return jsonify({"ok": False, "error": "lead_id es obligatorio"}), 400
    lead_row, err = _lead_or_error(lead_id)
    if err:
        return err
    result = _commercial.contact(lead_row, attempt, score_data)
    return jsonify({"ok": True, "result": result})


@agent_services_bp.route("/recovery/attempt", methods=["POST"])
def recovery_attempt():
    auth_err = _check_internal_auth()
    if auth_err:
        return auth_err
    payload = request.get_json(silent=True) or {}
    lead_id = payload.get("lead_id")
    recovery_attempt_no = int(payload.get("recovery_attempt") or 1)
    if not lead_id:
        return jsonify({"ok": False, "error": "lead_id es obligatorio"}), 400
    lead_row, err = _lead_or_error(lead_id)
    if err:
        return err
    result = _recovery.run_attempt(lead_row, recovery_attempt_no)
    return jsonify({"ok": True, "result": result})


@agent_services_bp.route("/recovery/mark-dead", methods=["POST"])
def recovery_mark_dead():
    auth_err = _check_internal_auth()
    if auth_err:
        return auth_err
    payload = request.get_json(silent=True) or {}
    lead_id = payload.get("lead_id")
    if not lead_id:
        return jsonify({"ok": False, "error": "lead_id es obligatorio"}), 400
    result = _recovery.mark_dead_lead(int(lead_id))
    return jsonify({"ok": True, "result": result})


@agent_services_bp.route("/closing/run", methods=["POST"])
def closing_run():
    auth_err = _check_internal_auth()
    if auth_err:
        return auth_err
    payload = request.get_json(silent=True) or {}
    lead_id = payload.get("lead_id")
    score_data = payload.get("score_data") or {}
    if not lead_id:
        return jsonify({"ok": False, "error": "lead_id es obligatorio"}), 400
    lead_row, err = _lead_or_error(lead_id)
    if err:
        return err
    proposal = _closing.prepare_proposal(lead_row, score_data)
    registration = _closing.register_sale(
        int(lead_id),
        sale_won=bool(payload.get("sale_won", True)),
        monto=payload.get("monto", 0),
        motivo_no_venta=payload.get("motivo_no_venta"),
    )
    return jsonify({"ok": True, "proposal": proposal, "registration": registration})


def create_agent_service_app():
    """App Flask mínima para el contenedor agent-services."""
    from flask import Flask
    from core.config import Config
    from core.extensions import mysql

    app = Flask(__name__)
    app.config.from_object(Config)
    mysql.init_app(app)
    app.register_blueprint(agent_services_bp, url_prefix="/agents")

    @app.route("/healthz")
    def root_healthz():
        return jsonify({"status": "ok", "service": "agent-services"}), 200

    return app
