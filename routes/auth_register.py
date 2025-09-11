from flask import Blueprint, render_template, request, redirect, url_for, flash  # , current_app
from extensions import mysql
from utils.security import hash_password
from MySQLdb import IntegrityError

register_bp = Blueprint("register", __name__)

@register_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        nombre   = (request.form.get("nombre") or "").strip()
        password = request.form.get("password") or ""
        rol_id   = request.form.get("rol")

        if not username or not nombre or not password or not rol_id:
            flash("Todos los campos son obligatorios", "warning")
            return redirect(url_for("register.register"))

        try:
            rol_id = int(rol_id)
        except (TypeError, ValueError):
            flash("Rol inválido.", "warning")
            return redirect(url_for("register.register"))

        hashed_pw = hash_password(password)

        cur = mysql.connection.cursor()
        try:
            # Pre-chequeo UX (no reemplaza la UNIQUE constraint)
            cur.execute("SELECT 1 FROM usuarios WHERE usuario=%s LIMIT 1", (username,))
            if cur.fetchone():
                flash("⚠️ El nombre de usuario ya existe.", "warning")
                return redirect(url_for("register.register"))

            # INSERT protegido
            cur.execute(
                "INSERT INTO usuarios (usuario, nombre, password, id_rol) VALUES (%s, %s, %s, %s)",
                (username, nombre, hashed_pw, rol_id),
            )
            mysql.connection.commit()

        except IntegrityError as e:
            mysql.connection.rollback()
            # 1062 = Duplicate entry
            if e.args and e.args[0] == 1062:
                flash("⚠️ El nombre de usuario ya existe.", "warning")
                return redirect(url_for("register.register"))
            # current_app.logger.exception(e)
            flash("❌ No se pudo crear el usuario (error de integridad).", "danger")
            return redirect(url_for("register.register"))

        except Exception as e:
            mysql.connection.rollback()
            # current_app.logger.exception(e)
            flash("❌ Ocurrió un error inesperado al crear el usuario.", "danger")
            return redirect(url_for("register.register"))

        finally:
            cur.close()

        flash("✅ Usuario registrado con éxito", "success")
        return redirect(url_for("auth.login"))

    # GET: carga de roles
    cur = mysql.connection.cursor()
    try:
        cur.execute("SELECT id, nombre FROM roles")
        roles = cur.fetchall()
    finally:
        cur.close()

    return render_template("auth/register.html", roles=roles)
