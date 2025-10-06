# routes/auth.register.py
from flask import Blueprint, render_template, request, flash
from extensions import mysql
from utils.security import hash_password
from MySQLdb import IntegrityError

register_bp = Blueprint("register", __name__)

def _load_roles():
    cur = mysql.connection.cursor()
    try:
        cur.execute("SELECT id, nombre FROM roles")
        return cur.fetchall()
    finally:
        cur.close()

@register_bp.route("/register", methods=["GET", "POST"])
def register():
    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        nombre   = (request.form.get("nombre") or "").strip()
        password = request.form.get("password") or ""
        rol_id   = request.form.get("rol") or ""

        # Para re-renderizar el formulario con los valores ingresados
        form_data = {"username": username, "nombre": nombre, "rol_id": rol_id}

        # Validaciones básicas
        if not username or not nombre or not password or not rol_id:
            flash("Todos los campos son obligatorios", "warning")
            roles = _load_roles()
            return render_template("auth/register.html", roles=roles, form_data=form_data)

        try:
            rol_id = int(rol_id)
        except (TypeError, ValueError):
            flash("Rol inválido.", "warning")
            roles = _load_roles()
            return render_template("auth/register.html", roles=roles, form_data=form_data)

        hashed_pw = hash_password(password)

        cur = mysql.connection.cursor()
        try:
            # Pre-chequeo UX (no reemplaza la UNIQUE constraint)
            cur.execute("SELECT 1 FROM usuarios WHERE usuario=%s LIMIT 1", (username,))
            if cur.fetchone():
                flash("⚠️ El nombre de usuario ya existe.", "warning")
                roles = _load_roles()
                return render_template("auth/register.html", roles=roles, form_data=form_data)

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
                roles = _load_roles()
                return render_template("auth/register.html", roles=roles, form_data=form_data)
            flash("❌ No se pudo crear el usuario (error de integridad).", "danger")
            roles = _load_roles()
            return render_template("auth/register.html", roles=roles, form_data=form_data)

        except Exception:
            mysql.connection.rollback()
            flash("❌ Ocurrió un error inesperado al crear el usuario.", "danger")
            roles = _load_roles()
            return render_template("auth/register.html", roles=roles, form_data=form_data)

        finally:
            cur.close()

        # Éxito: no redirigimos, mostramos la notificación y dejamos el formulario (vacío o con alguno valor)
        flash("✅ Usuario registrado con éxito", "success")
        roles = _load_roles()
        # Si prefieres limpiar el formulario después de registrar, envía form_data = {} aquí
        return render_template("auth/register.html", roles=roles, form_data={})

    # GET: carga de roles
    roles = _load_roles()
    return render_template("auth/register.html", roles=roles, form_data={})
