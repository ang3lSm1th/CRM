"""Topología del sistema para evidencia de arquitectura distribuida."""

import os
import socket

import requests


def _env_bool(name, default="0"):
    return os.getenv(name, default).strip().lower() in {"1", "true", "yes", "on"}


def _probe_url(url, timeout=2):
    if not url:
        return {"ok": False, "error": "URL no configurada"}
    try:
        res = requests.get(f"{url.rstrip('/')}/healthz", timeout=timeout)
        data = res.json() if res.headers.get("content-type", "").startswith("application/json") else {}
        return {"ok": res.ok, "status_code": res.status_code, "payload": data}
    except Exception as exc:
        return {"ok": False, "error": str(exc)}


def get_system_architecture(*, probe=False):
    """Describe capas y servicios; opcionalmente verifica health de cada nodo."""
    distributed = _env_bool("WORKFLOW_DISTRIBUTED")
    use_celery = _env_bool("USE_CELERY") or bool(os.getenv("REDIS_URL"))
    redis_url = os.getenv("REDIS_URL", "")
    agent_url = os.getenv("AGENT_SERVICE_URL", "http://127.0.0.1:8001")
    web_url = os.getenv("WEB_SERVICE_URL", "http://127.0.0.1:8000")

    mode = "distributed" if distributed and use_celery else "monolith"

    services = [
        {
            "id": "web",
            "name": "CRM Web + Orquestador",
            "role": "API REST, UI, Socket.IO monitor",
            "protocol": "HTTP / WebSocket",
            "url": web_url,
            "process": "gunicorn (puerto 8000)",
        },
        {
            "id": "workflow-worker",
            "name": "Workflow Worker",
            "role": "Ejecuta process_lead desde cola Redis",
            "protocol": "Celery + Redis",
            "url": redis_url or None,
            "process": "celery worker",
            "enabled": use_celery,
        },
        {
            "id": "agent-services",
            "name": "Microservicio Agentes IA",
            "role": "Scoring, comercial, recovery, closing vía REST",
            "protocol": "HTTP/JSON",
            "url": agent_url,
            "process": "gunicorn (puerto 8001)",
            "enabled": distributed,
        },
        {
            "id": "redis",
            "name": "Redis",
            "role": "Broker Celery + bus Socket.IO entre procesos",
            "protocol": "Redis",
            "url": redis_url or None,
            "enabled": use_celery,
        },
        {
            "id": "mysql",
            "name": "MySQL CRM",
            "role": "Estado compartido: lead_agent_state, agent_interactions",
            "protocol": "SQL",
            "url": os.getenv("MYSQL_HOST", "127.0.0.1"),
        },
    ]

    communication = [
        {
            "from": "web",
            "to": "redis",
            "protocol": "Redis LPUSH",
            "purpose": "Encolar workflow al crear lead",
            "active": use_celery,
        },
        {
            "from": "workflow-worker",
            "to": "agent-services",
            "protocol": "HTTP POST /agents/*",
            "purpose": "Delegar tareas a agentes especializados",
            "active": distributed,
        },
        {
            "from": "workflow-worker",
            "to": "mysql",
            "protocol": "SQL",
            "purpose": "Persistir estado e interacciones",
            "active": True,
        },
        {
            "from": "workflow-worker",
            "to": "web",
            "protocol": "Socket.IO (Redis message queue)",
            "purpose": "Eventos workflow_event al monitor",
            "active": use_celery and bool(redis_url),
        },
    ]

    result = {
        "ok": True,
        "mode": mode,
        "hostname": socket.gethostname(),
        "description": (
            "Arquitectura distribuida: web, worker Celery, microservicio de agentes y Redis."
            if mode == "distributed"
            else "Modo monolito: orquestador invoca agentes in-process (desarrollo local)."
        ),
        "env": {
            "WORKFLOW_DISTRIBUTED": distributed,
            "USE_CELERY": use_celery,
            "REDIS_URL": bool(redis_url),
            "AGENT_SERVICE_URL": agent_url,
        },
        "services": services,
        "communication": communication,
        "agent_endpoints": [
            "POST /agents/scoring/analyze",
            "POST /agents/commercial/assign",
            "POST /agents/commercial/contact",
            "POST /agents/recovery/attempt",
            "POST /agents/recovery/mark-dead",
            "POST /agents/closing/run",
            "POST /agents/cotizacion/generate",
        ],
    }

    if probe:
        result["health"] = {
            "web": _probe_url(web_url),
            "agent_services": _probe_url(agent_url) if distributed else {"ok": None, "skipped": True},
        }

    return result
