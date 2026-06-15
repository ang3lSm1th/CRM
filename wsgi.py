"""Compatibilidad — punto de entrada web para Gunicorn."""
from entrypoints.web_wsgi import app

__all__ = ["app"]
