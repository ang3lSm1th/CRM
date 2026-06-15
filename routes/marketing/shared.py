from flask import Blueprint, render_template, session, jsonify, request, redirect, url_for, flash
from extensions import mysql
from MySQLdb.cursors import DictCursor
from utils.security import (
    login_required,
    role_required,
    ROLE_ADMIN,
    ROLE_GERENTE,
    ROLE_MARKETING,
)
import os
from datetime import datetime, date, timedelta
from decimal import Decimal, InvalidOperation
from werkzeug.utils import secure_filename
import requests


marketing_bp = Blueprint("marketing", __name__)


@marketing_bp.before_request
@login_required
@role_required(ROLE_ADMIN, ROLE_GERENTE, ROLE_MARKETING)
def _marketing_before_request():
    return None


@marketing_bp.route("/api/lineas_producto", methods=["GET"])
def marketing_lineas_producto_underscore_api():
    """Devuelve las líneas de producto filtradas por id de familia (id_familia)."""
    linea_familia_id = request.args.get("linea_familia_id")
    if not linea_familia_id or not _table_exists("linea_producto"):
        return jsonify({"items": []})
    cur = mysql.connection.cursor(DictCursor)
    try:
        cur.execute(
            """
            SELECT lp.id, lp.nombre
            FROM linea_producto lp
            WHERE lp.id_familia = %s
            ORDER BY lp.nombre
            """,
            (linea_familia_id,),
        )
        items = cur.fetchall() or []
        return jsonify({"items": items})
    finally:
        cur.close()


DEPARTAMENTOS = {
    "1": "Amazonas",
    "2": "Ancash",
    "3": "Apurimac",
    "4": "Arequipa",
    "5": "Ayacucho",
    "6": "Cajamarca",
    "7": "Callao",
    "8": "Cusco",
    "9": "Huancavelica",
    "10": "Huanuco",
    "11": "Ica",
    "12": "Junin",
    "13": "La Libertad",
    "14": "Lambayeque",
    "15": "Lima",
    "16": "Loreto",
    "17": "Madre de Dios",
    "18": "Moquegua",
    "19": "Pasco",
    "20": "Piura",
    "21": "Puno",
    "22": "San Martin",
    "23": "Tacna",
    "24": "Tumbes",
    "25": "Ucayali",
}

CAMPAIGN_CHANNELS = {
    "meta": "Meta",
    "google_ads": "Google Ads",
    "correo": "Correo",
    "feria": "Feria",
}

CHANNEL_LEAD_NAME_FILTERS = {
    "meta": ["meta", "facebook", "facebook ads", "instagram", "instagram ads", "fb"],
    "google_ads": ["google ads", "google", "adwords"],
    "correo": ["correo", "email", "mail"],
}


def obtener_nombre_departamento(id_dept):
    if not id_dept:
        return "Sin especificar"
    id_str = str(id_dept).strip()
    return DEPARTAMENTOS.get(id_str, id_str)


def _to_decimal(value):
    raw = (value or "").strip()
    if not raw:
        return None
    normalized = raw.replace(",", "")
    try:
        return Decimal(normalized)
    except (InvalidOperation, ValueError):
        return None


def _table_exists(table_name):
    cur = mysql.connection.cursor(DictCursor)
    try:
        cur.execute(
            """
            SELECT COUNT(*) AS total
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s
            """,
            (table_name,),
        )
        row = cur.fetchone() or {}
        return int(row.get("total") or 0) > 0
    finally:
        cur.close()


def _column_exists(table_name, column_name):
    cur = mysql.connection.cursor(DictCursor)
    try:
        cur.execute(
            """
            SELECT COUNT(*) AS total
            FROM information_schema.COLUMNS
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = %s
              AND COLUMN_NAME = %s
            """,
            (table_name, column_name),
        )
        row = cur.fetchone() or {}
        return int(row.get("total") or 0) > 0
    finally:
        cur.close()


