"""Agente 1: Costo de Adquisición (CAC) por lead, campaña y canal."""

import os

import MySQLdb.cursors

from extensions import mysql


class CACAgent:
    AGENT_NAME = "cac_agent"

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

    def _column_exists(self, table_name, column_name):
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            cur.execute(
                """
                SELECT COUNT(*) AS total
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = %s AND COLUMN_NAME = %s
                """,
                (table_name, column_name),
            )
            return int((cur.fetchone() or {}).get("total", 0)) > 0
        finally:
            cur.close()

    def analyze(self, lead_row):
        lead_id = lead_row.get("id")
        canal_id = lead_row.get("canal_id")
        canal_nombre = (lead_row.get("canal_nombre") or "desconocido").strip()

        inversion_total = 0.0
        leads_canal = 1
        cac_canal = 0.0
        cac_campana = None
        fuente = "estimado_por_canal"

        if self._table_exists("marketing_campaigns"):
            has_inversion = self._column_exists("marketing_campaigns", "inversion")
            has_canal = self._column_exists("marketing_campaigns", "canal")
            has_negocio = self._column_exists("marketing_campaigns", "negocio_id")

            if has_inversion:
                where = ["1=1"]
                params = []
                if has_negocio:
                    where.append("negocio_id = %s")
                    params.append(self.negocio_id)

                cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
                try:
                    cur.execute(
                        f"""
                        SELECT COALESCE(SUM(inversion), 0) AS inversion_total,
                               COUNT(*) AS campanas
                        FROM marketing_campaigns
                        WHERE {' AND '.join(where)}
                        """,
                        tuple(params),
                    )
                    camp_row = cur.fetchone() or {}
                    inversion_total = float(camp_row.get("inversion_total") or 0)

                    if has_canal and canal_nombre:
                        cur.execute(
                            f"""
                            SELECT COALESCE(SUM(inversion), 0) AS inversion_canal
                            FROM marketing_campaigns
                            WHERE {' AND '.join(where)}
                              AND LOWER(TRIM(canal)) = LOWER(TRIM(%s))
                            """,
                            tuple(params) + (canal_nombre,),
                        )
                        inv_canal = float((cur.fetchone() or {}).get("inversion_canal") or 0)
                        if inv_canal > 0:
                            inversion_total = inv_canal
                            fuente = "campana_canal"
                finally:
                    cur.close()

        if self._table_exists("leads"):
            cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            try:
                cur.execute(
                    """
                    SELECT COUNT(*) AS total
                    FROM leads
                    WHERE negocio_id = %s
                      AND (canal_id = %s OR %s IS NULL)
                    """,
                    (self.negocio_id, canal_id, canal_id),
                )
                leads_canal = max(1, int((cur.fetchone() or {}).get("total") or 1))
            finally:
                cur.close()

        if inversion_total > 0:
            cac_canal = round(inversion_total / leads_canal, 2)
            fuente = "campanas_marketing"

        roi_score = 50
        if cac_canal <= 0:
            roi_score = 70
            interpretacion = "Sin inversión registrada en campaña; CAC no penaliza el lead."
        elif cac_canal < 100:
            roi_score = 90
            interpretacion = "CAC bajo: canal eficiente para adquisición."
        elif cac_canal < 300:
            roi_score = 65
            interpretacion = "CAC moderado: validar conversión antes de escalar inversión."
        else:
            roi_score = 35
            interpretacion = "CAC alto: priorizar leads con mayor probabilidad de cierre."

        return {
            "agent": self.AGENT_NAME,
            "ok": True,
            "lead_id": lead_id,
            "cac_canal": cac_canal,
            "cac_campana": cac_campana,
            "inversion_referencia": inversion_total,
            "leads_en_canal": leads_canal,
            "canal": canal_nombre,
            "roi_score": roi_score,
            "interpretacion": interpretacion,
            "fuente_datos": fuente,
        }
