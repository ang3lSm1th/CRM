"""Tareas Celery del workflow multiagente."""

import logging

from core.celery_app import celery
from agents.lead_workflow.socket_events import emit_workflow_event

logger = logging.getLogger(__name__)


@celery.task(name="agents.lead_workflow.celery_tasks.process_lead_task")
def process_lead_task(lead_id, auto_advance=True):
    from agents.lead_workflow.orchestrator import LeadWorkflowOrchestrator
    from agents.lead_workflow.state_store import LeadWorkflowStateStore

    store = LeadWorkflowStateStore()
    row = store.fetch_lead(int(lead_id))
    codigo = (row or {}).get("codigo")
    emit_workflow_event(
        "workflow_async_started",
        {"lead_id": lead_id, "codigo": codigo, "transport": "celery"},
    )
    try:
        orchestrator = LeadWorkflowOrchestrator()
        result = orchestrator.process_lead(int(lead_id), auto_advance=auto_advance)
        return result
    except Exception as exc:
        logger.exception("Error Celery workflow lead_id=%s", lead_id)
        emit_workflow_event(
            "workflow_error",
            {"lead_id": lead_id, "codigo": codigo, "error": str(exc)},
        )
        raise
