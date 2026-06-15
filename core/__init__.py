"""Núcleo compartido: configuración, extensiones Flask y Celery."""

from core.config import Config
from core.extensions import bcrypt, login_manager, mysql, socketio

__all__ = ["Config", "bcrypt", "login_manager", "mysql", "socketio"]
