"""Crea 13 campañas semanales Orbes (Campaña 14-26) ene-mar 2026 con 260 soles y NLC por tabla."""

import os
import sys
from datetime import date, timedelta
from decimal import Decimal

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
import MySQLdb
from MySQLdb.cursors import DictCursor

load_dotenv()

ORBES_NEGOCIO_ID = int(os.getenv("ORBES_NEGOCIO_ID", "1"))
CREATED_BY = 18
INVERSION = Decimal("260.00")

# NLC por Campaña 14..26 (tabla pretest)
NLC_BY_NUM = {
    14: 100,
    15: 102,
    16: 104,
    17: 104,
    18: 110,
    19: 111,
    20: 112,
    21: 112,
    22: 90,
    23: 92,
    24: 94,
    25: 96,
    26: 98,
}

# 13 semanas consecutivas ene-mar 2026 (sin solapamiento)
WEEK_RANGES = [
    (date(2026, 1, 1), date(2026, 1, 7)),
    (date(2026, 1, 8), date(2026, 1, 14)),
    (date(2026, 1, 15), date(2026, 1, 21)),
    (date(2026, 1, 22), date(2026, 1, 28)),
    (date(2026, 1, 29), date(2026, 2, 4)),
    (date(2026, 2, 5), date(2026, 2, 11)),
    (date(2026, 2, 12), date(2026, 2, 18)),
    (date(2026, 2, 19), date(2026, 2, 25)),
    (date(2026, 2, 26), date(2026, 3, 4)),
    (date(2026, 3, 5), date(2026, 3, 11)),
    (date(2026, 3, 12), date(2026, 3, 18)),
    (date(2026, 3, 19), date(2026, 3, 25)),
    (date(2026, 3, 26), date(2026, 3, 31)),
]

PRODUCTS = [
    {
        "linea_negocio": "Equipos Fuerzas",
        "linea_familia": "MOTOCULTORES Y MOTOSEGADORAS",
        "linea_producto": "MOTOCULTIVADOR",
        "producto": "Motocultor Orbes",
        "bien_servicio_id": 4,
    },
    {
        "linea_negocio": "Proyecto de riego",
        "linea_familia": "RIEGO POR GOTEO",
        "linea_producto": "CINTA DE GOTEO",
        "producto": "Cinta de riego por goteo",
        "bien_servicio_id": 5,
    },
    {
        "linea_negocio": "Equipos Menores",
        "linea_familia": "EQUIPOS DE PULVERIZACION",
        "linea_producto": "PULVERIZADORES",
        "producto": "Pulverizador de mochila",
        "bien_servicio_id": 3,
    },
    {
        "linea_negocio": "Maquinaria Agricola",
        "linea_familia": "TRACTORES AGRICOLAS",
        "linea_producto": "TRACTORES",
        "producto": "Tractor Lovol",
        "bien_servicio_id": 1,
    },
    {
        "linea_negocio": "Equipos Fuerzas",
        "linea_familia": "MOTOBOMBAS Y ELECTROBOMBAS",
        "linea_producto": "MOTOBOMBAS",
        "producto": "Motobomba agricola",
        "bien_servicio_id": 4,
    },
    {
        "linea_negocio": "Plasticos Agricolas",
        "linea_familia": "MALLAS Y AGROFILMS",
        "linea_producto": "AGROFILMS",
        "producto": "Agrofilm termico",
        "bien_servicio_id": 7,
    },
    {
        "linea_negocio": "Proyecto de riego",
        "linea_familia": "RIEGO POR ASPERSION",
        "linea_producto": "ASPERSORES",
        "producto": "Aspersor agricola",
        "bien_servicio_id": 5,
    },
    {
        "linea_negocio": "Equipos Menores",
        "linea_familia": "EQUIPO DE JARDINERIA Y FORESTALES",
        "linea_producto": "MOTOSIERRAS",
        "producto": "Motosierra Movicam",
        "bien_servicio_id": 3,
    },
    {
        "linea_negocio": "Maquinaria Agricola",
        "linea_familia": "IMPLEMENTOS AGRICOLAS",
        "linea_producto": "ARADO DE DISCOS",
        "producto": "Arado de discos",
        "bien_servicio_id": 1,
    },
    {
        "linea_negocio": "Equipos Fuerzas",
        "linea_familia": "MOTOCULTORES Y MOTOSEGADORAS",
        "linea_producto": "MOTOSEGADORAS",
        "producto": "Motosegadora",
        "bien_servicio_id": 4,
    },
    {
        "linea_negocio": "Proyecto de riego",
        "linea_familia": "COMPLEMENTO DE RIEGO",
        "linea_producto": "FILTROS",
        "producto": "Filtro de riego",
        "bien_servicio_id": 5,
    },
    {
        "linea_negocio": "Equipos Menores",
        "linea_familia": "EQUIPOS DE PULVERIZACION",
        "linea_producto": "ATOMIZADORES",
        "producto": "Atomizador agricola",
        "bien_servicio_id": 3,
    },
    {
        "linea_negocio": "Plasticos Agricolas",
        "linea_familia": "MALLAS Y AGROFILMS",
        "linea_producto": "MALLAS",
        "producto": "Malla sombra",
        "bien_servicio_id": 7,
    },
]

OLD_CAMPAIGN_IDS = (12, 13, 14, 15, 16, 17)


