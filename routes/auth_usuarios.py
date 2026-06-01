from flask import Blueprint, render_template, request, jsonify, session
from models.user import User
from utils.security import (
    hash_password,
    login_required,
    role_required,
    ROLE_ADMIN,
    ROLE_GERENTE,
    ROLE_RRHH,
)
from extensions import mysql
import MySQLdb.cursors


def _find_fk_blockers_for_user(user_id):
    """Return list of (table, column, count) that reference usuarios.id = user_id."""
    cur = mysql.connection.cursor()
    try:
        # Find all foreign key columns that reference usuarios.id
        cur.execute(
            """
            SELECT TABLE_NAME, COLUMN_NAME
            FROM INFORMATION_SCHEMA.KEY_COLUMN_USAGE
            WHERE REFERENCED_TABLE_SCHEMA = DATABASE()
              AND REFERENCED_TABLE_NAME = 'usuarios'
              AND REFERENCED_COLUMN_NAME = 'id'
            """
        )
        rows = cur.fetchall() or []
        blockers = []
        for row in rows:
            # row can be tuple or dict depending on cursor type
            if isinstance(row, dict):
                t = row.get('TABLE_NAME')
                col = row.get('COLUMN_NAME')
            else:
                t, col = row[0], row[1]

            # Count referencing rows
            try:
                c2 = mysql.connection.cursor()
                try:
                    c2.execute(f"SELECT COUNT(*) FROM `{t}` WHERE `{col}` = %s", (user_id,))
                    count_row = c2.fetchone()
                    cnt = (count_row[0] if isinstance(count_row, (list, tuple)) else (count_row.get('COUNT(*)') if isinstance(count_row, dict) else None))
                    if cnt is None:
                        # Try common keys
                        cnt = (count_row.get('cnt') if isinstance(count_row, dict) else 0) or 0
                finally:
                    c2.close()
            except Exception:
                cnt = 0

            try:
                cnt = int(cnt or 0)
            except Exception:
                cnt = 0

            if cnt > 0:
                blockers.append((t, col, cnt))

        return blockers
    finally:
        cur.close()

usuarios_bp = Blueprint('usuarios', __name__, url_prefix='/usuarios')

@usuarios_bp.before_request
@login_required
@role_required(ROLE_ADMIN, ROLE_GERENTE, ROLE_RRHH)
def _usuarios_before_request():
    return None

@usuarios_bp.route('/registrados', methods=['GET'])
def usuarios_registrados():
    usuarios = User.get_all()
    return render_template('auth/usuarios_registrados.html', usuarios=usuarios)

@usuarios_bp.route('/reset_password', methods=['POST'])
def reset_password():
    allowed_roles = ['administrador', 'gerente', 'RRHH']
    user_rol = session.get('id_rol')
    if user_rol not in allowed_roles:
        return jsonify({'success': False, 'error': 'No autorizado'}), 403

    data = request.get_json(silent=True) or {}
    user_id = data.get('user_id')
    new_password = data.get('new_password')

    if not user_id or not new_password:
        return jsonify({'success': False, 'error': 'Parámetros incompletos'}), 400

    hashed = hash_password(new_password)

    cur = mysql.connection.cursor()
    try:
        cur.execute("UPDATE usuarios SET password=%s WHERE id=%s", (hashed, user_id))
        mysql.connection.commit()
    except Exception:
        mysql.connection.rollback()
        return jsonify({'success': False, 'error': 'Error al actualizar contraseña'}), 500
    finally:
        cur.close()

    return jsonify({'success': True})

@usuarios_bp.route('/eliminar/<int:user_id>', methods=['DELETE'])
def eliminar_usuario(user_id):
    allowed_roles = ['administrador', 'gerente', 'rrhh']
    user_rol = str(session.get('id_rol') or '').strip().lower()
    
    if user_rol not in allowed_roles:
        return jsonify({'success': False, 'error': 'No autorizado'}), 403

    # Check FK blockers before attempting delete
    try:
        blockers = _find_fk_blockers_for_user(user_id)
    except Exception as e:
        print('Error comprobando restricciones FK:', e)
        blockers = []

    if blockers:
        detail = ", ".join([f"{b[2]} en {b[0]}.{b[1]}" for b in blockers])
        return jsonify({'success': False, 'error': f'No se pudo eliminar el usuario: existen referencias ({detail}). Reasigna o elimina esos registros primero.'}), 409

    if User.delete_by_id(user_id):
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': 'Error al eliminar el usuario o usuario no encontrado'}), 404


