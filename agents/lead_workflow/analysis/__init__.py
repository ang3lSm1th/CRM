from agents.lead_workflow.analysis.costo_adquisicion_agent import CostoAdquisicionAgent
from agents.lead_workflow.analysis.tasa_adquisicion_agent import TasaAdquisicionAgent
from agents.lead_workflow.analysis.tasa_retencion_agent import TasaRetencionAgent
from agents.lead_workflow.analysis.tasa_abandono_agent import TasaAbandonoAgent

# Alias retrocompatibles
CACAgent = CostoAdquisicionAgent
AcquisitionRateAgent = TasaAdquisicionAgent

__all__ = [
    "CostoAdquisicionAgent",
    "TasaAdquisicionAgent",
    "TasaRetencionAgent",
    "TasaAbandonoAgent",
    "CACAgent",
    "AcquisitionRateAgent",
]
