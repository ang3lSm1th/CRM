"""Persistencia del estado del workflow multiagente por lead."""

import json
import re
from datetime import datetime

import MySQLdb.cursors

from extensions import mysql


def _sanitize_db_text(value):
    """Quita caracteres de 4 bytes (emojis) incompatibles con columnas utf8."""
    if value is None:
        return None
    if not isinstance(value, str):
        value = str(value)
    return re.sub(r"[\U00010000-\U0010ffff]", "", value)


class LeadWorkflowStateStore:
    WORKFLOW_NODES = (
        "scoring",
        "assignment",
        "commercial",
        "recovery",
        "closing",
        "dead",
        "completed",
    )

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

    def ensure_tables(self):
        return self._table_exists("lead_agent_state")

    def get_state(self, lead_id):
        if not self.ensure_tables():
            return None
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            cur.execute(
                "SELECT * FROM lead_agent_state WHERE lead_id = %s LIMIT 1",
                (lead_id,),
            )
            row = cur.fetchone()
            if row and row.get("data") and isinstance(row["data"], str):
                try:
                    row["data"] = json.loads(row["data"])
                except json.JSONDecodeError:
                    pass
            return row
        finally:
            cur.close()

    def upsert_state(
        self,
        lead_id,
        *,
        current_node=None,
        score=None,
        priority_label=None,
        recommendation=None,
        assigned_to=None,
        attempts=None,
        next_action_date=None,
        data=None,
        workflow_status=None,
    ):
        existing = self.get_state(lead_id)
        merged_data = existing.get("data") if existing else {}
        if isinstance(merged_data, str):
            try:
                merged_data = json.loads(merged_data)
            except json.JSONDecodeError:
                merged_data = {}
        if data:
            merged_data.update(data)

        payload = {
            "current_node": current_node
            or (existing or {}).get("current_node", "scoring"),
            "score": score if score is not None else (existing or {}).get("score", 0),
            "priority_label": priority_label
            or (existing or {}).get("priority_label"),
            "recommendation": _sanitize_db_text(
                recommendation or (existing or {}).get("recommendation")
            ),
            "assigned_to": assigned_to
            if assigned_to is not None
            else (existing or {}).get("assigned_to"),
            "attempts": attempts
            if attempts is not None
            else (existing or {}).get("attempts", 0),
            "next_action_date": next_action_date
            or (existing or {}).get("next_action_date"),
            "data": json.dumps(merged_data, ensure_ascii=True),
            "workflow_status": workflow_status
            or (existing or {}).get("workflow_status", "active"),
            "last_action": datetime.now(),
        }

        cur = mysql.connection.cursor()
        try:
            if existing:
                cur.execute(
                    """
                    UPDATE lead_agent_state
                    SET current_node = %s, score = %s, priority_label = %s,
                        recommendation = %s, assigned_to = %s, attempts = %s,
                        next_action_date = %s, data = %s, workflow_status = %s,
                        last_action = %s
                    WHERE lead_id = %s
                    """,
                    (
                        payload["current_node"],
                        payload["score"],
                        payload["priority_label"],
                        payload["recommendation"],
                        payload["assigned_to"],
                        payload["attempts"],
                        payload["next_action_date"],
                        payload["data"],
                        payload["workflow_status"],
                        payload["last_action"],
                        lead_id,
                    ),
                )
            else:
                cur.execute(
                    """
                    INSERT INTO lead_agent_state
                    (lead_id, current_node, score, priority_label, recommendation,
                     assigned_to, attempts, next_action_date, data, workflow_status, last_action)
                    VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s)
                    """,
                    (
                        lead_id,
                        payload["current_node"],
                        payload["score"],
                        payload["priority_label"],
                        payload["recommendation"],
                        payload["assigned_to"],
                        payload["attempts"],
                        payload["next_action_date"],
                        payload["data"],
                        payload["workflow_status"],
                        payload["last_action"],
                    ),
                )
            mysql.connection.commit()
        finally:
            cur.close()
        return self.get_state(lead_id)

    def log_interaction(
        self,
        lead_id,
        agent_name,
        *,
        interaction_type="system",
        direction="outbound",
        content=None,
        response_received=False,
        response_content=None,
        metadata=None,
    ):
        if not self._table_exists("agent_interactions"):
            return None
        content = _sanitize_db_text(content)
        response_content = _sanitize_db_text(response_content)
        cur = mysql.connection.cursor()
        try:
            cur.execute(
                """
                INSERT INTO agent_interactions
                (lead_id, agent_name, interaction_type, direction, content,
                 response_received, response_content, metadata)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
                """,
                (
                    lead_id,
                    agent_name,
                    interaction_type,
                    direction,
                    content,
                    1 if response_received else 0,
                    response_content,
                    json.dumps(metadata or {}, ensure_ascii=True),
                ),
            )
            mysql.connection.commit()
            return cur.lastrowid
        finally:
            cur.close()

    def get_interactions(self, lead_id, limit=50):
        if not self._table_exists("agent_interactions"):
            return []
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            cur.execute(
                """
                SELECT * FROM agent_interactions
                WHERE lead_id = %s
                ORDER BY created_at DESC
                LIMIT %s
                """,
                (lead_id, limit),
            )
            return cur.fetchall() or []
        finally:
            cur.close()

    @staticmethod
    def normalize_codigo(raw):
        """Normaliza entrada: trim + mayúsculas. No inventa prefijos LED-."""
        return (raw or "").strip().upper()

    def resolve_lead(self, codigo_raw):
        """
        Resuelve un lead exclusivamente por su codigo en tabla leads.
        Retorna (row, error).
        """
        codigo = self.normalize_codigo(codigo_raw)
        if not codigo:
            return None, "codigo es obligatorio (ej: LED-4376)"
        row = self.fetch_lead_by_codigo(codigo)
        if not row:
            return None, f"Lead con código '{codigo}' no encontrado."
        return row, None

    def fetch_lead(self, lead_id):
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            cur.execute(
                """
                SELECT l.*, c.nombre AS canal_nombre
                FROM leads l
                LEFT JOIN canales_recepcion c ON c.id = l.canal_id
                WHERE l.id = %s
                LIMIT 1
                """,
                (lead_id,),
            )
            return cur.fetchone()
        finally:
            cur.close()

    def fetch_lead_by_codigo(self, codigo):
        codigo = self.normalize_codigo(codigo)
        if not codigo:
            return None
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            cur.execute(
                """
                SELECT l.*, c.nombre AS canal_nombre
                FROM leads l
                LEFT JOIN canales_recepcion c ON c.id = l.canal_id
                WHERE l.codigo COLLATE utf8mb4_0900_ai_ci = %s
                LIMIT 1
                """,
                (codigo,),
            )
            return cur.fetchone()
        finally:
            cur.close()

    def resolve_lead_id(self, codigo):
        row, _err = self.resolve_lead(codigo)
        return int(row["id"]) if row else None

    def list_recent_interactions(self, limit=50):
        if not self._table_exists("agent_interactions"):
            return []
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            cur.execute(
                """
                SELECT ai.*, l.nombre AS lead_nombre, l.codigo AS lead_codigo
                FROM agent_interactions ai
                JOIN leads l ON l.id = ai.lead_id
                ORDER BY ai.created_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            return cur.fetchall() or []
        finally:
            cur.close()

    def list_active_workflows(self, limit=30):
        if not self.ensure_tables():
            return []
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            cur.execute(
                """
                SELECT las.*, l.nombre AS lead_nombre, l.codigo AS lead_codigo
                FROM lead_agent_state las
                JOIN leads l ON l.id = las.lead_id
                ORDER BY las.updated_at DESC
                LIMIT %s
                """,
                (limit,),
            )
            rows = cur.fetchall() or []
            for row in rows:
                if row.get("data") and isinstance(row["data"], str):
                    try:
                        row["data"] = json.loads(row["data"])
                    except json.JSONDecodeError:
                        pass
            return rows
        finally:
            cur.close()
