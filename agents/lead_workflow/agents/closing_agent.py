"""Cierre y facturación: propuesta, objeciones y registro de venta/no venta.

WORKFLOW · PASO 5/5 — prepare_proposal() + register_sale()
Invocado desde orchestrator._run_closing() cuando el lead responde.
La propuesta ahora se genera con CotizacionAgent (Cursor/OpenAI + scoring).
"""

import MySQLdb.cursors

from extensions import mysql
from agents.lead_workflow.agents.cotizacion_agent import CotizacionAgent


class ClosingAgent:
    AGENT_NAME = "closing_agent"

    def __init__(self):
        self.cotizacion_agent = CotizacionAgent()

    def prepare_proposal(self, lead_row, score_data):
        # ═══ WORKFLOW · PASO 5/5 · Propuesta comercial personalizada ═══
        quote = self.cotizacion_agent.generate(lead_row, score_data)
        nombre = (lead_row.get("nombre") or "cliente").strip()
        score = score_data.get("global_score", 0)
        mensaje = quote.get("mensaje_comercial") or ""
        summary = (
            f"Cotización {quote.get('cotizacion_codigo')} para {nombre} "
            f"(score {score}, provider={quote.get('provider')}). "
            f"Monto S/ {quote.get('monto_total')}. "
            f"{mensaje[:180]}"
        )
        return {
            "agent": self.AGENT_NAME,
            "ok": True,
            "lead_id": lead_row.get("id"),
            "action": "proposal",
            "summary": summary,
            "cotizacion": quote,
            "next_steps": [
                "Revisar cotización generada",
                "Enviar mensaje comercial al cliente",
                "Registrar resultado en seguimiento",
            ],
        }

    def register_sale(self, lead_id, *, sale_won=True, monto=0, motivo_no_venta=None):
        # ═══ WORKFLOW · FIN · Registro venta/no venta → nodo completed ═══
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            if sale_won and self._table_exists("ventas_concretadas"):
                cur.execute(
                    """
                    INSERT INTO ventas_concretadas (lead_id, monto, fecha_venta)
                    VALUES (%s, %s, CURDATE())
                    """,
                    (lead_id, monto or 0),
                )
                mysql.connection.commit()

            return {
                "agent": self.AGENT_NAME,
                "ok": True,
                "lead_id": lead_id,
                "sale_won": sale_won,
                "monto": monto,
                "motivo_no_venta": motivo_no_venta,
                "registered_at": "now",
            }
        finally:
            cur.close()

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
