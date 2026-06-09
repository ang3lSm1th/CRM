"""Celery — cola de trabajo distribuida para el workflow de leads."""

import os

from celery import Celery

redis_url = os.getenv("REDIS_URL", "redis://localhost:6379/0")

celery = Celery(
    "crm_orbes",
    broker=redis_url,
    backend=redis_url,
    include=["agents.lead_workflow.celery_tasks"],
)

celery.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_default_queue="workflow",
    task_routes={"agents.lead_workflow.celery_tasks.process_lead_task": {"queue": "workflow"}},
)


def init_celery(flask_app):
    """Vincula tareas Celery al contexto Flask (MySQL, config)."""

    class ContextTask(celery.Task):
        abstract = True

        def __call__(self, *args, **kwargs):
            with flask_app.app_context():
                return super().__call__(*args, **kwargs)

    celery.Task = ContextTask
    return celery
