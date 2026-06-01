"""Mueve fuera del mes a cerrados sin venta en ese mes (fecha de respaldo)."""

import os
import sys
import calendar

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
import MySQLdb

load_dotenv()

TARGETS = {1: 410, 2: 445, 3: 470}


def month_range(year, month):
    last = calendar.monthrange(year, month)[1]
    return f"{year}-{month:02d}-01", f"{year}-{month:02d}-{last:02d}"


def main():
    conn = MySQLdb.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        user=os.getenv("MYSQL_USER", "root"),
        passwd=os.getenv("MYSQL_PASSWORD", "123456"),
        db=os.getenv("MYSQL_DB", "u349183440_crm_orbes"),
        port=int(os.getenv("MYSQL_PORT", "3307")),
    )
    cur = conn.cursor()

    try:
        for month in (1, 2, 3):
            f_ini, f_fin = month_range(2026, month)
            cur.execute(
                """
                SELECT l.id,
                       COALESCE(b1.fecha_original, b2.fecha_original) AS backup_fecha
                FROM leads l
                JOIN (SELECT lead_id, MAX(id) lid FROM seguimientos GROUP BY lead_id) x
                  ON x.lead_id = l.id
                JOIN seguimientos s ON s.id = x.lid
                JOIN proceso p ON p.id = s.proceso_id
                LEFT JOIN leads_fecha_backup_cerrado_demo b1 ON b1.lead_id = l.id
                LEFT JOIN leads_fecha_backup_demo b2 ON b2.lead_id = l.id
                WHERE LOWER(p.nombre_proceso) = 'cerrado'
                  AND l.fecha BETWEEN %s AND %s
                  AND NOT EXISTS (
                    SELECT 1 FROM ventas_concretadas vc
                    WHERE vc.lead_id = l.id
                      AND vc.fecha_venta BETWEEN %s AND %s
                  )
                """,
                (f_ini, f_fin, f_ini, f_fin),
            )
            rows = cur.fetchall()
            moved = 0
            for lead_id, backup_fecha in rows:
                if backup_fecha and (
                    backup_fecha.year != 2026
                    or backup_fecha.month != month
                ):
                    new_fecha = backup_fecha
                else:
                    fallback_month = 10 + ((lead_id + month) % 3)
                    new_fecha = f"2025-{fallback_month:02d}-{(lead_id % 28) + 1:02d}"
                cur.execute(
                    "UPDATE leads SET fecha = %s WHERE id = %s",
                    (new_fecha, lead_id),
                )
                moved += 1
            print(f"Mes {month}: movidos fuera {moved}")

        conn.commit()

        print("\nVerificación final:")
        for month, target in TARGETS.items():
            f_ini, f_fin = month_range(2026, month)
            cur.execute(
                "SELECT COUNT(DISTINCT lead_id) FROM ventas_concretadas WHERE fecha_venta BETWEEN %s AND %s",
                (f_ini, f_fin),
            )
            ventas = cur.fetchone()[0]
            cur.execute(
                """
                SELECT COUNT(*) FROM leads l
                JOIN (SELECT lead_id, MAX(id) lid FROM seguimientos GROUP BY lead_id) x
                  ON x.lead_id = l.id
                JOIN seguimientos s ON s.id = x.lid
                JOIN proceso p ON p.id = s.proceso_id
                WHERE LOWER(p.nombre_proceso) = 'cerrado'
                  AND l.fecha BETWEEN %s AND %s
                """,
                (f_ini, f_fin),
            )
            cerrados = cur.fetchone()[0]
            print(f"  Mes {month}: ventas={ventas}, cerrados={cerrados} (meta {target})")
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
