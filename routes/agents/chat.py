from flask import Blueprint, request, jsonify, session
from extensions import mysql
import MySQLdb.cursors
from utils.security import login_required
from datetime import datetime

chat_bp = Blueprint("chat", __name__, url_prefix="/chat")


# Obtener mensajes (individual o grupal)
@chat_bp.route("/mensajes", methods=["GET"])
@login_required
def get_mensajes():
    tipo = request.args.get("tipo", "grupal")  # grupal o individual
    destinatario_id = request.args.get("destinatario_id", None)
    usuario_id = session.get("user_id")

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    try:
        if tipo == "individual" and destinatario_id:
            # Conversación 1 a 1
            sql = """
                SELECT 
                    m.id,
                    m.mensaje,
                    m.fecha_envio,
                    m.leido,
                    m.usuario_id,
                    u.nombre as usuario_nombre,
                    m.destinatario_id
                FROM chat_mensajes m
                JOIN usuarios u ON m.usuario_id = u.id
                WHERE (m.usuario_id = %s AND m.destinatario_id = %s)
                   OR (m.usuario_id = %s AND m.destinatario_id = %s)
                ORDER BY m.fecha_envio ASC
                LIMIT 100
            """
            cur.execute(sql, (usuario_id, destinatario_id, destinatario_id, usuario_id))
        else:
            # Chat grupal
            sql = """
                SELECT 
                    m.id,
                    m.mensaje,
                    m.fecha_envio,
                    m.leido,
                    m.usuario_id,
                    u.nombre as usuario_nombre
                FROM chat_mensajes m
                JOIN usuarios u ON m.usuario_id = u.id
                WHERE m.es_grupal = TRUE
                ORDER BY m.fecha_envio DESC
                LIMIT 50
            """
            cur.execute(sql)

        mensajes = cur.fetchall()

        # Formatear fechas
        for msg in mensajes:
            if msg.get("fecha_envio"):
                msg["fecha_envio"] = msg["fecha_envio"].strftime("%Y-%m-%d %H:%M:%S")

        return jsonify(mensajes), 200

    except Exception as e:
        print(f"Error al obtener mensajes: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()


# Enviar mensaje
@chat_bp.route("/enviar", methods=["POST"])
@login_required
def enviar_mensaje():
    data = request.get_json()
    mensaje = data.get("mensaje", "").strip()
    tipo = data.get("tipo", "grupal")
    destinatario_id = data.get("destinatario_id", None)
    usuario_id = session.get("user_id")

    if not mensaje:
        return jsonify({"error": "El mensaje no puede estar vacío"}), 400

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    try:
        if tipo == "individual" and destinatario_id:
            sql = """
                INSERT INTO chat_mensajes (usuario_id, destinatario_id, mensaje, es_grupal)
                VALUES (%s, %s, %s, FALSE)
            """
            cur.execute(sql, (usuario_id, destinatario_id, mensaje))
        else:
            sql = """
                INSERT INTO chat_mensajes (usuario_id, mensaje, es_grupal)
                VALUES (%s, %s, TRUE)
            """
            cur.execute(sql, (usuario_id, mensaje))

        mysql.connection.commit()
        mensaje_id = cur.lastrowid

        # Obtener el mensaje recién creado
        cur.execute(
            """
            SELECT 
                m.id,
                m.mensaje,
                m.fecha_envio,
                m.usuario_id,
                u.nombre as usuario_nombre
            FROM chat_mensajes m
            JOIN usuarios u ON m.usuario_id = u.id
            WHERE m.id = %s
        """,
            (mensaje_id,),
        )

        nuevo_mensaje = cur.fetchone()
        if nuevo_mensaje and nuevo_mensaje.get("fecha_envio"):
            nuevo_mensaje["fecha_envio"] = nuevo_mensaje["fecha_envio"].strftime(
                "%Y-%m-%d %H:%M:%S"
            )

        return jsonify(nuevo_mensaje), 201

    except Exception as e:
        mysql.connection.rollback()
        print(f"Error al enviar mensaje: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()


# Marcar mensajes como leídos
@chat_bp.route("/marcar-leido", methods=["POST"])
@login_required
def marcar_leido():
    data = request.get_json()
    destinatario_id = data.get("destinatario_id")
    usuario_id = session.get("user_id")

    cur = mysql.connection.cursor()

    try:
        sql = """
            UPDATE chat_mensajes 
            SET leido = TRUE
            WHERE destinatario_id = %s AND usuario_id = %s AND leido = FALSE
        """
        cur.execute(sql, (usuario_id, destinatario_id))
        mysql.connection.commit()

        return jsonify({"success": True}), 200

    except Exception as e:
        mysql.connection.rollback()
        print(f"Error al marcar como leído: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()


# Obtener usuarios para chat individual
@chat_bp.route("/usuarios", methods=["GET"])
@login_required
def get_usuarios():
    usuario_id = session.get("user_id")

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    try:
        sql = """
            SELECT 
                u.id, 
                u.nombre,
                u.id_rol,
                r.nombre as id_rol_texto,
                CASE 
                    WHEN LOWER(r.nombre) = 'administrador' THEN 'Administrador'
                    WHEN LOWER(r.nombre) = 'gerente' THEN 'Gerente'
                    WHEN UPPER(r.nombre) = 'RRHH' THEN 'RRHH'
                    WHEN LOWER(r.nombre) = 'asesor' THEN 'Asesor'
                    ELSE CONCAT(UPPER(LEFT(r.nombre, 1)), LOWER(SUBSTRING(r.nombre, 2)))
                END as nombre_rol,
                COALESCE(
                    (SELECT COUNT(*) 
                     FROM chat_mensajes 
                     WHERE (usuario_id = u.id AND destinatario_id = %s)
                        OR (usuario_id = %s AND destinatario_id = u.id)
                    ), 0
                ) as total_mensajes,
                COALESCE(
                    (SELECT COUNT(*) 
                     FROM chat_mensajes 
                     WHERE usuario_id = u.id 
                       AND destinatario_id = %s 
                       AND leido = FALSE
                    ), 0
                ) as mensajes_no_leidos
            FROM usuarios u
            LEFT JOIN roles r ON u.id_rol = r.id
            WHERE u.id != %s
            ORDER BY u.nombre ASC
        """
        cur.execute(sql, (usuario_id, usuario_id, usuario_id, usuario_id))
        usuarios = cur.fetchall() or []

        # Convertir a lista si es necesario
        if not isinstance(usuarios, list):
            usuarios = list(usuarios)

        return jsonify(usuarios), 200

    except Exception as e:
        print(f"Error al obtener usuarios: {e}")
        import traceback

        traceback.print_exc()
        return jsonify({"error": str(e), "usuarios": []}), 200
    finally:
        cur.close()


# Contar mensajes no leídos
@chat_bp.route("/no-leidos", methods=["GET"])
@login_required
def mensajes_no_leidos():
    usuario_id = session.get("user_id")

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)

    try:
        sql = """
            SELECT COUNT(*) as total
            FROM chat_mensajes
            WHERE destinatario_id = %s AND leido = FALSE
        """
        cur.execute(sql, (usuario_id,))
        resultado = cur.fetchone()

        return jsonify({"total": resultado.get("total", 0)}), 200

    except Exception as e:
        print(f"Error al contar mensajes no leídos: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        cur.close()
