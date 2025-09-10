from flask_mysqldb import MySQL
from flask_bcrypt import Bcrypt
from flask_login import LoginManager

login_manager = LoginManager()
login_manager.login_view = "auth.login"  # redirige al login si no está autenticado
mysql = MySQL()
bcrypt = Bcrypt()
