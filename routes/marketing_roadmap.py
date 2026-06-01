from routes.marketing import (
    Decimal,
    DictCursor,
    ROLE_ADMIN,
    ROLE_GERENTE,
    ROLE_MARKETING,
    _column_exists,
    _latest_seguimiento_subquery,
    _table_exists,
    jsonify,
    login_required,
    marketing_bp,
    mysql,
    render_template,
    request,
    role_required,
    url_for,
)
import unicodedata
from datetime import date, datetime, timedelta


SPECIAL_EVENT_TYPES = {
    "revista",
    "medio especial",
    "medios especiales",
    "evento corporativo",
    "eventos corporativos",
    "viaje",
    "viajes",
}

TABLE_ROW_LIMIT = 7


def _as_decimal(value):
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    try:
        return Decimal(str(value))
    except Exception:
        return Decimal("0")


def _safe_rois(total_ventas_cerradas, total_inversion):
    inversion = _as_decimal(total_inversion)
    if inversion <= 0:
        return None
    return float(Decimal(int(total_ventas_cerradas or 0)) / inversion)


def _format_ratio(value, digits=4):
    return f"{value:.{digits}f}" if value is not None else "-"


def _format_percent(value, digits=2):
    return f"{value:.{digits}f}%" if value is not None else "-"


def _serialize_rois_rows(rows):
    items = []
    for row in rows:
        items.append(
            {
                "id": int(row.get("id") or 0),
                "name": str(row.get("name") or ""),
                "closed_sales": int(row.get("closed_sales") or 0),
                "investment": _format_money(row.get("investment")),
                "rois": _format_ratio(row.get("rois"), 4),
                "rois_percent": _format_percent(row.get("rois_percent"), 2),
                "detail_url": row.get("detail_url") or "#",
            }
        )
    return items


def _resolve_negocio_id(brand_slug):
    if not _table_exists("negocios"):
        return None

    cur = mysql.connection.cursor(DictCursor)
    try:
        cur.execute("SELECT id FROM negocios WHERE slug = %s LIMIT 1", (brand_slug,))
        row = cur.fetchone() or {}
        return row.get("id")
    except Exception:
        return None
    finally:
        cur.close()


def _scope_where(table_name, alias, brand_slug, negocio_id):
    if _column_exists(table_name, "negocio_id") and negocio_id:
        return f"{alias}.negocio_id = %s", [negocio_id]
    if _column_exists(table_name, "brand"):
        return f"{alias}.brand = %s", [brand_slug]
    return "1=1", []


def _normalize_label(raw_value):
    value = str(raw_value or "").strip().lower()
    normalized = unicodedata.normalize("NFKD", value)
    return "".join(ch for ch in normalized if ord(ch) < 128).strip()


def _format_money(value):
    return f"S/ {_as_decimal(value):,.2f}"


def _parse_iso_date(raw_value):
    raw = (raw_value or "").strip()
    if not raw:
        return None
    try:
        return datetime.strptime(raw, "%Y-%m-%d").date()
    except Exception:
        return None


def _resolve_period_filter(period_raw, start_date_raw, end_date_raw):
    period = (period_raw or "all").strip().lower()
    if period not in {"all", "day", "week", "month", "custom"}:
        period = "all"

    start_date = None
    end_date = None
    today = date.today()

    if period == "day":
        start_date = today
        end_date = today
    elif period == "week":
        end_date = today
        start_date = today - timedelta(days=6)
    elif period == "month":
        end_date = today
        start_date = today - timedelta(days=29)
    elif period == "custom":
        start_date = _parse_iso_date(start_date_raw)
        end_date = _parse_iso_date(end_date_raw)
        if not start_date or not end_date:
            period = "all"
            start_date = None
            end_date = None
        elif start_date > end_date:
            start_date, end_date = end_date, start_date

    return {
        "period": period,
        "start_date": start_date,
        "end_date": end_date,
        "start_date_str": start_date.isoformat() if start_date else "",
        "end_date_str": end_date.isoformat() if end_date else "",
    }


