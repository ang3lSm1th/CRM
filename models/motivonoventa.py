from extensions import mysql

class Motivonoventa:
    def __init__(self, id, motivo_no_venta):
        self.id = id
        self.motivo_no_venta = motivo_no_venta

    @staticmethod
    def get_all():
        cur = mysql.connection.cursor()
        cur.execute("SELECT id, motivo_no_venta FROM motivo_no_venta")
        rows = cur.fetchall()
        cur.close()
        # 👇 como DictCursor, accedemos con claves
        return [Motivonoventa(id=row["id"], motivo_no_venta=row["motivo_no_venta"]) for row in rows]