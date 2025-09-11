from flask import Blueprint, render_template, request, redirect, url_for, flash, session
from models.user import User
from utils.security import check_password
import re

auth_bp = Blueprint("auth", __name__)

@auth_bp.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        username = request.form.get("usuario", "").strip()
        password = request.form.get("password", "")

        # Validación mínima del username
        if not re.match(r"^[A-Za-z0-9_.-]{3,50}$", username):
            flash("Usuario inválido", "warning")
            return redirect(url_for("auth.login"))

        user = User.get_by_username(username)

        if not user or not check_password(user.password, password):
            flash("Usuario o contraseña incorrecta", "danger")
            return redirect(url_for("auth.login"))

# después de verificar credenciales...
        session.clear()
        session["user_id"] = int(user.id)
        session["username"] = user.usuario        # si igual lo quieres tener
        session["nombre"] = user.nombre           # ← agrega esto
        session["id_rol"] = str(user.id_rol)



        return redirect(url_for("dashboard.dashboard_router"))

    return render_template("auth/login.html")


@auth_bp.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("auth.login"))
