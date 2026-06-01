import os

from flask_mysqldb import MySQL
from flask_bcrypt import Bcrypt
from flask_login import LoginManager
from flask_socketio import SocketIO

login_manager = LoginManager()
login_manager.login_view = "auth.login"  # redirige al login si no está autenticado
mysql = MySQL()
bcrypt = Bcrypt()
socketio = SocketIO(
    async_mode=os.getenv("SOCKETIO_ASYNC_MODE", "threading"),
    cors_allowed_origins=os.getenv("SOCKETIO_CORS_ALLOWED_ORIGINS", "*"),
)
