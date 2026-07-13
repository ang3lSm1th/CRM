"""Agente: Tasa de retención (TDR) por lead y a nivel negocio.

WORKFLOW · PASO 1.4 — Sub-agente de scoring (lead_scoring.analyze)
"""

import re

import MySQLdb.cursors

from extensions import mysql
from utils.text_normalizer import normalize_user_text


class TasaRetencionAgent:
    AGENT_NAME = "tasa_retencion_agent"

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

    def _run_one(self, sql, params=None):
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            cur.execute(sql, params or ())
            return cur.fetchone() or {}
        finally:
            cur.close()

    def _lead_metrics(self, lead_row):
        lead_id = lead_row.get("id")
        if not lead_id:
            return {
                "lead_id": lead_id,
                "dias_inactivo": 999,
                "compras_historicas": 0,
            }

        # Prefer columns that exist across deployments (no s.created_at).
        row = self._run_one(
            """
            SELECT
                DATEDIFF(
                    CURDATE(),
                    MAX(DATE(COALESCE(s.fecha_guardado, s.fecha_seguimiento, CURDATE())))
                ) AS dias_inactivo,
                COUNT(DISTINCT CASE
                    WHEN LOWER(TRIM(COALESCE(p.nombre_proceso, ''))) = 'cerrado' THEN s.id
                    ELSE NULL
                END) AS compras_historicas
            FROM seguimientos s
            LEFT JOIN proceso p ON p.id = s.proceso_id
            WHERE s.lead_id = %s
            """,
            (lead_id,),
        )

        dias_inactivo = row.get("dias_inactivo")
        compras_historicas = row.get("compras_historicas")
        return {
            "lead_id": lead_id,
            "dias_inactivo": int(dias_inactivo if dias_inactivo is not None else 999),
            "compras_historicas": int(compras_historicas or 0),
        }

    def analyze(self, lead_row, engagement_metrics=None):
        if engagement_metrics:
            lead_id = lead_row.get("id")
            metrics = {
                "lead_id": lead_id,
                "dias_inactivo": int(engagement_metrics.get("dias_ultimo_seg") or 999),
                "compras_historicas": int(engagement_metrics.get("compras_historicas") or 0),
            }
        else:
            metrics = self._lead_metrics(lead_row)
        lead_id = metrics["lead_id"]
        dias_inactivo = metrics["dias_inactivo"]
        compras = metrics["compras_historicas"]

        if compras >= 2:
            retention_score = 85
            tasa_retencion = 85.0
        elif compras == 1:
            retention_score = 70
            tasa_retencion = 70.0
        elif dias_inactivo <= 14:
            retention_score = 75
            tasa_retencion = 75.0
        elif dias_inactivo <= 45:
            retention_score = 55
            tasa_retencion = 55.0
        elif dias_inactivo <= 90:
            retention_score = 35
            tasa_retencion = 35.0
        else:
            retention_score = 20
            tasa_retencion = 20.0

        acciones = []
        if compras >= 1:
            acciones.append("Cliente con historial: enfoque en fidelización")
        if dias_inactivo <= 30:
            acciones.append("Contacto reciente: mantener seguimiento proactivo")
        if not acciones:
            acciones.append("Mantener seguimiento proactivo estándar")

        return {
            "agent": self.AGENT_NAME,
            "ok": True,
            "lead_id": lead_id,
            "retention_score": retention_score,
            "tasa_retencion": tasa_retencion,
            "dias_inactivo": dias_inactivo,
            "compras_historicas": compras,
            "acciones_sugeridas": acciones,
        }

    def tasa_retencion_negocio(self):
        """TDR agregada del negocio (clientes recurrentes / clientes con compra)."""
        if not self._table_exists("ventas_concretadas"):
            return {"ok": False, "error": "No existe la tabla ventas_concretadas."}

        sql = """
            SELECT
                COUNT(DISTINCT cliente_id) AS clientes_con_compra,
                COUNT(DISTINCT CASE WHEN c.ventas_cliente >= 2 THEN cliente_id END) AS clientes_recurrentes
            FROM (
                SELECT cliente_id, COUNT(*) AS ventas_cliente
                FROM ventas_concretadas
                WHERE cliente_id IS NOT NULL
                GROUP BY cliente_id
            ) c
        """
        row = self._run_one(sql)
        clientes = int(row.get("clientes_con_compra") or 0)
        recurrentes = int(row.get("clientes_recurrentes") or 0)
        tasa = round((recurrentes / clientes) * 100, 2) if clientes else 0.0

        return {
            "ok": True,
            "answer": (
                f"Tasa de retención estimada: {tasa}% "
                f"({recurrentes} clientes recurrentes de {clientes} con compra)."
            ),
            "data": {
                "clientes_con_compra": clientes,
                "clientes_recurrentes": recurrentes,
                "tasa_retencion": tasa,
            },
            "confidence": 0.9,
        }

    def handle(self, question):
        q = normalize_user_text(question)
        if not re.search(r"\b(retencion|retención|recurrente)\b", q):
            return {
                "ok": False,
                "agent": self.AGENT_NAME,
                "error": "Consulta no reconocida para tasa de retención.",
            }

        result = self.tasa_retencion_negocio()
        if not result.get("ok"):
            return {
                "ok": False,
                "agent": self.AGENT_NAME,
                "error": result.get("error", "Error al calcular tasa de retención."),
            }

        return {
            "ok": True,
            "agent": self.AGENT_NAME,
            "intent": "tasa_retencion",
            "answer": result.get("answer"),
            "data": result.get("data"),
            "confidence": result.get("confidence", 0.8),
        }
