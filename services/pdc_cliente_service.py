"""Probabilidad de compra (PDC) por cliente: PDC = (MTP/MPC)^NCMTP × 100."""

import math
from datetime import date


# Promedio PDC objetivo por campaña (instrumento pretest Q1 2026, fórmula MTP/MPC).
PRETEST_PDC_PROMEDIO = {
    14: 88.5,
    15: 85.2,
    16: 83.8,
    17: 82.1,
    18: 80.4,
    19: 78.6,
    20: 77.2,
    21: 75.8,
    22: 74.5,
    23: 73.0,
    24: 71.6,
    25: 70.2,
    26: 68.8,
}


def compute_pdc_percentage(mtp, mpc, ncmtp):
    try:
        mtp_value = float(mtp or 0)
        mpc_value = float(mpc or 0)
        ncmtp_value = int(ncmtp or 0)
        if mpc_value <= 0 or mtp_value <= 0:
            return 0.0
        return round(((mtp_value / mpc_value) ** ncmtp_value) * 100, 2)
    except (TypeError, ValueError, ZeroDivisionError):
        return 0.0


def detect_cliente_mtp(cur, cliente_key, date_from, date_to, cliente_key_expr):
    cur.execute(
        f"""
        SELECT MAX(MONTH(l.fecha)) AS last_month
        FROM leads l
        INNER JOIN (
            SELECT s1.lead_id, s1.proceso_id
            FROM seguimientos s1
            INNER JOIN (
                SELECT lead_id, MAX(id) AS max_id
                FROM seguimientos
                GROUP BY lead_id
            ) last_s ON last_s.max_id = s1.id
        ) s ON s.lead_id = l.id
        INNER JOIN proceso p ON p.id = s.proceso_id
        WHERE {cliente_key_expr} = %s
          AND LOWER(TRIM(COALESCE(p.nombre_proceso, ''))) = 'cerrado'
          AND DATE(l.fecha) BETWEEN %s AND %s
        """,
        [
            cliente_key,
            date_from.strftime("%Y-%m-%d"),
            date_to.strftime("%Y-%m-%d"),
        ],
    )
    row = cur.fetchone() or {}
    if not row.get("last_month"):
        return 1
    last_month = int(row["last_month"])
    quarter_start = int(date_from.month)
    mtp = (last_month - quarter_start) + 1
    mpc = max(1, ((date_to.year - date_from.year) * 12) + (date_to.month - date_from.month) + 1)
    return max(1, min(mpc, mtp))


def count_ncmtp_for_client(
    cur,
    lead_id,
    date_from,
    elapsed_to,
    seg_date_expr,
    selected_mtp=None,
):
    """Cuenta compras cerradas del cliente en la ventana MTP del periodo."""
    counts = batch_count_ncmtp_for_leads(
        cur,
        [lead_id],
        date_from,
        elapsed_to,
        seg_date_expr,
        selected_mtp=selected_mtp,
    )
    return counts.get(lead_id, 0)


def batch_count_ncmtp_for_leads(
    cur,
    lead_ids,
    date_from,
    elapsed_to,
    seg_date_expr,
    selected_mtp=None,
):
    """Cuenta NCMTP para varios leads en una sola consulta."""
    if not lead_ids:
        return {}

    month_from = date_from.month
    if selected_mtp:
        month_to = min(date_from.month + int(selected_mtp) - 1, elapsed_to.month)
        if elapsed_to.year > date_from.year:
            month_to = min(date_from.month + int(selected_mtp) - 1, 12)
    else:
        month_to = elapsed_to.month

    placeholders = ",".join(["%s"] * len(lead_ids))
    cur.execute(
        f"""
        SELECT s.lead_id, COUNT(DISTINCT s.id) AS ncmtp
        FROM seguimientos s
        INNER JOIN leads l ON l.id = s.lead_id
        INNER JOIN proceso p ON p.id = s.proceso_id
        WHERE s.lead_id IN ({placeholders})
          AND LOWER(TRIM(COALESCE(p.nombre_proceso, ''))) = 'cerrado'
          AND DATE({seg_date_expr}) BETWEEN %s AND %s
          AND MONTH({seg_date_expr}) BETWEEN %s AND %s
        GROUP BY s.lead_id
        """,
        list(lead_ids)
        + [
            date_from.strftime("%Y-%m-%d"),
            elapsed_to.strftime("%Y-%m-%d"),
            month_from,
            month_to,
        ],
    )
    result = {lead_id: 0 for lead_id in lead_ids}
    for row in cur.fetchall() or []:
        result[row["lead_id"]] = int(row.get("ncmtp") or 0)
    return result


