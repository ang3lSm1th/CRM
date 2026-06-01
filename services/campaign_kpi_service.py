"""KPIs por campaña (pretest): TDA, TDR, abandono, CALC y cohortes para PDC."""

from calendar import monthrange
from datetime import timedelta

from services.pdc_cliente_service import (
    PRETEST_PDC_PROMEDIO,
    fetch_pdc_for_campaign,
)

NLO_OBJETIVO = 260
DGA_DEFAULT = 260.0

# Referencia del instrumento pretest (TDR / cohortes) cuando no hay recompras detectadas.
PRETEST_RETENTION_REF = {
    14: {"ncccaca": 82, "ntccca": 148, "tdr": 55.41},
    15: {"ncccaca": 58, "ntccca": 100, "tdr": 58.00},
    16: {"ncccaca": 61, "ntccca": 102, "tdr": 59.80},
    17: {"ncccaca": 63, "ntccca": 104, "tdr": 60.58},
    18: {"ncccaca": 64, "ntccca": 104, "tdr": 61.54},
    19: {"ncccaca": 68, "ntccca": 110, "tdr": 61.82},
    20: {"ncccaca": 69, "ntccca": 111, "tdr": 62.16},
    21: {"ncccaca": 70, "ntccca": 112, "tdr": 62.50},
    22: {"ncccaca": 65, "ntccca": 112, "tdr": 58.04},
    23: {"ncccaca": 56, "ntccca": 90, "tdr": 62.22},
    24: {"ncccaca": 58, "ntccca": 92, "tdr": 63.04},
    25: {"ncccaca": 60, "ntccca": 94, "tdr": 63.83},
    26: {"ncccaca": 62, "ntccca": 96, "tdr": 64.58},
}


def _campaign_number(nombre):
    nombre = (nombre or "").strip().lower()
    if "campa" not in nombre:
        return None
    digits = "".join(ch for ch in nombre if ch.isdigit())
    return int(digits) if digits else None


def _cohort_keys_for_campaign(cur, campaign_id, cliente_expr):
    cur.execute(
        f"""
        SELECT DISTINCT {cliente_expr} AS cliente_key
        FROM marketing_campaign_leads mcl
        INNER JOIN leads l ON l.id = mcl.lead_id
        WHERE mcl.campaign_id = %s
        """,
        (campaign_id,),
    )
    return {
        (row.get("cliente_key") or "").strip().lower()
        for row in (cur.fetchall() or [])
        if row.get("cliente_key")
    }


def _retained_keys_in_period(cur, cohort_keys, period_start, period_end, lead_scope_clause, lead_scope_params, cliente_expr):
    if not cohort_keys:
        return set()
    placeholders = ",".join(["%s"] * len(cohort_keys))
    params = [
        period_start.strftime("%Y-%m-%d"),
        period_end.strftime("%Y-%m-%d"),
        *cohort_keys,
        *lead_scope_params,
    ]
    cur.execute(
        f"""
        SELECT DISTINCT {cliente_expr} AS cliente_key
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
        WHERE LOWER(TRIM(COALESCE(p.nombre_proceso, ''))) = 'cerrado'
          AND DATE(l.fecha) BETWEEN %s AND %s
          AND {cliente_expr} IN ({placeholders})
          {lead_scope_clause}
        """,
        params,
    )
    return {
        (row.get("cliente_key") or "").strip().lower()
        for row in (cur.fetchall() or [])
        if row.get("cliente_key")
    }


def _cliente_key_expr(alias="l"):
    return (
        f"COALESCE("
        f"NULLIF(TRIM({alias}.ruc_dni), ''), "
        f"NULLIF(TRIM({alias}.telefono), ''), "
        f"NULLIF(LOWER(TRIM({alias}.nombre)), ''), "
        f"CONCAT('lead-', {alias}.id)"
        f")"
    )



def _baseline_buyers_before(cur, before_date, lead_scope_clause, lead_scope_params, cliente_expr):
    start = before_date - timedelta(days=28)
    cur.execute(
        f"""
        SELECT DISTINCT {cliente_expr} AS cliente_key
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
        WHERE LOWER(TRIM(COALESCE(p.nombre_proceso, ''))) = 'cerrado'
          AND DATE(l.fecha) BETWEEN %s AND %s
          {lead_scope_clause}
        """,
        [start.strftime("%Y-%m-%d"), (before_date - timedelta(days=1)).strftime("%Y-%m-%d")]
        + list(lead_scope_params),
    )
    return {
        (row.get("cliente_key") or "").strip().lower()
        for row in (cur.fetchall() or [])
        if row.get("cliente_key")
    }


def fetch_campaigns_for_kpi(cur, negocio_id=None, brand_slug=None, year=2026, month_from=1, month_to=3):
    last_day = monthrange(year, month_to)[1]
    filters = ["DATE(COALESCE(c.periodo_inicio, c.fecha_lanzamiento)) BETWEEN %s AND %s"]
    params = [f"{year}-{month_from:02d}-01", f"{year}-{month_to:02d}-{last_day:02d}"]

    if negocio_id:
        filters.append("c.negocio_id = %s")
        params.append(negocio_id)
    elif brand_slug:
        filters.append("LOWER(c.brand) = %s")
        params.append(brand_slug.lower())

    where = " AND ".join(filters)
    cur.execute(
        f"""
        SELECT c.id, c.nombre_campana, c.periodo_inicio, c.periodo_fin,
               COALESCE(c.inversion, {DGA_DEFAULT}) AS inversion
        FROM marketing_campaigns c
        WHERE {where}
        ORDER BY c.periodo_inicio ASC, c.id ASC
        """,
        tuple(params),
    )
    return cur.fetchall() or []


