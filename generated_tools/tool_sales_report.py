from __future__ import annotations

import re
import os
from typing import Any, Dict

import MySQLdb.cursors

from extensions import mysql
from utils.text_normalizer import normalize_user_text

TOOL_NAME = "tool_sales_report"
TOOL_DESCRIPTION = "Analiza ventas por cliente y periodo con salida agregada."

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
    "octubre": 10,
    "noviembre": 11,
    "diciembre": 12,
}

_ORBES_NEGOCIO_ID = int(os.getenv("ORBES_NEGOCIO_ID", "1"))


def _table_exists(table_name: str) -> bool:
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        cur.execute(
            """
            SELECT COUNT(*) AS total
            FROM information_schema.TABLES
            WHERE TABLE_SCHEMA = DATABASE()
              AND TABLE_NAME = %s
            """,
            (table_name,),
        )
        row = cur.fetchone() or {}
        return int(row.get("total", 0)) > 0
    finally:
        cur.close()


def _run_one(sql: str, params=None) -> Dict[str, Any]:
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        cur.execute(sql, params or ())
        return cur.fetchone() or {}
    finally:
        cur.close()


def _run_all(sql: str, params=None):
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        cur.execute(sql, params or ())
        return cur.fetchall() or []
    finally:
        cur.close()


def _extract_period(question: str):
    q = normalize_user_text(question)
    month = None
    year = None

    month_regex = r"\b(" + "|".join(_MONTHS.keys()) + r")\b"
    m_month = re.search(month_regex, q)
    if m_month:
        month = _MONTHS[m_month.group(1)]

    m_year = re.search(r"\b(19\d{2}|20\d{2})\b", q)
    if m_year:
        year = int(m_year.group(1))

    return month, year


