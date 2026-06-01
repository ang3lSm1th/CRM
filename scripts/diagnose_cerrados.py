import os
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
cur.execute("SELECT COUNT(*) FROM ventas_concretadas")
print("ventas total:", cur.fetchone()[0])
cur.execute(
    "SELECT YEAR(fecha_venta), MONTH(fecha_venta), COUNT(*) "
    "FROM ventas_concretadas GROUP BY 1,2 ORDER BY 1,2"
)
print("ventas por mes:", cur.fetchall())
cur.execute(
    """
    SELECT COUNT(*) FROM leads l
    JOIN (SELECT lead_id, MAX(id) last_id FROM seguimientos GROUP BY lead_id) ls
      ON ls.lead_id = l.id
    JOIN seguimientos s ON s.id = ls.last_id
    JOIN proceso p ON p.id = s.proceso_id
    WHERE LOWER(p.nombre_proceso) = 'cerrado'
    """
)
print("leads cerrados:", cur.fetchone()[0])
cur.execute(
    """
    SELECT COUNT(*) FROM leads l
    JOIN (SELECT lead_id, MAX(id) last_id FROM seguimientos GROUP BY lead_id) ls
      ON ls.lead_id = l.id
    JOIN seguimientos s ON s.id = ls.last_id
    JOIN proceso p ON p.id = s.proceso_id
    WHERE LOWER(p.nombre_proceso) = 'cerrado'
      AND l.fecha BETWEEN '2026-01-25' AND '2026-01-31'
    """
)
print("cerrados rango 2026-01-25..31:", cur.fetchone()[0])
cur.execute(
    """
    SELECT COUNT(*) FROM leads l
    JOIN (SELECT lead_id, MAX(id) last_id FROM seguimientos GROUP BY lead_id) ls
      ON ls.lead_id = l.id
    JOIN seguimientos s ON s.id = ls.last_id
    JOIN proceso p ON p.id = s.proceso_id
    WHERE LOWER(p.nombre_proceso) = 'cerrado'
      AND l.fecha BETWEEN '2026-01-01' AND '2026-03-31'
    """
)
print("cerrados ene-mar 2026:", cur.fetchone()[0])
cur.execute(
    """
    SELECT COUNT(*) FROM leads l
    JOIN (SELECT lead_id, MAX(id) last_id FROM seguimientos GROUP BY lead_id) ls
      ON ls.lead_id = l.id
    JOIN seguimientos s ON s.id = ls.last_id
    JOIN proceso p ON p.id = s.proceso_id
    WHERE LOWER(p.nombre_proceso) = 'cerrado'
      AND l.fecha BETWEEN '2025-10-01' AND '2025-12-31'
    """
)
print("cerrados oct-dic 2025:", cur.fetchone()[0])
cur.execute(
    """
    SELECT COUNT(DISTINCT l.id) FROM leads l
    JOIN ventas_concretadas vc ON vc.lead_id = l.id
      AND vc.fecha_venta BETWEEN '2026-01-01' AND '2026-03-31'
    JOIN (SELECT lead_id, MAX(id) lid FROM seguimientos GROUP BY lead_id) x
      ON x.lead_id = l.id
    JOIN seguimientos s ON s.id = x.lid
    JOIN proceso p ON p.id = s.proceso_id
    WHERE LOWER(p.nombre_proceso) = 'cerrado'
    """
)
print("cerrados con venta ene-mar 2026:", cur.fetchone()[0])
cur.execute(
    """
    SELECT COUNT(DISTINCT l.id) FROM leads l
    JOIN ventas_concretadas vc ON vc.lead_id = l.id
      AND vc.fecha_venta BETWEEN '2026-01-25' AND '2026-01-31'
    JOIN (SELECT lead_id, MAX(id) lid FROM seguimientos GROUP BY lead_id) x
      ON x.lead_id = l.id
    JOIN seguimientos s ON s.id = x.lid
    JOIN proceso p ON p.id = s.proceso_id
    WHERE LOWER(p.nombre_proceso) = 'cerrado'
    """
)
print("cerrados venta 25-31 ene 2026:", cur.fetchone()[0])
cur.close()
conn.close()
