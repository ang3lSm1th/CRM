"""Asesor comercial automatizado: 1er y 2do contacto según canal preferido.

WORKFLOW · PASO 2/5 — assign_advisor()  (orchestrator._run_assignment)
WORKFLOW · PASO 3/5 — contact()         (orchestrator._run_commercial_contact)
"""

from datetime import datetime, timedelta

import MySQLdb.cursors

from extensions import mysql


class CommercialAssistantAgent:
    AGENT_NAME = "commercial_assistant"
    MAX_COMMERCIAL_ATTEMPTS = 2

    CHANNELS = ("email", "whatsapp", "sms", "call")

    def _pick_channel(self, lead_row):
        if lead_row.get("email"):
            return "email"
        if lead_row.get("telefono"):
            return "whatsapp"
        return "call"

    def _build_message(self, lead_row, attempt, score_data):
        nombre = (lead_row.get("nombre") or "cliente").strip()
        score = score_data.get("global_score", 0)
        priority = score_data.get("priority_label", "Media")
        if attempt == 1:
            return (
                f"Hola {nombre}, somos su equipo comercial. "
                f"Detectamos interés en nuestros productos (prioridad {priority}, score {score}). "
                "¿Podemos agendar una llamada breve?"
            )
        return (
            f"Hola {nombre}, segundo seguimiento comercial. "
            "Queremos confirmar si aún evalúa nuestra propuesta. "
            "Responda a este mensaje para continuar."
        )

    def contact(self, lead_row, attempt, score_data):
        # ═══ WORKFLOW · PASO 3/5 · Intento comercial N (máx. 2) ═══
        channel = self._pick_channel(lead_row)
        message = self._build_message(lead_row, attempt, score_data)
        next_followup = datetime.now() + timedelta(days=2 if attempt == 1 else 3)

        return {
            "agent": self.AGENT_NAME,
            "ok": True,
            "lead_id": lead_row.get("id"),
            "attempt": attempt,
            "channel": channel,
            "message": message,
            "next_followup": next_followup.isoformat(),
            "awaiting_response": True,
        }

    def assign_advisor(self, lead_row, score_data):
        """WORKFLOW · PASO 2/5 · Asigna lead al asesor con menor carga activa."""
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            cur.execute(
                """
                SELECT u.id, u.nombre,
                       COUNT(l.id) AS leads_activos
                FROM usuarios u
                LEFT JOIN leads l ON l.asignado_a = u.id
                JOIN roles r ON r.id = u.id_rol
                WHERE LOWER(r.nombre) IN ('asesor', 'gerente', 'administrador')
                GROUP BY u.id, u.nombre
                ORDER BY leads_activos ASC, u.id ASC
                LIMIT 1
                """
            )
            advisor = cur.fetchone()
        except Exception:
            advisor = None
        finally:
            cur.close()

        assigned_id = lead_row.get("asignado_a") or (advisor or {}).get("id")
        return {
            "assigned_to": assigned_id,
            "advisor_name": (advisor or {}).get("nombre"),
            "reason": "Asignación automática por score y carga de trabajo",
            "priority": score_data.get("priority_label"),
        }
