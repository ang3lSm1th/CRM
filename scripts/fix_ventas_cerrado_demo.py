import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
import MySQLdb

load_dotenv()
conn = MySQLdb.connect(
    host=os.getenv("MYSQL_HOST", "localhost"),
    user=os.getenv("MYSQL_USER", "root"),
    passwd=os.getenv("MYSQL_PASSWORD", "123456"),
    db=os.getenv("MYSQL_DB", "u349183440_crm_orbes"),
    port=int(os.getenv("MYSQL_PORT", "3307")),
)
cur = conn.cursor()
cur.execute(
    """
    INSERT INTO ventas_concretadas (cliente_id, lead_id, bien_servicio_id, monto, fecha_venta)
    SELECT l.cliente_id, s.lead_id, l.bien_servicio_id, s.monto, s.fecha_guardado
    FROM seguimientos s
    JOIN leads l ON l.id = s.lead_id
    WHERE s.comentario = %s
      AND s.proceso_id = 5
      AND NOT EXISTS (
        SELECT 1 FROM ventas_concretadas vc
        WHERE vc.lead_id = s.lead_id
          AND vc.fecha_venta = s.fecha_guardado
          AND vc.monto <=> s.monto
      )
    """,
    ("Demo clase: cierre automático",),
)
print("ventas insertadas:", cur.rowcount)
conn.commit()
cur.execute(
    "SELECT COUNT(*) FROM ventas_concretadas WHERE fecha_venta BETWEEN '2026-01-01' AND '2026-03-31'"
)
print("ventas ene-mar 2026:", cur.fetchone()[0])
cur.close()
conn.close()