def _connect():
    return MySQLdb.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        user=os.getenv("MYSQL_USER", "root"),
        passwd=os.getenv("MYSQL_PASSWORD", "123456"),
        db=os.getenv("MYSQL_DB", "u349183440_crm_orbes"),
        port=int(os.getenv("MYSQL_PORT", "3307")),
    )


def _pick_leads(cur, start, end, limit, exclude_ids):
    params = [ORBES_NEGOCIO_ID, start, end]
    exclude_sql = ""
    if exclude_ids:
        placeholders = ",".join(["%s"] * len(exclude_ids))
        exclude_sql = f" AND l.id NOT IN ({placeholders})"
        params.extend(exclude_ids)
    params.append(limit)

    cur.execute(
        f"""
        SELECT l.id
        FROM leads l
        INNER JOIN usuarios ua ON ua.id = l.asignado_a
        LEFT JOIN marketing_campaign_leads mcl ON mcl.lead_id = l.id
        WHERE ua.negocio_id = %s
          AND l.fecha BETWEEN %s AND %s
          AND mcl.lead_id IS NULL
          {exclude_sql}
        ORDER BY l.fecha ASC, l.id ASC
        LIMIT %s
        """,
        tuple(params),
    )
    rows = cur.fetchall() or []
    return [r["id"] for r in rows]


def _pick_leads_spillover(cur, start, end, limit, exclude_ids):
    lead_ids = _pick_leads(cur, start, end, limit, exclude_ids)
    if len(lead_ids) >= limit:
        return lead_ids[:limit]

    needed = limit - len(lead_ids)
    used = set(exclude_ids) | set(lead_ids)
    window_start = start - timedelta(days=14)
    window_end = end + timedelta(days=14)
    params = [ORBES_NEGOCIO_ID, window_start, window_end, start]
    exclude = list(used)
    exclude_sql = ""
    if exclude:
        placeholders = ",".join(["%s"] * len(exclude))
        exclude_sql = f" AND l.id NOT IN ({placeholders})"
        params.extend(exclude)
    params.append(needed)
    cur.execute(
        f"""
        SELECT l.id
        FROM leads l
        INNER JOIN usuarios ua ON ua.id = l.asignado_a
        LEFT JOIN marketing_campaign_leads mcl ON mcl.lead_id = l.id
        WHERE ua.negocio_id = %s
          AND l.fecha BETWEEN %s AND %s
          AND mcl.lead_id IS NULL
          {exclude_sql}
        ORDER BY ABS(DATEDIFF(l.fecha, %s)) ASC, l.id ASC
        LIMIT %s
        """,
        tuple(params),
    )
    lead_ids.extend(r["id"] for r in (cur.fetchall() or []))
    return lead_ids[:limit]


def main():
    conn = _connect()
    cur = conn.cursor(DictCursor)
    linked_global = []

    try:
        placeholders = ",".join(["%s"] * len(OLD_CAMPAIGN_IDS))
        cur.execute(
            f"DELETE FROM marketing_campaign_leads WHERE campaign_id IN ({placeholders})",
            OLD_CAMPAIGN_IDS,
        )
        deleted_links = cur.rowcount
        cur.execute(
            f"DELETE FROM marketing_campaigns WHERE id IN ({placeholders})",
            OLD_CAMPAIGN_IDS,
        )
        deleted_campaigns = cur.rowcount

        created = []
        for idx, (start, end) in enumerate(WEEK_RANGES):
            num = 14 + idx
            nlc = NLC_BY_NUM[num]
            prod = PRODUCTS[idx]
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

            lead_ids = _pick_leads_spillover(cur, start, end, nlc, linked_global)
            if len(lead_ids) < nlc:
                raise RuntimeError(
                    f"{nombre}: solo {len(lead_ids)} leads disponibles, se requieren {nlc}"
                )

            for lead_id in lead_ids:
                cur.execute(
                    """
                    INSERT INTO marketing_campaign_leads
                    (campaign_id, lead_id, fecha_atribucion, metodo_atribucion, created_by, created_at)
                    VALUES (%s, %s, %s, 'periodo_automatico', %s, NOW())
                    """,
                    (campaign_id, lead_id, start, CREATED_BY),
                )

            cur.execute(
                """
                UPDATE leads
                SET bien_servicio_id = %s
                WHERE id IN ({})
                """.format(",".join(["%s"] * len(lead_ids))),
                (prod["bien_servicio_id"], *lead_ids),
            )

            linked_global.extend(lead_ids)
            created.append(
                {
                    "id": campaign_id,
                    "nombre": nombre,
                    "periodo": f"{start}..{end}",
                    "nlc": nlc,
                    "linked": len(lead_ids),
                    "cpl": round(float(INVERSION) / nlc, 2),
                    "producto": prod["producto"],
                }
            )

        conn.commit()
        print(f"Eliminadas {deleted_campaigns} campanas antiguas (ids {OLD_CAMPAIGN_IDS}).")
        print(f"Desvinculados {deleted_links} leads de campanas anteriores.")
        print(f"Creadas {len(created)} campanas Orbes ene-mar 2026:\n")
        for row in created:
            print(
                f"  id={row['id']} {row['nombre']} | {row['periodo']} | "
                f"leads={row['linked']}/{row['nlc']} | CPL=S/ {row['cpl']} | {row['producto']}"
            )
        print(f"\nTotal leads vinculados: {sum(r['linked'] for r in created)}")
        print(f"Inversion total: S/ {float(INVERSION) * len(created):.2f}")
    except Exception:
        conn.rollback()
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
