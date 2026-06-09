"""Ejecución asíncrona del workflow.

Modo distribuido (USE_CELERY=1 + REDIS_URL): encola tarea Celery en workflow-worker.
Modo local: threading con contexto Flask.
"""

import logging
import os
import threading

from agents.lead_workflow.socket_events import emit_workflow_event

logger = logging.getLogger(__name__)


def _use_celery():
    if os.getenv("USE_CELERY", "0").strip().lower() not in {"1", "true", "yes"}:
        return False
    return bool(os.getenv("REDIS_URL", "").strip())


def run_workflow_async(app, lead_id, orchestrator, *, auto_advance=True, callback=None):
    """Ejecuta process_lead sin bloquear la petición HTTP."""

    if _use_celery():
        from agents.lead_workflow.celery_tasks import process_lead_task

        row = orchestrator.store.fetch_lead(lead_id)
        codigo = (row or {}).get("codigo")
        emit_workflow_event(
            "workflow_queued",
            {"lead_id": lead_id, "codigo": codigo, "transport": "celery"},
        )
        process_lead_task.delay(int(lead_id), auto_advance=auto_advance)
        return None

    def _worker():
        with app.app_context():
            try:
                row = orchestrator.store.fetch_lead(lead_id)
                codigo = (row or {}).get("codigo")
                emit_workflow_event(
                    "workflow_async_started",
                    {"lead_id": lead_id, "codigo": codigo, "transport": "thread"},
                )
                result = orchestrator.process_lead(lead_id, auto_advance=auto_advance)
                if callback:
                    callback(result)
            except Exception:
                logger.exception("Error en workflow async lead_id=%s", lead_id)
                emit_workflow_event(
                    "workflow_error",
                    {"lead_id": lead_id, "error": "Error en workflow async"},
                )

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    return thread
