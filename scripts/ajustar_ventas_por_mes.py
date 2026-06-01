"""
Ajusta ventas/cerrados demo a metas exactas:
  Enero 2026: 410 | Febrero: 445 | Marzo: 470
"""

import os
import sys
import calendar

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
import MySQLdb

load_dotenv()

TARGETS = {1: 410, 2: 445, 3: 470}
YEAR = 2026


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
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS ajuste_ventas_mes_backup (
                id INT AUTO_INCREMENT PRIMARY KEY,
                lead_id INT NOT NULL,
                mes TINYINT NOT NULL,
                accion VARCHAR(30) NOT NULL,
                created_at DATETIME DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        for month, target in TARGETS.items():
            f_ini, f_fin = month_range(YEAR, month)

            cur.execute(
                """
                SELECT DISTINCT vc.lead_id
                FROM ventas_concretadas vc
                WHERE vc.fecha_venta BETWEEN %s AND %s
                ORDER BY vc.lead_id
                """,
                (f_ini, f_fin),
            )
            lead_ids = [row[0] for row in cur.fetchall()]
            keep = set(lead_ids[:target])
            excess = [lid for lid in lead_ids if lid not in keep]

            if excess:
                placeholders = ",".join(["%s"] * len(excess))
                cur.execute(
                    f"""
                    DELETE FROM ventas_concretadas
                    WHERE lead_id IN ({placeholders})
                      AND fecha_venta BETWEEN %s AND %s
                    """,
                    tuple(excess) + (f_ini, f_fin),
                )

                cur.execute(
                    f"""
                    DELETE FROM seguimientos
                    WHERE lead_id IN ({placeholders})
                      AND comentario = 'Demo clase: cierre automático'
                    """,
                    tuple(excess),
                )

                cur.execute(
                    f"""
                    UPDATE leads l
                    LEFT JOIN leads_fecha_backup_cerrado_demo b1 ON b1.lead_id = l.id
                    LEFT JOIN leads_fecha_backup_demo b2 ON b2.lead_id = l.id
                    SET l.fecha = COALESCE(b1.fecha_original, b2.fecha_original, l.fecha)
                    WHERE l.id IN ({placeholders})
                    """,
                    tuple(excess),
                )

                for lid in excess:
                    cur.execute(
                        """
                        INSERT INTO ajuste_ventas_mes_backup (lead_id, mes, accion)
                        VALUES (%s, %s, 'removed_from_month')
                        """,
                        (lid, month),
                    )

            # Alinear fecha del lead con venta para los que se conservan
            if keep:
                placeholders = ",".join(["%s"] * len(keep))
                cur.execute(
                    f"""
                    UPDATE leads l
                    JOIN (
                        SELECT lead_id, MIN(fecha_venta) AS fv
                        FROM ventas_concretadas
                        WHERE lead_id IN ({placeholders})
                          AND fecha_venta BETWEEN %s AND %s
                        GROUP BY lead_id
                    ) v ON v.lead_id = l.id
                    SET l.fecha = v.fv
                    WHERE l.id IN ({placeholders})
                    """,
                    tuple(keep) + (f_ini, f_fin) + tuple(keep),
                )

            # Quitar cerrados del mes sin venta en ese mes (restos de sync)
            cur.execute(
                """
                SELECT l.id
                FROM leads l
                JOIN (
                    SELECT lead_id, MAX(id) lid FROM seguimientos GROUP BY lead_id
                ) x ON x.lead_id = l.id
                JOIN seguimientos s ON s.id = x.lid
                JOIN proceso p ON p.id = s.proceso_id
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
            orphan_cerrados = [r[0] for r in cur.fetchall()]
            if orphan_cerrados:
                ph = ",".join(["%s"] * len(orphan_cerrados))
                cur.execute(
                    f"""
                    DELETE FROM seguimientos
                    WHERE lead_id IN ({ph})
                      AND comentario = 'Demo clase: cierre automático'
                    """,
                    tuple(orphan_cerrados),
                )
                cur.execute(
                    f"""
                    UPDATE leads l
                    LEFT JOIN leads_fecha_backup_cerrado_demo b1 ON b1.lead_id = l.id
                    LEFT JOIN leads_fecha_backup_demo b2 ON b2.lead_id = l.id
                    SET l.fecha = COALESCE(b1.fecha_original, b2.fecha_original, l.fecha)
                    WHERE l.id IN ({ph})
                    """,
                    tuple(orphan_cerrados),
                )

            # Pasada 2: cerrados en el mes sin venta en el mes (p. ej. sync previo)
            cur.execute(
                """
                SELECT l.id
                FROM leads l
                JOIN (
                    SELECT lead_id, MAX(id) lid FROM seguimientos GROUP BY lead_id
                ) x ON x.lead_id = l.id
                JOIN seguimientos s ON s.id = x.lid
                JOIN proceso p ON p.id = s.proceso_id
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
            still_orphan = [r[0] for r in cur.fetchall()]
            if still_orphan:
                ph2 = ",".join(["%s"] * len(still_orphan))
                cur.execute(
                    f"""
                    UPDATE leads l
                    LEFT JOIN leads_fecha_backup_cerrado_demo b1 ON b1.lead_id = l.id
                    LEFT JOIN leads_fecha_backup_demo b2 ON b2.lead_id = l.id
                    SET l.fecha = COALESCE(b1.fecha_original, b2.fecha_original, DATE('2025-10-01'))
                    WHERE l.id IN ({ph2})
                    """,
                    tuple(still_orphan),
                )

            print(f"Mes {month:02d}/{YEAR}: objetivo={target}, antes={len(lead_ids)}, removidos={len(excess)}, orphans_ajustados={len(still_orphan)}")

        conn.commit()

        print("\nVerificación:")
        for month, target in TARGETS.items():
            f_ini, f_fin = month_range(YEAR, month)
            cur.execute(
                """
                SELECT COUNT(DISTINCT lead_id) FROM ventas_concretadas
                WHERE fecha_venta BETWEEN %s AND %s
                """,
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
            print(f"  {f_ini}..{f_fin}: ventas={ventas}, cerrados={cerrados} (meta {target})")

    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