@usuarios_bp.route('/eliminar/usuario/<string:username>', methods=['DELETE'])
def eliminar_usuario_por_username(username):
    """Eliminar usuario por su nombre de usuario (string)."""
    allowed_roles = ['administrador', 'gerente', 'rrhh']
    user_rol = str(session.get('id_rol') or '').strip().lower()

    if user_rol not in allowed_roles:
        return jsonify({'success': False, 'error': 'No autorizado'}), 403

    # Evitar auto-eliminación por username
    current_username = str(session.get('username') or '')
    if current_username and current_username == username:
        return jsonify({'success': False, 'error': 'No puedes eliminar tu propio usuario'}), 400

    # Verificar existencia
    existing = User.get_by_username(username)
    if not existing:
        return jsonify({'success': False, 'error': 'Usuario no encontrado'}), 404

    # Check FK blockers before attempting delete
    try:
        user_id = int(existing.id)
    except Exception:
        user_id = None

    if user_id is not None:
        try:
            blockers = _find_fk_blockers_for_user(user_id)
        except Exception as e:
            print('Error comprobando restricciones FK:', e)
            blockers = []
    else:
        blockers = []

    if blockers:
        detail = ", ".join([f"{b[2]} en {b[0]}.{b[1]}" for b in blockers])
        return jsonify({'success': False, 'error': f'No se pudo eliminar el usuario: existen referencias ({detail}). Reasigna o elimina esos registros primero.'}), 409

    try:
        deleted = User.delete_by_username(username)
        if deleted:
            return jsonify({'success': True}), 200
        else:
            return jsonify({'success': False, 'error': 'No se pudo eliminar el usuario (restricción de BD o error)'}), 500
    except Exception as e:
        print(f"Error eliminar_usuario_por_username: {e}")
        return jsonify({'success': False, 'error': 'Error interno al eliminar el usuario'}), 500


@usuarios_bp.route('/api_reassign_targets', methods=['GET'])
def api_reassign_targets():
    """Return a list of users suitable as reassign targets (exclude none)."""
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        cur.execute("SELECT id, usuario, nombre, id_rol FROM usuarios ORDER BY nombre")
        rows = cur.fetchall() or []
        return jsonify([{"id": r["id"], "usuario": r["usuario"], "nombre": r["nombre"], "id_rol": r["id_rol"]} for r in rows]), 200
    finally:
        cur.close()


@usuarios_bp.route('/reasignar', methods=['POST'])
def reasignar_y_eliminar():
    """Reassign all FK references from one user to another and optionally delete the source user.

    JSON body:
      - from_user_id OR from_username
      - to_user_id OR to_username
      - delete_after_reassign: boolean (default true)
    """
    allowed_roles = ['administrador', 'gerente', 'rrhh']
    user_rol = str(session.get('id_rol') or '').strip().lower()

    if user_rol not in allowed_roles:
        return jsonify({'success': False, 'error': 'No autorizado'}), 403

    data = request.get_json(silent=True) or {}
    from_user_id = data.get('from_user_id')
    from_username = data.get('from_username')
    to_user_id = data.get('to_user_id')
    to_username = data.get('to_username')
    delete_after = data.get('delete_after_reassign', True)

    # Resolve from
    if not from_user_id and from_username:
        u = User.get_by_username(from_username)
        if not u:
            return jsonify({'success': False, 'error': 'Usuario origen no encontrado'}), 404
        try:
            from_user_id = int(u.id)
        except Exception:
            return jsonify({'success': False, 'error': 'Usuario origen inválido'}), 400

    # Resolve to
    if not to_user_id and to_username:
        u2 = User.get_by_username(to_username)
        if not u2:
            return jsonify({'success': False, 'error': 'Usuario destino no encontrado'}), 404
        try:
            to_user_id = int(u2.id)
        except Exception:
            return jsonify({'success': False, 'error': 'Usuario destino inválido'}), 400

    try:
        from_user_id = int(from_user_id)
        to_user_id = int(to_user_id)
    except Exception:
        return jsonify({'success': False, 'error': 'IDs inválidos'}), 400

    if from_user_id == to_user_id:
        return jsonify({'success': False, 'error': 'El usuario origen y destino deben ser distintos'}), 400

    # Prevent self-delete via this flow
    current_user_id = None
    try:
        current_user_id = int(session.get('user_id') or 0)
    except Exception:
        current_user_id = None

    if current_user_id and current_user_id == from_user_id:
        return jsonify({'success': False, 'error': 'No puedes reasignar/eliminar tu propio usuario'}), 400

    # Find FK columns that reference usuarios.id and have rows with from_user_id
    try:
        blockers = _find_fk_blockers_for_user(from_user_id)
    except Exception as e:
        print('Error comprobando restricciones FK (reasignar):', e)
        return jsonify({'success': False, 'error': 'Error comprobando restricciones FK'}), 500

    results = []
    cur = mysql.connection.cursor()
    try:
        # Begin pseudo-transaction: we'll commit at the end
        for (table, col, cnt) in blockers:
            try:
                sql = f"UPDATE `{table}` SET `{col}` = %s WHERE `{col}` = %s"
                cur.execute(sql, (to_user_id, from_user_id))
                updated = cur.rowcount
                results.append({'table': table, 'column': col, 'updated': updated})
            except Exception as e:
                print(f"Error updating {table}.{col}: {e}")
                raise

        # After reassign, attempt delete if requested
        deleted = False
        if delete_after:
            try:
                deleted = User.delete_by_id(from_user_id)
            except Exception as e:
                print('Error borrando usuario tras reasignar:', e)
                mysql.connection.rollback()
                return jsonify({'success': False, 'error': 'Error al eliminar el usuario después de reasignar'}), 500

        mysql.connection.commit()
        return jsonify({'success': True, 'updated': results, 'deleted': bool(deleted)}), 200
    except Exception as e:
        mysql.connection.rollback()
        print('Error en reasignar_y_eliminar:', e)
        return jsonify({'success': False, 'error': 'Error al reasignar registros'}), 500
    finally:
        cur.close()


