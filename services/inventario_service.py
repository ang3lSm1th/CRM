"""Servicio de inventario comercial para cotizaciones."""

from __future__ import annotations

import logging
from typing import Any

import MySQLdb.cursors

from extensions import mysql

logger = logging.getLogger(__name__)


def ensure_inventario_table() -> None:
    """Crea la tabla si aún no existe (idempotente)."""
    cur = mysql.connection.cursor()
    try:
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
              UNIQUE KEY uq_inventario_codigo (codigo),
              KEY idx_inv_bien (bien_servicio_id),
              KEY idx_inv_linea (linea_producto_id),
              KEY idx_inv_activo (activo)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
        mysql.connection.commit()
    except Exception as exc:
        logger.warning("ensure_inventario_table: %s", exc)
        try:
            mysql.connection.rollback()
        except Exception:
            pass
    finally:
        cur.close()


def listar_productos(
    *,
    bien_servicio_id: int | None = None,
    solo_activos: bool = True,
    solo_con_stock: bool = False,
    limit: int = 80,
) -> list[dict[str, Any]]:
    ensure_inventario_table()
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        clauses = ["1=1"]
        params: list[Any] = []
        if solo_activos:
            clauses.append("p.activo = 1")
        if solo_con_stock:
            clauses.append("p.stock > 0")
        if bien_servicio_id:
            clauses.append("p.bien_servicio_id = %s")
            params.append(int(bien_servicio_id))
        params.append(int(limit))
        cur.execute(
            f"""
            SELECT
              p.id,
              p.codigo,
              p.descripcion,
              p.unidad,
              p.bien_servicio_id,
              p.linea_producto_id,
              p.marca,
              p.especificacion,
              p.precio_unitario,
              p.incluye_igv,
              p.stock,
              p.stock_minimo,
              p.activo,
              bs.nombre AS bien_nombre,
              lp.nombre AS linea_nombre
            FROM inventario_productos p
            LEFT JOIN bienes_servicios bs ON bs.id = p.bien_servicio_id
            LEFT JOIN linea_producto lp ON lp.id = p.linea_producto_id
            WHERE {' AND '.join(clauses)}
            ORDER BY p.descripcion ASC
            LIMIT %s
            """,
            tuple(params),
        )
        rows = cur.fetchall() or []
        out = []
        for r in rows:
            item = dict(r)
            try:
                item["precio_unitario"] = float(item.get("precio_unitario") or 0)
                item["stock"] = float(item.get("stock") or 0)
            except Exception:
                pass
            out.append(item)
        return out
    except Exception as exc:
        logger.warning("listar_productos falló: %s", exc)
        return []
    finally:
        cur.close()


def producto_por_codigo(codigo: str) -> dict[str, Any] | None:
    codigo = (codigo or "").strip().upper()
    if not codigo:
        return None
    ensure_inventario_table()
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        cur.execute(
            """
            SELECT *
            FROM inventario_productos
            WHERE UPPER(codigo) = %s AND activo = 1
            LIMIT 1
            """,
            (codigo,),
        )
        row = cur.fetchone()
        if not row:
            return None
        data = dict(row)
        data["precio_unitario"] = float(data.get("precio_unitario") or 0)
        data["stock"] = float(data.get("stock") or 0)
        return data
    except Exception:
        return None
    finally:
        cur.close()


def catalogo_para_prompt(productos: list[dict[str, Any]]) -> str:
    if not productos:
        return "(Sin productos en inventario para esta línea)"
    lines = []
    for p in productos:
        lines.append(
            f"- codigo={p.get('codigo')} | {p.get('descripcion')} | "
            f"UM={p.get('unidad') or 'UND'} | precio_unitario={float(p.get('precio_unitario') or 0):.2f} | "
            f"stock={float(p.get('stock') or 0):.0f}"
            + (f" | marca={p.get('marca')}" if p.get("marca") else "")
        )
    return "\n".join(lines)


