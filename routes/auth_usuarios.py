from flask import Blueprint, render_template, request, jsonify, session
from models.user import User
from utils.security import hash_password
from extensions import mysql

usuarios_bp = Blueprint('usuarios', __name__, url_prefix='/usuarios')

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
    allowed_roles = ['administrador']
    user_rol = session.get('id_rol')
    
    if user_rol not in allowed_roles:
        return jsonify({'success': False, 'error': 'No autorizado'}), 403

    if User.delete_by_id(user_id):
        return jsonify({'success': True})
    else:
        return jsonify({'success': False, 'error': 'Error al eliminar el usuario o usuario no encontrado'}), 404