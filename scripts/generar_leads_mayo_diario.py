"""
Genera leads diarios desde el 1 de mayo hasta hoy con distintos procesos.
Usa clientes existentes (reciclados) y contactos nuevos sin campaña.
"""

import argparse
import os
import random
import sys
from datetime import date, timedelta

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dotenv import load_dotenv
import MySQLdb
from MySQLdb.cursors import DictCursor

load_dotenv()

ORBES_NEGOCIO_ID = int(os.getenv("ORBES_NEGOCIO_ID", "1"))
CREATED_BY = int(os.getenv("LEAD_SEED_USER_ID", "18"))
DEFAULT_START = date(2026, 5, 1)

PROCESO = {
    "no iniciado": 1,
    "seguimiento": 2,
    "programado": 3,
    "cotizado": 4,
    "cerrado": 5,
    "cerrado no vendido": 6,
}

# Mezcla diaria de procesos (nombre -> cantidad por cada 10 leads base)
DAILY_PATTERNS = [
    [("seguimiento", 3), ("cotizado", 2), ("cerrado", 2), ("programado", 1), ("no iniciado", 1), ("cerrado no vendido", 1)],
    [("seguimiento", 2), ("cotizado", 3), ("cerrado", 1), ("programado", 2), ("no iniciado", 1), ("cerrado no vendido", 1)],
    [("seguimiento", 4), ("cotizado", 1), ("cerrado", 2), ("programado", 1), ("no iniciado", 1), ("cerrado no vendido", 1)],
    [("seguimiento", 2), ("cotizado", 2), ("cerrado", 3), ("programado", 1), ("no iniciado", 1), ("cerrado no vendido", 1)],
    [("seguimiento", 3), ("cotizado", 2), ("cerrado", 1), ("programado", 2), ("no iniciado", 1), ("cerrado no vendido", 1)],
]

CANALES = [1, 2, 3, 4, 5]
BIENES = [1, 3, 4, 5, 7]


def connect():
    return MySQLdb.connect(
        host=os.getenv("MYSQL_HOST", "localhost"),
        user=os.getenv("MYSQL_USER", "root"),
        passwd=os.getenv("MYSQL_PASSWORD", "123456"),
        db=os.getenv("MYSQL_DB", "u349183440_crm_orbes"),
        port=int(os.getenv("MYSQL_PORT", "3307")),
        charset="utf8mb4",
    )


def daterange(start, end):
    d = start
    while d <= end:
        yield d
        d += timedelta(days=1)


def leads_per_day(day):
    if day.weekday() >= 5:
        return random.randint(5, 8)
    return random.randint(9, 14)


