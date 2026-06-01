"""Recepción + scoring global: orquesta los 4 agentes de análisis del diagrama TO-BE."""

from agents.core.prediccion_agente import PrediccionCompraAgente
from agents.core.retencion_agente import RetencionAbandonoAgente
from agents.lead_workflow.analysis.cac_agent import CACAgent
from agents.lead_workflow.analysis.acquisition_agent import AcquisitionRateAgent


class LeadScoringAgent:
    AGENT_NAME = "lead_scoring"

    WEIGHTS = {
        "cac": 0.20,
        "acquisition": 0.20,
        "purchase_probability": 0.35,
        "retention": 0.25,
    }

    def __init__(self):
        self.cac_agent = CACAgent()
        self.acquisition_agent = AcquisitionRateAgent()
        self.prediccion_agent = PrediccionCompraAgente()
        self.retencion_agent = RetencionAbandonoAgente()

    def _retention_score_for_lead(self, lead_row):
        lead_id = lead_row.get("id")
        predictions = self.prediccion_agent.predict_percentages_for_leads(
            [{"id": lead_id}]
        )
        pred = predictions.get(int(lead_id), {})
        dias_inactivo = int(pred.get("dias_ultimo_seg") or 999)
        compras = int(pred.get("compras_historicas") or 0)

        if compras >= 2:
            retention_score = 85
            riesgo = "bajo"
        elif compras == 1:
            retention_score = 70
            riesgo = "medio"
        elif dias_inactivo <= 14:
            retention_score = 75
            riesgo = "bajo"
        elif dias_inactivo <= 45:
            retention_score = 55
            riesgo = "medio"
        elif dias_inactivo <= 90:
            retention_score = 35
            riesgo = "alto"
        else:
            retention_score = 20
            riesgo = "critico"

        acciones = []
        if riesgo in ("alto", "critico"):
            acciones.append("Activar estrategia de retención con oferta de valor")
        if compras >= 1:
            acciones.append("Cliente con historial: enfoque en fidelización")
        if not acciones:
            acciones.append("Mantener seguimiento proactivo estándar")

        return {
            "agent": "retention_agent",
            "ok": True,
            "lead_id": lead_id,
            "retention_score": retention_score,
            "riesgo_abandono": riesgo,
            "dias_inactivo": dias_inactivo,
            "compras_historicas": compras,
            "acciones_sugeridas": acciones,
        }

    def _priority_label(self, score):
        if score >= 75:
            return "Alta"
        if score >= 50:
            return "Media"
        return "Baja"

    def _build_recommendation(self, score, agent_outputs):
        parts = []
        pred = agent_outputs.get("purchase_probability", {})
        recs = pred.get("recomendaciones") or []
        if recs:
            parts.append(recs[0])

        cac = agent_outputs.get("cac", {})
        if cac.get("interpretacion"):
            parts.append(f"CAC: {cac['interpretacion']}")

        acq = agent_outputs.get("acquisition", {})
        if acq.get("interpretacion"):
            parts.append(f"Adquisición: {acq['interpretacion']}")

        ret = agent_outputs.get("retention", {})
        if ret.get("acciones_sugeridas"):
            parts.append(f"Retención: {ret['acciones_sugeridas'][0]}")

        if score >= 75:
            parts.insert(0, "Priorizar contacto inmediato y asignar al mejor asesor disponible.")
        elif score >= 50:
            parts.insert(0, "Contactar en las próximas 24-48 h con propuesta personalizada.")
        else:
            parts.insert(0, "Nutrir con contenido automatizado; contacto humano si responde.")

        return " | ".join(parts[:4])

    def analyze(self, lead_row):
        lead_id = lead_row.get("id")
        cac = self.cac_agent.analyze(lead_row)
        acquisition = self.acquisition_agent.analyze(lead_row)
        retention = self._retention_score_for_lead(lead_row)

        predictions = self.prediccion_agent.predict_percentages_for_leads(
            [{"id": lead_id}]
        )
        pred = predictions.get(int(lead_id), {})
        purchase_score = float(pred.get("porcentaje") or 50)

        purchase_output = {
            "agent": "purchase_probability_agent",
            "ok": True,
            "lead_id": lead_id,
            "purchase_score": purchase_score,
            "probabilidad_compra": purchase_score,
            "recomendaciones": pred.get("recomendaciones") or [],
            "motivos": pred.get("motivos") or [],
            "tipo_prediccion": pred.get("tipo_prediccion"),
        }

        global_score = round(
            cac.get("roi_score", 50) * self.WEIGHTS["cac"]
            + acquisition.get("acquisition_score", 50) * self.WEIGHTS["acquisition"]
            + purchase_score * self.WEIGHTS["purchase_probability"]
            + retention.get("retention_score", 50) * self.WEIGHTS["retention"]
        )
        global_score = max(0, min(100, global_score))
        priority = self._priority_label(global_score)

        agent_outputs = {
            "cac": cac,
            "acquisition": acquisition,
            "purchase_probability": purchase_output,
            "retention": retention,
        }
        recommendation = self._build_recommendation(global_score, agent_outputs)

        return {
            "agent": self.AGENT_NAME,
            "ok": True,
            "lead_id": lead_id,
            "global_score": global_score,
            "priority_label": priority,
            "recommendation": recommendation,
            "agent_outputs": agent_outputs,
            "weights": self.WEIGHTS,
        }
