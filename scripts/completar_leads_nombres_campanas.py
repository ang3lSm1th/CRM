"""
1) Completa nombres vacíos en leads (ene..to).
2) Crea campañas semanales Orbes faltantes hasta --to.
3) Vincula leads sin campaña al periodo correspondiente.
"""

from __future__ import annotations

import argparse
import os
import random
import sys
from datetime import date, timedelta
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
import MySQLdb
from MySQLdb.cursors import DictCursor

load_dotenv()

ORBES_NEGOCIO_ID = int(os.getenv("ORBES_NEGOCIO_ID", "1"))
CREATED_BY = int(os.getenv("LEAD_SEED_USER_ID", "18"))
INVERSION = Decimal("260.00")

NOMBRES = [
    "José", "María", "Carlos", "Ana", "Luis", "Rosa", "Miguel", "Carmen",
    "Pedro", "Lucía", "Jorge", "Elena", "Ricardo", "Patricia", "Andrés",
    "Sofía", "Fernando", "Gloria", "Manuel", "Teresa", "Roberto", "Isabel",
    "Héctor", "Diana", "Álvaro", "Pilar", "Raúl", "Mónica", "César", "Silvia",
    "Óscar", "Verónica", "Felipe", "Adriana", "Guillermo", "Beatriz",
    "Martín", "Claudia", "Eduardo", "Angélica", "Sergio", "Liliana",
    "Iván", "Paola", "Daniel", "Karina", "Ángel", "Nancy", "Víctor", "Evelyn",
]
APELLIDOS = [
    "Quispe", "Huamán", "Mamani", "Condori", "Flores", "García", "Rodríguez",
    "López", "Pérez", "Sánchez", "Ramírez", "Torres", "Flores", "Díaz",
    "Vargas", "Castillo", "Rojas", "Espinoza", "Mendoza", "Silva", "Cruz",
    "Reyes", "Morales", "Ortiz", "Gutiérrez", "Chávez", "Ramos", "Romero",
    "Aguilar", "Navarro", "Castro", "Medina", "Herrera", "Soto", "Paredes",
    "Salazar", "Vega", "Campos", "Delgado", "Cabrera", "Valencia", "Ponce",
    "Arce", "León", "Bautista", "Cordero", "Palomino", "Yupanqui", "Ccama",
]
EMPRESAS = [
    "Agroindustrias", "Agrícola", "Inversiones", "Servicios", "Comercial",
    "Productores", "Cultivos", "Campo Verde", "Valle Andino", "Sierra Norte",
]

PRODUCTS = [
    {"linea_negocio": "Equipos Fuerzas", "linea_familia": "MOTOCULTORES Y MOTOSEGADORAS",
     "linea_producto": "MOTOCULTIVADOR", "producto": "Motocultor Orbes", "bien_servicio_id": 4},
    {"linea_negocio": "Proyecto de riego", "linea_familia": "RIEGO POR GOTEO",
     "linea_producto": "CINTA DE GOTEO", "producto": "Cinta de riego por goteo", "bien_servicio_id": 5},
    {"linea_negocio": "Equipos Menores", "linea_familia": "EQUIPOS DE PULVERIZACION",
     "linea_producto": "PULVERIZADORES", "producto": "Pulverizador de mochila", "bien_servicio_id": 3},
    {"linea_negocio": "Maquinaria Agricola", "linea_familia": "TRACTORES AGRICOLAS",
     "linea_producto": "TRACTORES", "producto": "Tractor Lovol", "bien_servicio_id": 1},
    {"linea_negocio": "Equipos Fuerzas", "linea_familia": "MOTOBOMBAS Y ELECTROBOMBAS",
     "linea_producto": "MOTOBOMBAS", "producto": "Motobomba agricola", "bien_servicio_id": 4},
    {"linea_negocio": "Plasticos Agricolas", "linea_familia": "MALLAS Y AGROFILMS",
     "linea_producto": "AGROFILMS", "producto": "Agrofilm termico", "bien_servicio_id": 7},
]


def connect():
    return MySQLdb.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        user=os.getenv("MYSQL_USER", "root"),
        passwd=os.getenv("MYSQL_PASSWORD", "123456"),
        db=os.getenv("MYSQL_DB", "u349183440_crm_orbes"),
        port=int(os.getenv("MYSQL_PORT", "3307")),
        charset="utf8mb4",
    )


def week_ranges(start: date, end: date):
    """Semanas lun-dom (o resto) desde start hasta end inclusive."""
    # Alinear al lunes de la semana de start
    d = start - timedelta(days=start.weekday())
    ranges = []
    while d <= end:
        w_end = d + timedelta(days=6)
        r_start = max(d, start)
        r_end = min(w_end, end)
        if r_start <= r_end:
            ranges.append((r_start, r_end))
        d = w_end + timedelta(days=1)
    return ranges


def make_person_name(rng: random.Random) -> str:
    return f"{rng.choice(NOMBRES)} {rng.choice(APELLIDOS)} {rng.choice(APELLIDOS)}"