def normalizar_items_desde_inventario(
    raw_items: list[Any],
    productos: list[dict[str, Any]],
    *,
    max_items: int = 4,
) -> list[dict[str, Any]]:
    """Fuerza precios/descripciones del inventario. Descarta inventados."""
    by_codigo = {str(p.get("codigo") or "").upper(): p for p in productos}
    by_desc = {
        str(p.get("descripcion") or "").strip().casefold(): p for p in productos
    }
    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    for raw in raw_items or []:
        if not isinstance(raw, dict):
            continue
        codigo = str(raw.get("codigo") or raw.get("sku") or "").strip().upper()
        desc = str(raw.get("descripcion") or "").strip()
        prod = by_codigo.get(codigo) if codigo else None
        if not prod and desc:
            prod = by_desc.get(desc.casefold())
            if not prod:
                # match parcial controlado
                for dkey, p in by_desc.items():
                    if desc.casefold() in dkey or dkey in desc.casefold():
                        prod = p
                        break
        if not prod:
            continue
        code = str(prod.get("codigo") or "").upper()
        if code in seen:
            continue
        seen.add(code)
        try:
            qty = float(raw.get("cantidad") or 1)
        except Exception:
            qty = 1.0
        if qty <= 0:
            qty = 1.0
        # No cotizar más del stock disponible (si hay stock cargado)
        stock = float(prod.get("stock") or 0)
        if stock > 0 and qty > stock:
            qty = stock
        precio = float(prod.get("precio_unitario") or 0)
        total = round(precio * qty, 2)
        out.append(
            {
                "codigo": prod.get("codigo"),
                "descripcion": prod.get("descripcion"),
                "unidad": prod.get("unidad") or "UND",
                "cantidad": int(qty) if float(qty).is_integer() else qty,
                "precio_unitario": round(precio, 2),
                "total": total,
                "stock": stock,
            }
        )
        if len(out) >= max_items:
            break
    return out


def items_fallback(productos: list[dict[str, Any]], *, max_items: int = 2) -> list[dict[str, Any]]:
    """Selecciona productos con stock (o primeros) para respaldo sin LLM."""
    ranked = sorted(
        productos,
        key=lambda p: (
            0 if float(p.get("stock") or 0) > 0 else 1,
            str(p.get("descripcion") or ""),
        ),
    )
    fake_raw = [
        {"codigo": p.get("codigo"), "cantidad": 1}
        for p in ranked[:max_items]
    ]
    return normalizar_items_desde_inventario(fake_raw, productos, max_items=max_items)


def ensure_cotizacion_items_table() -> None:
    cur = mysql.connection.cursor()
    try:
        cur.execute(
            """
            CREATE TABLE IF NOT EXISTS cotizacion_items (
              id INT AUTO_INCREMENT PRIMARY KEY,
              lead_id INT NOT NULL,
              seguimiento_id INT NULL,
              producto_id INT NULL,
              codigo VARCHAR(40) NOT NULL,
              descripcion VARCHAR(255) NOT NULL,
              unidad VARCHAR(20) NOT NULL DEFAULT 'UND',
              cantidad DECIMAL(12,2) NOT NULL DEFAULT 1.00,
              precio_unitario DECIMAL(12,2) NOT NULL DEFAULT 0.00,
              total DECIMAL(12,2) NOT NULL DEFAULT 0.00,
              created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
              KEY idx_ci_lead (lead_id),
              KEY idx_ci_seg (seguimiento_id),
              KEY idx_ci_prod (producto_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4
            """
        )
        mysql.connection.commit()
    except Exception as exc:
        logger.warning("ensure_cotizacion_items_table: %s", exc)
        try:
            mysql.connection.rollback()
        except Exception:
            pass
    finally:
        cur.close()


def catalogo_para_lead(bien_servicio_id: int | None = None) -> list[dict[str, Any]]:
    """Inventario completo para cualquier lead; prioriza productos de su línea."""
    todos = listar_productos(bien_servicio_id=None, solo_activos=True, limit=120)
    if not bien_servicio_id:
        return todos
    try:
        bien_id = int(bien_servicio_id)
    except Exception:
        return todos
    propios = [p for p in todos if int(p.get("bien_servicio_id") or 0) == bien_id]
    otros = [p for p in todos if int(p.get("bien_servicio_id") or 0) != bien_id]
    return propios + otros


