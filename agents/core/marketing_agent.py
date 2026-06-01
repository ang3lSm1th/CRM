import re
import MySQLdb.cursors
from extensions import mysql
from utils.text_normalizer import normalize_user_text


class MarketingAgent:
    """Agente especializado en campañas, inventario y ferias de marketing."""

    def _table_exists(self, table_name):
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            cur.execute(
                """
                SELECT COUNT(*) AS total
                FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = %s
                """,
                (table_name,),
            )
            row = cur.fetchone() or {}
            return int(row.get("total", 0)) > 0
        finally:
            cur.close()

    def _column_exists(self, table_name, column_name):
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            cur.execute(
                """
                SELECT COUNT(*) AS total
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = %s
                  AND COLUMN_NAME = %s
                """,
                (table_name, column_name),
            )
            row = cur.fetchone() or {}
            return int(row.get("total", 0)) > 0
        finally:
            cur.close()

    def _run_one(self, sql, params=None):
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            cur.execute(sql, params or ())
            return cur.fetchone() or {}
        finally:
            cur.close()

    def handle(self, question):
        q = normalize_user_text(question)

        # 1) Estado de campañas
        if re.search(r"\b(campana|campaña|campanas|campañas)\b", q):
            if not self._table_exists("marketing_campaigns"):
                return {
                    "ok": False,
                    "agent": "marketing_agent",
                    "error": "La tabla marketing_campaigns no existe.",
                }

            status_col = (
                "status"
                if self._column_exists("marketing_campaigns", "status")
                else None
            )
            if status_col:
                sql = f"""
                    SELECT
                        COUNT(*) AS total,
                        SUM(CASE WHEN LOWER({status_col}) IN ('activa', 'activo', 'active', 'en curso') THEN 1 ELSE 0 END) AS activas,
                        SUM(CASE WHEN LOWER({status_col}) IN ('finalizada', 'cerrada', 'closed', 'completed') THEN 1 ELSE 0 END) AS finalizadas
                    FROM marketing_campaigns
                """
            else:
                sql = "SELECT COUNT(*) AS total, 0 AS activas, 0 AS finalizadas FROM marketing_campaigns"

            row = self._run_one(sql)
            total = int(row.get("total") or 0)
            activas = int(row.get("activas") or 0)
            finalizadas = int(row.get("finalizadas") or 0)
            answer = (
                f"Campañas registradas: {total}. "
                f"Activas: {activas}. Finalizadas: {finalizadas}."
            )
            return {
                "ok": True,
                "agent": "marketing_agent",
                "intent": "marketing",
                "sql": " ".join(sql.split()),
                "answer": answer,
                "data": {
                    "total": total,
                    "activas": activas,
                    "finalizadas": finalizadas,
                },
            }

        # 2) Inventario de mercaderia
        if re.search(r"\b(inventario|stock|mercaderia|mercadería)\b", q):
            if self._table_exists("marketing_inventario_mercaderia"):
                qty_col = (
                    "cantidad"
                    if self._column_exists(
                        "marketing_inventario_mercaderia", "cantidad"
                    )
                    else None
                )
                if qty_col:
                    sql = f"SELECT COUNT(*) AS items, COALESCE(SUM({qty_col}), 0) AS stock_total FROM marketing_inventario_mercaderia"
                else:
                    sql = "SELECT COUNT(*) AS items, COUNT(*) AS stock_total FROM marketing_inventario_mercaderia"
                row = self._run_one(sql)
                items = int(row.get("items") or 0)
                stock_total = int(row.get("stock_total") or 0)
                return {
                    "ok": True,
                    "agent": "marketing_agent",
                    "intent": "marketing",
                    "sql": sql,
                    "answer": f"Inventario marketing: {items} registros, stock total aproximado {stock_total}.",
                    "data": {"items": items, "stock_total": stock_total},
                }

            if self._table_exists("af_activos"):
                sql = "SELECT COUNT(*) AS items FROM af_activos WHERE estado = 'Activo'"
                row = self._run_one(sql)
                items = int(row.get("items") or 0)
                return {
                    "ok": True,
                    "agent": "marketing_agent",
                    "intent": "marketing",
                    "sql": sql,
                    "answer": f"Inventario de activos en estado Activo: {items} unidades.",
                    "data": {"items": items},
                }

            return {
                "ok": False,
                "agent": "marketing_agent",
                "error": "No encontré tablas de inventario (marketing_inventario_mercaderia o af_activos).",
            }

        # 3) Ferias
        if re.search(r"\b(feria|ferias|evento|eventos)\b", q):
            if not self._table_exists("marketing_ferias"):
                return {
                    "ok": False,
                    "agent": "marketing_agent",
                    "error": "La tabla marketing_ferias no existe.",
                }

            sql = "SELECT COUNT(*) AS total_ferias FROM marketing_ferias"
            row = self._run_one(sql)
            total = int(row.get("total_ferias") or 0)
            answer = f"Actualmente hay {total} ferias registradas."

            if self._table_exists("marketing_feria_resultados") and self._column_exists(
                "marketing_feria_resultados", "leads_generados"
            ):
                sql2 = "SELECT COALESCE(SUM(leads_generados), 0) AS leads_ferias FROM marketing_feria_resultados"
                row2 = self._run_one(sql2)
                leads = int(row2.get("leads_ferias") or 0)
                answer += f" Leads generados acumulados: {leads}."

            return {
                "ok": True,
                "agent": "marketing_agent",
                "intent": "marketing",
                "sql": sql,
                "answer": answer,
                "data": {"total_ferias": total},
            }

        return {
            "ok": False,
            "agent": "marketing_agent",
            "error": "No pude mapear la consulta a campañas, inventario o ferias.",
        }
