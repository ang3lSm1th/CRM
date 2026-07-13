"""Asigna productos del inventario a leads ya cotizados (sin detalle).

Usa el bien_servicio del lead para elegir 1–2 SKUs oficiales.
No inventa precios: toma inventario_productos.

Uso:
  python scripts/asignar_inventario_leads_cotizados.py
  python scripts/asignar_inventario_leads_cotizados.py --limit 500
"""

from __future__ import annotations

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env", override=True)

import MySQLdb
from MySQLdb.cursors import DictCursor


def connect():
    return MySQLdb.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        user=os.getenv("MYSQL_USER", "root"),
        passwd=os.getenv("MYSQL_PASSWORD", ""),
        db=os.getenv("MYSQL_DB") or os.getenv("DB_NAME"),
        port=int(os.getenv("MYSQL_PORT") or os.getenv("DB_PORT") or 3306),
        charset="utf8mb4",
        cursorclass=DictCursor,
    )


def ensure_tables(cur):
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS cotizacion_items (
          id INT AUTO_INCREMENT PRIMARY KEY,
          lead_id INT NOT NULL,
          seguimiento_id INT NULL,
          producto_id INT NULL,
          codigo VARCHAR(40) NOT NULL,
          descripcion VARCHAR(255) NOT NULL,
          unidad VARCHAR(20) NOT NULL DEFAULT 'UND',
          cantidad DECIMAL(12,2) NOT NULL DEFAULT 1.00,
          precio_unitario DECIMAL(12,2) NOT NULL DEFAULT 0.00,
          total DECIMAL(12,2) NOT NULL DEFAULT 0.00,
          created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
          KEY idx_ci_lead (lead_id),
          KEY idx_ci_seg (seguimiento_id),
          KEY idx_ci_prod (producto_id)
        ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
        """
    )


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=0, help="Máximo de leads a procesar (0=todos)")
    args = parser.parse_args()

    conn = connect()
    cur = conn.cursor()
    try:
        ensure_tables(cur)
        conn.commit()

        cur.execute(
            """
            SELECT p.id
            FROM inventario_productos p
            WHERE p.activo = 1
            ORDER BY p.bien_servicio_id, p.descripcion
            """
        )
        # reload products with details
        cur.execute(
            """
            SELECT id, codigo, descripcion, unidad, bien_servicio_id, precio_unitario, stock
            FROM inventario_productos
            WHERE activo = 1
            ORDER BY bien_servicio_id, descripcion
            """
        )
        products = cur.fetchall() or []
        by_bien: dict[int, list] = {}
        for p in products:
            by_bien.setdefault(int(p["bien_servicio_id"]), []).append(p)

        # Leads cuyo último seguimiento es Cotizado y aún no tienen cotizacion_items
        sql = """
            SELECT l.id AS lead_id, l.bien_servicio_id, su.id AS seguimiento_id, su.monto
            FROM leads l
            INNER JOIN (
              SELECT s1.lead_id, s1.id, s1.proceso_id, s1.monto
              FROM seguimientos s1
              INNER JOIN (
                SELECT lead_id, MAX(id) AS max_id
                FROM seguimientos
                GROUP BY lead_id
              ) t ON t.lead_id = s1.lead_id AND t.max_id = s1.id
            ) su ON su.lead_id = l.id
            INNER JOIN proceso pr ON pr.id = su.proceso_id
            WHERE LOWER(TRIM(pr.nombre_proceso)) = 'cotizado'
              AND NOT EXISTS (
                SELECT 1 FROM cotizacion_items ci WHERE ci.lead_id = l.id
              )
            ORDER BY l.id
        """
        if args.limit and args.limit > 0:
            sql += f" LIMIT {int(args.limit)}"
        cur.execute(sql)
        leads = cur.fetchall() or []

        assigned = 0
        for row in leads:
            lid = int(row["lead_id"])
            sid = row.get("seguimiento_id")
            bien = int(row.get("bien_servicio_id") or 0)
            candidates = by_bien.get(bien) or products[:2]
            pick = candidates[:2]
            if not pick:
                continue
            for p in pick:
                precio = float(p.get("precio_unitario") or 0)
                cant = 1
                total = round(precio * cant, 2)
                cur.execute(
                    """
                    INSERT INTO cotizacion_items (
                      lead_id, seguimiento_id, producto_id, codigo, descripcion,
                      unidad, cantidad, precio_unitario, total
                    ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                    """,
                    (
                        lid,
                        sid,
                        p.get("id"),
                        p.get("codigo"),
                        p.get("descripcion"),
                        p.get("unidad") or "UND",
                        cant,
                        precio,
                        total,
                    ),
                )
            # Si el seguimiento no tiene monto, actualizarlo
            if row.get("monto") in (None, 0, 0.0):
                monto = round(sum(float(p.get("precio_unitario") or 0) for p in pick), 2)
                cur.execute("UPDATE seguimientos SET monto=%s WHERE id=%s", (monto, sid))
            assigned += 1

        conn.commit()
        print(f"OK: productos asignados a {assigned} leads cotizados")
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