def guardar_cotizacion_items(
    *,
    lead_id: int,
    seguimiento_id: int | None,
    items: list[dict[str, Any]],
) -> int:
    """Persiste ítems de cotización vinculados al lead/seguimiento."""
    ensure_inventario_table()
    ensure_cotizacion_items_table()
    if not items:
        return 0
    catalogo = listar_productos(bien_servicio_id=None, solo_activos=True, limit=200)
    normalizados = normalizar_items_desde_inventario(items, catalogo, max_items=20)
    if not normalizados:
        return 0
    by_codigo = {str(p.get("codigo") or "").upper(): p for p in catalogo}
    cur = mysql.connection.cursor()
    saved = 0
    try:
        for it in normalizados:
            prod = by_codigo.get(str(it.get("codigo") or "").upper()) or {}
            cur.execute(
                """
                INSERT INTO cotizacion_items (
                  lead_id, seguimiento_id, producto_id, codigo, descripcion,
                  unidad, cantidad, precio_unitario, total
                ) VALUES (%s,%s,%s,%s,%s,%s,%s,%s,%s)
                """,
                (
                    int(lead_id),
                    int(seguimiento_id) if seguimiento_id else None,
                    prod.get("id"),
                    it.get("codigo"),
                    it.get("descripcion"),
                    it.get("unidad") or "UND",
                    it.get("cantidad") or 1,
                    it.get("precio_unitario") or 0,
                    it.get("total") or 0,
                ),
            )
            saved += 1
        mysql.connection.commit()
        return saved
    except Exception as exc:
        logger.warning("guardar_cotizacion_items: %s", exc)
        try:
            mysql.connection.rollback()
        except Exception:
            pass
        return 0
    finally:
        cur.close()


def resumen_productos_por_leads(lead_ids: list[int]) -> dict[int, str]:
    """Últimos productos cotizados por lead (texto resumen)."""
    if not lead_ids:
        return {}
    ensure_cotizacion_items_table()
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        placeholders = ",".join(["%s"] * len(lead_ids))
        cur.execute(
            f"""
            SELECT lead_id, seguimiento_id, codigo, cantidad, id
            FROM cotizacion_items
            WHERE lead_id IN ({placeholders})
            ORDER BY lead_id ASC, id DESC
            """,
            tuple(lead_ids),
        )
        out: dict[int, str] = {}
        current_lead = None
        current_seg = object()
        parts: list[str] = []
        for row in cur.fetchall() or []:
            lid = int(row["lead_id"])
            seg = row.get("seguimiento_id")
            if lid != current_lead:
                if current_lead is not None and parts:
                    out[current_lead] = " | ".join(parts)
                current_lead = lid
                current_seg = seg
                parts = []
            elif seg != current_seg:
                continue
            qty = row.get("cantidad") or 1
            try:
                qty_f = float(qty)
                qty_s = str(int(qty_f)) if qty_f.is_integer() else str(qty_f)
            except Exception:
                qty_s = str(qty)
            parts.append(f"{row.get('codigo')}×{qty_s}")
        if current_lead is not None and parts:
            out[current_lead] = " | ".join(parts)
        return out
    except Exception as exc:
        logger.warning("resumen_productos_por_leads: %s", exc)
        return {}
    finally:
        cur.close()


def items_por_lead(lead_id: int) -> list[dict[str, Any]]:
    ensure_cotizacion_items_table()
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        cur.execute(
            """
            SELECT codigo, descripcion, unidad, cantidad, precio_unitario, total, seguimiento_id
            FROM cotizacion_items
            WHERE lead_id = %s
            ORDER BY id DESC
            LIMIT 20
            """,
            (int(lead_id),),
        )
        rows = cur.fetchall() or []
        if not rows:
            return []
        # Solo del último seguimiento (o lote sin seguimiento)
        sid = rows[0].get("seguimiento_id")
        batch = [r for r in rows if r.get("seguimiento_id") == sid]
        out = []
        for r in batch:
            item = dict(r)
            try:
                item["cantidad"] = float(item.get("cantidad") or 1)
                item["precio_unitario"] = float(item.get("precio_unitario") or 0)
                item["total"] = float(item.get("total") or 0)
            except Exception:
                pass
            out.append(item)
        return list(reversed(out))
    except Exception:
        return []
    finally:
        cur.close()
