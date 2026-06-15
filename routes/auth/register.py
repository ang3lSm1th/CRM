# routes/auth.register.py
from flask import Blueprint, render_template, request, flash, current_app, abort, session
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


def _load_negocios():
    cur = mysql.connection.cursor()
    try:
        cur.execute("SELECT id, nombre, slug FROM negocios ORDER BY nombre")
        return cur.fetchall() or []
    finally:
        cur.close()


def _column_exists(table, column):
    cur = mysql.connection.cursor()
    try:
        cur.execute(
            "SELECT COUNT(*) AS cnt FROM INFORMATION_SCHEMA.COLUMNS WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s AND COLUMN_NAME = %s",
            (table, column),
        )
        row = cur.fetchone() or {}
        try:
            cnt = row[0] if isinstance(row, (list, tuple)) else (row.get('cnt') if isinstance(row, dict) else 0)
        except Exception:
            cnt = 0
        return int(cnt or 0) > 0
    finally:
        cur.close()


@register_bp.route("/register", methods=["GET", "POST"])
def register():
    if not current_app.config.get("ALLOW_PUBLIC_REGISTRATION") and not session.get("user_id"):
        abort(404)

    if request.method == "POST":
        username = (request.form.get("username") or "").strip()
        nombre = (request.form.get("nombre") or "").strip()
        password = request.form.get("password") or ""
        rol_id = request.form.get("rol") or ""
        negocio_id_raw = request.form.get("negocio_id") or ""

        # Para re-renderizar el formulario con los valores ingresados
        form_data = {"username": username, "nombre": nombre, "rol_id": rol_id, "negocio_id": negocio_id_raw}

        # Validaciones básicas
        if not username or not nombre or not password or not rol_id:
            flash("Todos los campos son obligatorios", "warning")
            roles = _load_roles()
            negocios = _load_negocios()
            return render_template("auth/register.html", roles=roles, negocios=negocios, form_data=form_data)

        try:
            rol_id = int(rol_id)
        except (TypeError, ValueError):
            flash("Rol inválido.", "warning")
            roles = _load_roles()
            negocios = _load_negocios()
            return render_template("auth/register.html", roles=roles, negocios=negocios, form_data=form_data)

        # Determine role name to decide if negocio is required
        role_name = None
        tmpc = mysql.connection.cursor()
        try:
            tmpc.execute("SELECT nombre FROM roles WHERE id = %s LIMIT 1", (rol_id,))
            r = tmpc.fetchone()
            if r:
                role_name = r[0] if isinstance(r, (list, tuple)) else (r.get('nombre') if isinstance(r, dict) else None)
        finally:
            tmpc.close()

        # If role is not administrador, negocio selection is required
        if not role_name or str(role_name).strip().lower() != 'administrador':
            if not negocio_id_raw:
                flash('Selecciona una empresa para usuarios que no son administradores', 'warning')
                roles = _load_roles()
                negocios = _load_negocios()
                return render_template('auth/register.html', roles=roles, negocios=negocios, form_data=form_data)

        hashed_pw = hash_password(password)

        # Validate negocio if provided
        negocio_val = None
        if negocio_id_raw:
            try:
                negocio_val = int(negocio_id_raw)
            except Exception:
                negocio_val = None

        # Pre-check username uniqueness and insert (include negocio_id if column exists)
        cur = mysql.connection.cursor()
        try:
            cur.execute("SELECT 1 FROM usuarios WHERE usuario=%s LIMIT 1", (username,))
            if cur.fetchone():
                flash("⚠️ El nombre de usuario ya existe.", "warning")
                roles = _load_roles()
                negocios = _load_negocios()
                return render_template("auth/register.html", roles=roles, negocios=negocios, form_data=form_data)

            if _column_exists('usuarios', 'negocio_id'):
                cur.execute(
                    "INSERT INTO usuarios (usuario, nombre, password, id_rol, negocio_id) VALUES (%s, %s, %s, %s, %s)",
                    (username, nombre, hashed_pw, rol_id, negocio_val),
                )
            else:
                cur.execute(
                    "INSERT INTO usuarios (usuario, nombre, password, id_rol) VALUES (%s, %s, %s, %s)",
                    (username, nombre, hashed_pw, rol_id),
                )
            mysql.connection.commit()

        except IntegrityError as e:
            mysql.connection.rollback()
            if e.args and e.args[0] == 1062:
                flash("⚠️ El nombre de usuario ya existe.", "warning")
                roles = _load_roles()
                negocios = _load_negocios()
                return render_template("auth/register.html", roles=roles, negocios=negocios, form_data=form_data)
            flash("❌ No se pudo crear el usuario (error de integridad).", "danger")
            roles = _load_roles()
            negocios = _load_negocios()
            return render_template("auth/register.html", roles=roles, negocios=negocios, form_data=form_data)

        except Exception:
            mysql.connection.rollback()
            flash("❌ Ocurrió un error inesperado al crear el usuario.", "danger")
            roles = _load_roles()
            negocios = _load_negocios()
            return render_template("auth/register.html", roles=roles, negocios=negocios, form_data=form_data)

        finally:
            cur.close()

        flash("✅ Usuario registrado con éxito", "success")
        roles = _load_roles()
        negocios = _load_negocios()
        return render_template("auth/register.html", roles=roles, negocios=negocios, form_data={})

    # GET: carga de roles y negocios
    roles = _load_roles()
    negocios = _load_negocios()
    return render_template("auth/register.html", roles=roles, negocios=negocios, form_data={})