def _period_presentation(period_ctx):
    period = period_ctx.get("period") or "all"
    start_date = period_ctx.get("start_date")
    end_date = period_ctx.get("end_date")
    labels = {
        "all": "Todo",
        "day": "Día",
        "week": "Última semana",
        "month": "Último mes",
        "custom": "Rango personalizado",
    }
    label = labels.get(period, "Todo")
    if start_date and end_date:
        return label, f"{start_date.strftime('%d/%m/%Y')} - {end_date.strftime('%d/%m/%Y')}"
    return label, "Sin límite de fechas"


def _apply_campaign_period_filter(base_where, base_params, period_ctx):
    where = base_where
    params = list(base_params)
    start_date = period_ctx.get("start_date")
    end_date = period_ctx.get("end_date")
    if start_date and end_date:
        where += (
            " AND COALESCE(c.periodo_inicio, c.fecha_lanzamiento) <= %s"
            " AND COALESCE(c.periodo_fin, c.fecha_lanzamiento) >= %s"
        )
        params.extend([end_date.isoformat(), start_date.isoformat()])
    return where, params


def _apply_feria_period_filter(base_where, base_params, period_ctx):
    where = base_where
    params = list(base_params)
    start_date = period_ctx.get("start_date")
    end_date = period_ctx.get("end_date")
    if start_date and end_date:
        where += " AND f.fecha_inicio <= %s AND f.fecha_fin >= %s"
        params.extend([end_date.isoformat(), start_date.isoformat()])
    return where, params


