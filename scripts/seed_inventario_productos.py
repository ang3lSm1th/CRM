"""Crea inventario_productos y carga catálogo comercial Orbes para cotizaciones.

Uso:
  python scripts/seed_inventario_productos.py
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
load_dotenv(ROOT / ".env", override=True)

import MySQLdb
from MySQLdb.cursors import DictCursor

# codigo, descripcion, unidad, bien_servicio_id, linea_producto_id, marca, espec, precio, stock
PRODUCTOS = [
    # —— Plásticos Agrícolas (7) ——
    ("PLA-MUL-25N", "Plástico mulching negro calibre 25 micras", "ROL", 7, 82, "Orbes", "1.20m x 400m", 548.00, 120),
    ("PLA-MUL-30N", "Plástico mulching negro calibre 30 micras", "ROL", 7, 82, "Orbes", "1.20m x 400m", 625.00, 80),
    ("PLA-MUL-25P", "Plástico mulching plata/negro calibre 25 micras", "ROL", 7, 82, "Orbes", "1.20m x 400m", 680.00, 60),
    ("PLA-INV-150", "Plástico para invernadero transparente 150 micras", "ROL", 7, 82, "Orbes", "8m x 50m", 2850.00, 35),
    ("PLA-INV-200", "Plástico para invernadero transparente 200 micras", "ROL", 7, 82, "Orbes", "8m x 50m", 3850.00, 28),
    ("PLA-TUN-80", "Plástico para túnel / mini invernadero 80 micras", "ROL", 7, 82, "Orbes", "6m x 100m", 980.00, 45),
    ("MAL-RAS-35", "Malla sombra Raschel 35%", "ROL", 7, 83, "Orbes", "4.20m x 100m", 320.00, 90),
    ("MAL-RAS-50", "Malla sombra Raschel 50%", "ROL", 7, 83, "Orbes", "4.20m x 100m", 420.00, 110),
    ("MAL-RAS-65", "Malla sombra Raschel 65%", "ROL", 7, 83, "Orbes", "4.20m x 100m", 510.00, 70),
    ("MAL-RAS-80", "Malla sombra Raschel 80%", "ROL", 7, 83, "Orbes", "4.20m x 100m", 595.00, 55),
    ("MAL-ANT-20", "Malla antiáfidos 20x10", "ROL", 7, 83, "Orbes", "3.0m x 100m", 860.00, 40),
    ("GEO-HDPE-1", "Geomembrana HDPE 1.0 mm", "M2", 7, 80, "Orbes", "Rollo estándar", 18.50, 5000),
    ("GEO-HDPE-15", "Geomembrana HDPE 1.5 mm", "M2", 7, 80, "Orbes", "Rollo estándar", 24.90, 3500),
    ("MAN-LAY-2", "Manguera layflat 2 pulgadas", "M", 7, 78, "Orbes", "100 psi", 12.80, 2000),
    ("MAN-LAY-3", "Manguera layflat 3 pulgadas", "M", 7, 78, "Orbes", "100 psi", 18.40, 1500),
    ("MAN-SUC-3", "Manguera succión y descarga 3 pulgadas", "M", 7, 79, "Orbes", "Reforzada", 28.00, 800),
    ("GTX-200", "Geotextil no tejido 200 g/m2", "M2", 7, 84, "Orbes", "Rollo", 4.80, 8000),
    # —— Proyecto de riego (5) ——
    ("RIE-CIN-16", "Cinta de riego por goteo 16 mm x 0.20 m", "ROL", 5, None, "Orbes", "1000 m", 185.00, 200),
    ("RIE-CIN-20", "Cinta de riego por goteo 16 mm x 0.30 m", "ROL", 5, None, "Orbes", "1000 m", 165.00, 180),
    ("RIE-TUB-16", "Tubería PE 16 mm riego", "M", 5, None, "Orbes", "PN4", 1.85, 10000),
    ("RIE-TUB-32", "Tubería PE 32 mm riego", "M", 5, None, "Orbes", "PN6", 4.20, 6000),
    ("RIE-ASP-1", "Aspersor plástico 1/2 pulgada", "UND", 5, None, "Orbes", "Radio 8-12 m", 28.50, 400),
    ("RIE-FIL-1", "Filtro de malla 1 pulgada", "UND", 5, None, "Orbes", "120 mesh", 95.00, 120),
    ("RIE-VAL-1", "Válvula de bola PVC 1 pulgada", "UND", 5, None, "Orbes", "Rosca", 22.00, 300),
    # —— Maquinaria agrícola (1) ——
    ("MAQ-MOT-7", "Motocultor 7 HP diésel", "UND", 1, None, "Orbes", "Arranque manual", 4850.00, 8),
    ("MAQ-MOT-9", "Motocultor 9 HP diésel", "UND", 1, None, "Orbes", "Con freza", 5650.00, 6),
    ("MAQ-ARA-3", "Arado de discos 3 discos", "UND", 1, None, "Orbes", "Para tractor mediana", 3200.00, 5),
    ("MAQ-RAS-20", "Rastra de discos 20 discos", "UND", 1, None, "Orbes", "Tiro", 7800.00, 3),
    ("MAQ-SER-MAN", "Servicio de puesta en marcha maquinaria", "SRV", 1, None, "Orbes", "Incluye inducción", 450.00, 999),
    # —— Equipos menores (3) ——
    ("EQM-PUL-20", "Pulverizadora manual 20 litros", "UND", 3, None, "Orbes", "Mochila", 145.00, 60),
    ("EQM-PUL-MOT", "Pulverizadora motorizada 25 litros", "UND", 3, None, "Orbes", "2 tiempos", 890.00, 25),
    ("EQM-DES-52", "Desbrozadora 52 cc", "UND", 3, None, "Orbes", "Arnés incluido", 620.00, 40),
    ("EQM-FUM-BAT", "Fumigadora a batería 16 litros", "UND", 3, None, "Orbes", "Li-ion", 480.00, 35),
    # —— Mantenimiento / servicios (2, 14) ——
    ("MAN-FIL-ACE", "Filtro de aceite tractor estándar", "UND", 2, None, "Orbes", "Compatible multi marca", 68.00, 150),
    ("MAN-FIL-AIR", "Filtro de aire tractor estándar", "UND", 2, None, "Orbes", "Primario", 95.00, 120),
    ("MAN-ACE-15W", "Aceite motor 15W-40 (galón)", "UND", 2, None, "Orbes", "API CI-4", 78.00, 200),
    ("SRV-DIAG", "Diagnóstico técnico en campo", "SRV", 14, None, "Orbes", "Visita técnica", 250.00, 999),
    ("SRV-MANT", "Servicio de mantenimiento preventivo", "SRV", 14, None, "Orbes", "Hasta 4 horas", 650.00, 999),
]


def connect():
    return MySQLdb.connect(
        host=os.getenv("MYSQL_HOST", "127.0.0.1"),
        user=os.getenv("MYSQL_USER", "root"),
        passwd=os.getenv("MYSQL_PASSWORD", ""),
        db=os.getenv("MYSQL_DB") or os.getenv("DB_NAME"),
        port=int(os.getenv("MYSQL_PORT") or os.getenv("DB_PORT") or 3306),
        charset="utf8mb4",
        cursorclass=DictCursor,
    )


def main():
    sql_path = ROOT / "db" / "migrations" / "2026_07_13_create_inventario_productos.sql"
    conn = connect()
    cur = conn.cursor()
    try:
        ddl = sql_path.read_text(encoding="utf-8")
        # Ejecutar sin FK si falla por orden — crear tabla base primero
        try:
            for stmt in ddl.split(";"):
                s = stmt.strip()
                if s:
                    cur.execute(s)
        except Exception:
            cur.execute(
                """
                CREATE TABLE IF NOT EXISTS inventario_productos (
                  id INT AUTO_INCREMENT PRIMARY KEY,
                  codigo VARCHAR(40) NOT NULL,
                  descripcion VARCHAR(255) NOT NULL,
                  unidad VARCHAR(20) NOT NULL DEFAULT 'UND',
                  bien_servicio_id INT NOT NULL,
                  linea_producto_id INT NULL,
                  marca VARCHAR(80) NULL,
                  especificacion VARCHAR(255) NULL,
                  precio_unitario DECIMAL(12,2) NOT NULL DEFAULT 0.00,
                  incluye_igv TINYINT(1) NOT NULL DEFAULT 1,
                  stock DECIMAL(12,2) NOT NULL DEFAULT 0.00,
                  stock_minimo DECIMAL(12,2) NOT NULL DEFAULT 0.00,
                  activo TINYINT(1) NOT NULL DEFAULT 1,
                  created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
                  updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                  UNIQUE KEY uq_inventario_codigo (codigo)
                ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
                """
            )

        # Validar linea_producto ids existentes
        cur.execute("SELECT id FROM linea_producto")
        valid_lp = {int(r["id"]) for r in (cur.fetchall() or [])}

        upserted = 0
        for row in PRODUCTOS:
            codigo, desc, und, bien_id, lp_id, marca, espec, precio, stock = row
            if lp_id is not None and int(lp_id) not in valid_lp:
                lp_id = None
            cur.execute(
                """
                INSERT INTO inventario_productos (
                  codigo, descripcion, unidad, bien_servicio_id, linea_producto_id,
                  marca, especificacion, precio_unitario, incluye_igv, stock, stock_minimo, activo
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,1,%s,5,1)
                ON DUPLICATE KEY UPDATE
                  descripcion=VALUES(descripcion),
                  unidad=VALUES(unidad),
                  bien_servicio_id=VALUES(bien_servicio_id),
                  linea_producto_id=VALUES(linea_producto_id),
                  marca=VALUES(marca),
                  especificacion=VALUES(especificacion),
                  precio_unitario=VALUES(precio_unitario),
                  stock=VALUES(stock),
                  activo=1
                """,
                (codigo, desc, und, bien_id, lp_id, marca, espec, precio, stock),
            )
            upserted += 1

        conn.commit()
        cur.execute(
            """
            SELECT bien_servicio_id, COUNT(*) AS n, SUM(stock) AS stock_total
            FROM inventario_productos WHERE activo=1
            GROUP BY bien_servicio_id ORDER BY bien_servicio_id
            """
        )
        print(f"OK inventario: {upserted} productos cargados/actualizados")
        for r in cur.fetchall() or []:
            print(
                f"  bien_servicio_id={r['bien_servicio_id']}: "
                f"{r['n']} SKUs, stock={float(r['stock_total'] or 0):.0f}"
            )
    finally:
        cur.close()
        conn.close()


if __name__ == "__main__":
    main()
