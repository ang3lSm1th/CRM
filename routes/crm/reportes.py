from flask import (
    Blueprint,
    render_template,
    session,
    jsonify,
    request,
    make_response,
    current_app,
)
from extensions import mysql
from MySQLdb.cursors import DictCursor
from utils.security import (
    login_required,
    role_required,
    ROLE_ADMIN,
    ROLE_GERENTE,
    ROLE_RRHH,
    ROLE_MARKETING,
)
from datetime import date, datetime, timedelta
import io
from services.campaign_kpi_service import compute_campaign_pretest_rows

reportes_bp = Blueprint("reportes", __name__)

# Mapeo de IDs a nombres de departamentos del Perú
DEPARTAMENTOS = {
    "1": "Amazonas",
    "2": "Áncash",
    "3": "Apurímac",
    "4": "Arequipa",
    "5": "Ayacucho",
    "6": "Cajamarca",
    "7": "Callao",
    "8": "Cusco",
    "9": "Huancavelica",
    "10": "Huánuco",
    "11": "Ica",
    "12": "Junín",
    "13": "La Libertad",
    "14": "Lambayeque",
    "15": "Lima",
    "16": "Loreto",
    "17": "Madre de Dios",
    "18": "Moquegua",
    "19": "Pasco",
    "20": "Piura",
    "21": "Puno",
    "22": "San Martín",
    "23": "Tacna",
    "24": "Tumbes",
    "25": "Ucayali",
}


_SCHEMA_CACHE = {}


def obtener_nombre_departamento(id_dept):
    """Convierte ID de departamento a nombre completo"""
    if not id_dept:
        return "Sin especificar"
    # Convertir a string por si viene como int
    id_str = str(id_dept).strip()
    return DEPARTAMENTOS.get(id_str, id_str)


def _table_exists(table_name):
    cache_key = ("table", table_name)
    if cache_key in _SCHEMA_CACHE:
        return _SCHEMA_CACHE[cache_key]

    cur = mysql.connection.cursor(DictCursor)
    try:
        cur.execute(
            """
            SELECT 1
            FROM information_schema.tables
            WHERE table_schema = DATABASE() AND table_name = %s
            LIMIT 1
            """,
            (table_name,),
        )
        result = bool(cur.fetchone())
    except Exception:
        result = False
    finally:
        cur.close()

    _SCHEMA_CACHE[cache_key] = result
    return result


def _column_exists(table_name, column_name):
    cache_key = ("column", table_name, column_name)
    if cache_key in _SCHEMA_CACHE:
        return _SCHEMA_CACHE[cache_key]

    cur = mysql.connection.cursor(DictCursor)
    try:
        cur.execute(
            """
            SELECT 1
            FROM information_schema.columns
            WHERE table_schema = DATABASE()
              AND table_name = %s
              AND column_name = %s
            LIMIT 1
            """,
            (table_name, column_name),
        )
        result = bool(cur.fetchone())
    except Exception:
        result = False
    finally:
        cur.close()

    _SCHEMA_CACHE[cache_key] = result
    return result


def _resolve_negocio_id_by_brand(brand_slug):
    if not brand_slug:
        return None
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


@reportes_bp.route("/reporte-asesores")
@login_required
@role_required(ROLE_ADMIN, ROLE_GERENTE, ROLE_RRHH)
def reporte_asesores():
    """
    Reporte de asesores: Monto cotizado, ventas cerradas y no cerradas.
    Solo accesible para Administrador y Gerente.
    """
    cur = mysql.connection.cursor(DictCursor)

    # Parse period filter: today, last_week, last_month, custom
    period = (request.args.get("period") or "last_month").strip()
    date_from = None
    date_to = None
    params = []
    try:
        today = date.today()
        if period == "today":
            date_from = date_to = today
        elif period == "last_week":
            date_to = today
            date_from = today - timedelta(days=6)
        elif period == "last_month":
            date_to = today
            date_from = today - timedelta(days=29)
        elif period == "custom":
            df = request.args.get("date_from")
            dt = request.args.get("date_to")
            try:
                if df:
                    date_from = datetime.strptime(df, "%Y-%m-%d").date()
                if dt:
                    date_to = datetime.strptime(dt, "%Y-%m-%d").date()
            except Exception:
                date_from = date_to = None

        # Build dynamic query with WHERE clauses
        base_query = """
            SELECT 
                u.id AS asesor_id,
                u.usuario AS asesor_usuario,
                u.nombre AS asesor_nombre,
                n.slug AS negocio_slug,
                COALESCE(SUM(CASE WHEN p.nombre_proceso = 'Cotizado' THEN s.monto ELSE 0 END), 0) AS monto_cotizado,
                COUNT(DISTINCT CASE WHEN p.nombre_proceso = 'Cotizado' THEN s.lead_id END) AS cantidad_cotizaciones,
                COALESCE(SUM(CASE WHEN p.nombre_proceso = 'Cerrado' THEN s.monto ELSE 0 END), 0) AS monto_cerrado,
                COUNT(DISTINCT CASE WHEN p.nombre_proceso = 'Cerrado' THEN s.lead_id END) AS cantidad_cerrados,
                COALESCE(SUM(CASE WHEN p.nombre_proceso = 'Cerrado No Vendido' THEN s.monto ELSE 0 END), 0) AS monto_no_cerrado,
                COUNT(DISTINCT CASE WHEN p.nombre_proceso = 'Cerrado No Vendido' THEN s.lead_id END) AS cantidad_no_cerrados
            FROM usuarios u
            INNER JOIN roles r ON u.id_rol = r.id
            LEFT JOIN negocios n ON n.id = u.negocio_id
            LEFT JOIN leads l ON l.asignado_a = u.id
            LEFT JOIN (
                SELECT s1.*
                FROM seguimientos s1
                INNER JOIN (
                    SELECT lead_id, MAX(id) as max_id
                    FROM seguimientos
                    GROUP BY lead_id
                ) s2 ON s1.id = s2.max_id
            ) s ON s.lead_id = l.id
            LEFT JOIN proceso p ON p.id = s.proceso_id
        """

        where_clauses = ["r.nombre = 'Asesor'"]
        # date filter on lead creation date
        if date_from and date_to:
            where_clauses.append("DATE(l.fecha) BETWEEN %s AND %s")
            params.extend(
                [date_from.strftime("%Y-%m-%d"), date_to.strftime("%Y-%m-%d")]
            )

        # brand filter from cookie
        brand = (request.cookies.get("brand") or "").strip().lower()
        if brand in ("orbes", "lovol"):
            where_clauses.append(
                "EXISTS (SELECT 1 FROM negocios nn WHERE nn.id = u.negocio_id AND nn.slug = %s)"
            )
            params.append(brand)

        final_query = (
            base_query
            + " WHERE "
            + " AND ".join(where_clauses)
            + " GROUP BY u.id, u.usuario, u.nombre, n.slug ORDER BY u.nombre"
        )
        cur.execute(final_query, tuple(params) if params else None)
        asesores = cur.fetchall()

        # Calcular totales generales
        totales = {
            "monto_cotizado": sum(a["monto_cotizado"] or 0 for a in asesores),
            "cantidad_cotizaciones": sum(
                a["cantidad_cotizaciones"] or 0 for a in asesores
            ),
            "monto_cerrado": sum(a["monto_cerrado"] or 0 for a in asesores),
            "cantidad_cerrados": sum(a["cantidad_cerrados"] or 0 for a in asesores),
            "monto_no_cerrado": sum(a["monto_no_cerrado"] or 0 for a in asesores),
            "cantidad_no_cerrados": sum(
                a["cantidad_no_cerrados"] or 0 for a in asesores
            ),
        }

        # Totales por negocio (orbes / lovol / unknown)
        totals_by_negocio = {}
        for a in asesores:
            slug = a.get("negocio_slug") or "unknown"
            slug = slug.strip().lower() if slug else "unknown"
            if slug not in totals_by_negocio:
                totals_by_negocio[slug] = {
                    "monto_cotizado": 0,
                    "cantidad_cotizaciones": 0,
                    "monto_cerrado": 0,
                    "cantidad_cerrados": 0,
                    "monto_no_cerrado": 0,
                    "cantidad_no_cerrados": 0,
                }
            totals_by_negocio[slug]["monto_cotizado"] += a.get("monto_cotizado") or 0
            totals_by_negocio[slug]["cantidad_cotizaciones"] += (
                a.get("cantidad_cotizaciones") or 0
            )
            totals_by_negocio[slug]["monto_cerrado"] += a.get("monto_cerrado") or 0
            totals_by_negocio[slug]["cantidad_cerrados"] += (
                a.get("cantidad_cerrados") or 0
            )
            totals_by_negocio[slug]["monto_no_cerrado"] += (
                a.get("monto_no_cerrado") or 0
            )
            totals_by_negocio[slug]["cantidad_no_cerrados"] += (
                a.get("cantidad_no_cerrados") or 0
            )

    finally:
        cur.close()

    return render_template(
        "reportes/reporte_asesores.html",
        asesores=asesores,
        totales=totales,
        totals_by_negocio=totals_by_negocio,
        period=period,
        date_from=(date_from.strftime("%Y-%m-%d") if date_from else ""),
        date_to=(date_to.strftime("%Y-%m-%d") if date_to else ""),
    )


