import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
import MySQLdb
load_dotenv()
conn = MySQLdb.connect(host=os.getenv('MYSQL_HOST','localhost'), user=os.getenv('MYSQL_USER','root'), passwd=os.getenv('MYSQL_PASSWORD','123456'), db=os.getenv('MYSQL_DB','u349183440_crm_orbes'), port=int(os.getenv('MYSQL_PORT','3307')))
cur = conn.cursor()
for m, ini, fin in [(1,'2026-01-01','2026-01-31'),(2,'2026-02-01','2026-02-28'),(3,'2026-03-01','2026-03-31')]:
    cur.execute(f"""
    SELECT l.id, l.fecha,
      (SELECT COUNT(*) FROM ventas_concretadas vc WHERE vc.lead_id=l.id AND vc.fecha_venta BETWEEN '{ini}' AND '{fin}') as v
    FROM leads l
    JOIN (SELECT lead_id, MAX(id) lid FROM seguimientos GROUP BY lead_id) x ON x.lead_id=l.id
    JOIN seguimientos s ON s.id=x.lid
    JOIN proceso p ON p.id=s.proceso_id
    WHERE LOWER(p.nombre_proceso)='cerrado' AND l.fecha BETWEEN '{ini}' AND '{fin}'
    HAVING v = 0
    """)
    rows = cur.fetchall()
    print(f'mes {m} cerrados sin venta:', len(rows), rows[:5])
cur.close(); conn.close()
