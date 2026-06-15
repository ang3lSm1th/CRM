from flask import Blueprint, render_template, request, redirect, url_for, flash, session, make_response
from models.user import User
from utils.security import check_password
import re
from datetime import datetime, timedelta

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("usuario", "").strip()
        password = request.form.get("password", "")

        # Bloqueo por intentos fallidos
        attempts = session.get("login_attempts", {})
        locked_until = attempts.get("locked_until")
        if locked_until:
            try:
                unlock_time = datetime.fromisoformat(locked_until)
                if unlock_time > datetime.utcnow():
                    flash(
                        "Has excedido los intentos de inicio de sesión. Intenta nuevamente más tarde.",
                        "danger",
                    )
                    return redirect(url_for("auth.login"))
                attempts = {}
            except ValueError:
                attempts = {}

        # Validaciones básicas
        if not username or len(username) < 3:
            flash("Por favor ingrese un usuario válido", "warning")
            return redirect(url_for("auth.login"))
        
        if not password or len(password) < 4:
            flash("Por favor ingrese una contraseña válida", "warning")
            return redirect(url_for("auth.login"))

        # Validación del formato de username
        if not re.match(r"^[A-Za-z0-9_.-]{3,50}$", username):
            flash("Formato de usuario no válido", "warning")
            return redirect(url_for("auth.login"))

        # Intentar obtener el usuario
        user = User.get_by_username(username)

        # Mensaje genérico por seguridad (no revelar si usuario existe o no)
        if not user or not check_password(user.password, password):
            attempts["count"] = attempts.get("count", 0) + 1
            if attempts["count"] >= 5:
                unlock_time = datetime.utcnow() + timedelta(minutes=15)
                attempts["locked_until"] = unlock_time.isoformat()
                session["login_attempts"] = attempts
                session.modified = True
                flash(
                    "Has excedido los intentos de inicio de sesión. Intenta nuevamente dentro de 15 minutos.",
                    "danger",
                )
            else:
                session["login_attempts"] = attempts
                flash("Usuario o contraseña incorrectos", "danger")
            return redirect(url_for("auth.login"))

        session.pop("login_attempts", None)

        # Credenciales correctas - crear sesión
        session.clear()
        session.permanent = True
        session["user_id"] = int(user.id)
        session["username"] = user.usuario
        session["nombre"] = user.nombre
        session["id_rol"] = str(user.id_rol)
        session["negocio_id"] = getattr(user, "negocio_id", None)
        session["negocio_slug"] = (getattr(user, "negocio_slug", "") or "").strip().lower()
        session["negocio_nombre"] = (getattr(user, "negocio_nombre", "") or "").strip()

        # Sincronizar marca activa por usuario (negocio) al iniciar sesión
        default_brand = "orbes"
        user_brand = (getattr(user, "negocio_slug", "") or "").strip().lower()
        brand = user_brand if user_brand in ("orbes", "lovol") else default_brand

        # flash de bienvenida eliminado para evitar modal innecesario
        response = make_response(redirect(url_for("dashboard.dashboard_router")))
        response.set_cookie("brand", brand, max_age=60 * 60 * 24 * 30, path="/", samesite="Lax")
        return response

    return render_template("auth/login.html")


@auth_bp.route("/logout")
def logout():
    session.clear()
    flash("Sesión cerrada exitosamente", "info")
    return redirect(url_for("auth.login"))