def _build_roadmap_context(
    brand,
    period_raw=None,
    start_date_raw=None,
    end_date_raw=None,
    return_next=None,
):
    negocio_id = _resolve_negocio_id(brand)
    period_ctx = _resolve_period_filter(period_raw, start_date_raw, end_date_raw)

    campaign_scope_where, campaign_scope_params = _scope_where(
        "marketing_campaigns", "c", brand, negocio_id
    )
    feria_scope_where, feria_scope_params = _scope_where(
        "marketing_ferias", "f", brand, negocio_id
    )
    campaign_where, campaign_params = _apply_campaign_period_filter(
        campaign_scope_where, campaign_scope_params, period_ctx
    )
    feria_where, feria_params = _apply_feria_period_filter(
        feria_scope_where, feria_scope_params, period_ctx
    )

    latest_seg = _latest_seguimiento_subquery()

    cur = mysql.connection.cursor(DictCursor)
    try:
        cur.execute(
            f"""
            SELECT
                c.id,
                c.nombre_campana,
                COALESCE(c.inversion, 0) AS inversion,
                COALESCE(c.impresiones, 0) AS impresiones,
                COALESCE(c.alcance, 0) AS alcance
            FROM marketing_campaigns c
            WHERE {campaign_where}
            ORDER BY c.nombre_campana ASC
            """,
            tuple(campaign_params),
        )
        campaigns = cur.fetchall() or []

        leads_sql = f"""
            SELECT COUNT(*) AS total_leads
            FROM marketing_campaign_leads mcl
            INNER JOIN marketing_campaigns c ON c.id = mcl.campaign_id
            INNER JOIN leads l ON l.id = mcl.lead_id
            WHERE {campaign_where}
        """
        leads_params = list(campaign_params)
        if period_ctx.get("start_date") and period_ctx.get("end_date"):
            leads_sql += " AND DATE(l.fecha) BETWEEN %s AND %s"
            leads_params.extend([
                period_ctx["start_date"].isoformat(),
                period_ctx["end_date"].isoformat(),
            ])
        cur.execute(
            leads_sql,
            tuple(leads_params),
        )
        campaign_leads_row = cur.fetchone() or {}

        campaign_sales_sql = f"""
            SELECT
                mcl.campaign_id,
                COUNT(*) AS ventas_cerradas
            FROM marketing_campaign_leads mcl
            INNER JOIN marketing_campaigns c ON c.id = mcl.campaign_id
            INNER JOIN leads l ON l.id = mcl.lead_id
            LEFT JOIN ({latest_seg}) s ON s.lead_id = l.id
            LEFT JOIN proceso p ON p.id = s.proceso_id
            WHERE {campaign_where}
              AND LOWER(TRIM(COALESCE(p.nombre_proceso, ''))) = 'cerrado'
        """
        campaign_sales_params = list(campaign_params)
        if period_ctx.get("start_date") and period_ctx.get("end_date"):
            campaign_sales_sql += " AND DATE(s.fecha_guardado) BETWEEN %s AND %s"
            campaign_sales_params.extend([
                period_ctx["start_date"].isoformat(),
                period_ctx["end_date"].isoformat(),
            ])
        campaign_sales_sql += " GROUP BY mcl.campaign_id"
        cur.execute(
            campaign_sales_sql,
            tuple(campaign_sales_params),
        )
        campaign_sales_rows = cur.fetchall() or []

        cur.execute(
            f"""
            SELECT
                f.id,
                f.nombre,
                COALESCE(f.tipo, '') AS tipo,
                COALESCE(f.total_inversion, 0) AS total_inversion
            FROM marketing_ferias f
            WHERE {feria_where}
            ORDER BY f.nombre ASC
            """,
            tuple(feria_params),
        )
        ferias = cur.fetchall() or []

        feria_sales_sql = f"""
            SELECT
                l.feria_id,
                COUNT(*) AS ventas_cerradas
            FROM leads l
            INNER JOIN marketing_ferias f ON f.id = l.feria_id
            LEFT JOIN ({latest_seg}) s ON s.lead_id = l.id
            LEFT JOIN proceso p ON p.id = s.proceso_id
            WHERE l.feria_id IS NOT NULL
              AND {feria_where}
              AND LOWER(TRIM(COALESCE(p.nombre_proceso, ''))) = 'cerrado'
        """
        feria_sales_params = list(feria_params)
        if period_ctx.get("start_date") and period_ctx.get("end_date"):
            feria_sales_sql += " AND DATE(s.fecha_guardado) BETWEEN %s AND %s"
            feria_sales_params.extend([
                period_ctx["start_date"].isoformat(),
                period_ctx["end_date"].isoformat(),
            ])
        feria_sales_sql += " GROUP BY l.feria_id"
        cur.execute(
            feria_sales_sql,
            tuple(feria_sales_params),
        )
        feria_sales_rows = cur.fetchall() or []
    finally:
        cur.close()

    campaign_sales_map = {
        int(row.get("campaign_id")): int(row.get("ventas_cerradas") or 0)
        for row in campaign_sales_rows
        if row.get("campaign_id") is not None
    }
    feria_sales_map = {
        int(row.get("feria_id")): int(row.get("ventas_cerradas") or 0)
        for row in feria_sales_rows
        if row.get("feria_id") is not None
    }

    total_campaigns = len(campaigns)
    total_campaign_closed_sales = sum(campaign_sales_map.values())
    total_campaign_leads = int(campaign_leads_row.get("total_leads") or 0)
    total_campaign_inversion = sum(
        (_as_decimal(c.get("inversion")) for c in campaigns), Decimal("0")
    )
    total_campaign_impresiones = sum(int(c.get("impresiones") or 0) for c in campaigns)
    total_campaign_alcance = sum(int(c.get("alcance") or 0) for c in campaigns)

    campaign_rois_rows = []
    campaign_detail_query = {"next": return_next} if return_next else {}
    for campaign in campaigns:
        campaign_id = int(campaign.get("id") or 0)
        inversion = _as_decimal(campaign.get("inversion"))
        ventas_cerradas = campaign_sales_map.get(campaign_id, 0)
        rois_value = _safe_rois(ventas_cerradas, inversion)
        campaign_rois_rows.append(
            {
                "id": campaign_id,
                "name": campaign.get("nombre_campana") or f"Campaña #{campaign_id}",
                "closed_sales": ventas_cerradas,
                "investment": inversion,
                "rois": rois_value,
                "rois_percent": (rois_value * 100.0) if rois_value is not None else None,
                "detail_url": url_for(
                    "marketing.marketing_campaign_results", campaign_id=campaign_id, **campaign_detail_query
                ),
            }
        )
    campaign_rois_rows = campaign_rois_rows[:TABLE_ROW_LIMIT]

    campaign_cac = (
        float(total_campaign_inversion / Decimal(total_campaign_closed_sales))
        if total_campaign_closed_sales > 0
        else None
    )
    campaign_cpc = (
        float(total_campaign_inversion / Decimal(total_campaign_alcance))
        if total_campaign_alcance > 0
        else None
    )
    campaign_conversion_rate = (
        float(Decimal(total_campaign_closed_sales) / Decimal(total_campaign_leads) * Decimal("100"))
        if total_campaign_leads > 0
        else 0.0
    )
    campaign_cpm = (
        float(total_campaign_inversion / Decimal(total_campaign_impresiones))
        if total_campaign_impresiones > 0
        else None
    )
    campaign_ctr = (
        float(Decimal(total_campaign_leads) / Decimal(total_campaign_impresiones))
        if total_campaign_impresiones > 0
        else None
    )

    total_ferias_demostraciones = 0
    total_special_events = 0
    for feria in ferias:
        tipo = _normalize_label(feria.get("tipo"))
        if tipo in {"feria", "demostracion"}:
            total_ferias_demostraciones += 1
        elif tipo in SPECIAL_EVENT_TYPES:
            total_special_events += 1

    total_feria_closed_sales = sum(feria_sales_map.values())
    total_feria_inversion = sum(
        (_as_decimal(f.get("total_inversion")) for f in ferias), Decimal("0")
    )

    feria_rois_rows = []
    feria_detail_query = {"next": return_next} if return_next else {}
    for feria in ferias:
        feria_id = int(feria.get("id") or 0)
        inversion = _as_decimal(feria.get("total_inversion"))
        ventas_cerradas = feria_sales_map.get(feria_id, 0)
        rois_value = _safe_rois(ventas_cerradas, inversion)
        feria_rois_rows.append(
            {
                "id": feria_id,
                "name": feria.get("nombre") or f"Feria #{feria_id}",
                "closed_sales": ventas_cerradas,
                "investment": inversion,
                "rois": rois_value,
                "rois_percent": (rois_value * 100.0) if rois_value is not None else None,
                "detail_url": url_for(
                    "marketing.marketing_feria_resultados", feria_id=feria_id, **feria_detail_query
                ),
            }
        )
    feria_rois_rows = feria_rois_rows[:TABLE_ROW_LIMIT]

    total_global_closed_sales = total_campaign_closed_sales + total_feria_closed_sales
    total_global_inversion = total_campaign_inversion + total_feria_inversion
    period_label, period_range_label = _period_presentation(period_ctx)

    rois_global = _safe_rois(total_global_closed_sales, total_global_inversion)
    rois_campaign = _safe_rois(total_campaign_closed_sales, total_campaign_inversion)
    rois_feria = _safe_rois(total_feria_closed_sales, total_feria_inversion)

    return {
        "campaigns": campaigns,
        "ferias": ferias,
        "selected_period": period_ctx.get("period") or "all",
        "selected_start_date": period_ctx.get("start_date_str") or "",
        "selected_end_date": period_ctx.get("end_date_str") or "",
        "selected_period_label": period_label,
        "selected_period_range_label": period_range_label,
        "total_campaigns": total_campaigns,
        "total_ferias_demostraciones": total_ferias_demostraciones,
        "total_special_events": total_special_events,
        "total_campaign_closed_sales": total_campaign_closed_sales,
        "total_campaign_leads": total_campaign_leads,
        "total_campaign_inversion": total_campaign_inversion,
        "total_campaign_impresiones": total_campaign_impresiones,
        "total_campaign_alcance": total_campaign_alcance,
        "campaign_cac": campaign_cac,
        "campaign_cpc": campaign_cpc,
        "campaign_conversion_rate": campaign_conversion_rate,
        "campaign_cpm": campaign_cpm,
        "campaign_ctr": campaign_ctr,
        "campaign_rois_rows": campaign_rois_rows,
        "total_feria_closed_sales": total_feria_closed_sales,
        "total_feria_inversion": total_feria_inversion,
        "feria_rois_rows": feria_rois_rows,
        "total_global_closed_sales": total_global_closed_sales,
        "total_global_inversion": total_global_inversion,
        "rois_global": rois_global,
        "rois_campaign": rois_campaign,
        "rois_feria": rois_feria,
    }


