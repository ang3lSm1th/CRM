# models/moneda.py
from extensions import mysql

class Moneda:
    def __init__(self, id, nombre_moneda):
        self.id = id
        self.nombre_moneda = nombre_moneda

    @staticmethod
    def get_all():
        cur = mysql.connection.cursor()
        cur.execute("SELECT id, nombre_moneda FROM moneda")
        rows = cur.fetchall()
        cur.close()
        # 👇 como DictCursor, accedemos con claves
        return [Moneda(id=row["id"], nombre_moneda=row["nombre_moneda"]) for row in rows]