def _resolve_ubigeo_name(level, raw_value):
    value = (raw_value or "").strip()
    if not value:
        return ""

    if not value.isdigit():
        return value

    lookups = {
        "departamento": ("departamentos", "idDepartamento", "departamento"),
        "provincia": ("provincia", "idProvincia", "provincia"),
        "distrito": ("distrito", "idDistrito", "distrito"),
    }
    if level not in lookups:
        return value

    table_name, id_col, name_col = lookups[level]
    cur = mysql.connection.cursor(DictCursor)
    try:
        cur.execute(
            f"SELECT {name_col} AS nombre FROM {table_name} WHERE {id_col} = %s LIMIT 1",
            (value,),
        )
        row = cur.fetchone() or {}
        return (row.get("nombre") or value).strip()
    except Exception:
        return value
    finally:
        cur.close()


def _save_feria_kpi_snapshot(feria_id, total_leads, ventas_cerradas, ingresos_generados):
    if not _table_exists("marketing_feria_resultados"):
        return

    fecha_snapshot = datetime.now().strftime("%Y-%m-%d")
    conversion_rate = (ventas_cerradas / total_leads * 100) if total_leads else 0
    ticket_promedio = (ingresos_generados / ventas_cerradas) if ventas_cerradas else 0

    cur = mysql.connection.cursor()
    try:
        cur.execute(
            """
            INSERT INTO marketing_feria_resultados
            (feria_id, fecha_snapshot, leads_generados, leads_convertidos, conversion_rate, ingresos_generados, ticket_promedio)
            VALUES (%s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                leads_generados = VALUES(leads_generados),
                leads_convertidos = VALUES(leads_convertidos),
                conversion_rate = VALUES(conversion_rate),
                ingresos_generados = VALUES(ingresos_generados),
                ticket_promedio = VALUES(ticket_promedio),
                updated_at = CURRENT_TIMESTAMP
            """,
            (
                feria_id,
                fecha_snapshot,
                int(total_leads or 0),
                int(ventas_cerradas or 0),
                float(conversion_rate or 0),
                float(ingresos_generados or 0),
                float(ticket_promedio or 0),
            ),
        )
        mysql.connection.commit()
    except Exception as ex:
        mysql.connection.rollback()
        print(f"No se pudo guardar snapshot KPI de feria: {ex}")
    finally:
        cur.close()


def _to_int(value):
    try:
        return int(value)
    except (TypeError, ValueError):
        return None


def _graph_api_get(resource_id, token, api_ver="v20.0", params=None):
    params = dict(params or {})
    params["access_token"] = token
    url = f"https://graph.facebook.com/{api_ver}/{resource_id}"
    response = requests.get(url, params=params, timeout=20)
    if response.status_code >= 300:
        raise ValueError(response.text or f"Graph API error {response.status_code}")
    return response.json()


def _last_year_date():
    today = datetime.now().date()
    try:
        return today.replace(year=today.year - 1)
    except ValueError:
        return today - timedelta(days=365)


def _get_previous_year_value(resource_id, metric_name, token, api_ver="v20.0"):
    try:
        last_year = _last_year_date()
        params = {
            "metric": metric_name,
            "period": "day",
            "since": last_year.strftime("%Y-%m-%d"),
            "until": last_year.strftime("%Y-%m-%d"),
        }
        data = _graph_api_get(f"{resource_id}/insights", token, api_ver, params=params)
        if not data or "data" not in data or not data["data"]:
            return None
        values = data["data"][0].get("values") or []
        if not values:
            return None
        return _to_int(values[-1].get("value"))
    except Exception:
        return None


def _calculate_growth(current, previous):
    if current is None or previous is None:
        return None
    try:
        current = int(current)
        previous = int(previous)
    except (TypeError, ValueError):
        return None
    if previous == 0:
        return None
    return round((current - previous) / previous * 100, 2)


def _resolve_negocio_id_by_brand(brand_slug):
    if not brand_slug:
        return None
    cur = mysql.connection.cursor(DictCursor)
    try:
        cur.execute("SELECT id FROM negocios WHERE slug = %s LIMIT 1", (brand_slug.lower(),))
        row = cur.fetchone()
        return row.get("id") if row else None
    except Exception:
        return None
    finally:
        cur.close()