@reportes_bp.route("/analisis-clientes")
@login_required
@role_required(ROLE_ADMIN, ROLE_GERENTE, ROLE_RRHH, ROLE_MARKETING)
def analisis_clientes():
    """
    Análisis de clientes: Líneas de compra por bien/servicio,
    frecuencia de compra mensual y departamentos.
    Solo accesible para Administrador y Gerente.
    """
    cur = mysql.connection.cursor(DictCursor)

    # Parse period filter (same logic as reporte_asesores)
    period = (request.args.get("period") or "last_month").strip()
    date_from = None
    date_to = None
    try:
        today = date.today()
        if period == "today":
            date_from = date_to = today
        elif period == "last_week":
            date_to = today
            date_from = today - timedelta(days=6)
        elif period == "last_month":
            date_to = today
            date_from = today - timedelta(days=29)
        elif period == "custom":
            df = request.args.get("date_from")
            dt = request.args.get("date_to")
            try:
                if df:
                    date_from = datetime.strptime(df, "%Y-%m-%d").date()
                if dt:
                    date_to = datetime.strptime(dt, "%Y-%m-%d").date()
            except Exception:
                date_from = date_to = None

        # Build and execute queries with optional date filters
        params = []
        date_clause = ""
        if date_from and date_to:
            date_clause = " AND DATE(l.fecha) BETWEEN %s AND %s"
            params = [date_from.strftime("%Y-%m-%d"), date_to.strftime("%Y-%m-%d")]

        # 1. Análisis por línea de bien/servicio y departamento
        query_lineas = f"""
            SELECT 
                bs.nombre AS bien_servicio,
                l.departamento,
                COUNT(DISTINCT l.id) AS cantidad_leads,
                COUNT(DISTINCT CASE WHEN p.nombre_proceso = 'Cerrado' THEN l.id END) AS ventas_cerradas,
                COALESCE(SUM(CASE WHEN p.nombre_proceso = 'Cerrado' THEN s.monto ELSE 0 END), 0) AS monto_total
            FROM leads l
            LEFT JOIN bienes_servicios bs ON bs.id = l.bien_servicio_id
            LEFT JOIN (
                SELECT s1.*
                FROM seguimientos s1
                INNER JOIN (
                    SELECT lead_id, MAX(id) as max_id
                    FROM seguimientos
                    GROUP BY lead_id
                ) s2 ON s1.id = s2.max_id
            ) s ON s.lead_id = l.id
            LEFT JOIN proceso p ON p.id = s.proceso_id
            WHERE l.departamento IS NOT NULL AND l.departamento != ''{date_clause}
            GROUP BY bs.nombre, l.departamento
            ORDER BY monto_total DESC, cantidad_leads DESC
        """

        cur.execute(query_lineas, tuple(params) if params else None)
        lineas_por_departamento = cur.fetchall()
        for linea in lineas_por_departamento:
            linea["departamento"] = obtener_nombre_departamento(linea["departamento"])

        # 2. Análisis de frecuencia mensual de compras por bien/servicio
        # default to last 12 months if no custom date provided
        if not (date_from and date_to):
            frecuencia_where = "WHERE l.fecha >= DATE_SUB(CURDATE(), INTERVAL 12 MONTH)"
            freq_params = []
        else:
            frecuencia_where = "WHERE DATE(l.fecha) BETWEEN %s AND %s"
            freq_params = [date_from.strftime("%Y-%m-%d"), date_to.strftime("%Y-%m-%d")]

        query_frecuencia = f"""
            SELECT 
                bs.nombre AS bien_servicio,
                DATE_FORMAT(l.fecha, '%%Y-%%m') AS mes,
                MONTHNAME(l.fecha) AS nombre_mes,
                YEAR(l.fecha) AS anio,
                COUNT(DISTINCT l.id) AS cantidad_leads,
                COUNT(DISTINCT CASE WHEN p.nombre_proceso = 'Cerrado' THEN l.id END) AS ventas_cerradas,
                COALESCE(SUM(CASE WHEN p.nombre_proceso = 'Cerrado' THEN s.monto ELSE 0 END), 0) AS monto_total
            FROM leads l
            LEFT JOIN bienes_servicios bs ON bs.id = l.bien_servicio_id
            LEFT JOIN (
                SELECT s1.*
                FROM seguimientos s1
                INNER JOIN (
                    SELECT lead_id, MAX(id) as max_id
                    FROM seguimientos
                    GROUP BY lead_id
                ) s2 ON s1.id = s2.max_id
            ) s ON s.lead_id = l.id
            LEFT JOIN proceso p ON p.id = s.proceso_id
            {frecuencia_where}
            GROUP BY bs.nombre, mes, nombre_mes, anio
            ORDER BY mes DESC, monto_total DESC
        """

        cur.execute(query_frecuencia, tuple(freq_params) if freq_params else None)
        frecuencia_mensual = cur.fetchall()

        # 3. Top departamentos por bien/servicio
        query_top_departamentos = f"""
            SELECT 
                bs.nombre AS bien_servicio,
                l.departamento,
                COUNT(DISTINCT l.id) AS cantidad_leads,
                COUNT(DISTINCT CASE WHEN p.nombre_proceso = 'Cerrado' THEN l.id END) AS ventas_cerradas,
                COALESCE(SUM(CASE WHEN p.nombre_proceso = 'Cerrado' THEN s.monto ELSE 0 END), 0) AS monto_total
            FROM leads l
            LEFT JOIN bienes_servicios bs ON bs.id = l.bien_servicio_id
            LEFT JOIN (
                SELECT s1.*
                FROM seguimientos s1
                INNER JOIN (
                    SELECT lead_id, MAX(id) as max_id
                    FROM seguimientos
                    GROUP BY lead_id
                ) s2 ON s1.id = s2.max_id
            ) s ON s.lead_id = l.id
            LEFT JOIN proceso p ON p.id = s.proceso_id
            WHERE l.departamento IS NOT NULL AND l.departamento != ''{date_clause}
            GROUP BY bs.nombre, l.departamento
            HAVING ventas_cerradas > 0
            ORDER BY bs.nombre, monto_total DESC
        """

        cur.execute(query_top_departamentos, tuple(params) if params else None)
        top_departamentos = cur.fetchall()
        for item in top_departamentos:
            item["departamento"] = obtener_nombre_departamento(item["departamento"])

        # Totales por negocio (para mostrar tarjetas y controlar UI)
        totals_by_negocio = {}
        try:
            seg_sub = """
                SELECT s1.*
                FROM seguimientos s1
                INNER JOIN (
                    SELECT lead_id, MAX(id) as max_id
                    FROM seguimientos
                    GROUP BY lead_id
                ) s2 ON s1.id = s2.max_id
            """
            params_tot = []
            date_clause_sql = ""
            if date_from and date_to:
                date_clause_sql = " WHERE DATE(l.fecha) BETWEEN %s AND %s "
                params_tot = [
                    date_from.strftime("%Y-%m-%d"),
                    date_to.strftime("%Y-%m-%d"),
                ]

            q_tot = f"""
                SELECT COALESCE(n.slug, 'unknown') AS slug,
                    COALESCE(SUM(CASE WHEN p.nombre_proceso = 'Cotizado' THEN s.monto ELSE 0 END), 0) AS monto_cotizado,
                    COUNT(DISTINCT CASE WHEN p.nombre_proceso = 'Cotizado' THEN s.lead_id END) AS cantidad_cotizaciones
                FROM leads l
                LEFT JOIN negocios n ON n.id = l.negocio_id
                LEFT JOIN ({seg_sub}) s ON s.lead_id = l.id
                LEFT JOIN proceso p ON p.id = s.proceso_id
                {date_clause_sql}
                GROUP BY COALESCE(n.slug, 'unknown')
            """
            cur2 = mysql.connection.cursor(DictCursor)
            try:
                cur2.execute(q_tot, tuple(params_tot) if params_tot else None)
                rows_tot = cur2.fetchall() or []
                for r in rows_tot:
                    slug = (r.get("slug") or "unknown").strip().lower()
                    totals_by_negocio[slug] = {
                        "monto_cotizado": r.get("monto_cotizado") or 0,
                        "cantidad_cotizaciones": r.get("cantidad_cotizaciones") or 0,
                    }
            finally:
                cur2.close()
        except Exception:
            totals_by_negocio = {}

    finally:
        cur.close()

    return render_template(
        "reportes/analisis_clientes.html",
        lineas_por_departamento=lineas_por_departamento,
        frecuencia_mensual=frecuencia_mensual,
        top_departamentos=top_departamentos,
        period=period,
        date_from=(date_from.strftime("%Y-%m-%d") if date_from else ""),
        date_to=(date_to.strftime("%Y-%m-%d") if date_to else ""),
        totals_by_negocio=totals_by_negocio,
    )


