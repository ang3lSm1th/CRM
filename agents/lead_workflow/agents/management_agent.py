"""Gerencia: KPIs ejecutivos, análisis predictivo y retroalimentación al scoring.

Fuera del flujo automático al crear lead. Dashboard: GET /lead_workflow/management/dashboard
"""

import json
import os
from datetime import date

import MySQLdb.cursors

from extensions import mysql
from agents.lead_workflow.analysis.costo_adquisicion_agent import CostoAdquisicionAgent
from agents.lead_workflow.analysis.tasa_retencion_agent import TasaRetencionAgent
from agents.lead_workflow.analysis.tasa_abandono_agent import TasaAbandonoAgent


class ManagementAgent:
    AGENT_NAME = "management_agent"

    def __init__(self):
        self.negocio_id = int(os.getenv("ORBES_NEGOCIO_ID", "1"))
        self.costo_adquisicion_agent = CostoAdquisicionAgent()
        self.tasa_retencion_agent = TasaRetencionAgent()
        self.tasa_abandono_agent = TasaAbandonoAgent()

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

    def compute_dashboard_kpis(self):
        kpis = {
            "fecha": date.today().isoformat(),
            "cac_promedio": 0.0,
            "tasa_adquisicion": 0.0,
            "score_promedio": 0.0,
            "tasa_retencion": 0.0,
            "tasa_abandono": 0.0,
            "leads_activos": 0,
            "leads_cerrados": 0,
            "leads_muertos": 0,
            "leads_riesgo_abandono": [],
            "retroalimentacion_scoring": {},
        }

        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            if self._table_exists("lead_agent_state"):
                cur.execute(
                    """
                    SELECT
                        AVG(score) AS score_promedio,
                        SUM(CASE WHEN workflow_status = 'active' THEN 1 ELSE 0 END) AS activos,
                        SUM(CASE WHEN workflow_status = 'completed' THEN 1 ELSE 0 END) AS cerrados,
                        SUM(CASE WHEN workflow_status = 'dead' THEN 1 ELSE 0 END) AS muertos
                    FROM lead_agent_state
                    """
                )
                row = cur.fetchone() or {}
                kpis["score_promedio"] = round(float(row.get("score_promedio") or 0), 2)
                kpis["leads_activos"] = int(row.get("activos") or 0)
                kpis["leads_cerrados"] = int(row.get("cerrados") or 0)
                kpis["leads_muertos"] = int(row.get("muertos") or 0)

            if self._table_exists("leads"):
                cur.execute(
                    """
                    SELECT COUNT(*) AS total FROM leads WHERE negocio_id = %s
                    """,
                    (self.negocio_id,),
                )
                total_leads = int((cur.fetchone() or {}).get("total") or 0)

                if self._table_exists("ventas_concretadas") and total_leads:
                    cur.execute(
                        """
                        SELECT COUNT(*) AS ventas
                        FROM ventas_concretadas vc
                        JOIN leads l ON l.id = vc.lead_id
                        WHERE l.negocio_id = %s
                        """,
                        (self.negocio_id,),
                    )
                    ventas = int((cur.fetchone() or {}).get("ventas") or 0)
                    kpis["tasa_adquisicion"] = round((ventas / total_leads) * 100, 2)
        finally:
            cur.close()

        retencion = self.tasa_retencion_agent.tasa_retencion_negocio()
        if retencion.get("ok"):
            kpis["tasa_retencion"] = retencion["data"].get("tasa_retencion", 0)
            kpis["tasa_abandono"] = round(100 - float(kpis["tasa_retencion"]), 2)

        riesgo = self.tasa_abandono_agent.leads_riesgo_abandono()
        if riesgo.get("ok"):
            kpis["leads_riesgo_abandono"] = (riesgo.get("data") or [])[:10]

        sample_lead = {"id": 0, "canal_id": None, "canal_nombre": "general", "asignado_a": None}
        cac_sample = self.costo_adquisicion_agent.analyze(sample_lead)
        kpis["cac_promedio"] = cac_sample.get("costo_adquisicion", 0)

        kpis["retroalimentacion_scoring"] = self._scoring_feedback(kpis)
        self._persist_snapshot(kpis)
        return kpis

    def _scoring_feedback(self, kpis):
        feedback = {}
        if kpis["tasa_adquisicion"] < 5:
            feedback["acquisition_weight_hint"] = "Incrementar peso de adquisición; revisar canales."
        if kpis["tasa_abandono"] > 40:
            feedback["retention_weight_hint"] = "Incrementar peso de retención; activar campañas de reactivación."
        if kpis["score_promedio"] < 45:
            feedback["quality_hint"] = "Calidad de leads baja: revisar fuentes de adquisición."
        if not feedback:
            feedback["status"] = "Modelos estables; mantener pesos actuales."
        return feedback

    def _persist_snapshot(self, kpis):
        if not self._table_exists("lead_workflow_kpi_snapshots"):
            return
        cur = mysql.connection.cursor()
        try:
            cur.execute(
                """
                INSERT INTO lead_workflow_kpi_snapshots
                (snapshot_date, cac_promedio, tasa_adquisicion, score_promedio,
                 tasa_retencion, tasa_abandono, leads_activos, leads_cerrados,
                 leads_muertos, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                ON DUPLICATE KEY UPDATE
                    cac_promedio = VALUES(cac_promedio),
                    tasa_adquisicion = VALUES(tasa_adquisicion),
                    score_promedio = VALUES(score_promedio),
                    tasa_retencion = VALUES(tasa_retencion),
                    tasa_abandono = VALUES(tasa_abandono),
                    leads_activos = VALUES(leads_activos),
                    leads_cerrados = VALUES(leads_cerrados),
                    leads_muertos = VALUES(leads_muertos),
                    metadata = VALUES(metadata)
                """,
                (
                    kpis["fecha"],
                    kpis["cac_promedio"],
                    kpis["tasa_adquisicion"],
                    kpis["score_promedio"],
                    kpis["tasa_retencion"],
                    kpis["tasa_abandono"],
                    kpis["leads_activos"],
                    kpis["leads_cerrados"],
                    kpis["leads_muertos"],
                    json.dumps(kpis.get("retroalimentacion_scoring") or {}, ensure_ascii=False),
                ),
            )
            mysql.connection.commit()
        finally:
            cur.close()