def _roadmap_live_payload(context):
    return {
        "ok": True,
        "period_label": context.get("selected_period_label") or "Todo",
        "period_range_label": context.get("selected_period_range_label") or "Sin límite de fechas",
        "total_campaigns": int(context.get("total_campaigns") or 0),
        "total_ferias_demostraciones": int(context.get("total_ferias_demostraciones") or 0),
        "total_special_events": int(context.get("total_special_events") or 0),
        "rois_global": _format_ratio(context.get("rois_global"), 4),
        "rois_campaign": _format_ratio(context.get("rois_campaign"), 4),
        "rois_feria": _format_ratio(context.get("rois_feria"), 4),
        "total_global_closed_sales": int(context.get("total_global_closed_sales") or 0),
        "total_campaign_closed_sales": int(context.get("total_campaign_closed_sales") or 0),
        "total_feria_closed_sales": int(context.get("total_feria_closed_sales") or 0),
        "total_global_inversion": _format_money(context.get("total_global_inversion")),
        "total_campaign_inversion": _format_money(context.get("total_campaign_inversion")),
        "total_feria_inversion": _format_money(context.get("total_feria_inversion")),
        "campaign_cac": _format_money(context.get("campaign_cac")) if context.get("campaign_cac") is not None else "-",
        "campaign_cpc": _format_money(context.get("campaign_cpc")) if context.get("campaign_cpc") is not None else "-",
        "campaign_conversion_rate": f"{float(context.get('campaign_conversion_rate') or 0):.2f}%",
        "campaign_cpm": _format_money(context.get("campaign_cpm")) if context.get("campaign_cpm") is not None else "-",
        "campaign_ctr": _format_ratio(context.get("campaign_ctr"), 6),
        "total_campaign_leads": int(context.get("total_campaign_leads") or 0),
        "total_campaign_impresiones": int(context.get("total_campaign_impresiones") or 0),
        "total_campaign_alcance": int(context.get("total_campaign_alcance") or 0),
        "campaign_rois_rows": _serialize_rois_rows(context.get("campaign_rois_rows") or []),
        "feria_rois_rows": _serialize_rois_rows(context.get("feria_rois_rows") or []),
    }


