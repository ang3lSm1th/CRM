"""Elimina leads de prueba (Prospecto Agro/Mayo, DEMO*, @demo.local)."""

import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
import MySQLdb
from MySQLdb.cursors import DictCursor

load_dotenv()

DEMO_WHERE = """
    nombre LIKE 'Prospecto Agro%%'
    OR nombre LIKE 'Prospecto Mayo%%'
    OR ruc_dni LIKE 'DEMO%%'
    OR email LIKE '%%@demo.local'
"""

# Orden: tablas hijas antes que leads (ventas_concretadas bloquea el DELETE)
CHILD_TABLES = (
    "ventas_concretadas",
    "marketing_campaign_leads",
    "lead_tractor_guardados",
    "notificaciones_venta",
    "lead_agent_state",
    "agent_interactions",
    "agent_predictions",
    "lead_cambios",
    "leads_fecha_backup_demo",
    "leads_fecha_backup_cerrado_demo",
    "seguimientos",
)


def connect():
    return MySQLdb.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        user=os.getenv("MYSQL_USER", "root"),
        passwd=os.getenv("MYSQL_PASSWORD", "123456"),
        db=os.getenv("MYSQL_DB", "u349183440_crm_orbes"),
        port=int(os.getenv("MYSQL_PORT", "3307")),
        charset="utf8mb4",
    )


def _delete_children(cur, ids):
    placeholders = ",".join(["%s"] * len(ids))
    deleted = {}
    for table in CHILD_TABLES:
        try:
            cur.execute(
                f"DELETE FROM {table} WHERE lead_id IN ({placeholders})",
                ids,
            )
            if cur.rowcount:
                deleted[table] = cur.rowcount
        except MySQLdb.ProgrammingError:
            pass
    return deleted


def main():
    parser = argparse.ArgumentParser(description="Elimina leads demo de la BD")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    conn = connect()
    cur = conn.cursor(DictCursor)
    try:
        cur.execute(f"SELECT id, codigo, nombre, fecha FROM leads WHERE {DEMO_WHERE}")
        rows = cur.fetchall() or []
        if not rows:
            print("No hay leads demo.")
            return 0

        print(f"Leads demo encontrados: {len(rows)}")
        for row in rows[:10]:
            print(f"  {row['codigo']} | {row['fecha']} | {row['nombre']}")
        if len(rows) > 10:
            print(f"  ... y {len(rows) - 10} más")

        if args.dry_run:
            print("(dry-run, no se eliminó nada)")
            return 0

        ids = [int(r["id"]) for r in rows]
        placeholders = ",".join(["%s"] * len(ids))

        removed = _delete_children(cur, ids)
        if removed:
            print("Registros hijos eliminados:")
            for table, count in removed.items():
                print(f"  {table}: {count}")

        cur.execute(f"DELETE FROM leads WHERE id IN ({placeholders})", ids)
        conn.commit()
        print(f"Eliminados: {len(ids)} leads demo")
        return 0
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
