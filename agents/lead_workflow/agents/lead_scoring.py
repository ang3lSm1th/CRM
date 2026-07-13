"""Recepción + scoring global: orquesta los agentes de análisis del diagrama TO-BE.

WORKFLOW · PASO 1/5 — Invocado desde orchestrator._run_scoring()
Sub-agentes (en analyze()):
  1.1 costo_adquisicion_agent.py   → Costo de adquisición
  1.2 tasa_adquisicion_agent.py    → Tasa de adquisición
    1.3 tasa_retencion_agent.py      → Tasa de retención
    1.4 tasa_abandono_agent.py       → Tasa de abandono
Salida → score global + prioridad → nodo assignment
"""

from agents.lead_workflow.analysis.costo_adquisicion_agent import CostoAdquisicionAgent
from agents.lead_workflow.analysis.tasa_adquisicion_agent import TasaAdquisicionAgent
from agents.lead_workflow.analysis.tasa_retencion_agent import TasaRetencionAgent
from agents.lead_workflow.analysis.tasa_abandono_agent import TasaAbandonoAgent


class LeadScoringAgent:
    AGENT_NAME = "lead_scoring"

    WEIGHTS = {
        "costo_adquisicion": 0.30,
        "tasa_adquisicion": 0.30,
        "tasa_retencion": 0.20,
        "tasa_abandono": 0.20,
    }

    def __init__(self):
        self.costo_adquisicion_agent = CostoAdquisicionAgent()
        self.tasa_adquisicion_agent = TasaAdquisicionAgent()
        self.tasa_retencion_agent = TasaRetencionAgent()
        self.tasa_abandono_agent = TasaAbandonoAgent()

    def _priority_label(self, score):
        if score >= 75:
            return "Alta"
        if score >= 50:
            return "Media"
        return "Baja"

    def _build_recommendation(self, score, agent_outputs):
        parts = []
        cac = agent_outputs.get("costo_adquisicion", {})
        if cac.get("interpretacion"):
            parts.append(f"Costo adquisición: {cac['interpretacion']}")

        acq = agent_outputs.get("tasa_adquisicion", {})
        if acq.get("interpretacion"):
            parts.append(f"Tasa adquisición: {acq['interpretacion']}")

        ret = agent_outputs.get("tasa_retencion", {})
        if ret.get("acciones_sugeridas"):
            parts.append(f"Retención: {ret['acciones_sugeridas'][0]}")

        abn = agent_outputs.get("tasa_abandono", {})
        if abn.get("acciones_sugeridas"):
            parts.append(f"Abandono: {abn['acciones_sugeridas'][0]}")

        if score >= 75:
            parts.insert(0, "Priorizar contacto inmediato y asignar al mejor asesor disponible.")
        elif score >= 50:
            parts.insert(0, "Contactar en las próximas 24-48 h con propuesta personalizada.")
        else:
            parts.insert(0, "Nutrir con contenido automatizado; contacto humano si responde.")

        return " | ".join(parts[:4])

    def analyze(self, lead_row):
        lead_id = lead_row.get("id")
        # ── PASO 1.1: Costo de adquisición ──
        costo_adquisicion = self.costo_adquisicion_agent.analyze(lead_row)
        # ── PASO 1.2: Tasa de adquisición ──
        tasa_adquisicion = self.tasa_adquisicion_agent.analyze(lead_row)
        # ── PASO 1.3: Tasa de retención ──
        tasa_retencion = self.tasa_retencion_agent.analyze(lead_row)
        # ── PASO 1.4: Tasa de abandono ──
        tasa_abandono = self.tasa_abandono_agent.analyze(lead_row, tasa_retencion)

        global_score = round(
            costo_adquisicion.get("roi_score", 50)
            * self.WEIGHTS["costo_adquisicion"]
            + tasa_adquisicion.get("acquisition_score", 50)
            * self.WEIGHTS["tasa_adquisicion"]
            + tasa_retencion.get("retention_score", 50)
            * self.WEIGHTS["tasa_retencion"]
            + tasa_abandono.get("abandonment_score", 50) * self.WEIGHTS["tasa_abandono"]
        )
        global_score = max(0, min(100, global_score))
        priority = self._priority_label(global_score)

        agent_outputs = {
            "costo_adquisicion": costo_adquisicion,
            "tasa_adquisicion": tasa_adquisicion,
            "tasa_retencion": tasa_retencion,
            "tasa_abandono": tasa_abandono,
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
