"""Agente: Tasa de abandono (TDA = 100 − TDR) por lead y a nivel negocio.

WORKFLOW · PASO 1.5 — Sub-agente de scoring (lead_scoring.analyze)
"""

import re

import MySQLdb.cursors

from extensions import mysql
from utils.text_normalizer import normalize_user_text


class TasaAbandonoAgent:
    AGENT_NAME = "tasa_abandono_agent"

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

    def analyze(self, lead_row, retention_result=None):
        if retention_result is None:
            from agents.lead_workflow.analysis.tasa_retencion_agent import TasaRetencionAgent

            retention_result = TasaRetencionAgent().analyze(lead_row)

        lead_id = retention_result.get("lead_id") or lead_row.get("id")
        retention_score = int(retention_result.get("retention_score") or 50)
        tasa_retencion = float(retention_result.get("tasa_retencion") or retention_score)
        tasa_abandono = round(100.0 - tasa_retencion, 2)
        abandonment_score = max(0, min(100, 100 - retention_score))
        dias_inactivo = int(retention_result.get("dias_inactivo") or 999)
        compras = int(retention_result.get("compras_historicas") or 0)

        if abandonment_score >= 65 or dias_inactivo > 90:
            riesgo = "critico"
        elif abandonment_score >= 45 or dias_inactivo > 45:
            riesgo = "alto"
        elif abandonment_score >= 30:
            riesgo = "medio"
        else:
            riesgo = "bajo"

        acciones = []
        if riesgo in ("alto", "critico"):
            acciones.append("Activar estrategia de retención con oferta de valor")
        if compras == 0 and dias_inactivo > 30:
            acciones.append("Lead sin compra e inactivo: campaña de reactivación")
        if not acciones:
            acciones.append("Riesgo de abandono bajo; mantener contacto periódico")

        return {
            "agent": self.AGENT_NAME,
            "ok": True,
            "lead_id": lead_id,
            "abandonment_score": abandonment_score,
            "tasa_abandono": tasa_abandono,
            "riesgo_abandono": riesgo,
            "dias_inactivo": dias_inactivo,
            "compras_historicas": compras,
            "acciones_sugeridas": acciones,
        }

    def leads_riesgo_abandono(self):
        if not self._table_exists("leads"):
            return {"ok": False, "error": "No existe la tabla leads."}

        sql = """
            SELECT
                l.id,
                l.nombre,
                l.telefono,
                COALESCE(MAX(s.fecha_guardado), l.fecha) AS ultima_actividad,
                DATEDIFF(CURDATE(), COALESCE(MAX(s.fecha_guardado), l.fecha)) AS dias_inactivo
            FROM leads l
            LEFT JOIN seguimientos s ON s.lead_id = l.id
            GROUP BY l.id, l.nombre, l.telefono, l.fecha
            HAVING dias_inactivo > 30
            ORDER BY dias_inactivo DESC
            LIMIT 25
        """
        rows = self._run_all(sql)

        if not rows:
            return {
                "ok": True,
                "answer": "No se detectaron leads con inactividad mayor a 30 días.",
                "data": [],
                "confidence": 0.84,
            }

        top = rows[0]
        return {
            "ok": True,
            "answer": (
                f"Detecté {len(rows)} leads con riesgo de abandono (>30 días). "
                f"Mayor inactividad: Lead #{top.get('id')} con {int(top.get('dias_inactivo') or 0)} días."
            ),
            "data": rows,
            "confidence": 0.88,
        }

    def handle(self, question):
        q = normalize_user_text(question)
        if not re.search(r"\b(riesgo|abandono|inactivo|inactividad)\b", q):
            return {
                "ok": False,
                "agent": self.AGENT_NAME,
                "error": "Consulta no reconocida para tasa de abandono.",
            }

        result = self.leads_riesgo_abandono()
        if not result.get("ok"):
            return {
                "ok": False,
                "agent": self.AGENT_NAME,
                "error": result.get("error", "Error al calcular tasa de abandono."),
            }

        return {
            "ok": True,
            "agent": self.AGENT_NAME,
            "intent": "tasa_abandono",
            "answer": result.get("answer"),
            "data": result.get("data"),
            "confidence": result.get("confidence", 0.8),
        }
