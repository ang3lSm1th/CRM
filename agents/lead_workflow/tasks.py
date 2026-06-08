"""Ejecución asíncrona del workflow (threading con contexto Flask).

WORKFLOW · PASO 0 → llama orchestrator.process_lead() tras crear lead o POST /process
"""

import logging
import threading

logger = logging.getLogger(__name__)


def run_workflow_async(app, lead_id, orchestrator, *, auto_advance=True, callback=None):
    """Ejecuta process_lead en background sin bloquear la petición HTTP."""

    def _worker():
        with app.app_context():
            try:
                result = orchestrator.process_lead(lead_id, auto_advance=auto_advance)
                if callback:
                    callback(result)
            except Exception:
                logger.exception("Error en workflow async lead_id=%s", lead_id)

    thread = threading.Thread(target=_worker, daemon=True)
    thread.start()
    return thread
