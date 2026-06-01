import re
import os
from datetime import date
import MySQLdb.cursors
from extensions import mysql
from utils.text_normalizer import normalize_user_text


class DBAgent:
    """Agente para consultas de leads y ventas con lenguaje natural → SQL."""

    _MONTHS = {
        "enero": 1,
        "febrero": 2,
        "marzo": 3,
        "abril": 4,
        "mayo": 5,
        "junio": 6,
        "julio": 7,
        "agosto": 8,
        "septiembre": 9,
        "setiembre": 9,
        "octubre": 10,
        "noviembre": 11,
        "diciembre": 12,
    }

    # Producto / línea de negocio → LIKE pattern para bienes_servicios.nombre
    _BS_PATTERNS = [
        (
            r"\b(maquinaria|tractor|tractores|cosechadora|lovol|maze|90hp)\b",
            "Maquinaria%",
            "maquinaria agrícola",
        ),
        (r"\b(mantenimiento|servicio t[eé]cnico)\b", "Mantenimiento%", "mantenimiento"),
        (r"\b(equipos? menores?)\b", "Equipos Menores%", "equipos menores"),
        (
            r"\b(equipos? fuerzas?|equipos? de fuerza)\b",
            "Equipos Fuerzas%",
            "equipos fuerzas",
        ),
        (r"\b(riego|proyecto de riego|manguera)\b", "%riego%", "proyecto de riego"),
        (r"\b(pl[aá]stico|pl[aá]sticos?)\b", "Plasticos%", "plásticos agrícolas"),
        (r"\b(servicios?)\b", "Servicios%", "servicios"),
    ]

    # Estado del proceso comercial → proceso_id (tabla proceso)
    _PROCESS_PATTERNS = [
        (
            r"\b(cerrad[oa]s? no vendid[oa]s?|no vendid[oa]s?|perdid[oa]s?)\b",
            6,
            "Cerrado No Vendido",
        ),
        (r"\b(cerrad[oa]s?|ganados?|ventas? cerradas?)\b", 5, "Cerrado"),
        (r"\b(cotizad[oa]s?|con cotizaci[oó]n)\b", 4, "Cotizado"),
        (r"\b(programad[oa]s?|agendad[oa]s?|con cita)\b", 3, "Programado"),
        (r"\b(en seguimiento|con seguimiento|gestionados?)\b", 2, "Seguimiento"),
        (r"\b(no iniciados?|sin gestionar|reci[eé]n ingresados?)\b", 1, "No iniciado"),
    ]

    def __init__(self):
        self.negocio_id = int(os.getenv("ORBES_NEGOCIO_ID", "1"))

    # ─── DB helpers ──────────────────────────────────────────────────────────

    def _table_exists(self, table_name):
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            cur.execute(
                "SELECT COUNT(*) AS n FROM information_schema.TABLES "
                "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s",
                (table_name,),
            )
            return int((cur.fetchone() or {}).get("n", 0)) > 0
        finally:
            cur.close()

    def _column_exists(self, table_name, column_name):
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            cur.execute(
                "SELECT COUNT(*) AS n FROM information_schema.COLUMNS "
                "WHERE TABLE_SCHEMA=DATABASE() AND TABLE_NAME=%s AND COLUMN_NAME=%s",
                (table_name, column_name),
            )
            return int((cur.fetchone() or {}).get("n", 0)) > 0
        finally:
            cur.close()

    def _run_scalar(self, sql, params=None):
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            cur.execute(sql, params or ())
            row = cur.fetchone() or {}
            return next(iter(row.values())) if row else 0
        finally:
            cur.close()

    def _run_row(self, sql, params=None):
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            cur.execute(sql, params or ())
            return cur.fetchone() or {}
        finally:
            cur.close()

    def _run_all(self, sql, params=None):
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            cur.execute(sql, params or ())
            return cur.fetchall() or []
        finally:
            cur.close()

    def _append_condition(self, sql, condition):
        split_re = re.compile(r"\b(GROUP\s+BY|ORDER\s+BY|LIMIT)\b", re.IGNORECASE)
        parts = split_re.split(sql, maxsplit=1)
        head = parts[0].strip()
        tail = ""
        if len(parts) > 1:
            tail = " " + "".join(parts[1:]).strip()

        if re.search(r"\bWHERE\b", head, re.IGNORECASE):
            head = f"{head} AND {condition}"
        else:
            head = f"{head} WHERE {condition}"
        return (head + tail).strip()

    def _scope_sql_to_orbes(self, sql, pattern):
        if not sql:
            return sql

        leads_table = self._resolve_leads_table()
        if not leads_table or not self._column_exists(leads_table, "negocio_id"):
            return sql

        condition = f"l.negocio_id = {int(self.negocio_id)}"

        if pattern in {"pipeline", "lead_proceso", "leads_by_bs", "lead_count"}:
            sql = re.sub(
                rf"\bFROM\s+{re.escape(leads_table)}\b(\s+l)?",
                f"FROM {leads_table} l",
                sql,
                count=1,
                flags=re.IGNORECASE,
            )
            return self._append_condition(sql, condition)

        if pattern in {"sales_month", "top_products"}:
            if re.search(r"\bFROM\s+ventas_concretadas\s+vc\b", sql, re.IGNORECASE):
                if not re.search(
                    r"\bJOIN\s+leads\s+l\s+ON\s+l\.id\s*=\s*vc\.lead_id\b",
                    sql,
                    re.IGNORECASE,
                ):
                    sql = re.sub(
                        r"\bFROM\s+ventas_concretadas\s+vc\b",
                        "FROM ventas_concretadas vc JOIN leads l ON l.id = vc.lead_id",
                        sql,
                        count=1,
                        flags=re.IGNORECASE,
                    )
                return self._append_condition(sql, condition)

            if re.search(r"\bFROM\s+ventas_concretadas\b", sql, re.IGNORECASE):
                sql = re.sub(
                    r"\bFROM\s+ventas_concretadas\b",
                    "FROM ventas_concretadas vc JOIN leads l ON l.id = vc.lead_id",
                    sql,
                    count=1,
                    flags=re.IGNORECASE,
                )
                return self._append_condition(sql, condition)

        return sql

    # ─── Schema resolution ────────────────────────────────────────────────────

    def _resolve_leads_table(self):
        for t in ("leads", "lead"):
            if self._table_exists(t):
                return t
        return None

    def _resolve_leads_date_column(self, leads_table):
        for col in ("fecha", "fecha_creacion", "created_at", "fecha_registro"):
            if self._column_exists(leads_table, col):
                return col
        return None

    # ─── Intent detectors ────────────────────────────────────────────────────

    def _detect_bien_servicio(self, q):
        """Returns (LIKE_pattern, label) if a product/service category is found."""
        for pat, like_val, label in self._BS_PATTERNS:
            if re.search(pat, q, re.IGNORECASE):
                return like_val, label
        return None, None

    def _detect_proceso(self, q):
        """Returns (proceso_id, nombre) if a sales process state is mentioned."""
        for pat, pid, nombre in self._PROCESS_PATTERNS:
            if re.search(pat, q, re.IGNORECASE):
                return pid, nombre
        return None, None

    # ─── Query builder ───────────────────────────────────────────────────────

    def _natural_to_sql(self, question):
        q_raw = (question or "").strip()
        q = normalize_user_text(q_raw)
        current_year = date.today().year

        leads_table = self._resolve_leads_table()
        if not leads_table:
            return None, {
                "ok": False,
                "pattern": "error",
                "error": "No existe la tabla leads en este esquema.",
            }

        lead_date_col = self._resolve_leads_date_column(leads_table)
        bs_like, bs_label = self._detect_bien_servicio(q)
        proceso_id, proceso_nombre = self._detect_proceso(q)

        month_regex = r"\b(" + "|".join(self._MONTHS.keys()) + r")\b"
        m_month = re.search(month_regex, q, re.IGNORECASE)
        m_year = re.search(r"\b(19\d{2}|20\d{2})\b", q)
        m_days = re.search(r"\bultim[oa]s?\s+(\d{1,3})\s+d[ií]as\b", q, re.IGNORECASE)

        is_lead = bool(re.search(r"\bleads?\b", q, re.IGNORECASE))
        is_venta = bool(
            re.search(
                r"\bventas?\b|factur|vendid[oa]|ingreso|vendimos", q, re.IGNORECASE
            )
        )
        is_pipeline = bool(
            re.search(
                r"\bpipeline\b|\bembudo\b|\bestados? del? (lead|pipeline)\b|\bresumen.*leads?\b",
                q,
                re.IGNORECASE,
            )
        )

        # ── PIPELINE / EMBUDO ────────────────────────────────────────────────
        if is_pipeline:
            sql = (
                f"SELECT p.nombre AS proceso, COUNT(DISTINCT l.id) AS total "
                f"FROM {leads_table} l "
                f"JOIN seguimientos s ON s.lead_id = l.id "
                f"  AND s.id = (SELECT MAX(s2.id) FROM seguimientos s2 WHERE s2.lead_id = l.id) "
                f"JOIN proceso p ON p.id = s.proceso_id "
                f"GROUP BY p.id, p.nombre ORDER BY p.id"
            )
            return sql, {"pattern": "pipeline"}

        # ── LEADS POR ESTADO DE PROCESO ──────────────────────────────────────
        if proceso_id and is_lead:
            bs_join = (
                (
                    f" JOIN bienes_servicios bs ON bs.id = l.bien_servicio_id "
                    f"AND bs.nombre LIKE '{bs_like}'"
                )
                if bs_like
                else ""
            )
            if m_month and lead_date_col:
                month_num = self._MONTHS[m_month.group(1).lower()]
                year_num = int(m_year.group(1)) if m_year else current_year
                date_filter = (
                    f" AND YEAR(l.{lead_date_col})={year_num}"
                    f" AND MONTH(l.{lead_date_col})={month_num}"
                )
            else:
                date_filter = ""
            sql = (
                f"SELECT COUNT(DISTINCT l.id) AS total "
                f"FROM {leads_table} l "
                f"JOIN seguimientos s ON s.lead_id = l.id "
                f"  AND s.id = (SELECT MAX(s2.id) FROM seguimientos s2 WHERE s2.lead_id = l.id) "
                f"{bs_join}"
                f"WHERE s.proceso_id = {proceso_id}{date_filter}"
            )
            return sql, {
                "pattern": "lead_proceso",
                "proceso_id": proceso_id,
                "proceso_nombre": proceso_nombre,
                "bs_label": bs_label,
                "month": m_month.group(1).lower() if m_month else None,
                "year": (
                    int(m_year.group(1))
                    if m_year
                    else (current_year if m_month else None)
                ),
            }

        # ── LEADS POR PRODUCTO / LÍNEA DE NEGOCIO ───────────────────────────
        if bs_like and is_lead:
            if not lead_date_col:
                return None, {
                    "ok": False,
                    "pattern": "error",
                    "error": "No se encontró columna de fecha en leads.",
                }
            bs_join = (
                f"JOIN bienes_servicios bs ON bs.id = l.bien_servicio_id "
                f"AND bs.nombre LIKE '{bs_like}'"
            )
            if m_month:
                month_num = self._MONTHS[m_month.group(1).lower()]
                year_num = int(m_year.group(1)) if m_year else current_year
                sql = (
                    f"SELECT COUNT(*) AS total FROM {leads_table} l "
                    f"{bs_join} "
                    f"WHERE YEAR(l.{lead_date_col})={year_num} AND MONTH(l.{lead_date_col})={month_num}"
                )
                return sql, {
                    "pattern": "leads_by_bs",
                    "bs_label": bs_label,
                    "month": m_month.group(1).lower(),
                    "year": year_num,
                }
            elif re.search(r"\b(este mes|del mes|mes actual)\b", q, re.IGNORECASE):
                sql = (
                    f"SELECT COUNT(*) AS total FROM {leads_table} l "
                    f"{bs_join} "
                    f"WHERE YEAR(l.{lead_date_col})=YEAR(CURDATE()) "
                    f"AND MONTH(l.{lead_date_col})=MONTH(CURDATE())"
                )
                return sql, {
                    "pattern": "leads_by_bs",
                    "bs_label": bs_label,
                    "period": "este_mes",
                }
            elif m_days:
                days = int(m_days.group(1))
                sql = (
                    f"SELECT COUNT(*) AS total FROM {leads_table} l "
                    f"{bs_join} "
                    f"WHERE l.{lead_date_col} >= DATE_SUB(CURDATE(), INTERVAL {days} DAY)"
                )
                return sql, {
                    "pattern": "leads_by_bs",
                    "bs_label": bs_label,
                    "period": "ultimos_dias",
                    "days": days,
                }
            else:
                sql = f"SELECT COUNT(*) AS total FROM {leads_table} l " f"{bs_join}"
                return sql, {
                    "pattern": "leads_by_bs",
                    "bs_label": bs_label,
                    "period": "total",
                }

        # ── LEADS: últimos N días ────────────────────────────────────────────
        if m_days and is_lead:
            if not lead_date_col:
                return None, {
                    "ok": False,
                    "pattern": "error",
                    "error": "No se encontró columna de fecha en leads.",
                }
            days = int(m_days.group(1))
            sql = (
                f"SELECT COUNT(*) AS total FROM {leads_table} "
                f"WHERE {lead_date_col} >= DATE_SUB(CURDATE(), INTERVAL {days} DAY)"
            )
            return sql, {
                "pattern": "lead_count",
                "period": "ultimos_dias",
                "days": days,
            }

        # ── LEADS: mes explícito ─────────────────────────────────────────────
        if m_month and is_lead:
            if not lead_date_col:
                return None, {
                    "ok": False,
                    "pattern": "error",
                    "error": "No se encontró columna de fecha en leads.",
                }
            month_name = m_month.group(1).lower()
            month_num = self._MONTHS[month_name]
            year_num = int(m_year.group(1)) if m_year else current_year
            sql = (
                f"SELECT COUNT(*) AS total FROM {leads_table} "
                f"WHERE YEAR({lead_date_col})={year_num} AND MONTH({lead_date_col})={month_num}"
            )
            return sql, {
                "pattern": "lead_count",
                "month": month_name,
                "month_num": month_num,
                "year": year_num,
            }

        # ── LEADS: este mes / del mes ────────────────────────────────────────
        if is_lead and re.search(
            r"\b(este mes|del mes|mes actual)\b", q, re.IGNORECASE
        ):
            if not lead_date_col:
                return None, {
                    "ok": False,
                    "pattern": "error",
                    "error": "No se encontró columna de fecha en leads.",
                }
            sql = (
                f"SELECT COUNT(*) AS total FROM {leads_table} "
                f"WHERE YEAR({lead_date_col})=YEAR(CURDATE()) "
                f"AND MONTH({lead_date_col})=MONTH(CURDATE())"
            )
            return sql, {"pattern": "lead_count", "period": "este_mes"}

        # ── LEADS: último mes ────────────────────────────────────────────────
        if is_lead and re.search(
            r"\b(ultimo mes|último mes|mes pasado)\b", q, re.IGNORECASE
        ):
            if not lead_date_col:
                return None, {
                    "ok": False,
                    "pattern": "error",
                    "error": "No se encontró columna de fecha en leads.",
                }
            sql = (
                f"SELECT COUNT(*) AS total FROM {leads_table} "
                f"WHERE YEAR({lead_date_col})=YEAR(DATE_SUB(CURDATE(),INTERVAL 1 MONTH)) "
                f"AND MONTH({lead_date_col})=MONTH(DATE_SUB(CURDATE(),INTERVAL 1 MONTH))"
            )
            return sql, {"pattern": "lead_count", "period": "ultimo_mes"}

        # ── LEADS: total ─────────────────────────────────────────────────────
        if re.search(
            r"\b(cu[aá]ntos|total|tenemos|hay)\b.*\bleads?\b"
            r"|\bleads?\b.*\b(tenemos|hay|total)\b",
            q,
            re.IGNORECASE,
        ):
            sql = f"SELECT COUNT(*) AS total FROM {leads_table}"
            return sql, {"pattern": "lead_count", "period": "total"}

        # ── VENTAS POR PRODUCTO ──────────────────────────────────────────────
        if bs_like and is_venta:
            bs_join = (
                f"JOIN bienes_servicios bs ON bs.id = vc.bien_servicio_id "
                f"AND bs.nombre LIKE '{bs_like}'"
            )
            if m_month:
                month_num = self._MONTHS[m_month.group(1).lower()]
                year_num = int(m_year.group(1)) if m_year else current_year
                sql = (
                    "SELECT COUNT(*) AS total, COALESCE(SUM(vc.monto),0) AS monto "
                    "FROM ventas_concretadas vc "
                    f"{bs_join} "
                    f"WHERE YEAR(vc.fecha_venta)={year_num} AND MONTH(vc.fecha_venta)={month_num}"
                )
                return sql, {
                    "pattern": "sales_month",
                    "bs_label": bs_label,
                    "month": m_month.group(1).lower(),
                    "year": year_num,
                }
            elif re.search(r"\b(este mes|del mes|mes actual)\b", q, re.IGNORECASE):
                sql = (
                    "SELECT COUNT(*) AS total, COALESCE(SUM(vc.monto),0) AS monto "
                    "FROM ventas_concretadas vc "
                    f"{bs_join} "
                    "WHERE YEAR(vc.fecha_venta)=YEAR(CURDATE()) "
                    "AND MONTH(vc.fecha_venta)=MONTH(CURDATE())"
                )
                return sql, {
                    "pattern": "sales_month",
                    "bs_label": bs_label,
                    "period": "este_mes",
                }
            elif m_days:
                days = int(m_days.group(1))
                sql = (
                    "SELECT COUNT(*) AS total, COALESCE(SUM(vc.monto),0) AS monto "
                    "FROM ventas_concretadas vc "
                    f"{bs_join} "
                    f"WHERE vc.fecha_venta >= DATE_SUB(CURDATE(), INTERVAL {days} DAY)"
                )
                return sql, {
                    "pattern": "sales_month",
                    "bs_label": bs_label,
                    "period": "ultimos_dias",
                    "days": days,
                }
            else:
                sql = (
                    "SELECT COUNT(*) AS total, COALESCE(SUM(vc.monto),0) AS monto "
                    "FROM ventas_concretadas vc "
                    f"{bs_join}"
                )
                return sql, {
                    "pattern": "sales_month",
                    "bs_label": bs_label,
                    "period": "total",
                }

        # ── VENTAS: mes explícito ────────────────────────────────────────────
        if m_month and is_venta:
            month_name = m_month.group(1).lower()
            month_num = self._MONTHS[month_name]
            year_num = int(m_year.group(1)) if m_year else current_year
            sql = (
                "SELECT COUNT(*) AS total, COALESCE(SUM(monto),0) AS monto "
                "FROM ventas_concretadas "
                f"WHERE YEAR(fecha_venta)={year_num} AND MONTH(fecha_venta)={month_num}"
            )
            return sql, {
                "pattern": "sales_month",
                "month": month_name,
                "month_num": month_num,
                "year": year_num,
            }

        # ── VENTAS: este mes / del mes ───────────────────────────────────────
        if is_venta and re.search(
            r"\b(este mes|del mes|mes actual)\b", q, re.IGNORECASE
        ):
            sql = (
                "SELECT COUNT(*) AS total, COALESCE(SUM(monto),0) AS monto "
                "FROM ventas_concretadas "
                "WHERE YEAR(fecha_venta)=YEAR(CURDATE()) "
                "AND MONTH(fecha_venta)=MONTH(CURDATE())"
            )
            return sql, {"pattern": "sales_month", "period": "este_mes"}

        # ── VENTAS: último mes ───────────────────────────────────────────────
        if is_venta and re.search(
            r"\b(ultimo mes|último mes|mes pasado)\b", q, re.IGNORECASE
        ):
            sql = (
                "SELECT COUNT(*) AS total, COALESCE(SUM(monto),0) AS monto "
                "FROM ventas_concretadas "
                "WHERE YEAR(fecha_venta)=YEAR(DATE_SUB(CURDATE(),INTERVAL 1 MONTH)) "
                "AND MONTH(fecha_venta)=MONTH(DATE_SUB(CURDATE(),INTERVAL 1 MONTH))"
            )
            return sql, {"pattern": "sales_month", "period": "ultimo_mes"}

        # ── VENTAS: últimos N días ───────────────────────────────────────────
        if m_days and is_venta:
            days = int(m_days.group(1))
            sql = (
                "SELECT COUNT(*) AS total, COALESCE(SUM(monto),0) AS monto "
                "FROM ventas_concretadas "
                f"WHERE fecha_venta >= DATE_SUB(CURDATE(), INTERVAL {days} DAY)"
            )
            return sql, {
                "pattern": "sales_month",
                "period": "ultimos_dias",
                "days": days,
            }

        # ── VENTAS: total (histórico) ────────────────────────────────────────
        if re.search(
            r"\b(cu[aá]ntas|total|tenemos)\b.*\bventas?\b"
            r"|\bventas?\b.*\b(totales?|en total|tenemos)\b",
            q,
            re.IGNORECASE,
        ):
            sql = "SELECT COUNT(*) AS total, COALESCE(SUM(monto),0) AS monto FROM ventas_concretadas"
            return sql, {"pattern": "sales_month", "period": "total"}

        # ── TOP PRODUCTOS ────────────────────────────────────────────────────
        if re.search(
            r"\b(top|mas vendido|m[aá]s vendido|productos? m[aá]s|m[aá]s vendidos?)\b",
            q,
            re.IGNORECASE,
        ):
            sql = (
                "SELECT bs.nombre AS producto, COUNT(*) AS total "
                "FROM ventas_concretadas vc "
                "JOIN bienes_servicios bs ON bs.id = vc.bien_servicio_id "
                "GROUP BY bs.nombre ORDER BY total DESC LIMIT 5"
            )
            return sql, {"pattern": "top_products"}

        # ── FALLBACK HELP ────────────────────────────────────────────────────
        return None, {
            "pattern": "help",
            "help": (
                "No entendí esa consulta. Puedes preguntarme:\n"
                "• 'cuántos leads en enero' / 'leads de este mes'\n"
                "• 'leads de maquinaria en enero' / 'leads cotizados'\n"
                "• 'ventas del mes' / 'ventas de enero de 2026'\n"
                "• 'ventas de tractores este mes'\n"
                "• 'top productos vendidos'\n"
                "• 'pipeline' o 'embudo de ventas'"
            ),
        }

    # ─── Main handler ────────────────────────────────────────────────────────

    def handle(self, question):
        sql, meta = self._natural_to_sql(question)

        if not sql:
            return {
                "ok": False,
                "agent": "db_agent",
                "error": meta.get("error") or meta.get("help"),
            }

        pattern = meta.get("pattern")
        sql = self._scope_sql_to_orbes(sql, pattern)

        # ── Pipeline / embudo ────────────────────────────────────────────────
        if pattern == "pipeline":
            rows = self._run_all(sql)
            if not rows:
                answer = "No hay datos de proceso/pipeline para mostrar (los leads necesitan seguimientos registrados)."
            else:
                lines = [f"  • {r['proceso']}: {r['total']} leads" for r in rows]
                total = sum(r["total"] for r in rows)
                answer = (
                    f"Pipeline de ventas ({total} leads con seguimiento):\n"
                    + "\n".join(lines)
                )
            return {
                "ok": True,
                "agent": "db_agent",
                "intent": "database",
                "sql": sql,
                "answer": answer,
                "data": {"rows": rows},
                "metadata": meta,
            }

        # ── Leads por proceso de venta ────────────────────────────────────────
        if pattern == "lead_proceso":
            total = int(self._run_scalar(sql))
            proceso_nombre = meta.get("proceso_nombre", "ese estado")
            bs_part = f" de {meta['bs_label']}" if meta.get("bs_label") else ""
            if meta.get("month") and meta.get("year"):
                answer = (
                    f"En {meta['month']} de {meta['year']} hay {total} leads{bs_part} "
                    f"en estado '{proceso_nombre}'."
                )
            else:
                answer = f"Hay {total} leads{bs_part} en estado '{proceso_nombre}'."
            return {
                "ok": True,
                "agent": "db_agent",
                "intent": "database",
                "sql": sql,
                "answer": answer,
                "data": {"total": total},
                "metadata": meta,
            }

        # ── Leads por producto / línea de negocio ─────────────────────────────
        if pattern == "leads_by_bs":
            total = int(self._run_scalar(sql))
            bs_label = meta.get("bs_label", "ese producto")
            if meta.get("month") and meta.get("year"):
                answer = f"En {meta['month']} de {meta['year']} se registraron {total} leads de {bs_label}."
            elif meta.get("period") == "este_mes":
                answer = f"Este mes se registraron {total} leads de {bs_label}."
            elif meta.get("period") == "ultimos_dias":
                answer = f"En los últimos {meta['days']} días se registraron {total} leads de {bs_label}."
            else:
                answer = f"Hay {total} leads de {bs_label} en total."
            return {
                "ok": True,
                "agent": "db_agent",
                "intent": "database",
                "sql": sql,
                "answer": answer,
                "data": {"total": total},
                "metadata": meta,
            }

        # ── Leads: conteo ─────────────────────────────────────────────────────
        if pattern == "lead_count":
            total = int(self._run_scalar(sql))
            period = meta.get("period")
            if period == "total":
                answer = f"Actualmente hay {total} leads en total."
            elif period == "este_mes":
                answer = f"Este mes se registraron {total} leads."
            elif period == "ultimo_mes":
                answer = f"El mes pasado se registraron {total} leads."
            elif period == "ultimos_dias":
                answer = f"En los últimos {meta.get('days')} días se registraron {total} leads."
            elif meta.get("month") and meta.get("year"):
                answer = f"En {meta['month']} de {meta['year']} se registraron {total} leads."
            else:
                answer = f"Se encontraron {total} leads."
            return {
                "ok": True,
                "agent": "db_agent",
                "intent": "database",
                "sql": sql,
                "answer": answer,
                "data": {"total": total},
                "metadata": meta,
            }

        # ── Ventas: conteo + monto ────────────────────────────────────────────
        if pattern == "sales_month":
            if not self._table_exists("ventas_concretadas"):
                return {
                    "ok": False,
                    "agent": "db_agent",
                    "error": "La tabla ventas_concretadas no existe en este esquema.",
                }
            row = self._run_row(sql)
            total = int(row.get("total") or 0)
            monto = float(row.get("monto") or 0)
            monto_str = f" (S/ {monto:,.2f})" if monto > 0 else ""
            bs_part = f" de {meta['bs_label']}" if meta.get("bs_label") else ""
            period = meta.get("period")
            if meta.get("month") and meta.get("year"):
                answer = f"En {meta['month']} de {meta['year']} se registraron {total} ventas{bs_part}{monto_str}."
            elif period == "este_mes":
                answer = f"Este mes se registraron {total} ventas{bs_part}{monto_str}."
            elif period == "ultimo_mes":
                answer = (
                    f"El mes pasado se registraron {total} ventas{bs_part}{monto_str}."
                )
            elif period == "ultimos_dias":
                answer = f"En los últimos {meta.get('days')} días: {total} ventas{bs_part}{monto_str}."
            elif period == "total":
                answer = f"En total hay {total} ventas registradas{bs_part}{monto_str}."
            else:
                answer = f"Se encontraron {total} ventas{bs_part}{monto_str}."
            return {
                "ok": True,
                "agent": "db_agent",
                "intent": "database",
                "sql": sql,
                "answer": answer,
                "data": {"total": total, "monto_total": monto},
                "metadata": meta,
            }

        # ── Top productos ──────────────────────────────────────────────────────
        if pattern == "top_products":
            if not self._table_exists("ventas_concretadas"):
                return {
                    "ok": False,
                    "agent": "db_agent",
                    "error": "La tabla ventas_concretadas no existe en este esquema.",
                }
            rows = self._run_all(sql)
            if not rows:
                answer = "No hay datos de productos vendidos para mostrar."
            else:
                lines = [
                    f"  {i+1}. {r.get('producto')}: {int(r.get('total', 0))} ventas"
                    for i, r in enumerate(rows)
                ]
                answer = "Top productos vendidos:\n" + "\n".join(lines)
            return {
                "ok": True,
                "agent": "db_agent",
                "intent": "database",
                "sql": sql,
                "answer": answer,
                "data": {"rows": rows},
                "metadata": meta,
            }

        return {
            "ok": False,
            "agent": "db_agent",
            "error": meta.get("help") or "No reconocí ese patrón de consulta.",
        }
