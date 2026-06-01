# models/canal_contacto.py
from extensions import mysql
from MySQLdb.cursors import DictCursor

class CanalContacto:
    @staticmethod
    def get_all():
        """
        Devuelve lista de dicts con llaves: id, nombre
        (Ordenado por nombre ascendente)
        """
        cur = mysql.connection.cursor(DictCursor)
        cur.execute("SELECT id, nombre FROM canal_contacto ORDER BY nombre")
        rows = cur.fetchall()
        cur.close()
        # Asegura estructura uniforme
        return [{"id": r.get("id"), "nombre": r.get("nombre")} for r in rows]