def execute(context: Dict[str, Any]) -> Dict[str, Any]:
    if not _table_exists("ventas_concretadas"):
        return {
            "ok": False,
            "tool": TOOL_NAME,
            "error": "No existe la tabla ventas_concretadas en este esquema.",
        }

    leads_table = (
        "leads"
        if _table_exists("leads")
        else ("lead" if _table_exists("lead") else None)
    )

    question = str((context or {}).get("question") or "")
    month, year = _extract_period(question)

    where_params = []
    period_label = "historico"
    if month and year:
        where_params = [year, month]
        period_label = f"{year}-{month:02d}"
    elif month:
        where_params = [month]
        period_label = f"mes {month:02d} del anio actual"
    elif year:
        where_params = [year]
        period_label = f"anio {year}"

    ventas_sql = (
        "SELECT COUNT(*) AS total "
        "FROM ventas_concretadas vc "
        "JOIN leads l ON l.id = vc.lead_id "
        "WHERE l.negocio_id = %s"
        + (
            " AND YEAR(vc.fecha_venta) = %s AND MONTH(vc.fecha_venta) = %s"
            if (month and year)
            else (
                " AND YEAR(vc.fecha_venta) = YEAR(CURDATE()) AND MONTH(vc.fecha_venta) = %s"
                if month
                else " AND YEAR(vc.fecha_venta) = %s" if year else ""
            )
        )
    )
    monto_sql = (
        "SELECT ROUND(COALESCE(SUM(vc.monto),0),2) AS monto_total "
        "FROM ventas_concretadas vc "
        "JOIN leads l ON l.id = vc.lead_id "
        "WHERE l.negocio_id = %s"
        + (
            " AND YEAR(vc.fecha_venta) = %s AND MONTH(vc.fecha_venta) = %s"
            if (month and year)
            else (
                " AND YEAR(vc.fecha_venta) = YEAR(CURDATE()) AND MONTH(vc.fecha_venta) = %s"
                if month
                else " AND YEAR(vc.fecha_venta) = %s" if year else ""
            )
        )
    )
    scoped_params = [_ORBES_NEGOCIO_ID] + where_params
    ventas_total_row = _run_one(ventas_sql, tuple(scoped_params))
    monto_total_row = _run_one(monto_sql, tuple(scoped_params))

    serie_6m = _run_all(
        """
        SELECT
            DATE_FORMAT(fecha_venta, '%%Y-%%m') AS periodo,
            COUNT(*) AS total_ventas,
            ROUND(COALESCE(SUM(monto), 0), 2) AS monto_total
        FROM ventas_concretadas vc
        JOIN leads l ON l.id = vc.lead_id
        WHERE l.negocio_id = %s
          AND vc.fecha_venta >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
        GROUP BY DATE_FORMAT(vc.fecha_venta, '%%Y-%%m')
        ORDER BY periodo ASC
        """,
        (_ORBES_NEGOCIO_ID,),
    )

    top_producto_sql = (
        """
        SELECT
            COALESCE(bs.nombre, CONCAT('ID ', vc.bien_servicio_id)) AS producto,
            COUNT(*) AS total_ventas,
            ROUND(COALESCE(SUM(vc.monto), 0), 2) AS monto_total
        FROM ventas_concretadas vc
        LEFT JOIN bienes_servicios bs ON bs.id = vc.bien_servicio_id
        """
        + (
            " JOIN leads l ON l.id = vc.lead_id WHERE l.negocio_id = %s AND YEAR(vc.fecha_venta) = %s AND MONTH(vc.fecha_venta) = %s"
            if (month and year)
            else (
                " JOIN leads l ON l.id = vc.lead_id WHERE l.negocio_id = %s AND YEAR(vc.fecha_venta) = YEAR(CURDATE()) AND MONTH(vc.fecha_venta) = %s"
                if month
                else (
                    " JOIN leads l ON l.id = vc.lead_id WHERE l.negocio_id = %s AND YEAR(vc.fecha_venta) = %s"
                    if year
                    else " JOIN leads l ON l.id = vc.lead_id WHERE l.negocio_id = %s"
                )
            )
        )
        + """
        GROUP BY vc.bien_servicio_id, bs.nombre
        ORDER BY total_ventas DESC, monto_total DESC
        LIMIT 1
        """
    )
    top_producto_params = tuple(scoped_params)
    top_producto = _run_one(top_producto_sql, top_producto_params)

    embudo = {}
    if leads_table and _table_exists("seguimientos"):
        embudo = _run_one(
            f"""
            SELECT
                (SELECT COUNT(*) FROM {leads_table} WHERE negocio_id = %s) AS total_leads,
                (SELECT COUNT(DISTINCT s.lead_id)
                 FROM seguimientos s
                 JOIN {leads_table} l ON l.id = s.lead_id
                 WHERE l.negocio_id = %s) AS leads_con_seguimiento,
                (SELECT COUNT(*)
                 FROM ventas_concretadas vc
                 JOIN {leads_table} l2 ON l2.id = vc.lead_id
                 WHERE l2.negocio_id = %s) AS ventas_cerradas
            """,
            (_ORBES_NEGOCIO_ID, _ORBES_NEGOCIO_ID, _ORBES_NEGOCIO_ID),
        )

    total_ventas = int(ventas_total_row.get("total") or 0)
    monto_total = float(monto_total_row.get("monto_total") or 0)
    producto = top_producto.get("producto") if top_producto else None

    summary = (
        f"Reporte CRM ({period_label}) desde BD: {total_ventas} ventas registradas, "
        f"monto acumulado {monto_total:.2f}. Top producto: {producto or 'sin datos'}."
    )

    return {
        "ok": True,
        "tool": TOOL_NAME,
        "description": TOOL_DESCRIPTION,
        "message": summary,
        "context_preview": str(context)[:300],
        "data": {
            "source": "mysql",
            "period": period_label,
            "ventas_total": total_ventas,
            "monto_total": monto_total,
            "serie_6m": serie_6m,
            "top_producto": top_producto,
            "embudo": embudo,
            "executed_queries": {
                "ventas_total_sql": ventas_sql,
                "monto_total_sql": monto_sql,
                "top_producto_sql": " ".join(top_producto_sql.split()),
                "query_params": scoped_params,
            },
        },
    }
