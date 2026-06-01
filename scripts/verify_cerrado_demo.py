import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
from dotenv import load_dotenv
import MySQLdb
load_dotenv()
conn = MySQLdb.connect(host=os.getenv('MYSQL_HOST','localhost'), user=os.getenv('MYSQL_USER','root'), passwd=os.getenv('MYSQL_PASSWORD','123456'), db=os.getenv('MYSQL_DB','u349183440_crm_orbes'), port=int(os.getenv('MYSQL_PORT','3307')))
cur = conn.cursor()
cur.execute("SELECT COUNT(*) FROM seguimientos WHERE comentario='Demo clase: cierre automático'")
print('seguimientos demo:', cur.fetchone()[0])
cur.execute("""
SELECT COUNT(*) FROM seguimientos s
WHERE s.comentario='Demo clase: cierre automático'
AND EXISTS (SELECT 1 FROM ventas_concretadas vc WHERE vc.lead_id=s.lead_id AND vc.fecha_venta=s.fecha_guardado)
""")
print('con venta misma fecha:', cur.fetchone()[0])
cur.execute("""
SELECT s.cotizacion, s.monto, s.moneda_id, s.fecha_guardado
FROM seguimientos s WHERE s.comentario='Demo clase: cierre automático' LIMIT 5
""")
for r in cur.fetchall(): print('sample:', r)
cur.close(); conn.close()
