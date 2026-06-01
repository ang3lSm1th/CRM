import os

import MySQLdb
from dotenv import load_dotenv
from MySQLdb.cursors import DictCursor


load_dotenv()


MESES_ES = {
    1: "enero",
    2: "febrero",
    3: "marzo",
    4: "abril",
    5: "mayo",
    6: "junio",
    7: "julio",
    8: "agosto",
    9: "septiembre",
    10: "octubre",
    11: "noviembre",
    12: "diciembre",
}


def connect():
    return MySQLdb.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        user=os.getenv("MYSQL_USER", "root"),
        passwd=os.getenv("MYSQL_PASSWORD", ""),
        db=os.getenv("MYSQL_DB", "u349183440_crm_orbes"),
        port=int(os.getenv("MYSQL_PORT", "3306")),
        charset="utf8mb4",
    )


def comentario_lead(fecha, bien_nombre):
    mes = MESES_ES.get(fecha.month, "el mes") if fecha else "el mes"
    producto = (bien_nombre or "producto agricola").strip()
    return (
        f"Cliente interesado en {producto}. "
        f"Contacto comercial realizado en {mes}; continuamos con asesoria tecnica personalizada."
    )


def comentario_seguimiento(fecha, bien_nombre, proceso_nombre):
    mes = MESES_ES.get(fecha.month, "el mes") if fecha else "el mes"
    producto = (bien_nombre or "producto agricola").strip()
    proceso = (proceso_nombre or "seguimiento").strip().lower()
    acciones = {
        "no iniciado": "pendiente de primer contacto comercial",
        "seguimiento": "en seguimiento activo con el cliente",
        "programado": "con visita o demostracion programada",
        "cotizado": "con cotizacion enviada para evaluacion",
        "cerrado": "con venta cerrada exitosamente",
        "cerrado no vendido": "cerrado sin venta en esta etapa",
    }
    accion = acciones.get(proceso, "en gestion comercial")
    return f"Gestion de {mes}: {producto}, {accion}."


def main():
    conn = connect()
    cur = conn.cursor(DictCursor)
    updated_leads = 0
    updated_segs = 0

    try:
        cur.execute(
            """
            SELECT l.id, l.fecha, bs.nombre AS bien_nombre
            FROM leads l
            LEFT JOIN bienes_servicios bs ON bs.id = l.bien_servicio_id
            WHERE l.comentario = 'Generado script mayo diario'
               OR l.comentario LIKE 'Generado script % diario'
            """
        )
        leads = cur.fetchall() or []

        for row in leads:
            nuevo = comentario_lead(row.get("fecha"), row.get("bien_nombre"))
            cur.execute("UPDATE leads SET comentario=%s WHERE id=%s", (nuevo, row["id"]))
            updated_leads += 1

        cur.execute(
            """
            SELECT s.id, s.fecha_seguimiento, p.nombre AS proceso_nombre, bs.nombre AS bien_nombre
            FROM seguimientos s
            JOIN leads l ON l.id = s.lead_id
            LEFT JOIN proceso p ON p.id = s.proceso_id
            LEFT JOIN bienes_servicios bs ON bs.id = l.bien_servicio_id
            WHERE s.comentario LIKE 'Lead demo %'
               OR s.comentario LIKE 'Generado script % diario'
            """
        )
        segs = cur.fetchall() or []

        for row in segs:
            nuevo = comentario_seguimiento(
                row.get("fecha_seguimiento"),
                row.get("bien_nombre"),
                row.get("proceso_nombre"),
            )
            cur.execute("UPDATE seguimientos SET comentario=%s WHERE id=%s", (nuevo, row["id"]))
            updated_segs += 1

        conn.commit()
        print(f"Leads actualizados: {updated_leads}")
        print(f"Seguimientos actualizados: {updated_segs}")
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
