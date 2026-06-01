#canal de recepcion

from extensions import mysql
from MySQLdb.cursors import DictCursor

class Canal:
    @staticmethod
    def get_all():
        """
        Retorna todos los canales disponibles.
        """
        cur = mysql.connection.cursor(DictCursor)   # 👈 en vez de dictionary=True
        cur.execute("SELECT id, nombre FROM canales_recepcion ORDER BY nombre")
        data = cur.fetchall()
        cur.close()
        return data

    @staticmethod
    def get_by_id(canal_id):
        """
        Retorna un canal específico por ID.
        """
        cur = mysql.connection.cursor(DictCursor)  # 👈 en vez de dictionary=True
        cur.execute("SELECT id, nombre FROM canales_recepcion WHERE id = %s", (canal_id,))
        data = cur.fetchone()
        cur.close()
        return data
