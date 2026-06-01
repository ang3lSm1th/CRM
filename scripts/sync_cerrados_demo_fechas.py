"""Sincroniza leads.fecha con ventas duplicadas ene-mar 2026 para vista Cerrados."""

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
import MySQLdb

load_dotenv()


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
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS leads_fecha_backup_demo (
                lead_id INT NOT NULL PRIMARY KEY,
                fecha_original DATE NOT NULL,
                backed_up_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            """
            INSERT IGNORE INTO leads_fecha_backup_demo (lead_id, fecha_original)
            SELECT l.id, l.fecha
            FROM leads l
            JOIN (
                SELECT lead_id, MAX(id) AS last_id
                FROM seguimientos GROUP BY lead_id
            ) ls ON ls.lead_id = l.id
            JOIN seguimientos s ON s.id = ls.last_id
            JOIN proceso p ON p.id = s.proceso_id
            JOIN ventas_concretadas vc ON vc.lead_id = l.id
            WHERE LOWER(TRIM(p.nombre_proceso)) = 'cerrado'
              AND vc.fecha_venta >= '2026-01-01'
              AND vc.fecha_venta < '2026-04-01'
            """
        )
        backup_count = cur.rowcount

        cur.execute(
            """
            UPDATE leads l
            INNER JOIN (
                SELECT lead_id, MIN(fecha_venta) AS nueva_fecha
                FROM ventas_concretadas
                WHERE fecha_venta >= '2026-01-01'
                  AND fecha_venta < '2026-04-01'
                GROUP BY lead_id
            ) vc ON vc.lead_id = l.id
            INNER JOIN (
                SELECT lead_id, MAX(id) AS last_id
                FROM seguimientos GROUP BY lead_id
            ) ls ON ls.lead_id = l.id
            INNER JOIN seguimientos s ON s.id = ls.last_id
            INNER JOIN proceso p ON p.id = s.proceso_id
            SET l.fecha = vc.nueva_fecha
            WHERE LOWER(TRIM(p.nombre_proceso)) = 'cerrado'
            """
        )
        updated = cur.rowcount
        conn.commit()

        cur.execute(
            """
            SELECT COUNT(*) FROM leads l
            JOIN (SELECT lead_id, MAX(id) lid FROM seguimientos GROUP BY lead_id) x
              ON x.lead_id = l.id
            JOIN seguimientos s ON s.id = x.lid
            JOIN proceso p ON p.id = s.proceso_id
            WHERE LOWER(p.nombre_proceso) = 'cerrado'
              AND l.fecha BETWEEN '2026-01-25' AND '2026-01-31'
            """
        )
        ene_25_31 = cur.fetchone()[0]

        cur.execute(
            """
            SELECT COUNT(*) FROM leads l
            JOIN (SELECT lead_id, MAX(id) lid FROM seguimientos GROUP BY lead_id) x
              ON x.lead_id = l.id
            JOIN seguimientos s ON s.id = x.lid
            JOIN proceso p ON p.id = s.proceso_id
            WHERE LOWER(p.nombre_proceso) = 'cerrado'
              AND l.fecha BETWEEN '2026-01-01' AND '2026-03-31'
            """
        )
        ene_mar = cur.fetchone()[0]

        print(f"Respaldo: {backup_count} fechas guardadas en leads_fecha_backup_demo")
        print(f"Leads cerrados actualizados: {updated}")
        print(f"Cerrados visibles 2026-01-25..31: {ene_25_31}")
        print(f"Cerrados visibles ene-mar 2026: {ene_mar}")
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