@usuarios_bp.route('/editar/<int:user_id>', methods=['POST'])
@login_required
@role_required(ROLE_ADMIN, ROLE_GERENTE, ROLE_RRHH)
def editar_usuario(user_id):
    """Editar campos básicos de usuario. Solo administradores pueden cambiar `negocio_id`.

    Campos aceptados (form/json): `nombre`, `usuario`, `id_rol`, `negocio_id`.
    """
    data = request.form.to_dict() if request.form else (request.get_json(silent=True) or {})

    # Si intentan cambiar negocio_id y no son administradores, denegar
    current_role = str(session.get('id_rol') or '').strip().lower()
    wants_negocio = 'negocio_id' in data and data.get('negocio_id') is not None and data.get('negocio_id') != ''
    allowed_negocio_roles = {ROLE_ADMIN.lower(), ROLE_RRHH.lower()}
    if wants_negocio and current_role not in allowed_negocio_roles:
        return jsonify({'success': False, 'error': 'No autorizado para cambiar la empresa (solo administradores y RRHH).'}), 403

    # Validar existencia del usuario destino
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        cur.execute("SELECT id FROM usuarios WHERE id = %s LIMIT 1", (user_id,))
        target = cur.fetchone()
        if not target:
            return jsonify({'success': False, 'error': 'Usuario no encontrado.'}), 404
    finally:
        cur.close()

    # Preparar update
    allowed_fields = ['nombre', 'usuario', 'id_rol', 'negocio_id']
    set_parts = []
    params = []
    for k in allowed_fields:
        if k in data:
            val = data.get(k)
            # normalize empty strings to NULL for negocio_id
            if k == 'negocio_id':
                if val is None or val == '':
                    params.append(None)
                else:
                    try:
                        params.append(int(val))
                    except Exception:
                        return jsonify({'success': False, 'error': 'negocio_id inválido.'}), 400
            elif k == 'id_rol':
                try:
                    params.append(int(val))
                except Exception:
                    return jsonify({'success': False, 'error': 'id_rol inválido.'}), 400
            else:
                params.append(val)
            set_parts.append(f"{k} = %s")

    if not set_parts:
        return jsonify({'success': False, 'error': 'No hay campos para actualizar.'}), 400

    sql = f"UPDATE usuarios SET {', '.join(set_parts)} WHERE id = %s"
    params.append(user_id)

    cur2 = mysql.connection.cursor()
    try:
        cur2.execute(sql, tuple(params))
        mysql.connection.commit()
        return jsonify({'success': True, 'updated': cur2.rowcount}), 200
    except Exception as ex:
        mysql.connection.rollback()
        return jsonify({'success': False, 'error': f'Error al actualizar usuario: {ex}'}), 500
    finally:
        cur2.close()