def _save_social_metrics_snapshot(negocio_id, snapshot_date, fb_page_id, ig_account_id, fb_followers, ig_followers, total_followers, fb_target, ig_target, total_target):
    if not _table_exists("marketing_social_metrics"):
        return False
    if not negocio_id:
        return False

    cur = mysql.connection.cursor()
    try:
        cur.execute(
            """
            INSERT INTO marketing_social_metrics (
                negocio_id,
                snapshot_date,
                fb_page_id,
                ig_account_id,
                fb_followers,
                ig_followers,
                total_followers,
                fb_target_followers,
                ig_target_followers,
                total_target_followers,
                created_at
            ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            ON DUPLICATE KEY UPDATE
                fb_followers = VALUES(fb_followers),
                ig_followers = VALUES(ig_followers),
                total_followers = VALUES(total_followers),
                fb_target_followers = VALUES(fb_target_followers),
                ig_target_followers = VALUES(ig_target_followers),
                total_target_followers = VALUES(total_target_followers),
                created_at = NOW()
            """,
            (
                negocio_id,
                snapshot_date,
                fb_page_id,
                ig_account_id,
                fb_followers,
                ig_followers,
                total_followers,
                fb_target,
                ig_target,
                total_target,
            ),
        )
        mysql.connection.commit()
        return True
    except Exception:
        return False
    finally:
        cur.close()


def _count_leads_by_year(negocio_id, year):
    if not negocio_id:
        return None
    cur = mysql.connection.cursor(DictCursor)
    try:
        cur.execute(
            "SELECT COUNT(*) AS total FROM leads WHERE negocio_id = %s AND YEAR(fecha) = %s",
            (negocio_id, year),
        )
        row = cur.fetchone()
        return int(row["total"]) if row else 0
    except Exception:
        return None
    finally:
        cur.close()


def _marketing_scope_clause(table_name, alias, negocio_id, brand_slug):
    if _column_exists(table_name, "negocio_id") and negocio_id:
        return f"{alias}.negocio_id = %s", [negocio_id]
    if _column_exists(table_name, "brand"):
        return f"LOWER(TRIM(COALESCE({alias}.brand, ''))) = %s", [brand_slug]
    return "1=1", []


def _latest_seguimiento_subquery():
    return """
        SELECT s1.*
        FROM seguimientos s1
        INNER JOIN (
            SELECT lead_id, MAX(id) AS max_id
            FROM seguimientos
            GROUP BY lead_id
        ) s2 ON s1.id = s2.max_id
    """


def _count_closed_sales_by_year(negocio_id, year):
    if not negocio_id:
        return None

    latest_seg = _latest_seguimiento_subquery()
    cur = mysql.connection.cursor(DictCursor)
    try:
        cur.execute(
            f"""
            SELECT COUNT(DISTINCT l.id) AS total
            FROM leads l
            LEFT JOIN ({latest_seg}) s ON s.lead_id = l.id
            LEFT JOIN proceso p ON p.id = s.proceso_id
            WHERE l.negocio_id = %s
              AND YEAR(l.fecha) = %s
              AND LOWER(TRIM(COALESCE(p.nombre_proceso, ''))) = 'cerrado'
            """,
            (negocio_id, year),
        )
        row = cur.fetchone() or {}
        return int(row.get("total") or 0)
    except Exception:
        return None
    finally:
        cur.close()


def _sum_marketing_investment_by_year(brand_slug, negocio_id, year):
    total = Decimal("0")
    cur = mysql.connection.cursor(DictCursor)
    try:
        if _table_exists("marketing_campaigns") and _column_exists("marketing_campaigns", "inversion"):
            where_sql, params = _marketing_scope_clause("marketing_campaigns", "c", negocio_id, brand_slug)
            cur.execute(
                f"""
                SELECT COALESCE(SUM(COALESCE(c.inversion, 0)), 0) AS total
                FROM marketing_campaigns c
                WHERE {where_sql}
                  AND COALESCE(c.periodo_inicio, c.fecha_lanzamiento) IS NOT NULL
                  AND YEAR(COALESCE(c.periodo_inicio, c.fecha_lanzamiento)) = %s
                """,
                tuple(params + [year]),
            )
            row = cur.fetchone() or {}
            total += Decimal(str(row.get("total") or 0))

        if _table_exists("marketing_ferias") and _column_exists("marketing_ferias", "total_inversion"):
            where_sql, params = _marketing_scope_clause("marketing_ferias", "f", negocio_id, brand_slug)
            cur.execute(
                f"""
                SELECT COALESCE(SUM(COALESCE(f.total_inversion, 0)), 0) AS total
                FROM marketing_ferias f
                WHERE {where_sql}
                  AND COALESCE(f.fecha_inicio, f.fecha_fin) IS NOT NULL
                  AND YEAR(COALESCE(f.fecha_inicio, f.fecha_fin)) = %s
                """,
                tuple(params + [year]),
            )
            row = cur.fetchone() or {}
            total += Decimal(str(row.get("total") or 0))
    except Exception:
        return None
    finally:
        cur.close()

    return total