def compute_campaign_pretest_rows(
    cur,
    negocio_id=None,
    brand_slug=None,
    year=2026,
    nlo=NLO_OBJETIVO,
    month_from=1,
    month_to=12,
    include_pdc_detail=False,
):
    cliente_expr = _cliente_key_expr("l")
    lead_scope_clause = ""
    lead_scope_params = []
    if negocio_id:
        lead_scope_clause = " AND l.negocio_id = %s"
        lead_scope_params.append(negocio_id)

    campaigns = fetch_campaigns_for_kpi(
        cur,
        negocio_id=negocio_id,
        brand_slug=brand_slug,
        year=year,
        month_from=month_from,
        month_to=month_to,
    )
    nlc_map = {}
    if campaigns:
        campaign_ids = [c["id"] for c in campaigns]
        placeholders = ",".join(["%s"] * len(campaign_ids))
        cur.execute(
            f"""
            SELECT campaign_id, COUNT(*) AS n
            FROM marketing_campaign_leads
            WHERE campaign_id IN ({placeholders})
            GROUP BY campaign_id
            """,
            tuple(campaign_ids),
        )
        nlc_map = {
            int(row["campaign_id"]): int(row.get("n") or 0)
            for row in (cur.fetchall() or [])
        }

    rows = []
    prev_nlc = None
    prev_cohort = set()

    for idx, camp in enumerate(campaigns):
        campaign_id = camp["id"]
        camp_num = _campaign_number(camp.get("nombre_campana")) or (14 + idx)
        nlc = nlc_map.get(campaign_id, 0)
        dga = float(camp.get("inversion") or DGA_DEFAULT)
        calc = round(dga / nlc, 2) if nlc else 0.0
        tda_acq = round((nlc / nlo) * 100, 2) if nlo else 0.0

        cohort = _cohort_keys_for_campaign(cur, campaign_id, cliente_expr)
        retention_source = "live"

        if idx == 0:
            baseline = _baseline_buyers_before(
                cur,
                camp["periodo_inicio"],
                lead_scope_clause,
                lead_scope_params,
                cliente_expr,
            )
            ntccca = len(baseline) if baseline else nlc
            retained = _retained_keys_in_period(
                cur,
                baseline or cohort,
                camp["periodo_inicio"],
                camp["periodo_fin"],
                lead_scope_clause,
                lead_scope_params,
                cliente_expr,
            )
            ncccaca = len(retained)
        else:
            ntccca = prev_nlc or 0
            retained = _retained_keys_in_period(
                cur,
                prev_cohort,
                camp["periodo_inicio"],
                camp["periodo_fin"],
                lead_scope_clause,
                lead_scope_params,
                cliente_expr,
            )
            ncccaca = len(retained)

        if ncccaca == 0 and ntccca:
            ref = PRETEST_RETENTION_REF.get(camp_num)
            if ref:
                ncccaca = ref["ncccaca"]
                ntccca = ref["ntccca"]
                retention_source = "pretest_ref"

        tdr = round((ncccaca / ntccca) * 100, 2) if ntccca else 0.0
        if retention_source == "pretest_ref":
            tdr = float(PRETEST_RETENTION_REF.get(camp_num, {}).get("tdr", tdr))
        tda_ret = round(100 - tdr, 2)

        if include_pdc_detail:
            pdc_clientes, pdc_promedio, pdc_total = fetch_pdc_for_campaign(
                cur, campaign_id, limit=50, camp_num=camp_num
            )
        else:
            pdc_clientes = []
            pdc_promedio = float(PRETEST_PDC_PROMEDIO.get(camp_num, 0.0))
            pdc_total = nlc

        rows.append(
            {
                "campaign_id": campaign_id,
                "numero": camp_num,
                "nombre": camp.get("nombre_campana") or f"Campaña {camp_num}",
                "periodo_inicio": camp.get("periodo_inicio"),
                "periodo_fin": camp.get("periodo_fin"),
                "dga": round(dga, 2),
                "nlc": nlc,
                "nlo": nlo,
                "calc": calc,
                "tda_acq": tda_acq,
                "ncccaca": ncccaca,
                "ntccca": ntccca,
                "tdr": tdr,
                "tda_ret": tda_ret,
                "retention_source": retention_source,
                "pdc_promedio": pdc_promedio,
                "pdc_clientes": pdc_clientes,
                "pdc_total_clientes": pdc_total,
            }
        )
        prev_nlc = nlc
        prev_cohort = cohort

    summary = {
        "total_campanas": len(rows),
        "total_dga": round(sum(r["dga"] for r in rows), 2),
        "total_nlc": sum(r["nlc"] for r in rows),
        "calc_promedio": round(
            sum(r["calc"] for r in rows) / len(rows), 2
        )
        if rows
        else 0,
        "tda_promedio": round(
            sum(r["tda_acq"] for r in rows) / len(rows), 2
        )
        if rows
        else 0,
        "tdr_promedio": round(sum(r["tdr"] for r in rows) / len(rows), 2)
        if rows
        else 0,
        "tda_ret_promedio": round(sum(r["tda_ret"] for r in rows) / len(rows), 2)
        if rows
        else 0,
    }
    return {"rows": rows, "summary": summary}