def _detect_cliente_mtp(cliente_key, date_from, date_to):
    """
    Detecta automáticamente el MTP según la ultima fecha de compra del cliente en el periodo.
    Regla: dentro del trimestre seleccionado, el ultimo mes comprado define el MTP:
        - Mes 1 del trimestre => MTP 1
        - Mes 2 del trimestre => MTP 2
        - Mes 3 del trimestre => MTP 3
    """
    cur = mysql.connection.cursor(DictCursor)
    try:
        # Cliente key expression: grouped by ruc/telefono/nombre
        cliente_key_expr = """COALESCE(
            NULLIF(TRIM(l.ruc_dni), ''),
            NULLIF(TRIM(l.telefono), ''),
            NULLIF(LOWER(TRIM(l.nombre)), ''),
            CONCAT('lead-', l.id)
        )"""

        query = f"""
        SELECT
            MAX(MONTH(l.fecha)) AS last_month
        FROM leads l
        LEFT JOIN (
            SELECT s1.*
            FROM seguimientos s1
            INNER JOIN (
                SELECT lead_id, MAX(id) AS max_id
                FROM seguimientos
                GROUP BY lead_id
            ) last_s ON last_s.max_id = s1.id
        ) s ON s.lead_id = l.id
        LEFT JOIN proceso p ON p.id = s.proceso_id
        WHERE {cliente_key_expr} = %s
          AND LOWER(TRIM(COALESCE(p.nombre_proceso, ''))) = 'cerrado'
          AND DATE(l.fecha) BETWEEN %s AND %s
        """
        params = [
            cliente_key,
            date_from.strftime("%Y-%m-%d"),
            date_to.strftime("%Y-%m-%d"),
        ]
        cur.execute(query, params)
        row = cur.fetchone()

        if row and row.get("last_month"):
            last_month = int(row.get("last_month") or date_from.month)
            quarter_start_month = int(date_from.month)
            mtp_from_last_purchase = (last_month - quarter_start_month) + 1
            return max(1, min(mtp_from_last_purchase, 3))
        else:
            return 1  # Default if no purchases found
    except Exception as e:
        current_app.logger.warning(f"Error detecting MTP for {cliente_key}: {e}")
        return 1  # Safe default on error
    finally:
        cur.close()


def _build_upsell_suggestions(goods):
    """Sugerencias comerciales basadas en bienes/servicios históricos comprados."""
    normalized = [(g or "").strip().lower() for g in goods if g]
    text = " ".join(normalized)
    suggestions = []

    if "tractor" in text or "maquinaria agricola" in text:
        suggestions.append(
            "Ofrecer mantenimiento preventivo y paquete de repuestos para maquinaria"
        )
        suggestions.append(
            "Proponer implementos complementarios: arado, rastra o pulverizador"
        )

    if "motocultor" in text or "equipos menores" in text:
        suggestions.append(
            "Ofrecer upgrade a equipo de mayor potencia según campaña actual"
        )
        suggestions.append(
            "Vender kit de servicio técnico y accesorios de alto desgaste"
        )

    if "riego" in text or "proyecto de riego" in text:
        suggestions.append(
            "Proponer ampliación modular del sistema de riego por etapas"
        )
        suggestions.append("Ofrecer automatización con sensores y tablero de control")

    if "equipos fuerzas" in text:
        suggestions.append(
            "Sugerir plan de renovación anual con descuentos por recompra"
        )

    if not suggestions:
        suggestions.append(
            "Ofrecer plan de fidelización con descuento por segunda compra"
        )
        suggestions.append(
            "Presentar bundle de servicio postventa + capacitación operativa"
        )

    return suggestions[:3]


