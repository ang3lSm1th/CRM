"""Ejecución asíncrona del workflow (threading con contexto Flask).

WORKFLOW · PASO 0 → llama orchestrator.process_lead() tras crear lead o POST /process
Emite workflow_event vía Socket.IO para /lead_workflow/monitor en tiempo real.
"""

import logging
import threading

from agents.lead_workflow.socket_events import emit_workflow_event

logger = logging.getLogger(__name__)


def run_workflow_async(app, lead_id, orchestrator, *, auto_advance=True, callback=None):
    """Ejecuta process_lead en background sin bloquear la petición HTTP."""

    def _worker():
        with app.app_context():
            try:
                row = orchestrator.store.fetch_lead(lead_id)
                codigo = (row or {}).get("codigo")
                emit_workflow_event(
                    "workflow_async_started",
                    {"lead_id": lead_id, "codigo": codigo},
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
