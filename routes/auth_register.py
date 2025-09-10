from flask import Blueprint, render_template, request, redirect, url_for, flash
from extensions import mysql
from utils.security import hash_password

register_bp = Blueprint("register", __name__)

@register_bp.route("/register", methods=["GET", "POST"])
def register():
    cursor = mysql.connection.cursor()

    # Obtener roles de la BD para mostrarlos en el formulario
    cursor.execute("SELECT id, nombre FROM roles")
    roles = cursor.fetchall()

    if request.method == "POST":
        username = request.form.get("username")
        nombre = request.form.get("nombre")
        password = request.form.get("password")
        rol_id = request.form.get("rol")  # Aquí recibiremos el id del rol

        if not username or not nombre or not password or not rol_id:
            flash("Todos los campos son obligatorios", "danger")
            cursor.close()
            return redirect(url_for("register.register"))

        hashed_pw = hash_password(password)

        cursor.execute(
            "INSERT INTO usuarios (usuario, nombre, password, id_rol) VALUES (%s, %s, %s, %s)",
            (username, nombre, hashed_pw, rol_id),
        )
        mysql.connection.commit()
        cursor.close()

        flash("Usuario registrado con éxito", "success")
        return redirect(url_for("auth.login"))

    # <-- SOLO se ejecuta si es GET
    cursor.close()
    return render_template("auth/register.html", roles=roles)
