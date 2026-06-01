# routes/ubigeo.py
import MySQLdb.cursors
from app import mysql   # <-- Ajusta esto si tu proyecto exporta `mysql` desde otro módulo

def get_departamentos():
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        cur.execute("SELECT idDepartamento AS id, departamento AS nombre FROM departamentos ORDER BY departamento")
        rows = cur.fetchall() or []
        # rows ya es lista de dicts con keys 'id' y 'nombre'
        return rows
    finally:
        cur.close()

def get_provincias_by_departamento(departamento_id):
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        cur.execute(
            "SELECT idProvincia AS id, provincia AS nombre FROM provincia WHERE idDepartamento = %s ORDER BY provincia",
            (departamento_id,)
        )
        rows = cur.fetchall() or []
        return rows
    finally:
        cur.close()

def get_distritos_by_provincia(provincia_id):
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        cur.execute(
            "SELECT idDistrito AS id, distrito AS nombre FROM distrito WHERE idProvincia = %s ORDER BY distrito",
            (provincia_id,)
        )
        rows = cur.fetchall() or []
        return rows
    finally:
        cur.close()
