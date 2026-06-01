# ...existing code...
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

    @staticmethod
    def create(nombre):
        """
        Inserta un nuevo bien/servicio y retorna su id.
        """
        cur = mysql.connection.cursor(DictCursor)
        try:
            cur.execute("INSERT INTO bienes_servicios (nombre) VALUES (%s)", (nombre,))
            mysql.connection.commit()
            return cur.lastrowid
        finally:
            cur.close()

    @staticmethod
    def update(bien_servicio_id, nombre):
        """
        Actualiza el nombre de un bien/servicio por id.
        """
        cur = mysql.connection.cursor(DictCursor)
        try:
            cur.execute("UPDATE bienes_servicios SET nombre = %s WHERE id = %s", (nombre, bien_servicio_id))
            mysql.connection.commit()
            return cur.rowcount
        finally:
            cur.close()

    @staticmethod
    def delete(bien_servicio_id):
        """
        Elimina un bien/servicio por id.
        """
        cur = mysql.connection.cursor(DictCursor)
        try:
            cur.execute("DELETE FROM bienes_servicios WHERE id = %s", (bien_servicio_id,))
            mysql.connection.commit()
            return cur.rowcount
        finally:
            cur.close()
# ...existing code...