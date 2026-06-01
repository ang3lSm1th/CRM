import calendar
import os
from datetime import date, datetime
from decimal import Decimal
from flask import jsonify
from MySQLdb.cursors import DictCursor
from extensions import mysql

from services.marketing_ai import generate_marketing_okr_analyses
from routes.marketing_roadmap import _build_roadmap_context
from routes.marketing_shared import (
    ROLE_ADMIN,
    ROLE_GERENTE,
    ROLE_MARKETING,
    _calculate_growth,
    _column_exists,
    _count_closed_sales_by_year,
    _count_leads_by_year,
    _fetch_facebook_followers,
    _fetch_instagram_followers_with_fallback,
    _load_social_metrics_history,
    _marketing_scope_clause,
    _resolve_negocio_id_by_brand,
    _save_social_metrics_snapshot,
    _sum_marketing_investment_by_year,
    _table_exists,
    _to_int,
    login_required,
    marketing_bp,
    render_template,
    request,
    role_required,
)


def _to_float(value):
    if value is None:
        return None
    if isinstance(value, Decimal):
        return float(value)
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _ensure_okr_goals_table():
    cur = mysql.connection.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS marketing_okr_goals (
                id INT AUTO_INCREMENT PRIMARY KEY,
                negocio_id INT NOT NULL,
                year INT NOT NULL,
                fb_target_followers INT NULL,
                ig_target_followers INT NULL,
                leads_target INT NULL,
                fb_previous_followers_manual INT NULL,
                ig_previous_followers_manual INT NULL,
                leads_previous_manual INT NULL,
                period_type VARCHAR(20) NOT NULL DEFAULT 'anual',
                period_quarter TINYINT NULL,
                period_custom_start DATE NULL,
                period_custom_end DATE NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                UNIQUE KEY uq_marketing_okr_goals_negocio_year (negocio_id, year)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """
        )
        if not _column_exists("marketing_okr_goals", "fb_previous_followers_manual"):
            cur.execute("ALTER TABLE marketing_okr_goals ADD COLUMN fb_previous_followers_manual INT NULL")
        if not _column_exists("marketing_okr_goals", "ig_previous_followers_manual"):
            cur.execute("ALTER TABLE marketing_okr_goals ADD COLUMN ig_previous_followers_manual INT NULL")
        if not _column_exists("marketing_okr_goals", "leads_previous_manual"):
            cur.execute("ALTER TABLE marketing_okr_goals ADD COLUMN leads_previous_manual INT NULL")
        if not _column_exists("marketing_okr_goals", "period_type"):
            cur.execute("ALTER TABLE marketing_okr_goals ADD COLUMN period_type VARCHAR(20) NOT NULL DEFAULT 'anual'")
        if not _column_exists("marketing_okr_goals", "period_quarter"):
            cur.execute("ALTER TABLE marketing_okr_goals ADD COLUMN period_quarter TINYINT NULL")
        if not _column_exists("marketing_okr_goals", "period_custom_start"):
            cur.execute("ALTER TABLE marketing_okr_goals ADD COLUMN period_custom_start DATE NULL")
        if not _column_exists("marketing_okr_goals", "period_custom_end"):
            cur.execute("ALTER TABLE marketing_okr_goals ADD COLUMN period_custom_end DATE NULL")
        mysql.connection.commit()
    finally:
        cur.close()


def _load_okr_goals(negocio_id, year):
    if not negocio_id or not year:
        return {}
    _ensure_okr_goals_table()
    cur = mysql.connection.cursor(DictCursor)
    try:
        cur.execute(
            """
            SELECT
                fb_target_followers,
                ig_target_followers,
                leads_target,
                fb_previous_followers_manual,
                ig_previous_followers_manual,
                leads_previous_manual,
                period_type,
                period_quarter,
                period_custom_start,
                period_custom_end
            FROM marketing_okr_goals
            WHERE negocio_id = %s AND year = %s
            LIMIT 1
            """,
            (negocio_id, year),
        )
        row = cur.fetchone() or {}
        return {
            "fb_target_followers": _to_int(row.get("fb_target_followers")) if row else None,
            "ig_target_followers": _to_int(row.get("ig_target_followers")) if row else None,
            "leads_target": _to_int(row.get("leads_target")) if row else None,
            "fb_previous_followers_manual": _to_int(row.get("fb_previous_followers_manual")) if row else None,
            "ig_previous_followers_manual": _to_int(row.get("ig_previous_followers_manual")) if row else None,
            "leads_previous_manual": _to_int(row.get("leads_previous_manual")) if row else None,
            "period_type": (row.get("period_type") or "anual") if row else "anual",
            "period_quarter": _to_int(row.get("period_quarter")) if row else None,
            "period_custom_start": row.get("period_custom_start") if row else None,
            "period_custom_end": row.get("period_custom_end") if row else None,
        }
    finally:
        cur.close()


def _save_okr_goals(
    negocio_id,
    year,
    fb_target_followers,
    ig_target_followers,
    leads_target,
    fb_previous_followers_manual,
    ig_previous_followers_manual,
    leads_previous_manual,
    period_type,
    period_quarter,
    period_custom_start,
    period_custom_end,
):
    if not negocio_id or not year:
        return False
    _ensure_okr_goals_table()
    cur = mysql.connection.cursor()
    try:
        cur.execute(
            """
            INSERT INTO marketing_okr_goals
                (
                    negocio_id,
                    year,
                    fb_target_followers,
                    ig_target_followers,
                    leads_target,
                    fb_previous_followers_manual,
                    ig_previous_followers_manual,
                    leads_previous_manual,
                    period_type,
                    period_quarter,
                    period_custom_start,
                    period_custom_end
                )
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                fb_target_followers = VALUES(fb_target_followers),
                ig_target_followers = VALUES(ig_target_followers),
                leads_target = VALUES(leads_target),
                fb_previous_followers_manual = VALUES(fb_previous_followers_manual),
                ig_previous_followers_manual = VALUES(ig_previous_followers_manual),
                leads_previous_manual = VALUES(leads_previous_manual),
                period_type = VALUES(period_type),
                period_quarter = VALUES(period_quarter),
                period_custom_start = VALUES(period_custom_start),
                period_custom_end = VALUES(period_custom_end),
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                negocio_id,
                year,
                fb_target_followers,
                ig_target_followers,
                leads_target,
                fb_previous_followers_manual,
                ig_previous_followers_manual,
                leads_previous_manual,
                period_type,
                period_quarter,
                period_custom_start,
                period_custom_end,
            ),
        )
        mysql.connection.commit()
        return True
    except Exception:
        mysql.connection.rollback()
        return False
    finally:
        cur.close()


