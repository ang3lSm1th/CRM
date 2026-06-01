"""Cierre y facturación: propuesta, objeciones y registro de venta/no venta."""

import MySQLdb.cursors

from extensions import mysql


class ClosingAgent:
    AGENT_NAME = "closing_agent"

    def prepare_proposal(self, lead_row, score_data):
        nombre = (lead_row.get("nombre") or "cliente").strip()
        score = score_data.get("global_score", 0)
        return {
            "agent": self.AGENT_NAME,
            "ok": True,
            "lead_id": lead_row.get("id"),
            "action": "proposal",
            "summary": (
                f"Propuesta comercial para {nombre} basada en score {score}. "
                "Incluye cotización, condiciones de pago y plazo de validez 15 días."
            ),
            "next_steps": ["Enviar cotización", "Agendar cierre", "Registrar resultado"],
        }

    def register_sale(self, lead_id, *, sale_won=True, monto=0, motivo_no_venta=None):
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
