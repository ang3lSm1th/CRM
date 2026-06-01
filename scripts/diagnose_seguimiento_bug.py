import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
import MySQLdb
load_dotenv()
conn = MySQLdb.connect(host=os.getenv('MYSQL_HOST','localhost'), user=os.getenv('MYSQL_USER','root'), passwd=os.getenv('MYSQL_PASSWORD','123456'), db=os.getenv('MYSQL_DB','u349183440_crm_orbes'), port=int(os.getenv('MYSQL_PORT','3307')))
cur = conn.cursor()

cur.execute("""
SELECT COUNT(*) FROM leads l
JOIN (SELECT lead_id, MAX(id) lid FROM seguimientos GROUP BY lead_id) x ON x.lead_id=l.id
JOIN seguimientos s ON s.id=x.lid
JOIN proceso p ON p.id=s.proceso_id
WHERE LOWER(p.nombre_proceso)='seguimiento'
""")
print('panel (MAX id) seguimiento:', cur.fetchone()[0])

last_sql_report_old = """
SELECT s1.lead_id, s1.proceso_id
FROM seguimientos s1
LEFT JOIN seguimientos s2
  ON s2.lead_id = s1.lead_id
 AND (s2.fecha_guardado > s1.fecha_guardado
   OR (s2.fecha_guardado = s1.fecha_guardado AND s2.id > s1.id))
WHERE s2.id IS NULL
"""
last_sql_report_new = """
SELECT s1.lead_id, s1.proceso_id
FROM seguimientos s1
INNER JOIN (
  SELECT lead_id, MAX(id) AS max_id FROM seguimientos GROUP BY lead_id
) s2 ON s1.id = s2.max_id AND s1.lead_id = s2.lead_id
"""

for label, sql in [('reporte OLD', last_sql_report_old), ('reporte NEW', last_sql_report_new)]:
    cur.execute(f"""
    SELECT COUNT(*) FROM leads l
    JOIN ({sql}) ls ON ls.lead_id = l.id
    JOIN proceso p ON p.id = ls.proceso_id
    WHERE LOWER(p.nombre_proceso)='seguimiento'
    """)
    print(f'{label} seguimiento:', cur.fetchone()[0])
cur.close(); conn.close()
