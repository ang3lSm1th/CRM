import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
import MySQLdb
load_dotenv()
conn = MySQLdb.connect(host=os.getenv('MYSQL_HOST','localhost'), user=os.getenv('MYSQL_USER','root'), passwd=os.getenv('MYSQL_PASSWORD','123456'), db=os.getenv('MYSQL_DB','u349183440_crm_orbes'), port=int(os.getenv('MYSQL_PORT','3307')))
cur = conn.cursor()
cur.execute("""
SELECT lead_id, COUNT(*) c FROM ventas_concretadas
WHERE fecha_venta BETWEEN '2026-01-01' AND '2026-01-31'
GROUP BY lead_id HAVING c > 1 LIMIT 10
""")
print('leads multi venta ene:', cur.fetchall())
cur.execute("SELECT COUNT(DISTINCT lead_id) FROM ventas_concretadas WHERE fecha_venta BETWEEN '2026-01-01' AND '2026-01-31'")
print('distinct leads venta ene:', cur.fetchone()[0])
cur.close(); conn.close()