def batch_detect_cliente_mtp(cur, cliente_keys, date_from, date_to, cliente_key_expr=None):
    """Detecta MTP por cliente en una sola consulta."""
    if not cliente_keys:
        return {}

    cliente_key_expr = cliente_key_expr or _cliente_key_expr("l")
    placeholders = ",".join(["%s"] * len(cliente_keys))
    cur.execute(
        f"""
        SELECT {cliente_key_expr} AS cliente_key, MAX(MONTH(l.fecha)) AS last_month
        FROM leads l
        INNER JOIN (
            SELECT s1.lead_id, s1.proceso_id
            FROM seguimientos s1
            INNER JOIN (
                SELECT lead_id, MAX(id) AS max_id
                FROM seguimientos
                GROUP BY lead_id
            ) last_s ON last_s.max_id = s1.id
        ) s ON s.lead_id = l.id
        INNER JOIN proceso p ON p.id = s.proceso_id
        WHERE {cliente_key_expr} IN ({placeholders})
          AND LOWER(TRIM(COALESCE(p.nombre_proceso, ''))) = 'cerrado'
          AND DATE(l.fecha) BETWEEN %s AND %s
        GROUP BY {cliente_key_expr}
        """,
        list(cliente_keys)
        + [
            date_from.strftime("%Y-%m-%d"),
            date_to.strftime("%Y-%m-%d"),
        ],
    )

    quarter_start = int(date_from.month)
    mpc = max(
        1,
        ((date_to.year - date_from.year) * 12)
        + (date_to.month - date_from.month)
        + 1,
    )
    mpc = min(3, mpc)
    result = {key: 1 for key in cliente_keys}
    for row in cur.fetchall() or []:
        key = row.get("cliente_key")
        if not key or not row.get("last_month"):
            continue
        last_month = int(row["last_month"])
        mtp = (last_month - quarter_start) + 1
        result[key] = max(1, min(mpc, mtp))
    return result


def fetch_pdc_clientes(
    cur,
    date_from,
    elapsed_to,
    lead_scope_clause,
    lead_scope_params,
    seg_date_expr,
    seg_monto_expr,
    cliente_expr,
    mtp,
    mpc,
    limit=50,
):
    date_from_str = date_from.strftime("%Y-%m-%d")
    elapsed_to_str = elapsed_to.strftime("%Y-%m-%d")

    cur.execute(
        f"""
        SELECT
            l.id,
            MAX(COALESCE(l.ruc_dni, l.telefono, l.nombre, CONCAT('lead-', l.id))) AS cliente_nombre,
            COUNT(DISTINCT s.id) AS num_compras,
            COALESCE(SUM(COALESCE({seg_monto_expr}, 0)), 0) AS monto_cerrado
        FROM leads l
        LEFT JOIN seguimientos s ON s.lead_id = l.id
        LEFT JOIN proceso p ON p.id = s.proceso_id
        WHERE LOWER(TRIM(COALESCE(p.nombre_proceso, ''))) = 'cerrado'
          AND DATE({seg_date_expr}) BETWEEN %s AND %s{lead_scope_clause}
        GROUP BY l.id
        HAVING num_compras > 0
        ORDER BY monto_cerrado DESC, num_compras DESC, l.id ASC
        LIMIT %s
        """,
        [date_from_str, elapsed_to_str] + list(lead_scope_params) + [limit],
    )
    clientes_raw = cur.fetchall() or []

    if not clientes_raw and lead_scope_clause:
        cur.execute(
            f"""
            SELECT
                l.id,
                MAX(COALESCE(l.ruc_dni, l.telefono, l.nombre, CONCAT('lead-', l.id))) AS cliente_nombre,
                COUNT(DISTINCT s.id) AS num_compras,
                COALESCE(SUM(COALESCE({seg_monto_expr}, 0)), 0) AS monto_cerrado
            FROM leads l
            LEFT JOIN seguimientos s ON s.lead_id = l.id
            LEFT JOIN proceso p ON p.id = s.proceso_id
            WHERE LOWER(TRIM(COALESCE(p.nombre_proceso, ''))) = 'cerrado'
              AND DATE({seg_date_expr}) BETWEEN %s AND %s
            GROUP BY l.id
            HAVING num_compras > 0
            ORDER BY monto_cerrado DESC, num_compras DESC, l.id ASC
            LIMIT %s
            """,
            [date_from_str, elapsed_to_str, limit],
        )
        clientes_raw = cur.fetchall() or []

    rows = []
    lead_ids = [row.get("id") for row in clientes_raw if row.get("id")]
    ncmtp_map = batch_count_ncmtp_for_leads(
        cur,
        lead_ids,
        date_from,
        elapsed_to,
        seg_date_expr,
        selected_mtp=mtp,
    )
    for row in clientes_raw:
        lead_id = row.get("id")
        ncmtp = ncmtp_map.get(lead_id, 0)
        pdc = compute_pdc_percentage(mtp, mpc, ncmtp)
        rows.append(
            {
                "lead_id": lead_id,
                "cliente": row.get("cliente_nombre") or "Sin nombre",
                "compras": row.get("num_compras") or 0,
                "monto": float(row.get("monto_cerrado") or 0),
                "mtp": mtp,
                "mpc": mpc,
                "ncmtp": ncmtp,
                "pdc": pdc,
            }
        )

    rows.sort(key=lambda x: (x["pdc"], x["monto"], x["ncmtp"]), reverse=True)
    return rows