def make_company_name(rng: random.Random) -> str:
    return f"{rng.choice(EMPRESAS)} {rng.choice(APELLIDOS)} SAC"


def fill_names(cur, date_from: date, date_to: date, rng: random.Random) -> int:
    cur.execute(
        """
        SELECT id, ruc_dni, telefono, nombre
        FROM leads
        WHERE fecha BETWEEN %s AND %s
          AND (
            nombre IS NULL OR TRIM(nombre) = ''
            OR LOWER(TRIM(nombre)) IN ('cliente', 'sin nombre', 'cliente sin nombre')
          )
        ORDER BY id
        """,
        (date_from, date_to),
    )
    leads = list(cur.fetchall() or [])
    if not leads:
        return 0

    # Mapas de clientes
    cur.execute(
        """
        SELECT ruc_dni, telefono, nombre
        FROM clientes
        WHERE nombre IS NOT NULL AND TRIM(nombre) <> ''
        """
    )
    by_ruc = {}
    by_tel = {}
    for c in cur.fetchall() or []:
        nombre = (c.get("nombre") or "").strip()
        if not nombre:
            continue
        ruc = (c.get("ruc_dni") or "").strip()
        tel = (c.get("telefono") or "").strip()
        if ruc and ruc not in by_ruc:
            by_ruc[ruc] = nombre
        if tel and tel not in by_tel:
            by_tel[tel] = nombre

    updated = 0
    for lead in leads:
        ruc = (lead.get("ruc_dni") or "").strip()
        tel = (lead.get("telefono") or "").strip()
        nombre = by_ruc.get(ruc) or by_tel.get(tel)
        if not nombre:
            # RUC de 11 dígitos ≈ empresa
            if len(ruc) >= 11:
                nombre = make_company_name(rng)
            else:
                nombre = make_person_name(rng)
        nombre = nombre[:120]
        cur.execute(
            "UPDATE leads SET nombre = %s, contacto = COALESCE(NULLIF(TRIM(contacto), ''), %s) WHERE id = %s",
            (nombre, nombre, lead["id"]),
        )
        updated += 1
    return updated


def next_campaign_number(cur) -> int:
    cur.execute(
        """
        SELECT nombre_campana FROM marketing_campaigns
        WHERE nombre_campana LIKE 'Campaña %%' OR nombre_campana LIKE 'Campana %%'
        """
    )
    nums = []
    for row in cur.fetchall() or []:
        digits = "".join(ch for ch in (row.get("nombre_campana") or "") if ch.isdigit())
        if digits:
            nums.append(int(digits))
    return (max(nums) + 1) if nums else 14


def ensure_weekly_campaigns(cur, date_from: date, date_to: date) -> list:
    """Crea campañas semanales Orbes faltantes en el rango (no toca las ya existentes)."""
    cur.execute(
        """
        SELECT id, nombre_campana, periodo_inicio, periodo_fin, bien_servicio_id
        FROM marketing_campaigns
        WHERE periodo_inicio IS NOT NULL AND periodo_fin IS NOT NULL
          AND (nombre_campana LIKE 'Campaña %%' OR nombre_campana LIKE 'Campana %%')
        ORDER BY periodo_inicio
        """
    )
    existing = list(cur.fetchall() or [])

    def covered(day: date) -> bool:
        for c in existing:
            if c["periodo_inicio"] <= day <= c["periodo_fin"]:
                return True
        return False

    ranges = week_ranges(date_from, date_to)
    # Solo crear semanas que no estén ya cubiertas por alguna campaña Orbes
    to_create = []
    for start, end in ranges:
        # Si la mayoría de días ya están cubiertos, skip
        days = (end - start).days + 1
        covered_days = sum(1 for i in range(days) if covered(start + timedelta(days=i)))
        if covered_days >= days:
            continue
        to_create.append((start, end))

    next_num = next_campaign_number(cur)
    created = []
    for idx, (start, end) in enumerate(to_create):
        num = next_num + idx
        prod = PRODUCTS[idx % len(PRODUCTS)]
        nombre = f"Campaña {num}"
        cur.execute(
            """
            INSERT INTO marketing_campaigns (
                nombre_campana, fecha_lanzamiento, periodo_inicio, periodo_fin,
                linea_negocio, linea_familia, linea_producto, producto,
                canal, bien_servicio_id, inversion, activo, created_by,
                brand, negocio_id
            ) VALUES (
                %s, %s, %s, %s,
                %s, %s, %s, %s,
                'meta', %s, %s, 1, %s,
                'orbes', %s
            )
            """,
            (
                nombre,
                start,
                start,
                end,
                prod["linea_negocio"],
                prod["linea_familia"],
                prod["linea_producto"],
                prod["producto"],
                prod["bien_servicio_id"],
                INVERSION,
                CREATED_BY,
                ORBES_NEGOCIO_ID,
            ),
        )
        campaign_id = cur.lastrowid
        created.append(
            {
                "id": campaign_id,
                "nombre": nombre,
                "periodo_inicio": start,
                "periodo_fin": end,
                "bien_servicio_id": prod["bien_servicio_id"],
            }
        )
        existing.append(
            {
                "id": campaign_id,
                "nombre_campana": nombre,
                "periodo_inicio": start,
                "periodo_fin": end,
                "bien_servicio_id": prod["bien_servicio_id"],
            }
        )
    return created