@reportes_bp.route("/api/lineas-por-bien-servicio")
@login_required
@role_required(ROLE_ADMIN, ROLE_GERENTE, ROLE_RRHH)
def api_lineas_por_bien_servicio():
    """
    API para obtener datos de líneas de compra por bien/servicio para gráficos.
    """
    cur = mysql.connection.cursor(DictCursor)

    try:
        query = """
            SELECT 
                bs.nombre AS bien_servicio,
                COUNT(DISTINCT CASE 
                    WHEN p.nombre_proceso = 'Cerrado' THEN l.id 
                END) AS ventas_cerradas,
                COALESCE(SUM(
                    CASE 
                        WHEN p.nombre_proceso = 'Cerrado' THEN s.monto 
                        ELSE 0 
                    END
                ), 0) AS monto_total
            FROM leads l
            LEFT JOIN bienes_servicios bs ON bs.id = l.bien_servicio_id
            LEFT JOIN (
                SELECT s1.*
                FROM seguimientos s1
                INNER JOIN (
                    SELECT lead_id, MAX(id) as max_id
                    FROM seguimientos
                    GROUP BY lead_id
                ) s2 ON s1.id = s2.max_id
            ) s ON s.lead_id = l.id
            LEFT JOIN proceso p ON p.id = s.proceso_id
            GROUP BY bs.nombre
            HAVING ventas_cerradas > 0
            ORDER BY monto_total DESC
        """

        cur.execute(query)
        datos = cur.fetchall()

    finally:
        cur.close()

    return jsonify(datos)


# ─────────────────────────────────────────────────────────────────
#  ANÁLISIS DE REPORTES — Indicadores KPI (MaSE Multi-Agente)
# ─────────────────────────────────────────────────────────────────