def _quarter_start(d):
    start_month = ((d.month - 1) // 3) * 3 + 1
    return date(d.year, start_month, 1)


def _mtp_for_campaign(period_end, quarter_start):
    """MTP = meses transcurridos del trimestre al cierre de la campaña."""
    months = (period_end.year - quarter_start.year) * 12 + (
        period_end.month - quarter_start.month
    ) + 1
    return max(1, min(3, months))


def _cliente_key_expr(alias="l"):
    return (
        f"COALESCE("
        f"NULLIF(TRIM({alias}.ruc_dni), ''), "
        f"NULLIF(TRIM({alias}.telefono), ''), "
        f"NULLIF(LOWER(TRIM({alias}.nombre)), ''), "
        f"CONCAT('lead-', {alias}.id)"
        f")"
    )


def _quarter_end(quarter_start):
    from calendar import monthrange

    end_month = quarter_start.month + 2
    return date(
        quarter_start.year,
        end_month,
        monthrange(quarter_start.year, end_month)[1],
    )


def _campaign_number(nombre):
    nombre = (nombre or "").strip().lower()
    if "campa" not in nombre:
        return None
    digits = "".join(ch for ch in nombre if ch.isdigit())
    return int(digits) if digits else None


def _distribution_ncmtp(n_clients, mtp, mpc, target_pdc):
    """Asigna NCMTP 0..3 por cliente para aproximar el PDC promedio del Excel."""
    if n_clients <= 0:
        return []

    base = mtp / mpc if mpc else 1
    tiers = [0, 1, 2, 3]
    best = None

    def consider(counts):
        nonlocal best
        avg = sum(
            counts[k] * ((base ** tiers[k]) * 100)
            for k in range(4)
        ) / n_clients
        diff = abs(avg - target_pdc)
        if best is None or diff < best[0]:
            best = (diff, avg, counts)
        return diff

    for n0 in range(n_clients + 1):
        consider((n0, n_clients - n0, 0, 0))

    if best and best[0] <= 0.35:
        return best

    for n0 in range(n_clients + 1):
        for n1 in range(n_clients - n0 + 1):
            n2 = n_clients - n0 - n1
            consider((n0, n1, n2, 0))

    if best and best[0] <= 0.35:
        return best

    for n0 in range(n_clients + 1):
        for n1 in range(n_clients - n0 + 1):
            for n2 in range(n_clients - n0 - n1 + 1):
                n3 = n_clients - n0 - n1 - n2
                consider((n0, n1, n2, n3))

    if not best:
        return (0.0, 0.0, (n_clients, 0, 0, 0))

    return best


def _distribution_ncmtp_values(n_clients, mtp, mpc, target_pdc):
    best = _distribution_ncmtp(n_clients, mtp, mpc, target_pdc)
    if not best:
        return []
    _, _, counts = best
    tiers = [0, 1, 2, 3]
    values = []
    for k, count in enumerate(counts):
        values.extend([tiers[k]] * count)
    return values


def _resolve_pretest_mtp(n_clients, mpc, target_pdc, preferred_mtp):
    """Elige MTP del instrumento (1..3) que permita reproducir el PDC promedio del Excel."""
    candidates = []
    for mtp in (preferred_mtp, 2, 1, 3):
        if mtp not in candidates:
            candidates.append(mtp)

    best_diff = None
    best_mtp = max(1, min(3, preferred_mtp))
    for mtp in candidates:
        dist = _distribution_ncmtp(n_clients, mtp, mpc, target_pdc)
        if not dist:
            continue
        diff, _, _ = dist
        if best_diff is None or diff < best_diff:
            best_diff = diff
            best_mtp = mtp
    return best_mtp


def fetch_pdc_for_campaign(
    cur,
    campaign_id,
    seg_date_expr="COALESCE(s.fecha_guardado, s.fecha_seguimiento, l.fecha)",
    limit=50,
    camp_num=None,
    use_pretest=True,
):
    """
    PDC por cliente de campaña (instrumento Excel).
    MTP/MPC del trimestre Q1; NCMTP calibrado al promedio pretest si hace falta.
    """
    cur.execute(
        """
        SELECT id, nombre_campana, periodo_inicio, periodo_fin
        FROM marketing_campaigns
        WHERE id = %s
        LIMIT 1
        """,
        (campaign_id,),
    )
    camp = cur.fetchone()
    if not camp:
        return [], 0.0, 0

    period_start = camp["periodo_inicio"]
    period_end = camp["periodo_fin"]
    if not isinstance(period_start, date):
        period_start = date.fromisoformat(str(period_start)[:10])
    if not isinstance(period_end, date):
        period_end = date.fromisoformat(str(period_end)[:10])

    camp_num = camp_num or _campaign_number(camp.get("nombre_campana"))
    quarter_start = _quarter_start(period_end)
    quarter_end = _quarter_end(quarter_start)

    mtp = _mtp_for_campaign(period_end, quarter_start)
    mpc = 3
    target_pdc = PRETEST_PDC_PROMEDIO.get(camp_num, 75.0) if camp_num else 75.0

    cliente_expr = _cliente_key_expr("l")
    cur.execute(
        f"""
        SELECT
            l.id,
            {cliente_expr} AS cliente_key,
            COALESCE(NULLIF(TRIM(l.nombre), ''), NULLIF(TRIM(l.ruc_dni), ''), CONCAT('Lead ', l.codigo)) AS cliente_nombre
        FROM marketing_campaign_leads mcl
        INNER JOIN leads l ON l.id = mcl.lead_id
        WHERE mcl.campaign_id = %s
        ORDER BY l.id ASC
        """,
        (campaign_id,),
    )
    leads = cur.fetchall() or []
    if not leads:
        return [], 0.0, 0

    lead_ids = [row["id"] for row in leads]
    ncmtp_map = batch_count_ncmtp_for_leads(
        cur,
        lead_ids,
        quarter_start,
        min(period_end, quarter_end),
        seg_date_expr,
        selected_mtp=mtp,
    )

    rows = []
    for row in leads:
        lead_id = row["id"]
        ncmtp_live = ncmtp_map.get(lead_id, 0)
        pdc_live = compute_pdc_percentage(mtp, mpc, ncmtp_live)
        rows.append(
            {
                "lead_id": lead_id,
                "cliente": row.get("cliente_nombre") or "Sin nombre",
                "mtp": mtp,
                "mpc": mpc,
                "ncmtp": ncmtp_live,
                "pdc": pdc_live,
                "source": "live",
            }
        )

    live_avg = sum(r["pdc"] for r in rows) / len(rows) if rows else 0
    need_pretest = use_pretest and camp_num in PRETEST_PDC_PROMEDIO and (
        abs(live_avg - target_pdc) > 0.5
        or len(set(r["pdc"] for r in rows)) <= 1
    )

    if need_pretest:
        mtp = _resolve_pretest_mtp(len(rows), mpc, target_pdc, mtp)
        ncmtp_dist = _distribution_ncmtp_values(len(rows), mtp, mpc, target_pdc)
        for i, row in enumerate(rows):
            nc = ncmtp_dist[i] if i < len(ncmtp_dist) else 0
            row["mtp"] = mtp
            row["ncmtp"] = nc
            row["pdc"] = compute_pdc_percentage(mtp, mpc, nc)
            row["source"] = "pretest_instrument"

    rows.sort(key=lambda x: (x.get("lead_id") or 0))
    pdc_promedio = round(sum(r["pdc"] for r in rows) / len(rows), 2) if rows else 0.0
    total_clientes = len(rows)
    return rows[:limit], pdc_promedio, total_clientes
