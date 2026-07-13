"""Compatibilidad: reexporta agentes de retención y abandono con nombre legacy."""

from agents.lead_workflow.analysis.tasa_retencion_agent import TasaRetencionAgent
from agents.lead_workflow.analysis.tasa_abandono_agent import TasaAbandonoAgent


class RetencionAbandonoAgente:
    """Fachada legacy que delega en TasaRetencionAgent y TasaAbandonoAgent."""

    def __init__(self):
        self._retencion = TasaRetencionAgent()
        self._abandono = TasaAbandonoAgent()

    def _tasa_retencion(self):
        return self._retencion.tasa_retencion_negocio()

    def _leads_riesgo_abandono(self):
        return self._abandono.leads_riesgo_abandono()

    def handle(self, question):
        from utils.text_normalizer import normalize_user_text
        import re

        q = normalize_user_text(question)
        if re.search(r"\b(retencion|retención|recurrente)\b", q):
            return self._retencion.handle(question)
        if re.search(r"\b(riesgo|abandono|inactivo|inactividad)\b", q):
            return self._abandono.handle(question)
        return {
            "ok": False,
            "agent": "retencion_abandono",
            "error": "No pude mapear la consulta a retención o abandono.",
        }


__all__ = ["RetencionAbandonoAgente", "TasaRetencionAgent", "TasaAbandonoAgent"]