def _load_social_metrics_history(negocio_id, limit=30):
    if not _table_exists("marketing_social_metrics"):
        return []
    if not negocio_id:
        return []

    cur = mysql.connection.cursor(DictCursor)
    try:
        cur.execute(
            """
            SELECT snapshot_date, fb_followers, ig_followers, total_followers,
                   fb_target_followers, ig_target_followers, total_target_followers, created_at
            FROM marketing_social_metrics
            WHERE negocio_id = %s
            ORDER BY snapshot_date DESC
            LIMIT %s
            """,
            (negocio_id, limit),
        )
        return cur.fetchall() or []
    finally:
        cur.close()


def _fetch_facebook_followers(page_id, token, api_ver="v20.0"):
    try:
        data = _graph_api_get(page_id, token, api_ver, {"fields": "followers_count"})
        current = _to_int(data.get("followers_count"))
        previous = _get_previous_year_value(page_id, "page_fans", token, api_ver)
        return {
            "current": current,
            "previous": previous,
            "growth_pct": _calculate_growth(current, previous),
            "error": None,
        }
    except Exception as ex:
        return {"current": None, "previous": None, "growth_pct": None, "error": str(ex)}


def _fetch_instagram_followers(ig_id, token, api_ver="v20.0"):
    try:
        data = _graph_api_get(ig_id, token, api_ver, {"fields": "followers_count"})
        current = _to_int(data.get("followers_count"))
        previous = _get_previous_year_value(ig_id, "follower_count", token, api_ver)
        return {
            "current": current,
            "previous": previous,
            "growth_pct": _calculate_growth(current, previous),
            "error": None,
            "resolved_ig_id": str(ig_id or "").strip(),
        }
    except Exception as first_error:
        return {
            "current": None,
            "previous": None,
            "growth_pct": None,
            "error": str(first_error),
            "resolved_ig_id": None,
        }


def _fetch_instagram_followers_with_fallback(ig_id, page_id, token, api_ver="v20.0"):
    direct_try = _fetch_instagram_followers(ig_id, token, api_ver) if ig_id else None
    if direct_try and not direct_try.get("error"):
        return direct_try

    if not page_id:
        return direct_try or {
            "current": None,
            "previous": None,
            "growth_pct": None,
            "error": "Falta FB_PAGE_ID para resolver cuenta de Instagram.",
            "resolved_ig_id": None,
        }

    try:
        page_data = _graph_api_get(
            page_id,
            token,
            api_ver,
            {"fields": "instagram_business_account{id,username},connected_instagram_account{id,username}"},
        )
        page_data = page_data or {}
        ig_obj = page_data.get("instagram_business_account") or page_data.get("connected_instagram_account") or {}
        resolved_ig_id = str(ig_obj.get("id") or "").strip()
        if not resolved_ig_id:
            direct_error = (direct_try or {}).get("error")
            if direct_error:
                combined_error = (
                    "No se pudo usar IG_ACCOUNT_ID directo y tampoco se detecto una cuenta IG conectada a la pagina. "
                    f"Error directo: {direct_error}"
                )
            else:
                combined_error = "La pagina de Facebook no tiene una cuenta de Instagram Business/Creator conectada."
            return {
                "current": None,
                "previous": None,
                "growth_pct": None,
                "error": combined_error,
                "resolved_ig_id": None,
            }

        resolved_data = _fetch_instagram_followers(resolved_ig_id, token, api_ver)
        if not resolved_data.get("error"):
            resolved_data["resolved_ig_id"] = resolved_ig_id
            return resolved_data

        direct_error = (direct_try or {}).get("error")
        resolved_error = resolved_data.get("error")
        return {
            "current": None,
            "previous": None,
            "growth_pct": None,
            "resolved_ig_id": resolved_ig_id,
            "error": resolved_error or direct_error,
        }
    except Exception as ex:
        return {
            "current": None,
            "previous": None,
            "growth_pct": None,
            "resolved_ig_id": None,
            "error": str(ex),
        }


