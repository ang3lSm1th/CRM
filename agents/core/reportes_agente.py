import re
import os
import MySQLdb.cursors

from extensions import mysql
from agents.core.db_agent import DBAgent
from generated_tools.tool_sales_report import execute as sales_report_execute
from utils.text_normalizer import normalize_user_text


class ReportesAgente:
    """Responde reportes avanzados: tendencia, embudo y producto más vendido."""

    def __init__(self):
        self.negocio_id = int(os.getenv("ORBES_NEGOCIO_ID", "1"))
        self.db_agent = DBAgent()

    def _table_exists(self, table_name):
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

    def _run_all(self, sql, params=None):
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            cur.execute(sql, params or ())
            return cur.fetchall() or []
        finally:
            cur.close()

    def _run_one(self, sql, params=None):
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            cur.execute(sql, params or ())
            return cur.fetchone() or {}
        finally:
            cur.close()

    def _ventas_tendencia(self):
        if not self._table_exists("ventas_concretadas"):
            return {"ok": False, "error": "No existe la tabla ventas_concretadas."}

        sql = """
            SELECT
                DATE_FORMAT(vc.fecha_venta, '%%Y-%%m') AS periodo,
                COUNT(*) AS total_ventas,
                ROUND(COALESCE(SUM(vc.monto), 0), 2) AS monto_total
            FROM ventas_concretadas vc
            JOIN leads l ON l.id = vc.lead_id
            WHERE l.negocio_id = %s
              AND vc.fecha_venta >= DATE_SUB(CURDATE(), INTERVAL 6 MONTH)
            GROUP BY DATE_FORMAT(vc.fecha_venta, '%%Y-%%m')
            ORDER BY periodo ASC
        """
        rows = self._run_all(sql, (self.negocio_id,))
        if not rows:
            return {
                "ok": True,
                "answer": "No hay ventas en los últimos 6 meses para calcular tendencia.",
                "data": [],
                "confidence": 0.65,
            }

        last = rows[-1]
        answer = (
            "Tendencia de ventas (últimos 6 meses): "
            f"último periodo {last.get('periodo')} con "
            f"{int(last.get('total_ventas') or 0)} ventas y "
            f"monto {float(last.get('monto_total') or 0):.2f}."
        )
        return {"ok": True, "answer": answer, "data": rows, "confidence": 0.88}

    def _embudo_conversion(self):
        if not self._table_exists("leads"):
            return {"ok": False, "error": "No existe la tabla leads."}

        sql = """
            SELECT
                (SELECT COUNT(*) FROM leads WHERE negocio_id = %s) AS total_leads,
                (SELECT COUNT(DISTINCT s.lead_id)
                 FROM seguimientos s
                 JOIN leads l ON l.id = s.lead_id
                 WHERE l.negocio_id = %s) AS leads_con_seguimiento,
                (SELECT COUNT(*)
                 FROM ventas_concretadas vc
                 JOIN leads l2 ON l2.id = vc.lead_id
                 WHERE l2.negocio_id = %s) AS ventas_cerradas
        """
        row = self._run_one(sql, (self.negocio_id, self.negocio_id, self.negocio_id))
        total_leads = int(row.get("total_leads") or 0)
        con_seg = int(row.get("leads_con_seguimiento") or 0)
        ventas = int(row.get("ventas_cerradas") or 0)

        tasa_contacto = round((con_seg / total_leads) * 100, 2) if total_leads else 0.0
        tasa_cierre = round((ventas / total_leads) * 100, 2) if total_leads else 0.0

        answer = (
            f"Embudo actual: {total_leads} leads, {con_seg} con seguimiento "
            f"({tasa_contacto}%), {ventas} ventas cerradas ({tasa_cierre}%)."
        )
        return {
            "ok": True,
            "answer": answer,
            "data": {
                "total_leads": total_leads,
                "leads_con_seguimiento": con_seg,
                "ventas_cerradas": ventas,
                "tasa_contacto": tasa_contacto,
                "tasa_cierre": tasa_cierre,
            },
            "confidence": 0.9,
        }

    def _producto_mas_vendido(self):
        if not self._table_exists("ventas_concretadas"):
            return {"ok": False, "error": "No existe la tabla ventas_concretadas."}

        sql = """
            SELECT
                COALESCE(bs.nombre, CONCAT('ID ', vc.bien_servicio_id)) AS producto,
                COUNT(*) AS total_ventas,
                ROUND(COALESCE(SUM(vc.monto), 0), 2) AS monto_total
            FROM ventas_concretadas vc
            JOIN leads l ON l.id = vc.lead_id
            LEFT JOIN bienes_servicios bs ON bs.id = vc.bien_servicio_id
            WHERE l.negocio_id = %s
            GROUP BY vc.bien_servicio_id, bs.nombre
            ORDER BY total_ventas DESC, monto_total DESC
            LIMIT 1
        """
        row = self._run_one(sql, (self.negocio_id,))
        if not row:
            return {
                "ok": True,
                "answer": "No hay ventas registradas para calcular el producto más vendido.",
                "data": None,
                "confidence": 0.65,
            }

        answer = (
            "Producto más vendido: "
            f"{row.get('producto')} con {int(row.get('total_ventas') or 0)} ventas "
            f"y monto total {float(row.get('monto_total') or 0):.2f}."
        )
        return {"ok": True, "answer": answer, "data": row, "confidence": 0.92}

    def handle(self, question):
        q = normalize_user_text(question)

        es_conteo_ventas = bool(
            re.search(
                r"\b(cuantas|cuantos|cantidad|total)\b.*\bventas?\b|\bventas?\b.*\b(cuantas|cuantos|cantidad|total)\b",
                q,
                re.IGNORECASE,
            )
        )

        if es_conteo_ventas:
            result = self.db_agent.handle(question)
            if result.get("ok"):
                return {
                    "ok": True,
                    "agent": "reportes_agente",
                    "intent": result.get("intent", "database"),
                    "answer": result.get("answer"),
                    "data": result.get("data"),
                    "sql": result.get("sql"),
                    "metadata": result.get("metadata"),
                    "confidence": result.get("confidence", 0.95),
                    "source_agent": "db_agent",
                }
            return {
                "ok": False,
                "agent": "reportes_agente",
                "error": result.get(
                    "error",
                    "No pude consultar la cantidad de ventas en la base de datos.",
                ),
            }

        # Las consultas de leads deben salir del agente SQL de BD, no del reporte de ventas.
        if re.search(r"\bleads?\b", q, re.IGNORECASE) and not re.search(
            r"\bventas?\b|\bproducto\b|\bservicio\b", q, re.IGNORECASE
        ):
            result = self.db_agent.handle(question)
            if result.get("ok"):
                return {
                    "ok": True,
                    "agent": "reportes_agente",
                    "intent": result.get("intent", "database"),
                    "answer": result.get("answer"),
                    "data": result.get("data"),
                    "sql": result.get("sql"),
                    "metadata": result.get("metadata"),
                    "confidence": result.get("confidence", 0.9),
                    "source_agent": "db_agent",
                }
            return {
                "ok": False,
                "agent": "reportes_agente",
                "error": result.get(
                    "error", "No pude consultar los leads en la base de datos."
                ),
            }

        if re.search(r"\b(reporte|reportes|resumen|informe)\b", q):
            if re.search(r"\bleads?\b", q, re.IGNORECASE):
                result = self.db_agent.handle(question)
                if result.get("ok"):
                    return {
                        "ok": True,
                        "agent": "reportes_agente",
                        "intent": result.get("intent", "database"),
                        "answer": result.get("answer"),
                        "data": result.get("data"),
                        "sql": result.get("sql"),
                        "metadata": result.get("metadata"),
                        "confidence": result.get("confidence", 0.9),
                        "source_agent": "db_agent",
                    }
                return {
                    "ok": False,
                    "agent": "reportes_agente",
                    "error": result.get(
                        "error", "No pude consultar los leads en la base de datos."
                    ),
                }

            tool_result = sales_report_execute(
                {"question": question, "agent": "reportes_agente"}
            )
            if not tool_result.get("ok"):
                return {
                    "ok": False,
                    "agent": "reportes_agente",
                    "error": tool_result.get(
                        "error", "No se pudo construir el reporte del sistema."
                    ),
                }
            return {
                "ok": True,
                "agent": "reportes_agente",
                "intent": "reportes",
                "answer": tool_result.get("message"),
                "data": tool_result.get("data"),
                "tool": tool_result.get("tool"),
                "confidence": 0.93,
            }
        elif re.search(
            r"\b(tendencia|evolucion|evolución)\b.*\bventas\b|\bventas\b.*\b(tendencia|evolucion|evolución)\b",
            q,
        ):
            result = self._ventas_tendencia()
        elif re.search(r"\b(embudo|conversion|conversión|funnel)\b", q):
            result = self._embudo_conversion()
        elif re.search(r"\b(producto|servicio)\b.*\bmas vendido|más vendido\b", q):
            result = self._producto_mas_vendido()
        else:
            return {
                "ok": False,
                "agent": "reportes_agente",
                "error": "No pude mapear la consulta a tendencia, embudo o producto más vendido.",
            }

        if not result.get("ok"):
            return {
                "ok": False,
                "agent": "reportes_agente",
                "error": result.get("error", "Error al generar reporte."),
            }

        return {
            "ok": True,
            "agent": "reportes_agente",
            "intent": "reportes",
            "answer": result.get("answer"),
            "data": result.get("data"),
            "confidence": result.get("confidence", 0.8),
        }