def next_codigo(cur, counter):
    if counter["n"] is None:
        cur.execute("SELECT codigo FROM leads ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
        if row and row.get("codigo", "").startswith("LED-"):
            try:
                counter["n"] = int(row["codigo"].split("-")[1])
            except ValueError:
                counter["n"] = 0
        else:
            counter["n"] = 0
    counter["n"] += 1
    return f"LED-{counter['n']:04d}"


def fetch_pools(cur):
    cur.execute(
        """
        SELECT id, ruc_dni, nombre, telefono, email, contacto,
               direccion, departamento, provincia, distrito
        FROM clientes
        WHERE ruc_dni IS NOT NULL AND TRIM(ruc_dni) <> ''
        ORDER BY id
        """
    )
    clientes = cur.fetchall() or []

    cur.execute(
        """
        SELECT u.id
        FROM usuarios u
        JOIN roles r ON r.id = u.id_rol
        WHERE LOWER(r.nombre) IN ('asesor', 'gerente')
          AND u.negocio_id = %s
        ORDER BY u.id
        """,
        (ORBES_NEGOCIO_ID,),
    )
    asesores = [r["id"] for r in (cur.fetchall() or [])] or [CREATED_BY]

    cur.execute(
        """
        SELECT id, bien_servicio_id, periodo_inicio, periodo_fin
        FROM marketing_campaigns
        WHERE activo = 1
        """
    )
    campanas = cur.fetchall() or []

    cur.execute("SELECT id FROM motivo_no_venta ORDER BY id LIMIT 1")
    motivo_row = cur.fetchone()
    motivo_default = int(motivo_row["id"]) if motivo_row else 8

    return clientes, asesores, campanas, motivo_default


def pick_campana(campanas, day, bien_servicio_id):
    for c in campanas:
        if c["periodo_inicio"] <= day <= c["periodo_fin"]:
            if not c.get("bien_servicio_id") or c["bien_servicio_id"] == bien_servicio_id:
                return c["id"]
    return None


def build_proceso_queue(pattern, total):
    queue = []
    for name, qty in pattern:
        queue.extend([name] * qty)
    random.shuffle(queue)
    while len(queue) < total:
        queue.append(random.choice(["seguimiento", "cotizado", "seguimiento"]))
    return queue[:total]


def insert_lead_bundle(cur, payload, seq):
    cur.execute(
        """
        INSERT INTO leads
        (codigo, fecha, telefono, ruc_dni, nombre, canal_id, contacto,
         departamento, provincia, distrito, direccion, email,
         bien_servicio_id, asignado_a, comentario, feria_id)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,NULL)
        """,
        (
            payload["codigo"],
            payload["fecha"],
            payload["telefono"],
            payload["ruc_dni"],
            payload["nombre"],
            payload["canal_id"],
            payload["contacto"],
            payload["departamento"],
            payload["provincia"],
            payload["distrito"],
            payload["direccion"],
            payload["email"],
            payload["bien_servicio_id"],
            payload["asignado_a"],
            payload["comentario"],
        ),
    )
    lead_id = cur.lastrowid
    proceso = payload["proceso"]
    proc_id = PROCESO[proceso]
    day = payload["fecha"]
    monto = round(480 + (seq % 47) * 125.5, 2)
    cotizacion = f"V{day.strftime('%y%m%d')}{seq:03d}"
    moneda_id = 1 if seq % 2 == 0 else 2

    fecha_prog = None
    motivo_id = None
    cot = None
    monto_val = None
    moneda_val = None

    if proceso == "programado":
        fecha_prog = day + timedelta(days=random.randint(1, 5))
    elif proceso in ("cotizado", "cerrado"):
        cot = cotizacion
        monto_val = monto
        moneda_val = moneda_id
    elif proceso == "cerrado no vendido":
        cot = cotizacion
        monto_val = monto
        moneda_val = moneda_id
        motivo_id = payload["motivo_id"]

    cur.execute(
        """
        INSERT INTO seguimientos
        (lead_id, usuario_id, fecha_seguimiento, proceso_id, fecha_programada,
         motivo_no_venta_id, cotizacion, monto, moneda_id, comentario, fecha_guardado)
        VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s,%s,%s)
        """,
        (
            lead_id,
            payload["asignado_a"],
            day,
            proc_id,
            fecha_prog,
            motivo_id,
            cot,
            monto_val,
            moneda_val,
            f"Lead demo mayo - {proceso}",
            day,
        ),
    )

    if payload.get("campaign_id"):
        cur.execute(
            """
            INSERT INTO marketing_campaign_leads
            (campaign_id, lead_id, fecha_atribucion, metodo_atribucion, created_by, created_at)
            VALUES (%s,%s,%s,'periodo_automatico',%s,NOW())
            """,
            (payload["campaign_id"], lead_id, day, CREATED_BY),
        )

    return lead_id, proceso


def main():
    parser = argparse.ArgumentParser(description="Genera leads diarios mayo 2026")
    parser.add_argument("--from", dest="date_from", default=DEFAULT_START.isoformat())
    parser.add_argument("--to", dest="date_to", default=date.today().isoformat())
    parser.add_argument("--seed", type=int, default=20260501, help="Semilla random")
    parser.add_argument("--force", action="store_true", help="Generar aunque ya existan leads en el rango")
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    start = date.fromisoformat(args.date_from)
    end = date.fromisoformat(args.date_to)
    if start > end:
        print("Rango de fechas inválido.")
        return 1

    random.seed(args.seed)
    conn = connect()
    cur = conn.cursor(DictCursor)

    try:
        cur.execute(
            "SELECT COUNT(*) AS n FROM leads WHERE fecha BETWEEN %s AND %s",
            (start, end),
        )
        existing = int(cur.fetchone()["n"])
        if existing and not args.force:
            print(f"Ya hay {existing} leads entre {start} y {end}. Use --force para continuar.")
            return 1

        clientes, asesores, campanas, motivo_default = fetch_pools(cur)
        if not clientes:
            print("No hay clientes en la BD.")
            return 1

        codigo_counter = {"n": None}
        seq = 0
        stats = {"total": 0, "con_cliente": 0, "nuevo_sin_campana": 0, "con_campana": 0}
        by_day = {}
        by_proceso = {k: 0 for k in PROCESO}

        cliente_idx = 0
        for day in daterange(start, end):
            n_day = leads_per_day(day)
            pattern = DAILY_PATTERNS[day.toordinal() % len(DAILY_PATTERNS)]
            procesos = build_proceso_queue(pattern, n_day)
            by_day[day.isoformat()] = n_day

            for proceso in procesos:
                seq += 1
                use_existing = seq % 10 != 0  # ~90% clientes existentes, 10% contactos nuevos

                if use_existing:
                    c = clientes[cliente_idx % len(clientes)]
                    cliente_idx += 1
                    nombre = (c.get("nombre") or "Cliente").strip()[:120]
                    ruc_dni = (c.get("ruc_dni") or "").strip()[:20]
                    telefono = (c.get("telefono") or f"9{seq:08d}")[:20]
                    email = (c.get("email") or "")[:120]
                    contacto = (c.get("contacto") or nombre)[:120]
                    direccion = (c.get("direccion") or "")[:200]
                    depto = (c.get("departamento") or "")[:80]
                    prov = (c.get("provincia") or "")[:80]
                    dist = (c.get("distrito") or "")[:80]
                    stats["con_cliente"] += 1
                else:
                    nombre = f"Prospecto Mayo {seq}"
                    ruc_dni = f"DEMO{day.strftime('%y%m%d')}{seq:04d}"
                    telefono = f"98{seq:08d}"[-9:]
                    email = f"prospecto{seq}@demo.local"
                    contacto = nombre
                    direccion = depto = prov = dist = ""
                    stats["nuevo_sin_campana"] += 1

                asignado = asesores[seq % len(asesores)]
                canal_id = CANALES[seq % len(CANALES)]
                bien_id = BIENES[seq % len(BIENES)]

                link_campana = seq % 4 == 0  # ~25% intentan campaña si hay periodo activo
                campaign_id = pick_campana(campanas, day, bien_id) if link_campana else None
                if campaign_id:
                    stats["con_campana"] += 1

                payload = {
                    "codigo": next_codigo(cur, codigo_counter),
                    "fecha": day,
                    "telefono": telefono,
                    "ruc_dni": ruc_dni,
                    "nombre": nombre,
                    "canal_id": canal_id,
                    "contacto": contacto,
                    "departamento": depto,
                    "provincia": prov,
                    "distrito": dist,
                    "direccion": direccion,
                    "email": email,
                    "bien_servicio_id": bien_id,
                    "asignado_a": asignado,
                    "comentario": "Generado script mayo diario",
                    "proceso": proceso,
                    "motivo_id": motivo_default,
                    "campaign_id": campaign_id,
                }

                if args.dry_run:
                    stats["total"] += 1
                    by_proceso[proceso] += 1
                    continue

                insert_lead_bundle(cur, payload, seq)
                stats["total"] += 1
                by_proceso[proceso] += 1

                if stats["total"] % 40 == 0:
                    conn.commit()

        if not args.dry_run:
            conn.commit()

        print(f"Rango: {start} a {end}")
        print(f"Leads generados: {stats['total']}")
        print(f"  Con cliente existente: {stats['con_cliente']}")
        print(f"  Contactos nuevos (sin campaña): {stats['nuevo_sin_campana']}")
        print(f"  Vinculados a campaña activa: {stats['con_campana']}")
        print("Por proceso:")
        for name, pid in PROCESO.items():
            print(f"  {name}: {by_proceso.get(name, 0)}")
        if args.dry_run:
            print("(dry-run, no se escribió en BD)")
        return 0
    except Exception as exc:
        conn.rollback()
        print(f"Error: {exc}")
        raise
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    raise SystemExit(main())
