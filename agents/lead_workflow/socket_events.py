"""Eventos Socket.IO en tiempo real para el monitor de workflow de leads."""

from datetime import datetime

from extensions import socketio


def emit_workflow_event(event_name, payload=None):
    """
    Emite al monitor /lead_workflow/monitor (evento workflow_event).
    No reemplaza la persistencia en agent_interactions; solo UI en vivo.
    """
    try:
        socketio.emit(
            "workflow_event",
            {
                "event": event_name,
                "timestamp": datetime.utcnow().isoformat() + "Z",
                **(payload or {}),
            },
        )
    except Exception:
        pass
