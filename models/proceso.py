from extensions import mysql
from MySQLdb.cursors import DictCursor

class Proceso:
    @staticmethod
    def get_all():
        cur = mysql.connection.cursor(DictCursor)
        cur.execute("SELECT id, nombre_proceso FROM proceso")
        procesos = cur.fetchall()
        cur.close()
        return procesos
