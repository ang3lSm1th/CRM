from extensions import mysql
from MySQLdb.cursors import DictCursor


class BienServicio:
    @staticmethod
    def get_all():
        """
        Retorna todos los bienes/servicios disponibles.
        """
        cur = mysql.connection.cursor(DictCursor)   # 👈 en vez de dictionary=True
        cur.execute("SELECT id, nombre FROM bienes_servicios ORDER BY nombre")
        data = cur.fetchall()
        cur.close()
        return data

    @staticmethod
    def get_by_id(bien_servicio_id):
        """
        Retorna un bien/servicio específico por ID.
        """
        cur = mysql.connection.cursor(DictCursor)   # 👈 en vez de dictionary=True
        cur.execute("SELECT id, nombre FROM bienes_servicios WHERE id = %s", (bien_servicio_id,))
        data = cur.fetchone()
        cur.close()
        return data
