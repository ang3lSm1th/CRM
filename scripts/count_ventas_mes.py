import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
import MySQLdb
load_dotenv()
conn = MySQLdb.connect(host=os.getenv('MYSQL_HOST','localhost'), user=os.getenv('MYSQL_USER','root'), passwd=os.getenv('MYSQL_PASSWORD','123456'), db=os.getenv('MYSQL_DB','u349183440_crm_orbes'), port=int(os.getenv('MYSQL_PORT','3307')))
cur = conn.cursor()

for m, name in [(1,'ene'),(2,'feb'),(3,'mar')]:
    cur.execute("""
        SELECT COUNT(*) FROM ventas_concretadas
        WHERE YEAR(fecha_venta)=2026 AND MONTH(fecha_venta)=%s
    """, (m,))
    print(f'ventas {name} 2026:', cur.fetchone()[0])
    cur.execute("""
        SELECT COUNT(*) FROM leads l
        JOIN (SELECT lead_id, MAX(id) lid FROM seguimientos GROUP BY lead_id) x ON x.lead_id=l.id
        JOIN seguimientos s ON s.id=x.lid
        JOIN proceso p ON p.id=s.proceso_id
        WHERE LOWER(p.nombre_proceso)='cerrado'
          AND YEAR(l.fecha)=2026 AND MONTH(l.fecha)=%s
    """, (m,))
    print(f'cerrados {name} 2026 (lead.fecha):', cur.fetchone()[0])

cur.close(); conn.close()
