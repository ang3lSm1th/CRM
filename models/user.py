from extensions import mysql
from MySQLdb.cursors import DictCursor

class User:
    def __init__(self, id, usuario, nombre, password, id_rol):
        self.id = id
        self.usuario = usuario
        self.nombre = nombre
        self.password = password
        self.id_rol = id_rol  # aquí id_rol es el NOMBRE del rol (ej: "asesor")

    # ---------------------------
    # Obtener usuario por username
    # ---------------------------
    @staticmethod
    def get_by_username(username: str):
        cur = mysql.connection.cursor(DictCursor)
        cur.execute("""
            SELECT u.id, u.usuario, u.nombre, u.password, r.nombre AS id_rol
            FROM usuarios u
            JOIN roles r ON u.id_rol = r.id
            WHERE u.usuario = %s
        """, (username,))
        row = cur.fetchone()
        cur.close()
        return User(**row) if row else None

    # ---------------------------
    # Obtener usuario por ID
    # ---------------------------
    @staticmethod
    def get_by_id(user_id: int):
        cur = mysql.connection.cursor(DictCursor)
        cur.execute("""
            SELECT u.id, u.usuario, u.nombre, u.password, r.nombre AS id_rol
            FROM usuarios u
            JOIN roles r ON u.id_rol = r.id
            WHERE u.id = %s
        """, (user_id,))
        row = cur.fetchone()
        cur.close()
        return User(**row) if row else None

    # ---------------------------
    # Obtener todos los usuarios
    # ---------------------------
    @staticmethod
    def get_all():
        cur = mysql.connection.cursor(DictCursor)
        cur.execute("""
            SELECT u.id, u.usuario, u.nombre, u.password, r.nombre AS id_rol
            FROM usuarios u
            JOIN roles r ON u.id_rol = r.id
            ORDER BY u.nombre
        """)
        rows = cur.fetchall()
        cur.close()
        return [User(**row) for row in rows]

    # ---------------------------
    # Obtener usuarios por nombre de rol
    # ---------------------------
    @staticmethod
    def get_by_role(role_name: str):
        cur = mysql.connection.cursor(DictCursor)
        cur.execute("""
            SELECT u.id, u.usuario, u.nombre, u.password, r.nombre AS id_rol
            FROM usuarios u
            JOIN roles r ON u.id_rol = r.id
            WHERE r.nombre = %s
        """, (role_name,))
        rows = cur.fetchall()
        cur.close()
        return [User(**row) for row in rows]
