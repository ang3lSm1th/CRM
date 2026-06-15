"""Compatibilidad — use `core.celery_app` en código nuevo."""
from core.celery_app import celery, init_celery

__all__ = ["celery", "init_celery"]