def link_leads_to_campaigns(cur, date_from: date, date_to: date) -> int:
    cur.execute(
        """
        SELECT id, periodo_inicio, periodo_fin, bien_servicio_id, nombre_campana
        FROM marketing_campaigns
        WHERE periodo_inicio IS NOT NULL AND periodo_fin IS NOT NULL
          AND periodo_fin >= %s AND periodo_inicio <= %s
          AND (nombre_campana LIKE 'Campaña %%' OR nombre_campana LIKE 'Campana %%')
        ORDER BY periodo_inicio
        """,
        (date_from, date_to),
    )
    camps = list(cur.fetchall() or [])
    if not camps:
        return 0

    cur.execute(
        """
        SELECT l.id, l.fecha, l.bien_servicio_id
        FROM leads l
        LEFT JOIN marketing_campaign_leads mcl ON mcl.lead_id = l.id
        WHERE l.fecha BETWEEN %s AND %s
          AND mcl.lead_id IS NULL
        ORDER BY l.fecha ASC, l.id ASC
        """,
        (date_from, date_to),
    )
    leads = list(cur.fetchall() or [])
    linked = 0

    for lead in leads:
        day = lead["fecha"]
        if hasattr(day, "date"):
            day = day.date()
        match = None
        for c in camps:
            if c["periodo_inicio"] <= day <= c["periodo_fin"]:
                match = c
                break
        if not match:
            # campaña Orbes más cercana
            match = min(
                camps,
                key=lambda c: min(
                    abs((day - c["periodo_inicio"]).days),
                    abs((day - c["periodo_fin"]).days),
                ),
            )
        cur.execute(
            """
            INSERT INTO marketing_campaign_leads
            (campaign_id, lead_id, fecha_atribucion, metodo_atribucion, created_by, created_at)
            VALUES (%s, %s, %s, 'periodo_automatico', %s, NOW())
            """,
            (match["id"], lead["id"], day, CREATED_BY),
        )
        bien = match.get("bien_servicio_id")
        if bien and not lead.get("bien_servicio_id"):
            cur.execute(
                "UPDATE leads SET bien_servicio_id = %s WHERE id = %s",
                (bien, lead["id"]),
            )
        linked += 1
    return linked


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--from", dest="date_from", default="2026-01-01")
    parser.add_argument("--to", dest="date_to", default="2026-07-11")
    parser.add_argument("--seed", type=int, default=20260711)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    date_from = date.fromisoformat(args.date_from)
    date_to = date.fromisoformat(args.date_to)
    rng = random.Random(args.seed)

    conn = connect()
    cur = conn.cursor(DictCursor)
    try:
        named = fill_names(cur, date_from, date_to, rng)
        print(f"Nombres asignados: {named}")

        created = ensure_weekly_campaigns(cur, date_from, date_to)
        print(f"Campañas creadas: {len(created)}")
        for c in created:
            print(f"  {c['nombre']} {c['periodo_inicio']}..{c['periodo_fin']} id={c['id']}")

        linked = link_leads_to_campaigns(cur, date_from, date_to)
        print(f"Leads vinculados a campañas: {linked}")

        if args.dry_run:
            conn.rollback()
            print("(dry-run, rollback)")
        else:
            conn.commit()
            print("OK commit")

        # Resumen
        cur.execute(
            """
            SELECT c.nombre_campana, c.periodo_inicio, c.periodo_fin, COUNT(mcl.lead_id) n
            FROM marketing_campaigns c
            LEFT JOIN marketing_campaign_leads mcl ON mcl.campaign_id = c.id
            WHERE c.nombre_campana LIKE 'Campaña %%' OR c.nombre_campana LIKE 'Campana %%'
            GROUP BY c.id
            ORDER BY c.periodo_inicio
            """
        )
        print("Resumen campañas Orbes:")
        for r in cur.fetchall() or []:
            print(
                f"  {r['nombre_campana']} | {r['periodo_inicio']}..{r['periodo_fin']} | NLC={r['n']}"
            )

        cur.execute(
            """
            SELECT COUNT(*) n FROM leads
            WHERE fecha BETWEEN %s AND %s
              AND (nombre IS NULL OR TRIM(nombre)='')
            """,
            (date_from, date_to),
        )
        print("Leads aún sin nombre:", cur.fetchone()["n"])

        cur.execute("SELECT MIN(fecha) mn, MAX(fecha) mx, COUNT(*) n FROM leads WHERE fecha BETWEEN %s AND %s", (date_from, date_to))
        print("Leads en rango:", cur.fetchone())
        return 0
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
