"""
Pasa leads en Seguimiento -> Cerrado con cotización única, monto, moneda
y registro en ventas_concretadas (ene/feb/mar 2026 para demo).
"""

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
            CREATE TABLE IF NOT EXISTS seguimientos_backup_cerrado_demo (
                id INT NOT NULL PRIMARY KEY,
                lead_id INT NOT NULL,
                proceso_id INT NULL,
                cotizacion VARCHAR(10) NULL,
                monto DECIMAL(10,2) NULL,
                moneda_id INT NULL,
                fecha_guardado DATE NOT NULL,
                backed_up_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS leads_fecha_backup_cerrado_demo (
                lead_id INT NOT NULL PRIMARY KEY,
                fecha_original DATE NOT NULL,
                backed_up_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        cur.execute(
            """
            INSERT IGNORE INTO seguimientos_backup_cerrado_demo
                (id, lead_id, proceso_id, cotizacion, monto, moneda_id, fecha_guardado)
            SELECT s.id, s.lead_id, s.proceso_id, s.cotizacion, s.monto, s.moneda_id, s.fecha_guardado
            FROM seguimientos s
            JOIN (
                SELECT lead_id, MAX(id) AS last_id FROM seguimientos GROUP BY lead_id
            ) ls ON ls.last_id = s.id
            JOIN proceso p ON p.id = s.proceso_id
            WHERE LOWER(TRIM(p.nombre_proceso)) = 'seguimiento'
            """
        )

        cur.execute("DROP TEMPORARY TABLE IF EXISTS tmp_leads_seguimiento")
        cur.execute(
            """
            CREATE TEMPORARY TABLE tmp_leads_seguimiento AS
            SELECT
                l.id AS lead_id,
                COALESCE(l.asignado_a, 1) AS usuario_id,
                l.fecha AS fecha_lead,
                l.cliente_id,
                l.bien_servicio_id,
                (@rn := @rn + 1) AS rn
            FROM leads l
            CROSS JOIN (SELECT @rn := 0) init
            JOIN (
                SELECT lead_id, MAX(id) AS last_id FROM seguimientos GROUP BY lead_id
            ) ls ON ls.lead_id = l.id
            JOIN seguimientos s ON s.id = ls.last_id
            JOIN proceso p ON p.id = s.proceso_id
            WHERE LOWER(TRIM(p.nombre_proceso)) = 'seguimiento'
            ORDER BY l.id
            """
        )

        cur.execute("SELECT COUNT(*) FROM tmp_leads_seguimiento")
        total = cur.fetchone()[0]
        if total == 0:
            print("No hay leads en Seguimiento para procesar.")
            conn.commit()
            return

        cur.execute(
            """
            INSERT IGNORE INTO leads_fecha_backup_cerrado_demo (lead_id, fecha_original)
            SELECT lead_id, fecha_lead FROM tmp_leads_seguimiento
            """
        )

        cur.execute("DROP TEMPORARY TABLE IF EXISTS tmp_leads_demo")
        cur.execute(
            """
            CREATE TEMPORARY TABLE tmp_leads_demo AS
            SELECT
                t.lead_id,
                t.usuario_id,
                t.cliente_id,
                t.bien_servicio_id,
                CASE MOD(t.lead_id, 3)
                    WHEN 0 THEN DATE(CONCAT('2026-01-', LPAD(LEAST(DAY(t.fecha_lead), 28), 2, '0')))
                    WHEN 1 THEN DATE(CONCAT('2026-02-', LPAD(LEAST(DAY(t.fecha_lead), 28), 2, '0')))
                    ELSE DATE(CONCAT('2026-03-', LPAD(LEAST(DAY(t.fecha_lead), 28), 2, '0')))
                END AS nueva_fecha,
                CONCAT('V', LPAD(260000 + t.rn, 6, '0')) AS cod_cotizacion,
                CASE WHEN MOD(t.rn, 2) = 0 THEN 1 ELSE 2 END AS moneda_id,
                ROUND(500 + (MOD(t.lead_id, 50) * 137.50), 2) AS monto_demo
            FROM tmp_leads_seguimiento t
            """
        )

        cur.execute(
            """
            UPDATE leads l
            JOIN tmp_leads_demo d ON d.lead_id = l.id
            SET l.fecha = d.nueva_fecha
            """
        )
        leads_updated = cur.rowcount

        cur.execute(
            """
            INSERT INTO seguimientos (
                lead_id, usuario_id, fecha_seguimiento, proceso_id,
                cotizacion, monto, moneda_id, comentario, fecha_guardado
            )
            SELECT
                d.lead_id,
                d.usuario_id,
                d.nueva_fecha,
                5,
                d.cod_cotizacion,
                d.monto_demo,
                d.moneda_id,
                'Demo clase: cierre automático',
                d.nueva_fecha
            FROM tmp_leads_demo d
            WHERE NOT EXISTS (
                SELECT 1 FROM seguimientos sx WHERE sx.cotizacion = d.cod_cotizacion
            )
            """
        )
        seg_inserted = cur.rowcount

        cur.execute(
            """
            INSERT INTO ventas_concretadas (cliente_id, lead_id, bien_servicio_id, monto, fecha_venta)
            SELECT
                d.cliente_id,
                d.lead_id,
                d.bien_servicio_id,
                d.monto_demo,
                d.nueva_fecha
            FROM tmp_leads_demo d
            WHERE NOT EXISTS (
                SELECT 1 FROM ventas_concretadas vc WHERE vc.lead_id = d.lead_id
            )
            """
        )
        ventas_inserted = cur.rowcount

        cur.execute(
            """
            INSERT INTO ventas_concretadas (cliente_id, lead_id, bien_servicio_id, monto, fecha_venta)
            SELECT
                d.cliente_id,
                d.lead_id,
                d.bien_servicio_id,
                d.monto_demo,
                d.nueva_fecha
            FROM tmp_leads_demo d
            JOIN (
                SELECT lead_id, MAX(id) AS last_id FROM seguimientos GROUP BY lead_id
            ) ls ON ls.lead_id = d.lead_id
            JOIN seguimientos s ON s.id = ls.last_id AND s.proceso_id = 5
            WHERE EXISTS (
                SELECT 1 FROM ventas_concretadas vc WHERE vc.lead_id = d.lead_id
            )
            AND NOT EXISTS (
                SELECT 1 FROM ventas_concretadas vc
                WHERE vc.lead_id = d.lead_id AND vc.fecha_venta = d.nueva_fecha
            )
            """
        )
        ventas_extra = cur.rowcount

        conn.commit()

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
        cerrados_demo = cur.fetchone()[0]

        cur.execute(
            """
            SELECT COUNT(*) FROM ventas_concretadas
            WHERE fecha_venta BETWEEN '2026-01-01' AND '2026-03-31'
            """
        )
        ventas_demo = cur.fetchone()[0]

        print(f"Leads en seguimiento procesados: {total}")
        print(f"Fechas de leads actualizadas: {leads_updated}")
        print(f"Seguimientos Cerrado insertados: {seg_inserted}")
        print(f"Ventas nuevas insertadas: {ventas_inserted + ventas_extra}")
        print(f"Cerrados visibles ene-mar 2026: {cerrados_demo}")
        print(f"Registros en ventas_concretadas ene-mar 2026: {ventas_demo}")
        print("Respaldo: seguimientos_backup_cerrado_demo, leads_fecha_backup_cerrado_demo")
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
