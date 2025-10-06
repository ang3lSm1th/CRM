from extensions import mysql
from MySQLdb.cursors import DictCursor

class User:
    def __init__(self, id, usuario, nombre, password, id_rol):
        self.id = id
        self.usuario = usuario
        self.nombre = nombre
        self.password = password
        self.id_rol = id_rol

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

    @staticmethod
    def delete_by_id(user_id: int):
        cur = mysql.connection.cursor()
        try:
            cur.execute("DELETE FROM usuarios WHERE id = %s", (user_id,))
            mysql.connection.commit()
            return cur.rowcount > 0
        except Exception as e:
            print(f"Error al eliminar usuario: {e}")
            mysql.connection.rollback()
            return False
        finally:
            cur.close()