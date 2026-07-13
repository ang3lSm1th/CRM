"""Agente: Tasa de adquisición (TDA = NLC / NLO × 100).

WORKFLOW · PASO 1.2 — Sub-agente de scoring (lead_scoring.analyze)
"""

import os

import MySQLdb.cursors

from extensions import mysql


class TasaAdquisicionAgent:
    AGENT_NAME = "tasa_adquisicion_agent"

    def __init__(self):
        self.negocio_id = int(os.getenv("ORBES_NEGOCIO_ID", "1"))

    def _table_exists(self, table_name):
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            cur.execute(
                """
                SELECT COUNT(*) AS total
                FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = %s
                """,
                (table_name,),
            )
            return int((cur.fetchone() or {}).get("total", 0)) > 0
        finally:
            cur.close()

    def analyze(self, lead_row):
        lead_id = lead_row.get("id")
        canal_id = lead_row.get("canal_id")
        asignado_a = lead_row.get("asignado_a")
        canal_nombre = (lead_row.get("canal_nombre") or "desconocido").strip()

        total_leads_canal = 0
        leads_con_seguimiento = 0
        ventas_canal = 0
        tasa_canal = 0.0
        tasa_asesor = 0.0

        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            if self._table_exists("leads"):
                cur.execute(
                    """
                    SELECT COUNT(*) AS total
                    FROM leads
                    WHERE negocio_id = %s AND canal_id = %s
                    """,
                    (self.negocio_id, canal_id),
                )
                total_leads_canal = int((cur.fetchone() or {}).get("total") or 0)

                cur.execute(
                    """
                    SELECT COUNT(DISTINCT s.lead_id) AS con_seg
                    FROM seguimientos s
                    JOIN leads l ON l.id = s.lead_id
                    WHERE l.negocio_id = %s AND l.canal_id = %s
                    """,
                    (self.negocio_id, canal_id),
                )
                leads_con_seguimiento = int((cur.fetchone() or {}).get("con_seg") or 0)

            if self._table_exists("ventas_concretadas") and total_leads_canal:
                cur.execute(
                    """
                    SELECT COUNT(*) AS ventas
                    FROM ventas_concretadas vc
                    JOIN leads l ON l.id = vc.lead_id
                    WHERE l.negocio_id = %s AND l.canal_id = %s
                    """,
                    (self.negocio_id, canal_id),
                )
                ventas_canal = int((cur.fetchone() or {}).get("ventas") or 0)
                tasa_canal = round((ventas_canal / total_leads_canal) * 100, 2)

            if asignado_a and self._table_exists("leads"):
                cur.execute(
                    """
                    SELECT COUNT(*) AS total
                    FROM leads
                    WHERE negocio_id = %s AND asignado_a = %s
                    """,
                    (self.negocio_id, asignado_a),
                )
                total_asesor = int((cur.fetchone() or {}).get("total") or 0)

                if total_asesor and self._table_exists("ventas_concretadas"):
                    cur.execute(
                        """
                        SELECT COUNT(*) AS ventas
                        FROM ventas_concretadas vc
                        JOIN leads l ON l.id = vc.lead_id
                        WHERE l.negocio_id = %s AND l.asignado_a = %s
                        """,
                        (self.negocio_id, asignado_a),
                    )
                    ventas_asesor = int((cur.fetchone() or {}).get("ventas") or 0)
                    tasa_asesor = round((ventas_asesor / total_asesor) * 100, 2)
        finally:
            cur.close()

        tasa_contacto = (
            round((leads_con_seguimiento / total_leads_canal) * 100, 2)
            if total_leads_canal
            else 0.0
        )

        acquisition_score = 50
        if tasa_canal >= 15:
            acquisition_score = 90
            interpretacion = "Canal con alta conversión histórica."
        elif tasa_canal >= 8:
            acquisition_score = 70
            interpretacion = "Canal con conversión aceptable."
        elif tasa_contacto >= 40:
            acquisition_score = 60
            interpretacion = "Buen contacto inicial; conversión aún en desarrollo."
        else:
            acquisition_score = 40
            interpretacion = "Canal o asignación con baja efectividad de adquisición."

        return {
            "agent": self.AGENT_NAME,
            "ok": True,
            "lead_id": lead_id,
            "canal": canal_nombre,
            "tasa_adquisicion": tasa_canal,
            "tasa_conversion_canal": tasa_canal,
            "tasa_contacto_canal": tasa_contacto,
            "tasa_conversion_asesor": tasa_asesor,
            "total_leads_canal": total_leads_canal,
            "ventas_canal": ventas_canal,
            "acquisition_score": acquisition_score,
            "interpretacion": interpretacion,
        }
