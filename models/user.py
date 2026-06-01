from extensions import mysql
from MySQLdb.cursors import DictCursor


class User:
    def __init__(self, id, usuario, nombre, password, id_rol, negocio_id=None, negocio_slug=None, negocio_nombre=None):
        self.id = id
        self.usuario = usuario
        self.nombre = nombre
        self.password = password
        self.id_rol = id_rol
        self.negocio_id = negocio_id
        self.negocio_slug = negocio_slug
        self.negocio_nombre = negocio_nombre

    @staticmethod
    def _has_negocios_table() -> bool:
        cur = mysql.connection.cursor(DictCursor)
        try:
            cur.execute("SHOW TABLES LIKE 'negocios'")
            return cur.fetchone() is not None
        finally:
            cur.close()

    @staticmethod
    def _user_select_sql(where_clause: str) -> str:
        if User._has_negocios_table():
            return f"""
                SELECT u.id, u.usuario, u.nombre, u.password, r.nombre AS id_rol,
                       u.negocio_id, n.slug AS negocio_slug, n.nombre AS negocio_nombre
                FROM usuarios u
                JOIN roles r ON u.id_rol = r.id
                LEFT JOIN negocios n ON u.negocio_id = n.id
                {where_clause}
            """
        return f"""
            SELECT u.id, u.usuario, u.nombre, u.password, r.nombre AS id_rol,
                   u.negocio_id, NULL AS negocio_slug, NULL AS negocio_nombre
            FROM usuarios u
            JOIN roles r ON u.id_rol = r.id
            {where_clause}
        """

    @staticmethod
    def get_by_username(username: str):
        cur = mysql.connection.cursor(DictCursor)
        cur.execute(User._user_select_sql("WHERE u.usuario = %s"), (username,))
        row = cur.fetchone()
        cur.close()
        return User(**row) if row else None

    @staticmethod
    def get_by_id(user_id: int):
        cur = mysql.connection.cursor(DictCursor)
        cur.execute(User._user_select_sql("WHERE u.id = %s"), (user_id,))
        row = cur.fetchone()
        cur.close()
        return User(**row) if row else None

    @staticmethod
    def get_all():
        cur = mysql.connection.cursor(DictCursor)
        cur.execute(User._user_select_sql("ORDER BY u.nombre"))
        rows = cur.fetchall()
        cur.close()
        return [User(**row) for row in rows]

    @staticmethod
    def get_by_role(role_name: str):
        cur = mysql.connection.cursor(DictCursor)
        cur.execute(User._user_select_sql("WHERE r.nombre = %s"), (role_name,))
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

    @staticmethod
    def delete_by_username(username: str):
        cur = mysql.connection.cursor()
        try:
            cur.execute("DELETE FROM usuarios WHERE usuario = %s", (username,))
            mysql.connection.commit()
            return cur.rowcount > 0
        except Exception as e:
            print(f"Error al eliminar usuario por username: {e}")
            mysql.connection.rollback()
            return False
        finally:
            cur.close()