def _get_lineas_negocio_options():
    cur = mysql.connection.cursor(DictCursor)
    try:
        cur.execute("SELECT id, nombre FROM bienes_servicios ORDER BY nombre")
        return cur.fetchall() or []
    finally:
        cur.close()


def _get_linea_familia_options(linea_negocio_id):
    if not linea_negocio_id or not _table_exists("linea_familia"):
        return []
    cur = mysql.connection.cursor(DictCursor)
    try:
        cur.execute(
            """
            SELECT id, nombre
            FROM linea_familia
            WHERE id_bien_servicio = %s
            ORDER BY nombre
            """,
            (linea_negocio_id,),
        )
        return cur.fetchall() or []
    finally:
        cur.close()


def _get_linea_producto_options(linea_negocio_id):
    if not linea_negocio_id or not _table_exists("linea_producto"):
        return []
    cur = mysql.connection.cursor(DictCursor)
    try:
        cur.execute(
            """
            SELECT lp.id, lp.nombre, bs.nombre AS bien_servicio
            FROM linea_producto lp
            INNER JOIN bienes_servicios bs ON lp.id_bien_servicio = bs.id
            WHERE lp.id_bien_servicio = %s
            ORDER BY lp.nombre
            """,
            (linea_negocio_id,),
        )
        return cur.fetchall() or []
    finally:
        cur.close()


def _resolve_line_selection(linea_negocio_id, linea_familia_id, linea_producto_id):
    if not (linea_negocio_id and linea_familia_id and linea_producto_id):
        return None
    if not _table_exists("linea_familia") or not _table_exists("linea_producto"):
        return None

    cur = mysql.connection.cursor(DictCursor)
    try:
        cur.execute(
            """
            SELECT
                bs.nombre AS linea_negocio,
                lf.nombre AS linea_familia,
                lp.nombre AS linea_producto
            FROM bienes_servicios bs
            INNER JOIN linea_familia lf ON lf.id_bien_servicio = bs.id
            INNER JOIN linea_producto lp ON lp.id_bien_servicio = bs.id
            WHERE bs.id = %s AND lf.id = %s AND lp.id = %s
            LIMIT 1
            """,
            (linea_negocio_id, linea_familia_id, linea_producto_id),
        )
        return cur.fetchone()
    finally:
        cur.close()


def _append_channel_filter(sql, params, channel_key):
    aliases = CHANNEL_LEAD_NAME_FILTERS.get(channel_key)
    if not aliases:
        return sql, params
    placeholders = ", ".join(["%s"] * len(aliases))
    sql += f" AND LOWER(TRIM(COALESCE(cr_filter.nombre, ''))) IN ({placeholders})"
    params.extend([a.lower() for a in aliases])
    return sql, params


def _safe_decimal(value):
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _campaign_financial_snapshot(kpis, ingresos_por_moneda):
    inversion = _safe_decimal(kpis.get("inversion"))
    total_leads = int(kpis.get("total_leads") or 0)
    ventas_cerradas = int(kpis.get("ventas_cerradas") or 0)

    cost_per_lead = (inversion / total_leads) if total_leads else Decimal("0")
    cost_per_sale = (inversion / ventas_cerradas) if ventas_cerradas else Decimal("0")

    total_ingresos = Decimal("0")
    total_ventas = 0
    single_currency = None
    if ingresos_por_moneda:
        single_currency = ingresos_por_moneda[0].get("moneda")
        if len(ingresos_por_moneda) > 1:
            single_currency = None
        for item in ingresos_por_moneda:
            total_ingresos += _safe_decimal(item.get("ingresos"))
            total_ventas += int(item.get("ventas") or 0)

    roas = (total_ingresos / inversion) if inversion > 0 and single_currency else None
    utilidad = (total_ingresos - inversion) if single_currency else None
    ticket_promedio = (total_ingresos / total_ventas) if total_ventas and single_currency else None

    return {
        "inversion": inversion,
        "cost_per_lead": cost_per_lead,
        "cost_per_sale": cost_per_sale,
        "total_ingresos": total_ingresos,
        "single_currency": single_currency,
        "roas": roas,
        "utilidad": utilidad,
        "ticket_promedio": ticket_promedio,
    }