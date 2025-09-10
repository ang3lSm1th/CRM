from functools import wraps
from flask import session, redirect, url_for, flash
from flask_bcrypt import Bcrypt

bcrypt = Bcrypt()

# --- Constantes de roles en texto ---
ROLE_ADMIN = "administrador"
ROLE_GERENTE = "gerente"
ROLE_RRHH = "RRHH"
ROLE_ASESOR = "asesor"

# --- Password helpers ---
def hash_password(password: str) -> str:
    """Genera un hash seguro para la contraseña."""
    return bcrypt.generate_password_hash(password).decode("utf-8")

def check_password(hashed: str, plain: str) -> bool:
    """Verifica si la contraseña ingresada coincide con el hash."""
    return bcrypt.check_password_hash(hashed, plain)

# --- Decoradores ---
def login_required(f):
    """Verifica que el usuario haya iniciado sesión."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Debes iniciar sesión", "warning")
            return redirect(url_for("auth.login"))
        return f(*args, **kwargs)
    return decorated_function

def role_required(*allowed_roles):
    """Verifica que el usuario tenga uno de los roles permitidos."""
    def decorator(f):
        @wraps(f)
        def _wrap(*args, **kwargs):
            rol_id = session.get("id_rol")
            if not rol_id:
                flash("Debes iniciar sesión", "warning")
                return redirect(url_for("auth.login"))
            if rol_id not in allowed_roles:
                flash("No tienes permiso para acceder a esta página", "danger")
                return redirect(url_for("dashboard.dashboard_router"))
            return f(*args, **kwargs)
        return _wrap
    return decorator
