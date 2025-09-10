from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models.user import User
from utils.security import check_password
import re

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        # Sanitizar entradas
        username = request.form.get("usuario", "").strip()
        password = request.form.get("password", "")

        # Validación mínima del username (solo letras, números, puntos, guiones, 3-50 chars)
        if not re.match(r"^[A-Za-z0-9_.-]{3,50}$", username):
            flash("Usuario inválido", "warning")
            return render_template("auth/login.html"), 400

        # Buscar usuario en la base de datos (usa parámetros -> sin inyección SQL)
        user = User.get_by_username(username)

        # Validar existencia y contraseña
        if not user or not check_password(user.password, password):
            flash("Usuario o contraseña inválidos", "danger")
            return render_template("auth/login.html"), 401

        # Limpiar sesión anterior antes de asignar nueva (evita session fixation)
        session.clear()
        session["user_id"] = int(user.id)
        session["username"] = user.usuario
        session["id_rol"] = str(user.id_rol)  # mejor como string por consistencia

        return redirect(url_for("dashboard.dashboard_router"))

    return render_template("auth/login.html")


@auth_bp.route("/logout")
def logout():
    # Eliminar datos de sesión
    session.clear()
    return redirect(url_for("auth.login"))