def _kpi_progress(value, target, lower_is_better=False):
    value_f = _to_float(value)
    target_f = _to_float(target)
    if value_f is None or target_f is None or target_f <= 0:
        return None
    if lower_is_better:
        return round(max(0.0, min((target_f / value_f) * 100.0 if value_f > 0 else 100.0, 100.0)), 2)
    return round(max(0.0, min((value_f / target_f) * 100.0, 100.0)), 2)


def _parse_iso_date(raw_value):
    raw = (raw_value or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except ValueError:
        return None


def _shift_year_safe(base_date, years):
    try:
        return base_date.replace(year=base_date.year + years)
    except ValueError:
        # Manejo de 29-feb -> 28-feb para años no bisiestos.
        return base_date.replace(month=2, day=28, year=base_date.year + years)


def _resolve_period_range(year, period_type, period_quarter=None, custom_start=None, custom_end=None):
    safe_period = (period_type or "anual").strip().lower()
    if safe_period not in ("anual", "trimestre", "personalizado"):
        safe_period = "anual"

    if safe_period == "trimestre":
        quarter = period_quarter if period_quarter in (1, 2, 3, 4) else 1
        month_start = ((quarter - 1) * 3) + 1
        month_end = month_start + 2
        start = date(year, month_start, 1)
        end_day = calendar.monthrange(year, month_end)[1]
        end = date(year, month_end, end_day)
        return {
            "period_type": "trimestre",
            "period_quarter": quarter,
            "custom_start": None,
            "custom_end": None,
            "start": start,
            "end": end,
            "label": f"Q{quarter} {year}",
            "error": None,
        }

    if safe_period == "personalizado":
        start = _parse_iso_date(custom_start)
        end = _parse_iso_date(custom_end)
        if not start or not end:
            return {
                "period_type": "personalizado",
                "period_quarter": None,
                "custom_start": custom_start,
                "custom_end": custom_end,
                "start": None,
                "end": None,
                "label": "Rango personalizado",
                "error": "Debes indicar fecha de inicio y fin para el rango personalizado.",
            }
        if start > end:
            return {
                "period_type": "personalizado",
                "period_quarter": None,
                "custom_start": custom_start,
                "custom_end": custom_end,
                "start": None,
                "end": None,
                "label": "Rango personalizado",
                "error": "La fecha de inicio no puede ser mayor que la fecha fin.",
            }
        return {
            "period_type": "personalizado",
            "period_quarter": None,
            "custom_start": start.isoformat(),
            "custom_end": end.isoformat(),
            "start": start,
            "end": end,
            "label": f"{start.isoformat()} a {end.isoformat()}",
            "error": None,
        }

    start = date(year, 1, 1)
    end = date(year, 12, 31)
    return {
        "period_type": "anual",
        "period_quarter": None,
        "custom_start": None,
        "custom_end": None,
        "start": start,
        "end": end,
        "label": str(year),
        "error": None,
    }


def _count_leads_in_range(negocio_id, start_date, end_date):
    if not negocio_id or not start_date or not end_date:
        return None
    cur = mysql.connection.cursor(DictCursor)
    try:
        cur.execute(
            """
            SELECT COUNT(*) AS total
            FROM leads
            WHERE negocio_id = %s
              AND DATE(fecha) BETWEEN %s AND %s
            """,
            (negocio_id, start_date, end_date),
        )
        row = cur.fetchone() or {}
        return int(row.get("total") or 0)
    except Exception:
        return None
    finally:
        cur.close()


def _latest_snapshot_upto(negocio_id, upto_date):
    if not negocio_id or not upto_date or not _table_exists("marketing_social_metrics"):
        return None
    cur = mysql.connection.cursor(DictCursor)
    try:
        cur.execute(
            """
            SELECT snapshot_date, fb_followers, ig_followers, total_followers
            FROM marketing_social_metrics
            WHERE negocio_id = %s
              AND snapshot_date <= %s
            ORDER BY snapshot_date DESC
            LIMIT 1
            """,
            (negocio_id, upto_date),
        )
        return cur.fetchone() or None
    finally:
        cur.close()


def _build_kpi_cards_for_brand(brand_slug):
    roadmap_ctx = _build_roadmap_context(brand_slug)
    brand_prefix = brand_slug.upper()

    # Metas de KPI configurables por marca (alineadas a roadmap)
    target_rois = _to_float(os.getenv(f"{brand_prefix}_KPI_TARGET_ROIS", "1.00"))
    target_cac = _to_float(os.getenv(f"{brand_prefix}_KPI_TARGET_CAC", "150.00"))
    target_cpc = _to_float(os.getenv(f"{brand_prefix}_KPI_TARGET_CPC", "3.50"))
    target_conversion_rate = _to_float(os.getenv(f"{brand_prefix}_KPI_TARGET_CONVERSION_RATE", "20.00"))
    target_cpm = _to_float(os.getenv(f"{brand_prefix}_KPI_TARGET_CPM", "0.12"))
    target_ctr = _to_float(os.getenv(f"{brand_prefix}_KPI_TARGET_CTR", "2.00"))

    rois_total = _to_float(roadmap_ctx.get("rois_global"))
    cac = _to_float(roadmap_ctx.get("campaign_cac"))
    cpc = _to_float(roadmap_ctx.get("campaign_cpc"))
    conversion_rate = _to_float(roadmap_ctx.get("campaign_conversion_rate"))
    cpm = _to_float(roadmap_ctx.get("campaign_cpm"))
    ctr_ratio = _to_float(roadmap_ctx.get("campaign_ctr"))
    ctr_pct = round((ctr_ratio or 0.0) * 100.0, 4) if ctr_ratio is not None else None

    kpis = [
        {
            "id": "rois_total",
            "title": "ROIS Total",
            "value": rois_total,
            "value_label": (f"{rois_total:.2f}x" if rois_total is not None else "-"),
            "target": target_rois,
            "target_label": (f"{target_rois:.2f}x" if target_rois is not None else "-"),
            "progress_pct": _kpi_progress(rois_total, target_rois),
            "lower_is_better": False,
        },
        {
            "id": "cac",
            "title": "CAC",
            "value": cac,
            "value_label": (f"S/ {cac:.2f}" if cac is not None else "-"),
            "target": target_cac,
            "target_label": (f"S/ {target_cac:.2f}" if target_cac is not None else "-"),
            "progress_pct": _kpi_progress(cac, target_cac, lower_is_better=True),
            "lower_is_better": True,
        },
        {
            "id": "cpc",
            "title": "CPC",
            "value": cpc,
            "value_label": (f"S/ {cpc:.4f}" if cpc is not None else "-"),
            "target": target_cpc,
            "target_label": (f"S/ {target_cpc:.2f}" if target_cpc is not None else "-"),
            "progress_pct": _kpi_progress(cpc, target_cpc, lower_is_better=True),
            "lower_is_better": True,
        },
        {
            "id": "tasa_conversion",
            "title": "Tasa de Conversión",
            "value": conversion_rate,
            "value_label": (f"{conversion_rate:.2f}%" if conversion_rate is not None else "-"),
            "target": target_conversion_rate,
            "target_label": (f"{target_conversion_rate:.2f}%" if target_conversion_rate is not None else "-"),
            "progress_pct": _kpi_progress(conversion_rate, target_conversion_rate),
            "lower_is_better": False,
        },
        {
            "id": "cpm",
            "title": "CPM",
            "value": cpm,
            "value_label": (f"S/ {cpm:.4f}" if cpm is not None else "-"),
            "target": target_cpm,
            "target_label": (f"S/ {target_cpm:.4f}" if target_cpm is not None else "-"),
            "progress_pct": _kpi_progress(cpm, target_cpm, lower_is_better=True),
            "lower_is_better": True,
        },
        {
            "id": "ctr",
            "title": "CTR",
            "value": ctr_pct,
            "value_label": (f"{ctr_pct:.4f}%" if ctr_pct is not None else "-"),
            "target": target_ctr,
            "target_label": (f"{target_ctr:.2f}%" if target_ctr is not None else "-"),
            "progress_pct": _kpi_progress(ctr_pct, target_ctr),
            "lower_is_better": False,
        },
    ]
    return kpis


def _build_marketing_okr_modules(base_data):
    modules = [
        {
            "id": "brand_digital",
            "title": "Posicionamiento de Marca - Digital",
            "measure": "Porcentaje (%)",
            "formula": "Incremento de los seguidores del año anterior.",
            "value": base_data.get("total_growth_pct"),
            "value_label": "Crecimiento de seguidores",
            "target": base_data.get("total_target"),
            "progress_pct": base_data.get("total_progress_pct"),
            "direction": "up" if (base_data.get("total_growth_pct") or 0) >= 0 else "down",
            "context": [
                f"Seguidores actuales: {base_data.get('total_followers') or 0}",
                f"Seguidores año anterior: {base_data.get('total_previous_followers') or 0}",
                f"Meta total: {base_data.get('total_target') or 0}",
            ],
        },
        {
            "id": "leads_obtenidos",
            "title": "Cantidad de Leads obtenidos",
            "measure": "Porcentaje (%)",
            "formula": "Incremento de Leads en comparación al año anterior.",
            "value": base_data.get("leads_growth_pct"),
            "value_label": "Crecimiento de leads",
            "target": base_data.get("leads_target"),
            "progress_pct": base_data.get("leads_progress_pct"),
            "direction": "up" if (base_data.get("leads_growth_pct") or 0) >= 0 else "down",
            "context": [
                f"Leads {base_data.get('leads_current_year_label')}: {base_data.get('leads_current_year') or 0}",
                f"Leads {base_data.get('leads_prev_year_label')}: {base_data.get('leads_prev_year') or 0}",
                f"Meta de leads: {base_data.get('leads_target') or 0}",
            ],
        },
        {
            "id": "retorno_inversion",
            "title": "Retorno de Inversión",
            "measure": "Porcentaje (%)",
            "formula": "Total Ventas Cerradas Leads / Total Inversión Marketing.",
            "value": base_data.get("roi_pct"),
            "value_label": "ROI de marketing",
            "target": None,
            "progress_pct": None,
            "direction": "up" if (base_data.get("roi_pct") or 0) >= 0 else "down",
            "context": [
                f"Ventas cerradas: {base_data.get('closed_sales_current_year') or 0}",
                f"Inversión marketing: S/ {base_data.get('marketing_investment_current_year') or 0}",
                f"Año evaluado: {base_data.get('leads_current_year_label')}",
            ],
        },
        {
            "id": "efectividad_leads",
            "title": "Efectividad de Leads",
            "measure": "Porcentaje (%)",
            "formula": "Total de Ventas Cerradas Leads / Total de Leads recibidos.",
            "value": base_data.get("lead_effectiveness_pct"),
            "value_label": "Efectividad comercial",
            "target": None,
            "progress_pct": None,
            "direction": "up" if (base_data.get("lead_effectiveness_pct") or 0) >= 0 else "down",
            "context": [
                f"Ventas cerradas: {base_data.get('closed_sales_current_year') or 0}",
                f"Leads recibidos: {base_data.get('leads_current_year') or 0}",
                f"Marca: {base_data.get('brand_label')}",
            ],
        },
    ]

    analysis_bundle = generate_marketing_okr_analyses(base_data.get("brand"), modules)
    analysis_items = analysis_bundle.get("items") or {}
    for module in modules:
        module["analysis"] = analysis_items.get(module.get("id"), {})
    return modules, analysis_bundle.get("engine") or "local"


def _compute_okr_for_brand(brand_slug, selected_year=None, period_type="anual", period_quarter=None, custom_start=None, custom_end=None):
    brand_prefix = brand_slug.upper()
    negocio_id = _resolve_negocio_id_by_brand(brand_slug)
    today = date.today()
    current_year = today.year
    selected_year = selected_year or current_year
    goals = _load_okr_goals(negocio_id, selected_year)

    safe_period_type = period_type or goals.get("period_type") or "anual"
    safe_period_quarter = period_quarter if period_quarter is not None else goals.get("period_quarter")
    safe_custom_start = custom_start if custom_start is not None else (
        goals.get("period_custom_start").isoformat() if goals.get("period_custom_start") else None
    )
    safe_custom_end = custom_end if custom_end is not None else (
        goals.get("period_custom_end").isoformat() if goals.get("period_custom_end") else None
    )
    period = _resolve_period_range(
        selected_year,
        safe_period_type,
        safe_period_quarter,
        safe_custom_start,
        safe_custom_end,
    )

    meta_token = os.getenv(f"{brand_prefix}_META_ACCESS_TOKEN", "").strip()
    api_ver = os.getenv(f"{brand_prefix}_META_API_VERSION", os.getenv(f"{brand_prefix}_WA_API_VERSION", "v20.0")).strip() or "v20.0"
    fb_page_id = os.getenv(f"{brand_prefix}_FB_PAGE_ID", "").strip()
    ig_account_id = os.getenv(f"{brand_prefix}_IG_ACCOUNT_ID", "").strip()
    fb_target_int = goals.get("fb_target_followers") or _to_int(os.getenv(f"{brand_prefix}_FB_TARGET_FOLLOWERS", "").strip())
    ig_target_int = goals.get("ig_target_followers") or _to_int(os.getenv(f"{brand_prefix}_IG_TARGET_FOLLOWERS", "").strip())
    leads_target = goals.get("leads_target") or _to_int(os.getenv(f"{brand_prefix}_LEADS_TARGET", "").strip())
    fb_prev_manual = goals.get("fb_previous_followers_manual")
    ig_prev_manual = goals.get("ig_previous_followers_manual")
    leads_prev_manual = goals.get("leads_previous_manual")

    fb_data = None
    ig_data = None
    errors = []

    if meta_token and fb_page_id:
        fb_data = _fetch_facebook_followers(fb_page_id, meta_token, api_ver)
        if fb_data.get("error"):
            errors.append(f"Facebook: {fb_data['error']}")
    elif fb_page_id:
        errors.append("Facebook: falta META_ACCESS_TOKEN o FB_PAGE_ID.")

    if meta_token and (ig_account_id or fb_page_id):
        ig_data = _fetch_instagram_followers_with_fallback(ig_account_id, fb_page_id, meta_token, api_ver)
        if ig_data.get("error"):
            errors.append(f"Instagram: {ig_data['error']}")
    elif ig_account_id:
        errors.append("Instagram: falta META_ACCESS_TOKEN o IG_ACCOUNT_ID.")

    current_total = None
    previous_total = None
    if fb_data or ig_data:
        current_total = (fb_data.get("current") or 0 if fb_data else 0) + (ig_data.get("current") or 0 if ig_data else 0)
        previous_total = (fb_data.get("previous") or 0 if fb_data else 0) + (ig_data.get("previous") or 0 if ig_data else 0)

    total_target = (fb_target_int or 0) + (ig_target_int or 0)
    history_rows = _load_social_metrics_history(negocio_id) if negocio_id else []
    if negocio_id and (fb_data or ig_data):
        _save_social_metrics_snapshot(
            negocio_id=negocio_id,
            snapshot_date=date.today(),
            fb_page_id=fb_page_id,
            ig_account_id=ig_account_id,
            fb_followers=fb_data.get("current") if fb_data else None,
            ig_followers=ig_data.get("current") if ig_data else None,
            total_followers=current_total,
            fb_target=fb_target_int,
            ig_target=ig_target_int,
            total_target=total_target,
        )
        history_rows = _load_social_metrics_history(negocio_id)

    period_start = period.get("start")
    period_end = period.get("end")
    period_error = period.get("error")
    if period_error:
        errors.append(period_error)
        period_start = date(selected_year, 1, 1)
        period_end = date(selected_year, 12, 31)
        period = _resolve_period_range(selected_year, "anual")

    prev_start = _shift_year_safe(period_start, -1)
    prev_end = _shift_year_safe(period_end, -1)

    leads_current_year = _count_leads_in_range(negocio_id, period_start, period_end)
    leads_prev_year_auto = _count_leads_in_range(negocio_id, prev_start, prev_end)
    # Manual toma prioridad: si el usuario llenó el dato manualmente, ese se usa (ej. primer año
    # donde la data previa en BD son datos de prueba). Años siguientes, cuando no haya valor
    # manual configurado, el sistema toma los leads recopilados automáticamente.
    leads_prev_year = leads_prev_manual if leads_prev_manual is not None else leads_prev_year_auto
    leads_growth_pct = _calculate_growth(leads_current_year, leads_prev_year) if leads_current_year is not None and leads_prev_year else None
    leads_progress_pct = round((leads_current_year / leads_target) * 100, 2) if leads_target and leads_current_year else None
    closed_sales_current_year = _count_closed_sales_by_year(negocio_id, selected_year)
    marketing_investment_current_year = _sum_marketing_investment_by_year(brand_slug, negocio_id, selected_year)

    # Baseline automático para el siguiente año: último snapshot al cierre del año previo.
    prev_year_end_snapshot = _latest_snapshot_upto(negocio_id, date(selected_year - 1, 12, 31))
    if prev_year_end_snapshot:
        fb_prev_auto = _to_int(prev_year_end_snapshot.get("fb_followers"))
        ig_prev_auto = _to_int(prev_year_end_snapshot.get("ig_followers"))
        total_prev_auto = _to_int(prev_year_end_snapshot.get("total_followers"))
    else:
        fb_prev_auto = fb_data.get("previous") if fb_data else None
        ig_prev_auto = ig_data.get("previous") if ig_data else None
        total_prev_auto = None

    # Manual toma prioridad para seguidores: si el usuario llenó el dato manualmente se usa ese
    # (ej. primer año sin snapshots previos). Años siguientes, cuando no hay valor manual,
    # el sistema usa el snapshot auto-capturado al cierre del año anterior.
    fb_previous_followers = fb_prev_manual if fb_prev_manual is not None else fb_prev_auto
    ig_previous_followers = ig_prev_manual if ig_prev_manual is not None else ig_prev_auto
    if fb_previous_followers is not None or ig_previous_followers is not None:
        previous_total = (fb_previous_followers or 0) + (ig_previous_followers or 0)
    elif total_prev_auto is not None:
        previous_total = total_prev_auto
    roi_pct = None
    if marketing_investment_current_year and marketing_investment_current_year > 0 and closed_sales_current_year is not None:
        roi_pct = round((closed_sales_current_year / float(marketing_investment_current_year)) * 100, 2)
    lead_effectiveness_pct = None
    if leads_current_year and closed_sales_current_year is not None:
        lead_effectiveness_pct = round((closed_sales_current_year / leads_current_year) * 100, 2)

    base_data = {
        "brand": brand_slug,
        "brand_label": brand_slug.capitalize(),
        "negocio_id": negocio_id,
        "api_ver": api_ver,
        "fb_page_id": fb_page_id,
        "ig_account_id": ig_account_id,
        "facebook_followers": fb_data.get("current") if fb_data else None,
        "facebook_previous_followers": fb_previous_followers,
        "facebook_growth_pct": fb_data.get("growth_pct") if fb_data else None,
        "fb_target": fb_target_int,
        "fb_progress_pct": round((fb_data.get("current") / fb_target_int) * 100, 2) if fb_target_int and fb_data and fb_data.get("current") else None,
        "instagram_followers": ig_data.get("current") if ig_data else None,
        "instagram_previous_followers": ig_previous_followers,
        "instagram_growth_pct": ig_data.get("growth_pct") if ig_data else None,
        "ig_target": ig_target_int,
        "ig_progress_pct": round((ig_data.get("current") / ig_target_int) * 100, 2) if ig_target_int and ig_data and ig_data.get("current") else None,
        "total_followers": current_total,
        "total_previous_followers": previous_total,
        "total_growth_pct": _calculate_growth(current_total, previous_total) if current_total is not None and previous_total is not None else None,
        "total_target": total_target if total_target > 0 else None,
        "total_progress_pct": round((current_total / total_target) * 100, 2) if total_target and current_total else None,
        "leads_current_year": leads_current_year,
        "leads_current_year_label": period.get("label"),
        "leads_prev_year": leads_prev_year,
        "leads_prev_year_label": f"{prev_start.isoformat()} a {prev_end.isoformat()}",
        "leads_growth_pct": leads_growth_pct,
        "leads_target": leads_target,
        "leads_progress_pct": leads_progress_pct,
        "closed_sales_current_year": closed_sales_current_year,
        "marketing_investment_current_year": float(marketing_investment_current_year) if marketing_investment_current_year is not None else None,
        "roi_pct": roi_pct,
        "lead_effectiveness_pct": lead_effectiveness_pct,
        "history_rows": history_rows,
        "errors": errors,
        "okr_goal_year": selected_year,
        "okr_goal_fb_target": fb_target_int,
        "okr_goal_ig_target": ig_target_int,
        "okr_goal_leads_target": leads_target,
        "okr_prev_fb_manual": fb_prev_manual,
        "okr_prev_ig_manual": ig_prev_manual,
        "okr_prev_leads_manual": leads_prev_manual,
        "okr_period_type": period.get("period_type"),
        "okr_period_quarter": period.get("period_quarter"),
        "okr_period_custom_start": period.get("custom_start"),
        "okr_period_custom_end": period.get("custom_end"),
        "okr_period_label": period.get("label"),
        "okr_period_start": period_start.isoformat() if period_start else None,
        "okr_period_end": period_end.isoformat() if period_end else None,
    }
    okr_modules, okr_analysis_engine = _build_marketing_okr_modules(base_data)
    base_data["okr_modules"] = okr_modules
    base_data["okr_analysis_engine"] = okr_analysis_engine
    base_data["kpi_cards"] = _build_kpi_cards_for_brand(brand_slug)
    return base_data


@marketing_bp.route("/okr", methods=["GET"])
@login_required
@role_required(ROLE_ADMIN)
def marketing_okr():
    brand = (request.cookies.get("brand") or "orbes").strip().lower()
    selected_year = _to_int(request.args.get("year")) or date.today().year
    period_type = (request.args.get("period") or "").strip().lower() or None
    period_quarter = _to_int(request.args.get("quarter"))
    custom_start = (request.args.get("start_date") or "").strip() or None
    custom_end = (request.args.get("end_date") or "").strip() or None
    bd = _compute_okr_for_brand(brand, selected_year, period_type, period_quarter, custom_start, custom_end)
    return render_template("marketing/okr.html", bd=bd)


@marketing_bp.route("/okr/goals", methods=["POST"])
@login_required
@role_required(ROLE_ADMIN)
def marketing_okr_goals():
    brand = (request.cookies.get("brand") or "orbes").strip().lower()
    negocio_id = _resolve_negocio_id_by_brand(brand)
    if not negocio_id:
        return jsonify({"ok": False, "message": "No se pudo resolver el negocio de la marca activa."}), 400

    payload = request.get_json(silent=True) or {}
    year = _to_int(payload.get("year")) or date.today().year
    fb_target = _to_int(payload.get("fb_target_followers"))
    ig_target = _to_int(payload.get("ig_target_followers"))
    leads_target = _to_int(payload.get("leads_target"))
    fb_prev_manual = _to_int(payload.get("fb_previous_followers_manual"))
    ig_prev_manual = _to_int(payload.get("ig_previous_followers_manual"))
    leads_prev_manual = _to_int(payload.get("leads_previous_manual"))
    period_type = (payload.get("period_type") or "anual").strip().lower()
    period_quarter = _to_int(payload.get("period_quarter"))
    period_custom_start = _parse_iso_date(payload.get("period_custom_start"))
    period_custom_end = _parse_iso_date(payload.get("period_custom_end"))

    if period_type not in ("anual", "trimestre", "personalizado"):
        return jsonify({"ok": False, "message": "Periodo inválido. Usa anual, trimestre o personalizado."}), 400
    if period_type == "trimestre" and period_quarter not in (1, 2, 3, 4):
        return jsonify({"ok": False, "message": "El trimestre debe estar entre 1 y 4."}), 400
    if period_type == "personalizado":
        if not period_custom_start or not period_custom_end:
            return jsonify({"ok": False, "message": "Debes indicar fecha de inicio y fin para el rango personalizado."}), 400
        if period_custom_start > period_custom_end:
            return jsonify({"ok": False, "message": "La fecha de inicio no puede ser mayor que la fecha fin."}), 400

    current = _load_okr_goals(negocio_id, year)
    current_fb = current.get("fb_target_followers")
    current_ig = current.get("ig_target_followers")
    current_leads = current.get("leads_target")
    current_fb_prev = current.get("fb_previous_followers_manual")
    current_ig_prev = current.get("ig_previous_followers_manual")
    current_leads_prev = current.get("leads_previous_manual")

    fb_target = fb_target if fb_target is not None else current_fb
    ig_target = ig_target if ig_target is not None else current_ig
    leads_target = leads_target if leads_target is not None else current_leads
    fb_prev_manual = fb_prev_manual if fb_prev_manual is not None else current_fb_prev
    ig_prev_manual = ig_prev_manual if ig_prev_manual is not None else current_ig_prev
    leads_prev_manual = leads_prev_manual if leads_prev_manual is not None else current_leads_prev

    if leads_target is not None and leads_target <= 0:
        return jsonify({"ok": False, "message": "La meta de leads debe ser mayor a 0."}), 400

    saved = _save_okr_goals(
        negocio_id,
        year,
        fb_target,
        ig_target,
        leads_target,
        fb_prev_manual,
        ig_prev_manual,
        leads_prev_manual,
        period_type,
        period_quarter,
        period_custom_start,
        period_custom_end,
    )
    if not saved:
        return jsonify({"ok": False, "message": "No se pudieron guardar las metas OKR."}), 500

    resolved_period = _resolve_period_range(
        year,
        period_type,
        period_quarter,
        period_custom_start.isoformat() if period_custom_start else None,
        period_custom_end.isoformat() if period_custom_end else None,
    )
    prev_start = _shift_year_safe(resolved_period.get("start"), -1) if resolved_period.get("start") else None
    prev_end = _shift_year_safe(resolved_period.get("end"), -1) if resolved_period.get("end") else None
    leads_prev_year = _count_leads_in_range(negocio_id, prev_start, prev_end) if prev_start and prev_end else None
    return jsonify(
        {
            "ok": True,
            "year": year,
            "leads_prev_year": int(leads_prev_year or 0),
            "fb_target_followers": fb_target,
            "ig_target_followers": ig_target,
            "leads_target": leads_target,
            "fb_previous_followers_manual": fb_prev_manual,
            "ig_previous_followers_manual": ig_prev_manual,
            "leads_previous_manual": leads_prev_manual,
            "period_type": period_type,
            "period_quarter": period_quarter,
            "period_custom_start": period_custom_start.isoformat() if period_custom_start else None,
            "period_custom_end": period_custom_end.isoformat() if period_custom_end else None,
            "message": "Metas OKR guardadas correctamente.",
        }
    )