def _compute_analisis_kpi():
    """Calcula el diccionario KPI para el panel de análisis de reportes."""
    cur = mysql.connection.cursor(DictCursor)

    # ── Periodo por rango mensual ────────────────────────────────
    period = "month_range"
    date_from = date_to = None
    today = date.today()
    current_quarter = ((today.month - 1) // 3) + 1
    selected_quarter = current_quarter
    selected_year = today.year
    selected_month = None

    try:
        selected_quarter = int(request.args.get("quarter", current_quarter))
    except (TypeError, ValueError):
        selected_quarter = current_quarter

    try:
        selected_year = int(request.args.get("year", today.year))
    except (TypeError, ValueError):
        selected_year = today.year

    if selected_quarter not in (1, 2, 3, 4):
        selected_quarter = current_quarter

    if selected_year < 2000 or selected_year > 2100:
        selected_year = today.year

    try:
        selected_month = int(request.args.get("month"))
    except (TypeError, ValueError):
        selected_month = None

    all_months = False
    if selected_month is None:
        selected_month = 0
        all_months = True
    elif selected_month == 0:
        all_months = True
    elif selected_month < 1 or selected_month > 12:
        selected_month = today.month
        all_months = False

    if all_months:
        date_from = date(selected_year, 1, 1)
        date_to = date(selected_year, 12, 31)
        camp_month_from, camp_month_to = 1, 12
        selected_quarter = ((today.month - 1) // 3) + 1
    else:
        date_from = date(selected_year, selected_month, 1)
        if selected_month == 12:
            date_to = date(selected_year, 12, 31)
        else:
            date_to = date(selected_year, selected_month + 1, 1) - timedelta(days=1)
        camp_month_from = camp_month_to = selected_month
        selected_quarter = ((selected_month - 1) // 3) + 1

    date_clause = ""
    params = []
    if date_from and date_to:
        date_clause = " AND DATE(l.fecha) BETWEEN %s AND %s"
        params = [date_from.strftime("%Y-%m-%d"), date_to.strftime("%Y-%m-%d")]

    # Meses del periodo seleccionado (trimestre = 3 meses)
    mpc = ((date_to.year - date_from.year) * 12) + (date_to.month - date_from.month) + 1
    if mpc < 1:
        mpc = 1

    brand_slug = (request.cookies.get("brand") or "").strip().lower()
    negocio_id = _resolve_negocio_id_by_brand(brand_slug) if brand_slug else None
    has_lead_negocio = _column_exists("leads", "negocio_id")
    has_lead_brand = _column_exists("leads", "brand")
    has_lead_ruc_dni = _column_exists("leads", "ruc_dni")
    has_lead_telefono = _column_exists("leads", "telefono")
    has_seg_fecha_guardado = _column_exists("seguimientos", "fecha_guardado")
    has_seg_fecha = _column_exists("seguimientos", "fecha")

    if has_seg_fecha_guardado and has_seg_fecha:
        seg_date_expr_s = "COALESCE(s.fecha_guardado, s.fecha, l.fecha)"
        seg_date_expr_s2 = "COALESCE(s2.fecha_guardado, s2.fecha, l2.fecha)"
    elif has_seg_fecha_guardado:
        seg_date_expr_s = "COALESCE(s.fecha_guardado, l.fecha)"
        seg_date_expr_s2 = "COALESCE(s2.fecha_guardado, l2.fecha)"
    elif has_seg_fecha:
        seg_date_expr_s = "COALESCE(s.fecha, l.fecha)"
        seg_date_expr_s2 = "COALESCE(s2.fecha, l2.fecha)"
    else:
        # Fallback defensivo para despliegues donde seguimientos no tiene columna de fecha.
        seg_date_expr_s = "l.fecha"
        seg_date_expr_s2 = "l2.fecha"

    if has_lead_ruc_dni and has_lead_telefono:
        cliente_expr_l = "COALESCE(NULLIF(TRIM(l.ruc_dni), ''), NULLIF(TRIM(l.telefono), ''), NULLIF(LOWER(TRIM(l.nombre)), ''), CONCAT('lead-', l.id))"
        cliente_expr_l2 = "COALESCE(NULLIF(TRIM(l2.ruc_dni), ''), NULLIF(TRIM(l2.telefono), ''), NULLIF(LOWER(TRIM(l2.nombre)), ''), CONCAT('lead-', l2.id))"
    elif has_lead_ruc_dni:
        cliente_expr_l = "COALESCE(NULLIF(TRIM(l.ruc_dni), ''), NULLIF(LOWER(TRIM(l.nombre)), ''), CONCAT('lead-', l.id))"
        cliente_expr_l2 = "COALESCE(NULLIF(TRIM(l2.ruc_dni), ''), NULLIF(LOWER(TRIM(l2.nombre)), ''), CONCAT('lead-', l2.id))"
    elif has_lead_telefono:
        cliente_expr_l = "COALESCE(NULLIF(TRIM(l.telefono), ''), NULLIF(LOWER(TRIM(l.nombre)), ''), CONCAT('lead-', l.id))"
        cliente_expr_l2 = "COALESCE(NULLIF(TRIM(l2.telefono), ''), NULLIF(LOWER(TRIM(l2.nombre)), ''), CONCAT('lead-', l2.id))"
    else:
        cliente_expr_l = (
            "COALESCE(NULLIF(LOWER(TRIM(l.nombre)), ''), CONCAT('lead-', l.id))"
        )
        cliente_expr_l2 = (
            "COALESCE(NULLIF(LOWER(TRIM(l2.nombre)), ''), CONCAT('lead-', l2.id))"
        )

    lead_scope_clause = ""
    lead_scope_params = []
    if has_lead_negocio and negocio_id:
        lead_scope_clause = " AND l.negocio_id = %s"
        lead_scope_params.append(negocio_id)
    elif has_lead_brand and brand_slug:
        lead_scope_clause = " AND LOWER(l.brand) = %s"
        lead_scope_params.append(brand_slug)

    lead_scope_clause_l2 = ""
    lead_scope_params_l2 = []
    if has_lead_negocio and negocio_id:
        lead_scope_clause_l2 = " AND l2.negocio_id = %s"
        lead_scope_params_l2.append(negocio_id)
    elif has_lead_brand and brand_slug:
        lead_scope_clause_l2 = " AND LOWER(l2.brand) = %s"
        lead_scope_params_l2.append(brand_slug)

    kpi = {}
    try:
        # ── NLC: leads convertidos (proceso = Cerrado) ────────────
        cur.execute(
            f"""
            SELECT COUNT(DISTINCT l.id) AS nlc
            FROM leads l
            LEFT JOIN (
                SELECT s1.*
                FROM seguimientos s1
                INNER JOIN (
                    SELECT lead_id, MAX(id) AS max_id FROM seguimientos GROUP BY lead_id
                ) s2 ON s1.id = s2.max_id
            ) s ON s.lead_id = l.id
            LEFT JOIN proceso p ON p.id = s.proceso_id
            WHERE p.nombre_proceso = 'Cerrado' {date_clause}{lead_scope_clause}
        """,
            params + lead_scope_params,
        )
        kpi["nlc"] = (cur.fetchone() or {}).get("nlc", 0) or 0

        # ── DGA: inversión de campañas + ferias del trimestre ─────
        inv_campanas = 0.0
        inv_ferias = 0.0
        campaign_feria_exists = False

        if _table_exists("marketing_campaigns") and _column_exists(
            "marketing_campaigns", "inversion"
        ):
            c_filters = []
            c_params = []

            has_c_negocio = _column_exists("marketing_campaigns", "negocio_id")
            has_c_brand = _column_exists("marketing_campaigns", "brand")
            has_c_inicio = _column_exists("marketing_campaigns", "periodo_inicio")
            has_c_lanzamiento = _column_exists(
                "marketing_campaigns", "fecha_lanzamiento"
            )
            has_c_canal = _column_exists("marketing_campaigns", "canal")

            if has_c_inicio and has_c_lanzamiento:
                c_start_expr = "COALESCE(c.periodo_inicio, c.fecha_lanzamiento)"
            elif has_c_inicio:
                c_start_expr = "c.periodo_inicio"
            elif has_c_lanzamiento:
                c_start_expr = "c.fecha_lanzamiento"
            else:
                c_start_expr = "NULL"

            # Filtro mensual estricto: solo registros cuyo inicio/lanzamiento
            # cae dentro del mes seleccionado (evita sumar periodos completos por solapamiento).
            c_filters.append(f"DATE({c_start_expr}) BETWEEN %s AND %s")
            c_params.append(date_from.strftime("%Y-%m-%d"))
            c_params.append(date_to.strftime("%Y-%m-%d"))

            if has_c_negocio and negocio_id:
                c_filters.append("c.negocio_id = %s")
                c_params.append(negocio_id)
            elif has_c_brand and brand_slug:
                c_filters.append("LOWER(c.brand) = %s")
                c_params.append(brand_slug)

            c_where = " AND ".join(c_filters) if c_filters else "1=1"
            cur.execute(
                f"""
                SELECT COALESCE(SUM(COALESCE(c.inversion, 0)), 0) AS total
                FROM marketing_campaigns c
                WHERE {c_where}
                """,
                tuple(c_params),
            )
            inv_campanas = float((cur.fetchone() or {}).get("total", 0) or 0)

            # Si ya existe campaña de canal Feria en el mes, evitar doble conteo
            # contra la tabla marketing_ferias para el mismo periodo.
            if has_c_canal:
                cur.execute(
                    f"""
                    SELECT 1
                    FROM marketing_campaigns c
                    WHERE {c_where}
                      AND LOWER(TRIM(COALESCE(c.canal, ''))) = 'feria'
                    LIMIT 1
                    """,
                    tuple(c_params),
                )
                campaign_feria_exists = bool(cur.fetchone())

        if (
            _table_exists("marketing_ferias")
            and _column_exists("marketing_ferias", "total_inversion")
            and not campaign_feria_exists
        ):
            f_filters = []
            f_params = []

            has_f_negocio = _column_exists("marketing_ferias", "negocio_id")
            has_f_brand = _column_exists("marketing_ferias", "brand")
            has_f_inicio = _column_exists("marketing_ferias", "fecha_inicio")
            has_f_fin = _column_exists("marketing_ferias", "fecha_fin")

            if has_f_inicio and has_f_fin:
                f_start_expr = "COALESCE(f.fecha_inicio, f.fecha_fin)"
            elif has_f_inicio:
                f_start_expr = "f.fecha_inicio"
            elif has_f_fin:
                f_start_expr = "f.fecha_fin"
            else:
                f_start_expr = "NULL"

            # Filtro mensual estricto para ferias: solo por fecha de inicio del registro.
            f_filters.append(f"DATE({f_start_expr}) BETWEEN %s AND %s")
            f_params.append(date_from.strftime("%Y-%m-%d"))
            f_params.append(date_to.strftime("%Y-%m-%d"))

            if has_f_negocio and negocio_id:
                f_filters.append("f.negocio_id = %s")
                f_params.append(negocio_id)
            elif has_f_brand and brand_slug:
                f_filters.append("LOWER(f.brand) = %s")
                f_params.append(brand_slug)

            f_where = " AND ".join(f_filters) if f_filters else "1=1"
            cur.execute(
                f"""
                SELECT COALESCE(SUM(COALESCE(f.total_inversion, 0)), 0) AS total
                FROM marketing_ferias f
                WHERE {f_where}
                """,
                tuple(f_params),
            )
            inv_ferias = float((cur.fetchone() or {}).get("total", 0) or 0)

        kpi["inv_campanas"] = inv_campanas
        kpi["inv_ferias"] = inv_ferias
        kpi["dga"] = inv_campanas + inv_ferias

        # ── NLO: meta fija de leads por periodo (800 por mes) ────
        kpi["nlo"] = 800 * mpc

        # ── CALC = DGA / NLC ──────────────────────────────────────
        kpi["calc"] = (kpi["dga"] / kpi["nlc"]) if kpi["nlc"] else 0

        # ── TDA adquisición = (NLC / NLO) * 100 ──────────────────
        kpi["tda_acq"] = (kpi["nlc"] / kpi["nlo"] * 100) if kpi["nlo"] else 0

        # ── KPIs por campaña semanal (pretest Campaña 14-26) ─────
        campanas_pretest = {"rows": [], "summary": {}}
        try:
            campanas_pretest = compute_campaign_pretest_rows(
                cur,
                negocio_id=negocio_id,
                brand_slug=brand_slug,
                year=selected_year,
                month_from=camp_month_from,
                month_to=camp_month_to,
            )
        except Exception as e:
            print(f"Error KPI campanas pretest: {e}")
        kpi["campanas_pretest"] = campanas_pretest

        # ── TDR / TDA retención ───────────────────────────────────
        # Usa únicamente el filtro principal (mes/año):
        # periodo anterior = mes previo, periodo actual = mes seleccionado.
        selected_month_start = date_from
        selected_month_end = date_to

        def _shift_month_first_day(base_date, delta_months):
            month_index = (base_date.year * 12) + (base_date.month - 1) + delta_months
            year = month_index // 12
            month = (month_index % 12) + 1
            return date(year, month, 1)

        first_prev_month = _shift_month_first_day(selected_month_start, -1)
        last_prev_month = selected_month_start - timedelta(days=1)

        tdr_prev_from = first_prev_month
        tdr_prev_to = last_prev_month
        tdr_cur_from = selected_month_start
        tdr_cur_to = selected_month_end
        kpi["tdr_prev_from"] = tdr_prev_from.strftime("%d/%m/%Y")
        kpi["tdr_prev_to"] = tdr_prev_to.strftime("%d/%m/%Y")
        kpi["tdr_cur_from"] = tdr_cur_from.strftime("%d/%m/%Y")
        kpi["tdr_cur_to"] = tdr_cur_to.strftime("%d/%m/%Y")
        prev_params_tdr = [
            tdr_prev_from.strftime("%Y-%m-%d"),
            tdr_prev_to.strftime("%Y-%m-%d"),
        ]
        cur_params_tdr = [
            tdr_cur_from.strftime("%Y-%m-%d"),
            tdr_cur_to.strftime("%Y-%m-%d"),
        ]

        # NCCPAPA: clientes en periodo actual que también compraron en periodo anterior
        cur.execute(
            f"""
            SELECT COUNT(DISTINCT {cliente_expr_l}) AS ntccpa
            FROM leads l
            WHERE EXISTS (
                SELECT 1
                FROM seguimientos s
                INNER JOIN proceso p ON p.id = s.proceso_id
                WHERE s.lead_id = l.id
                  AND LOWER(TRIM(COALESCE(p.nombre_proceso, ''))) = 'cerrado'
                  AND DATE({seg_date_expr_s}) BETWEEN %s AND %s
            ){lead_scope_clause}
        """,
            prev_params_tdr + lead_scope_params,
        )
        ntccpa = (cur.fetchone() or {}).get("ntccpa", 0) or 0

        cur.execute(
            f"""
            SELECT COUNT(DISTINCT {cliente_expr_l}) AS nccpapa
            FROM leads l
            WHERE EXISTS (
                SELECT 1
                FROM seguimientos s
                INNER JOIN proceso p ON p.id = s.proceso_id
                WHERE s.lead_id = l.id
                  AND LOWER(TRIM(COALESCE(p.nombre_proceso, ''))) = 'cerrado'
                  AND DATE({seg_date_expr_s}) BETWEEN %s AND %s
            ){lead_scope_clause}
              AND {cliente_expr_l} IN (
                  SELECT DISTINCT {cliente_expr_l2}
                  FROM leads l2
                  WHERE EXISTS (
                      SELECT 1
                      FROM seguimientos s2
                      INNER JOIN proceso p2 ON p2.id = s2.proceso_id
                      WHERE s2.lead_id = l2.id
                        AND LOWER(TRIM(COALESCE(p2.nombre_proceso, ''))) = 'cerrado'
                        AND DATE({seg_date_expr_s2}) BETWEEN %s AND %s
                  ){lead_scope_clause_l2}
              )
        """,
            cur_params_tdr + lead_scope_params + prev_params_tdr + lead_scope_params_l2,
        )
        nccpapa = (cur.fetchone() or {}).get("nccpapa", 0) or 0

        kpi["ntccpa"] = ntccpa
        kpi["nccpapa"] = nccpapa
        tdr_raw = (nccpapa / ntccpa) if ntccpa else 0  # 0..1
        kpi["tdr"] = tdr_raw * 100  # porcentaje para mostrar
        kpi["tda_ret"] = 100 - kpi["tdr"]

    finally:
        cur.close()

    agent_bundle = {}
    month_labels = {
        1: "Enero",
        2: "Febrero",
        3: "Marzo",
        4: "Abril",
        5: "Mayo",
        6: "Junio",
        7: "Julio",
        8: "Agosto",
        9: "Septiembre",
        10: "Octubre",
        11: "Noviembre",
        12: "Diciembre",
    }
    period_label = (
        f"Año {selected_year} (todo)"
        if all_months
        else f"{month_labels.get(selected_month, 'Mes')} {selected_year}"
    )
    redirect_quarter = selected_quarter

    return dict(
        kpi=kpi,
        agent_bundle=agent_bundle,
        period=period,
        quarter=selected_quarter,
        month=selected_month,
        month_all=all_months,
        period_label=period_label,
        redirect_quarter=redirect_quarter,
        year=selected_year,
        current_year=today.year,
        date_from=(date_from.strftime("%Y-%m-%d") if date_from else ""),
        date_to=(date_to.strftime("%Y-%m-%d") if date_to else ""),
    )


@reportes_bp.route("/analisis-reportes")
@login_required
@role_required(ROLE_ADMIN, ROLE_GERENTE, ROLE_RRHH, ROLE_MARKETING)
def analisis_reportes():
    ctx = _compute_analisis_kpi()
    return render_template("reportes/analisis_reportes.html", **ctx)


@reportes_bp.route("/api/campana-leads/<int:campaign_id>")
@login_required
@role_required(ROLE_ADMIN, ROLE_GERENTE, ROLE_RRHH, ROLE_MARKETING)
def api_campana_leads(campaign_id):
    """Leads vinculados a una campaña + resumen KPI para el popup."""
    cur = mysql.connection.cursor(DictCursor)
    try:
        if not _table_exists("marketing_campaigns"):
            return jsonify({"ok": False, "message": "Campañas no disponibles."}), 404

        cur.execute(
            """
            SELECT id, nombre_campana, periodo_inicio, periodo_fin,
                   COALESCE(inversion, 0) AS inversion
            FROM marketing_campaigns
            WHERE id = %s
            LIMIT 1
            """,
            (campaign_id,),
        )
        camp = cur.fetchone()
        if not camp:
            return jsonify({"ok": False, "message": "Campaña no encontrada."}), 404

        has_codigo = _column_exists("leads", "codigo")
        has_telefono = _column_exists("leads", "telefono")
        has_ruc = _column_exists("leads", "ruc_dni")
        has_bien = _table_exists("bienes_servicios") and _column_exists(
            "leads", "bien_servicio_id"
        )
        has_canal = _table_exists("canales_recepcion") and _column_exists(
            "leads", "canal_id"
        )
        has_proceso = _table_exists("proceso")

        codigo_expr = (
            "COALESCE(NULLIF(TRIM(l.codigo), ''), CONCAT('LED-', l.id))"
            if has_codigo
            else "CONCAT('LED-', l.id)"
        )
        telefono_expr = "COALESCE(l.telefono, '—')" if has_telefono else "'—'"
        ruc_expr = "COALESCE(l.ruc_dni, '—')" if has_ruc else "'—'"
        bien_join = (
            "LEFT JOIN bienes_servicios bs ON bs.id = l.bien_servicio_id"
            if has_bien
            else ""
        )
        bien_expr = "COALESCE(bs.nombre, '—')" if has_bien else "'—'"
        canal_join = (
            "LEFT JOIN canales_recepcion cr ON cr.id = l.canal_id" if has_canal else ""
        )
        canal_expr = "COALESCE(cr.nombre, '—')" if has_canal else "'—'"

        proceso_join = ""
        proceso_expr = "'—'"
        if has_proceso:
            proceso_join = """
                LEFT JOIN (
                    SELECT s1.lead_id, s1.proceso_id
                    FROM seguimientos s1
                    INNER JOIN (
                        SELECT lead_id, MAX(id) AS max_id
                        FROM seguimientos
                        GROUP BY lead_id
                    ) last_s ON last_s.max_id = s1.id
                ) s ON s.lead_id = l.id
                LEFT JOIN proceso p ON p.id = s.proceso_id
            """
            proceso_expr = "COALESCE(p.nombre_proceso, 'Sin iniciar')"

        leads = []
        if _table_exists("marketing_campaign_leads"):
            cur.execute(
                f"""
                SELECT
                    l.id,
                    {codigo_expr} AS codigo,
                    COALESCE(NULLIF(TRIM(l.nombre), ''), 'Sin nombre') AS nombre,
                    {telefono_expr} AS telefono,
                    {ruc_expr} AS ruc_dni,
                    DATE(l.fecha) AS fecha,
                    {bien_expr} AS bien_servicio,
                    {canal_expr} AS canal,
                    {proceso_expr} AS proceso
                FROM marketing_campaign_leads mcl
                INNER JOIN leads l ON l.id = mcl.lead_id
                {bien_join}
                {canal_join}
                {proceso_join}
                WHERE mcl.campaign_id = %s
                ORDER BY l.fecha DESC, l.id DESC
                """,
                (campaign_id,),
            )
            for row in cur.fetchall() or []:
                fecha = row.get("fecha")
                leads.append(
                    {
                        "id": int(row.get("id") or 0),
                        "codigo": row.get("codigo") or f"LED-{row.get('id')}",
                        "nombre": row.get("nombre") or "Sin nombre",
                        "telefono": row.get("telefono") or "—",
                        "ruc_dni": row.get("ruc_dni") or "—",
                        "fecha": fecha.strftime("%Y-%m-%d") if fecha else "—",
                        "bien_servicio": row.get("bien_servicio") or "—",
                        "canal": row.get("canal") or "—",
                        "proceso": row.get("proceso") or "—",
                    }
                )

        return jsonify(
            {
                "ok": True,
                "campaign": {
                    "id": int(camp["id"]),
                    "nombre": camp.get("nombre_campana") or f"Campaña {campaign_id}",
                    "periodo_inicio": str(camp.get("periodo_inicio") or ""),
                    "periodo_fin": str(camp.get("periodo_fin") or ""),
                    "dga": float(camp.get("inversion") or 0),
                },
                "total_leads": len(leads),
                "leads": leads,
            }
        )
    except Exception as e:
        print(f"Error api_campana_leads: {e}")
        return jsonify({"ok": False, "message": str(e)}), 500
    finally:
        cur.close()


@reportes_bp.route("/analisis-reportes/pdf")
@login_required
@role_required(ROLE_ADMIN, ROLE_GERENTE, ROLE_RRHH, ROLE_MARKETING)
def analisis_reportes_pdf():
    from reportlab.lib import colors as rl_colors
    from reportlab.lib.pagesizes import A4
    from reportlab.platypus import (
        SimpleDocTemplate,
        Table,
        TableStyle,
        Paragraph,
        Spacer,
        HRFlowable,
    )
    from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
    from reportlab.lib.units import cm

    ctx = _compute_analisis_kpi()
    kpi = ctx["kpi"]
    q = ctx["quarter"]
    y = ctx["year"]

    quarter_names = {
        1: "Q1 (Ene-Mar)",
        2: "Q2 (Abr-Jun)",
        3: "Q3 (Jul-Sep)",
        4: "Q4 (Oct-Dic)",
    }
    quarter_label = quarter_names.get(q, f"Q{q}")
    period_label = f"{quarter_label} {y}"
    user_name = session.get("nombre") or session.get("usuario") or "Analista CRM"
    org = (request.cookies.get("brand") or "CRM").upper()
    generated_at = datetime.now().strftime("%d/%m/%Y %H:%M")

    buf = io.BytesIO()
    doc = SimpleDocTemplate(
        buf,
        pagesize=A4,
        leftMargin=2 * cm,
        rightMargin=2 * cm,
        topMargin=2 * cm,
        bottomMargin=2 * cm,
    )

    styles = getSampleStyleSheet()
    title_s = ParagraphStyle(
        "RPT_Title",
        parent=styles["Title"],
        fontSize=20,
        spaceAfter=8,
        textColor=rl_colors.HexColor("#0c3f93"),
    )
    h2_s = ParagraphStyle(
        "RPT_H2",
        parent=styles["Heading2"],
        fontSize=13,
        spaceAfter=6,
        spaceBefore=14,
        textColor=rl_colors.HexColor("#0c3f93"),
    )
    body_s = ParagraphStyle(
        "RPT_Body", parent=styles["Normal"], fontSize=10, spaceAfter=4, leading=14
    )
    bullet_s = ParagraphStyle(
        "RPT_Bullet",
        parent=styles["Normal"],
        fontSize=10,
        spaceAfter=3,
        leading=14,
        leftIndent=12,
    )
    small_s = ParagraphStyle(
        "RPT_Small",
        parent=styles["Normal"],
        fontSize=8.5,
        textColor=rl_colors.HexColor("#5b6a85"),
    )

    story = []

    # ── Portada ──────────────────────────────────────────────────
    story.append(
        Paragraph("Informe Profesional de An\u00e1lisis de Reportes KPI", title_s)
    )
    story.append(Paragraph(f"Periodo: <b>{period_label}</b>", body_s))
    story.append(Spacer(1, 0.3 * cm))
    story.append(Paragraph(f"Autor: {user_name}", small_s))
    story.append(Paragraph(f"Fecha: {generated_at}", small_s))
    story.append(Paragraph(f"Organizaci\u00f3n: {org}", small_s))
    story.append(
        HRFlowable(
            width="100%",
            thickness=1,
            color=rl_colors.HexColor("#d6e1f2"),
            spaceAfter=10,
        )
    )

    # ── Resumen ejecutivo ────────────────────────────────────────
    story.append(Paragraph("Resumen Ejecutivo", h2_s))
    story.append(
        Paragraph(
            f"Este informe sintetiza los principales indicadores de adquisici\u00f3n, retenci\u00f3n y "
            f"comportamiento de clientes para {period_label}. Los resultados muestran la relaci\u00f3n "
            f"entre inversi\u00f3n comercial, conversi\u00f3n efectiva y permanencia de clientes.",
            body_s,
        )
    )

    def _acq_q(c):
        return "eficiente" if c <= 1200 else ("moderada" if c <= 2500 else "costosa")

    def _acq_r(t):
        return (
            "alto cumplimiento"
            if t >= 70
            else ("cumplimiento parcial" if t >= 40 else "bajo cumplimiento")
        )

    def _ret_l(t):
        return (
            "retenci\u00f3n robusta"
            if t >= 60
            else (
                "retenci\u00f3n intermedia" if t >= 35 else "retenci\u00f3n fr\u00e1gil"
            )
        )

    for ins in [
        f'<b>Eficiencia de adquisici\u00f3n:</b> CALC = S/ {kpi["calc"]:.2f} \u2192 costo {_acq_q(kpi["calc"])}.',
        f'<b>Objetivo comercial:</b> TDA adquisici\u00f3n = {kpi["tda_acq"]:.1f}% \u2192 {_acq_r(kpi["tda_acq"])}.',
        f'<b>Fidelizaci\u00f3n:</b> TDR = {kpi["tdr"]:.1f}% \u2192 {_ret_l(kpi["tdr"])}.',
        f'<b>Riesgo de abandono:</b> TDA retenci\u00f3n = {kpi["tda_ret"]:.1f}%.',
    ]:
        story.append(Paragraph(f"\u2022 {ins}", bullet_s))

    # ── Introducción ─────────────────────────────────────────────
    story.append(Paragraph("Introducci\u00f3n", h2_s))
    story.append(
        Paragraph(
            "El panel anal\u00edtico integra informaci\u00f3n de leads, seguimientos y procesos comerciales "
            "para medir la eficiencia del embudo y la sostenibilidad de la cartera. Se adopta una lectura "
            "trimestral para consolidar resultados con perspectiva ejecutiva.",
            body_s,
        )
    )

    # ── Metodología ──────────────────────────────────────────────
    story.append(Paragraph("Metodolog\u00eda", h2_s))
    story.append(
        Paragraph(
            f"Datos transaccionales del CRM con el \u00faltimo seguimiento de cada lead para evitar "
            f"duplicidades. Criterio temporal: {period_label}. Unidad de an\u00e1lisis: lead convertido "
            f"identificado por RUC/DNI o nombre.",
            body_s,
        )
    )

    # ── Tabla de KPIs ────────────────────────────────────────────
    story.append(Paragraph("Tabla de Indicadores KPI", h2_s))
    tbl_data = [
        ["Indicador", "Valor", "Interpretaci\u00f3n"],
        [
            "DGA",
            f'S/ {kpi["dga"]:.2f}',
            "Inversi\u00f3n total (campa\u00f1as + ferias)",
        ],
        ["NLC", str(int(kpi["nlc"])), "Leads cerrados en el periodo"],
        ["CALC", f'S/ {kpi["calc"]:.2f}', "Costo por lead convertido"],
        [
            "TDA adquisici\u00f3n",
            f'{kpi["tda_acq"]:.1f}%',
            f'Avance vs meta NLO ({int(kpi["nlo"])})',
        ],
        ["TDR", f'{kpi["tdr"]:.1f}%', "Retenci\u00f3n entre periodos consecutivos"],
        [
            "TDA retenci\u00f3n",
            f'{kpi["tda_ret"]:.1f}%',
            "Clientes que no repiten compra",
        ],
    ]
    tbl = Table(tbl_data, colWidths=[3.5 * cm, 2.8 * cm, 10.7 * cm], repeatRows=1)
    tbl.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), rl_colors.HexColor("#edf3ff")),
                ("TEXTCOLOR", (0, 0), (-1, 0), rl_colors.HexColor("#0c3f93")),
                ("FONTNAME", (0, 0), (-1, 0), "Helvetica-Bold"),
                ("FONTSIZE", (0, 0), (-1, -1), 9),
                ("GRID", (0, 0), (-1, -1), 0.5, rl_colors.HexColor("#d5dfef")),
                (
                    "ROWBACKGROUNDS",
                    (0, 1),
                    (-1, -1),
                    [rl_colors.white, rl_colors.HexColor("#f5f8ff")],
                ),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
            ]
        )
    )
    story.append(tbl)
    story.append(Spacer(1, 0.4 * cm))

    # ── Conclusiones ─────────────────────────────────────────────
    story.append(Paragraph("Conclusiones", h2_s))
    for c in [
        "La eficiencia comercial se explica por el balance entre inversi\u00f3n (DGA) y conversi\u00f3n efectiva (NLC).",
        "La retenci\u00f3n observada impacta directamente en la duraci\u00f3n del ciclo de vida y valor futuro del cliente.",
        "La lectura combinada de adquisici\u00f3n y fidelizaci\u00f3n permite priorizar acciones con mayor retorno.",
    ]:
        story.append(Paragraph(f"\u2022 {c}", bullet_s))

    # ── Recomendaciones ──────────────────────────────────────────
    story.append(Paragraph("Recomendaciones", h2_s))
    for i, r in enumerate(
        [
            "Reasignar presupuesto hacia canales con menor CALC y mayor contribuci\u00f3n al NLC trimestral.",
            "Implementar t\u00e1cticas de reactivaci\u00f3n sobre clientes con alta probabilidad de abandono.",
            "Definir metas mensuales de conversi\u00f3n y retenci\u00f3n con seguimiento quincenal.",
            "Monitorear continuamente la tasa de retenci\u00f3n e implementar acciones correctivas cuando baje del objetivo.",
        ],
        1,
    ):
        story.append(Paragraph(f"{i}. {r}", bullet_s))

    # ── Anexos ───────────────────────────────────────────────────
    story.append(Paragraph("Anexos", h2_s))
    story.append(
        Paragraph(
            "F\u00f3rmulas: CALC=DGA/NLC; TDA adq=(NLC/NLO)\u00d7100; "
            "TDR=(NCCPAPA/NTCCPA)\u00d7100; TDA ret=100\u2212TDR.",
            small_s,
        )
    )

    doc.build(story)
    buf.seek(0)
    filename = f"informe_analisis_Q{q}_{y}.pdf"
    response = make_response(buf.read())
    response.headers["Content-Type"] = "application/pdf"
    response.headers["Content-Disposition"] = f'attachment; filename="{filename}"'
    return response