@marketing_bp.route("/roadmap", methods=["GET"])
@login_required
@role_required(ROLE_ADMIN)
def marketing_roadmap():
    brand = request.cookies.get("brand") or "orbes"
    next_params = {}
    for key in ("period", "start_date", "end_date"):
        value = (request.args.get(key) or "").strip()
        if value:
            next_params[key] = value
    return_next = url_for("marketing.marketing_roadmap", **next_params)
    context = _build_roadmap_context(
        brand,
        request.args.get("period"),
        request.args.get("start_date"),
        request.args.get("end_date"),
        return_next,
    )
    return render_template("marketing/roadmap.html", **context)


@marketing_bp.route("/roadmap/live", methods=["GET"])
@login_required
@role_required(ROLE_ADMIN)
def marketing_roadmap_live():
    brand = request.cookies.get("brand") or "orbes"
    next_params = {}
    for key in ("period", "start_date", "end_date"):
        value = (request.args.get(key) or "").strip()
        if value:
            next_params[key] = value
    return_next = url_for("marketing.marketing_roadmap", **next_params)
    context = _build_roadmap_context(
        brand,
        request.args.get("period"),
        request.args.get("start_date"),
        request.args.get("end_date"),
        return_next,
    )
    return jsonify(_roadmap_live_payload(context)), 200
