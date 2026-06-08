"""Agente 4 (recuperación): estrategias alternativas tras 2 intentos sin respuesta.

WORKFLOW · PASO 4/5 — run_attempt() / mark_dead_lead()
Invocado desde orchestrator._run_recovery_contact()
"""

from datetime import datetime, timedelta


class RecoveryAgent:
    AGENT_NAME = "recovery_agent"
    MAX_RECOVERY_ATTEMPTS = 2

    STRATEGIES = (
        {
            "type": "email",
            "template": "Oferta especial de reactivación con descuento limitado.",
        },
        {
            "type": "whatsapp",
            "template": "Mensaje personalizado con caso de éxito similar a su perfil.",
        },
    )

    def run_attempt(self, lead_row, recovery_attempt):
        # ═══ WORKFLOW · PASO 4/5 · Intento recuperación N (máx. 2) ═══
        strategy = self.STRATEGIES[(recovery_attempt - 1) % len(self.STRATEGIES)]
        nombre = (lead_row.get("nombre") or "cliente").strip()
        message = (
            f"Hola {nombre}, {strategy['template']} "
            f"(Intento recuperación #{recovery_attempt})."
        )
        return {
            "agent": self.AGENT_NAME,
            "ok": True,
            "lead_id": lead_row.get("id"),
            "recovery_attempt": recovery_attempt,
            "channel": strategy["type"],
            "message": message,
            "next_followup": (datetime.now() + timedelta(days=5)).isoformat(),
            "awaiting_response": True,
        }

    def mark_dead_lead(self, lead_id):
        # ═══ WORKFLOW · FIN alternativo · venta_muerta (sin respuesta) ═══
        return {
            "agent": self.AGENT_NAME,
            "ok": True,
            "lead_id": lead_id,
            "status": "venta_muerta",
            "reason": "Sin respuesta tras contacto comercial y recuperación.",
        }
