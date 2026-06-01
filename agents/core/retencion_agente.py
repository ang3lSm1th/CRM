import re
import MySQLdb.cursors

from extensions import mysql
from utils.text_normalizer import normalize_user_text


class RetencionAbandonoAgente:
    """Calcula retención de clientes y riesgo de abandono en leads."""

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

    def _run_all(self, sql, params=None):
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            cur.execute(sql, params or ())
            return cur.fetchall() or []
        finally:
            cur.close()

    def _run_one(self, sql, params=None):
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            cur.execute(sql, params or ())
            return cur.fetchone() or {}
        finally:
            cur.close()

    def _tasa_retencion(self):
        if not self._table_exists("ventas_concretadas"):
            return {"ok": False, "error": "No existe la tabla ventas_concretadas."}

        sql = """
            SELECT
                COUNT(DISTINCT cliente_id) AS clientes_con_compra,
                COUNT(DISTINCT CASE WHEN c.ventas_cliente >= 2 THEN cliente_id END) AS clientes_recurrentes
            FROM (
                SELECT cliente_id, COUNT(*) AS ventas_cliente
                FROM ventas_concretadas
                WHERE cliente_id IS NOT NULL
                GROUP BY cliente_id
            ) c
        """
        row = self._run_one(sql)
        clientes = int(row.get("clientes_con_compra") or 0)
        recurrentes = int(row.get("clientes_recurrentes") or 0)
        tasa = round((recurrentes / clientes) * 100, 2) if clientes else 0.0

        answer = (
            f"Tasa de retención estimada: {tasa}% "
            f"({recurrentes} clientes recurrentes de {clientes} con compra)."
        )
        return {
            "ok": True,
            "answer": answer,
            "data": {
                "clientes_con_compra": clientes,
                "clientes_recurrentes": recurrentes,
                "tasa_retencion": tasa,
            },
            "confidence": 0.9,
        }

    def _leads_riesgo_abandono(self):
        if not self._table_exists("leads"):
            return {"ok": False, "error": "No existe la tabla leads."}

        sql = """
            SELECT
                l.id,
                l.nombre,
                l.telefono,
                COALESCE(MAX(s.fecha_guardado), l.fecha) AS ultima_actividad,
                DATEDIFF(CURDATE(), COALESCE(MAX(s.fecha_guardado), l.fecha)) AS dias_inactivo
            FROM leads l
            LEFT JOIN seguimientos s ON s.lead_id = l.id
            GROUP BY l.id, l.nombre, l.telefono, l.fecha
            HAVING dias_inactivo > 30
            ORDER BY dias_inactivo DESC
            LIMIT 25
        """
        rows = self._run_all(sql)

        if not rows:
            return {
                "ok": True,
                "answer": "No se detectaron leads con inactividad mayor a 30 días.",
                "data": [],
                "confidence": 0.84,
            }

        top = rows[0]
        answer = (
            f"Detecté {len(rows)} leads con riesgo de abandono (>30 días). "
            f"Mayor inactividad: Lead #{top.get('id')} con {int(top.get('dias_inactivo') or 0)} días."
        )
        return {
            "ok": True,
            "answer": answer,
            "data": rows,
            "confidence": 0.88,
        }

    def handle(self, question):
        q = normalize_user_text(question)

        if re.search(r"\b(retencion|retención|recurrente)\b", q):
            result = self._tasa_retencion()
        elif re.search(r"\b(riesgo|abandono|inactivo|inactividad)\b", q):
            result = self._leads_riesgo_abandono()
        else:
            return {
                "ok": False,
                "agent": "retencion_abandono",
                "error": "No pude mapear la consulta a retención o abandono.",
            }

        if not result.get("ok"):
            return {
                "ok": False,
                "agent": "retencion_abandono",
                "error": result.get("error", "Error al calcular retención/abandono."),
            }

        return {
            "ok": True,
            "agent": "retencion_abandono",
            "intent": "retencion_abandono",
            "answer": result.get("answer"),
            "data": result.get("data"),
            "confidence": result.get("confidence", 0.8),
        }
