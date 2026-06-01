from flask import (
    Blueprint,
    render_template,
    request,
    redirect,
    url_for,
    session,
    flash,
    jsonify,
    Response,
    current_app,
)
from utils.security import (
    login_required,
    role_required,
    ROLE_ADMIN,
    ROLE_GERENTE,
    ROLE_RRHH,
    ROLE_ASESOR,
)

# 1. IMPORTAR LA EXCEPCIÓN LeadDuplicatedError (MODIFICADO)
from models.lead import Lead, LeadDuplicatedError
from models.canal import Canal
from models.bien_servicio import BienServicio
from models.user import User
import MySQLdb.cursors
from datetime import date, datetime
from models.proceso import Proceso
from models.moneda import Moneda
from models.motivonoventa import Motivonoventa
from MySQLdb import IntegrityError
from extensions import mysql
import io, base64
import csv
import matplotlib

matplotlib.use("Agg")  # backend sin ventana para servidores
import matplotlib.pyplot as plt
from math import ceil
from models.canal_contacto import CanalContacto
from functools import wraps
import inspect
from urllib.parse import urlsplit, parse_qsl, urlencode, quote
import requests
import json
import ast
from services.tractor_state_agent import TractorStateAgent
from agents.core.prediccion_agente import PrediccionCompraAgente

# Blueprint principal de leads (namespace 'leads')
lead_bp = Blueprint("leads", __name__)
prediccion_agente = PrediccionCompraAgente()


@lead_bp.before_request
@login_required
def _lead_before_request():
    return None


# --- helper permiso columna "Asignado a" ---
def user_can_view_assigned():
    """
    Devuelve True si el rol actual puede ver la columna 'Asignado a'.
    Roles permitidos: ADMIN, GERENTE, RRHH
    """
    return session.get("id_rol") in (ROLE_ADMIN, ROLE_GERENTE, ROLE_RRHH)


def _safe_next_url(next_raw, fallback_endpoint="leads.list_leads", **fallback_kwargs):
    fallback_url = url_for(fallback_endpoint, **fallback_kwargs)
    value = (next_raw or "").strip()
    if not value:
        return fallback_url

    parsed = urlsplit(value)
    if parsed.scheme or parsed.netloc:
        return fallback_url
    if not parsed.path.startswith("/") or parsed.path.startswith("//"):
        return fallback_url

    query = urlencode(parse_qsl(parsed.query, keep_blank_values=True), doseq=True)
    safe_url = parsed.path
    if query:
        safe_url += f"?{query}"
    return safe_url


def _lead_return_label(next_url):
    path = (urlsplit(next_url).path or "").lower()
    if path.startswith("/marketing/roadmap"):
        return "Volver a Roadmap Marketing"
    if path.startswith("/marketing/campanas"):
        return "Volver a Campanas Publicitarias"
    if path.startswith("/marketing/ferias"):
        return "Volver a Ferias"
    if path.startswith("/leads/sin-iniciar"):
        return "Volver a Leads no iniciados"
    if path.startswith("/leads/en-seguimiento"):
        return "Volver a Leads en seguimiento"
    if path.startswith("/leads/programados"):
        return "Volver a Leads programados"
    if path.startswith("/leads/cotizados"):
        return "Volver a Leads cotizados"
    if path.startswith("/leads/cerrados-no-vendidos"):
        return "Volver a Leads cerrados no vendidos"
    if path.startswith("/leads/cerrados"):
        return "Volver a Leads cerrados"
    if path.startswith("/leads/list"):
        return "Volver a Gestión de Leads"
    return "Volver"


def _normalize_text(value):
    return " ".join((value or "").strip().lower().split())


def _is_equipo_bien_servicio(nombre_bien_servicio):
    nombre = _normalize_text(nombre_bien_servicio)
    categorias_permitidas = (
        "maquinaria agricola",
        "maquinaria agrícola",
        "tractor",
        "tractor agricola",
        "tractor agrícola",
        "equipo de fuerza",
        "equipos de fuerza",
        "equipo fuerza",
        "equipos fuerza",
        "equipo menor",
        "equipo menores",
        "equipos menores",
    )
    return any(cat in nombre for cat in categorias_permitidas)


def _get_tractor_db_connection():
    return MySQLdb.connect(
        host=current_app.config.get("TRACTOR_DB_HOST"),
        user=current_app.config.get("TRACTOR_DB_USER"),
        passwd=current_app.config.get("TRACTOR_DB_PASSWORD"),
        db=current_app.config.get("TRACTOR_DB_NAME"),
        port=int(current_app.config.get("TRACTOR_DB_PORT", 3306)),
        charset="utf8mb4",
        cursorclass=MySQLdb.cursors.DictCursor,
        connect_timeout=int(current_app.config.get("TRACTOR_DB_CONNECT_TIMEOUT", 8)),
    )


def _ensure_lead_tractor_guardados_table():
    cur = mysql.connection.cursor()
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS lead_tractor_guardados (
                id INT AUTO_INCREMENT PRIMARY KEY,
                lead_id INT NOT NULL,
                codigo_lead VARCHAR(30) NOT NULL,
                serie VARCHAR(80) NOT NULL,
                equipo VARCHAR(180) NULL,
                modelo VARCHAR(220) NULL,
                estado VARCHAR(80) NULL,
                proceso VARCHAR(60) NULL,
                guardado_por INT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                INDEX idx_ltg_lead (lead_id),
                INDEX idx_ltg_serie (serie),
                UNIQUE KEY uq_ltg_lead_proceso (lead_id, proceso)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)

        # Compatibilidad con tablas ya creadas sin el índice único.
        cur.execute("""
            SELECT COUNT(*) AS total
            FROM information_schema.statistics
            WHERE table_schema = DATABASE()
              AND table_name = 'lead_tractor_guardados'
              AND index_name = 'uq_ltg_lead_proceso'
            """)
        unique_row = cur.fetchone()
        if isinstance(unique_row, dict):
            has_unique = int(unique_row.get("total") or 0) > 0
        else:
            has_unique = bool(unique_row and unique_row[0] > 0)
        if not has_unique:
            # Limpiar duplicados previos por lead+proceso conservando el id más alto.
            cur.execute("""
                DELETE t1
                FROM lead_tractor_guardados t1
                INNER JOIN lead_tractor_guardados t2
                    ON t1.lead_id = t2.lead_id
                   AND COALESCE(NULLIF(LOWER(TRIM(t1.proceso)), ''), '__NULL__') = COALESCE(NULLIF(LOWER(TRIM(t2.proceso)), ''), '__NULL__')
                   AND t1.id < t2.id
                """)
            cur.execute("""
                ALTER TABLE lead_tractor_guardados
                ADD UNIQUE KEY uq_ltg_lead_proceso (lead_id, proceso)
                """)
        mysql.connection.commit()
    finally:
        cur.close()


def _ensure_notificaciones_venta_table():
    cur = mysql.connection.cursor()
    try:
        cur.execute("""
            CREATE TABLE IF NOT EXISTS notificaciones_ventas (
                id INT AUTO_INCREMENT PRIMARY KEY,
                lead_id INT NOT NULL,
                codigo_lead VARCHAR(30) NOT NULL,
                serie_tractor VARCHAR(80) NOT NULL,
                cliente_nombre VARCHAR(180) NULL,
                cliente_documento VARCHAR(60) NULL,
                cliente_telefono VARCHAR(60) NULL,
                cliente_email VARCHAR(150) NULL,
                cliente_direccion VARCHAR(220) NULL,
                departamento VARCHAR(100) NULL,
                provincia VARCHAR(100) NULL,
                distrito VARCHAR(100) NULL,
                bien_servicio VARCHAR(180) NULL,
                cotizacion VARCHAR(30) NULL,
                monto DECIMAL(12, 2) NULL,
                estado_notificacion VARCHAR(20) NOT NULL DEFAULT 'pendiente',
                tractor_estado_actual VARCHAR(30) NULL,
                agente_nombre VARCHAR(120) NULL,
                external_notification_id INT NULL,
                detalle_agente LONGTEXT NULL,
                created_by INT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP ON UPDATE CURRENT_TIMESTAMP,
                resolved_at DATETIME NULL,
                INDEX idx_nv_estado (estado_notificacion),
                INDEX idx_nv_serie (serie_tractor),
                INDEX idx_nv_lead (lead_id)
            ) ENGINE=InnoDB DEFAULT CHARSET=utf8mb4 COLLATE=utf8mb4_unicode_ci
            """)
        mysql.connection.commit()
    finally:
        cur.close()


def _build_postventa_snapshot(lead_id, codigo):
    _ensure_lead_tractor_guardados_table()

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        cur.execute(
            """
            SELECT
                l.id AS lead_id,
                l.codigo AS codigo_lead,
                COALESCE(NULLIF(l.nombre, ''), NULLIF(c.nombre, ''), '') AS cliente_nombre,
                COALESCE(NULLIF(l.ruc_dni, ''), NULLIF(c.ruc_dni, ''), '') AS cliente_documento,
                COALESCE(NULLIF(l.telefono, ''), NULLIF(c.telefono, ''), '') AS cliente_telefono,
                COALESCE(NULLIF(l.email, ''), NULLIF(c.email, ''), '') AS cliente_email,
                COALESCE(NULLIF(l.direccion, ''), NULLIF(c.direccion, ''), '') AS cliente_direccion,
                COALESCE(NULLIF(l.departamento, ''), NULLIF(c.departamento, ''), '') AS departamento,
                COALESCE(NULLIF(l.provincia, ''), NULLIF(c.provincia, ''), '') AS provincia,
                COALESCE(NULLIF(l.distrito, ''), NULLIF(c.distrito, ''), '') AS distrito,
                COALESCE(NULLIF(bs.nombre, ''), '') AS bien_servicio,
                COALESCE(NULLIF(ltg.serie, ''), '') AS tractor_serie,
                COALESCE(NULLIF(ltg.estado, ''), '') AS tractor_estado_guardado,
                COALESCE(NULLIF(su.cotizacion, ''), '') AS cotizacion,
                su.monto AS monto
            FROM leads l
            LEFT JOIN clientes c ON c.id = l.cliente_id
            LEFT JOIN bienes_servicios bs ON bs.id = l.bien_servicio_id
            LEFT JOIN (
                SELECT x.lead_id, x.serie, x.estado, x.equipo, x.modelo
                FROM lead_tractor_guardados x
                INNER JOIN (
                    SELECT lead_id, MAX(id) AS max_id
                    FROM lead_tractor_guardados
                    GROUP BY lead_id
                ) y ON y.max_id = x.id
            ) ltg ON ltg.lead_id = l.id
            LEFT JOIN (
                SELECT s1.lead_id, s1.cotizacion, s1.monto
                FROM seguimientos s1
                INNER JOIN (
                    SELECT lead_id, MAX(id) AS max_id
                    FROM seguimientos
                    GROUP BY lead_id
                ) s2 ON s2.max_id = s1.id
            ) su ON su.lead_id = l.id
            WHERE l.id = %s
              AND l.codigo COLLATE utf8mb4_0900_ai_ci = %s
            LIMIT 1
            """,
            (lead_id, codigo),
        )
        return cur.fetchone()
    finally:
        cur.close()


def _upsert_notificacion_venta(
    snapshot,
    actor_user_id=None,
    external_notification_id=None,
    agente_nombre=None,
    detalle_payload=None,
    correlation_id=None,
):
    _ensure_notificaciones_venta_table()

    estado_notif = "pendiente"
    tractor_estado = (
        snapshot.get("tractor_estado_guardado") or ""
    ).strip().upper() or None

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        cur.execute(
            """
            SELECT id
                        FROM notificaciones_ventas
            WHERE lead_id = %s
              AND serie_tractor COLLATE utf8mb4_0900_ai_ci = %s
              AND estado_notificacion = 'pendiente'
            ORDER BY id DESC
            LIMIT 1
            """,
            (snapshot.get("lead_id"), snapshot.get("tractor_serie")),
        )
        existing = cur.fetchone()

        payload = {"source": "crm", "snapshot": snapshot}
        if correlation_id:
            payload["correlation_id"] = correlation_id
        if detalle_payload is not None:
            payload["agent_detail"] = detalle_payload

        payload_json = json.dumps(payload, ensure_ascii=True)
        external_id = external_notification_id
        agent_name_value = (agente_nombre or "CRMDataQueue").strip() or "CRMDataQueue"

        if existing:
            cur.execute(
                """
                UPDATE notificaciones_ventas
                SET
                    cliente_nombre = %s,
                    cliente_documento = %s,
                    cliente_telefono = %s,
                    cliente_email = %s,
                    cliente_direccion = %s,
                    departamento = %s,
                    provincia = %s,
                    distrito = %s,
                    bien_servicio = %s,
                    cotizacion = %s,
                    monto = %s,
                    estado_notificacion = %s,
                    tractor_estado_actual = %s,
                    agente_nombre = %s,
                    external_notification_id = %s,
                    detalle_agente = %s,
                    resolved_at = NULL,
                    updated_at = NOW()
                WHERE id = %s
                """,
                (
                    snapshot.get("cliente_nombre"),
                    snapshot.get("cliente_documento"),
                    snapshot.get("cliente_telefono"),
                    snapshot.get("cliente_email"),
                    snapshot.get("cliente_direccion"),
                    snapshot.get("departamento"),
                    snapshot.get("provincia"),
                    snapshot.get("distrito"),
                    snapshot.get("bien_servicio"),
                    snapshot.get("cotizacion"),
                    snapshot.get("monto"),
                    estado_notif,
                    tractor_estado or None,
                    agent_name_value,
                    external_id,
                    payload_json,
                    existing.get("id"),
                ),
            )
            notif_id = existing.get("id")
        else:
            cur.execute(
                """
                INSERT INTO notificaciones_ventas
                (
                    lead_id,
                    codigo_lead,
                    serie_tractor,
                    cliente_nombre,
                    cliente_documento,
                    cliente_telefono,
                    cliente_email,
                    cliente_direccion,
                    departamento,
                    provincia,
                    distrito,
                    bien_servicio,
                    cotizacion,
                    monto,
                    estado_notificacion,
                    tractor_estado_actual,
                    agente_nombre,
                    external_notification_id,
                    detalle_agente,
                    created_by,
                    resolved_at
                )
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NULL)
                """,
                (
                    snapshot.get("lead_id"),
                    snapshot.get("codigo_lead"),
                    snapshot.get("tractor_serie"),
                    snapshot.get("cliente_nombre"),
                    snapshot.get("cliente_documento"),
                    snapshot.get("cliente_telefono"),
                    snapshot.get("cliente_email"),
                    snapshot.get("cliente_direccion"),
                    snapshot.get("departamento"),
                    snapshot.get("provincia"),
                    snapshot.get("distrito"),
                    snapshot.get("bien_servicio"),
                    snapshot.get("cotizacion"),
                    snapshot.get("monto"),
                    estado_notif,
                    tractor_estado or None,
                    agent_name_value,
                    external_id,
                    payload_json,
                    actor_user_id,
                ),
            )
            notif_id = cur.lastrowid

        mysql.connection.commit()
        return {
            "id": notif_id,
            "estado_notificacion": estado_notif,
            "tractor_estado_actual": tractor_estado or None,
        }
    except Exception:
        mysql.connection.rollback()
        raise
    finally:
        cur.close()


def _run_postventa_close_flow(lead_id, codigo, actor_user_id=None):
    snapshot = _build_postventa_snapshot(lead_id, codigo)
    if not snapshot:
        return {
            "ok": False,
            "message": "No se encontro el lead para notificacion de venta.",
        }

    serie = (snapshot.get("tractor_serie") or "").strip()
    if not serie:
        return {
            "ok": False,
            "message": "No se encontro serie de tractor guardada para este lead. Guarda primero la serie en Seguimiento.",
        }

    notif_result = _upsert_notificacion_venta(
        snapshot,
        actor_user_id=actor_user_id,
        external_notification_id=None,
        agente_nombre="PostventaSync",
        detalle_payload={
            "ok": True,
            "mode": "direct_sync",
            "message": "Registro directo de postventa (sin orquestacion multiagente).",
        },
        correlation_id=None,
    )

    return {
        "ok": True,
        "message": "Informacion de venta guardada para consumo del sistema de postventa.",
        "notification": notif_result,
        "correlation_id": None,
        "traces": [],
    }


def _extract_serie_payload(payload):
    """
    Soporta respuestas API en formatos: dict directo, {'data': []}, {'results': []} o lista.
    """
    candidates = []

    if isinstance(payload, list):
        candidates = payload
    elif isinstance(payload, dict):
        for key in ("data", "results", "items", "rows"):
            value = payload.get(key)
            if isinstance(value, list):
                candidates = value
                break
        if not candidates:
            candidates = [payload]

    if not candidates:
        return None

    row = candidates[0] if isinstance(candidates[0], dict) else None
    if not row:
        return None

    # Si viene anidado dentro de una clave principal (ej: {"equipo": {...}}), lo aplanamos.
    for key in ("equipo", "tractor", "item"):
        nested = row.get(key)
        if isinstance(nested, dict):
            row = {**row, **nested}

    modelo = (
        row.get("modelo")
        or row.get("model")
        or row.get("modelo_equipo")
        or row.get("model_name")
    )
    equipo = (
        row.get("equipo")
        or row.get("tipo_equipo")
        or row.get("nombre_equipo")
        or row.get("categoria")
        or row.get("clase")
    )
    estado = (
        row.get("estado")
        or row.get("status")
        or row.get("estado_equipo")
        or row.get("estado_actual")
    )
    serie = (
        row.get("serie")
        or row.get("serial")
        or row.get("numero_serie")
        or row.get("serie_equipo")
    )

    return {
        "serie": (serie or "").strip(),
        "equipo": (equipo or "").strip(),
        "modelo": (modelo or "").strip(),
        "estado": (estado or "").strip(),
    }


def _is_cotizado_or_cerrado(proceso_value):
    proceso = _normalize_text(proceso_value or "")
    if not proceso:
        return False
    return proceso == "cotizado" or "cerrad" in proceso


def _proceso_bucket(proceso_value):
    proceso = _normalize_text(proceso_value or "")
    if "cerrad" in proceso:
        return "cerrado"
    if proceso == "cotizado":
        return "cotizado"
    return proceso or None


def _save_tractor_for_lead(
    codigo,
    serie,
    proceso_value,
    actor_user_id=None,
    equipo_hint="",
    modelo_hint="",
    estado_hint="",
):
    serie = (serie or "").strip()
    proceso_guardado = _proceso_bucket(proceso_value)

    if not serie:
        return {"ok": False, "message": "Debe ingresar la serie para guardar."}
    if proceso_guardado not in ("cotizado", "cerrado"):
        return {
            "ok": False,
            "message": "Selecciona proceso Cotizado o Cerrado para guardar la serie.",
        }

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        cur.execute(
            """
            SELECT l.id, l.codigo, b.nombre AS bien_servicio_nombre
            FROM leads l
            LEFT JOIN bienes_servicios b ON b.id = l.bien_servicio_id
            WHERE l.codigo COLLATE utf8mb4_0900_ai_ci = %s
            LIMIT 1
            """,
            (codigo,),
        )
        lead_row = cur.fetchone()
    finally:
        cur.close()

    if not lead_row:
        return {"ok": False, "message": "Lead no encontrado.", "status": 404}
    if not _is_equipo_bien_servicio(lead_row.get("bien_servicio_nombre")):
        return {
            "ok": False,
            "message": "Este lead no corresponde a categoria de equipos.",
            "status": 400,
        }

    tractor_conn = None
    tractor_cur = None
    try:
        tractor_conn = _get_tractor_db_connection()
        tractor_cur = tractor_conn.cursor()
        tractor_cur.execute(
            """
            SELECT serie, estado, situacion, equipo, modelo
            FROM tractor
            WHERE UPPER(TRIM(serie)) = UPPER(TRIM(%s))
            LIMIT 1
            """,
            (serie,),
        )
        tractor_row = tractor_cur.fetchone()
    except Exception:
        return {
            "ok": False,
            "message": "No se pudo validar la serie en la base de tractores.",
            "status": 200,
        }
    finally:
        if tractor_cur:
            tractor_cur.close()
        if tractor_conn:
            tractor_conn.close()

    if not tractor_row:
        return {
            "ok": False,
            "message": "La serie no existe en la tabla tractor.",
            "status": 404,
        }

    estado_actual = (
        (tractor_row.get("estado") or tractor_row.get("situacion") or estado_hint or "")
        .strip()
        .upper()
    )
    if estado_actual != "STOCK":
        return {
            "ok": False,
            "message": f"Solo se puede guardar si el tractor esta en STOCK. Estado actual: {estado_actual or 'SIN ESTADO'}.",
            "status": 400,
        }

    equipo = (tractor_row.get("equipo") or equipo_hint or "").strip()
    modelo = (tractor_row.get("modelo") or modelo_hint or "").strip()
    estado = "STOCK"

    _ensure_lead_tractor_guardados_table()

    save_cur = mysql.connection.cursor()
    try:
        save_cur.execute(
            """
            INSERT INTO lead_tractor_guardados
                (lead_id, codigo_lead, serie, equipo, modelo, estado, proceso, guardado_por)
            VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ON DUPLICATE KEY UPDATE
                codigo_lead = VALUES(codigo_lead),
                serie = VALUES(serie),
                equipo = VALUES(equipo),
                modelo = VALUES(modelo),
                estado = VALUES(estado),
                guardado_por = VALUES(guardado_por),
                updated_at = NOW()
            """,
            (
                lead_row.get("id"),
                lead_row.get("codigo"),
                serie,
                equipo,
                modelo,
                estado,
                proceso_guardado,
                actor_user_id,
            ),
        )
        mysql.connection.commit()
    except Exception:
        mysql.connection.rollback()
        raise
    finally:
        save_cur.close()

    return {
        "ok": True,
        "message": "Datos del tractor guardados en CRM.",
        "serie": serie,
        "equipo": equipo,
        "modelo": modelo,
        "estado": estado,
        "proceso": proceso_guardado,
    }


def _safe_parse_external_payload(response):
    """
    Intenta parsear la respuesta externa en varios formatos comunes.
    """
    try:
        return response.json()
    except ValueError:
        pass

    raw = (response.text or "").strip()
    if not raw:
        return None

    try:
        return json.loads(raw)
    except Exception:
        pass

    # Algunas APIs legacy devuelven dict/list como texto Python.
    if raw.startswith("{") or raw.startswith("["):
        try:
            return ast.literal_eval(raw)
        except Exception:
            return None

    return None


# ----------------------------------------------------------------------
# FUNCIÓN AUXILIAR CENTRALIZADA PARA PAGINACIÓN Y GEO-CARGADO (¡NUEVO!)
# ----------------------------------------------------------------------


def _get_geoloc_maps(leads):
    """
    Carga los nombres de Departamento, Provincia, Distrito
    para los IDs encontrados en la lista de leads.
    """
    dep_ids = set()
    prov_ids = set()
    dist_ids = set()

    for l in leads or []:
        # Lógica de extracción de IDs de tu código original
        try:
            dep_val = (
                l.get("departamento")
                if isinstance(l, dict)
                else getattr(l, "departamento", None)
            )
            prov_val = (
                l.get("provincia")
                if isinstance(l, dict)
                else getattr(l, "provincia", None)
            )
            dist_val = (
                l.get("distrito")
                if isinstance(l, dict)
                else getattr(l, "distrito", None)
            )
        except Exception:
            dep_val = getattr(l, "departamento", None)
            prov_val = getattr(l, "provincia", None)
            dist_val = getattr(l, "distrito", None)

        if dep_val is not None and str(dep_val).strip() != "":
            dep_ids.add(str(dep_val))
        if prov_val is not None and str(prov_val).strip() != "":
            prov_ids.add(str(prov_val))
        if dist_val is not None and str(dist_val).strip() != "":
            dist_ids.add(str(dist_val))

    departamentos_map = {}
    provincias_map = {}
    distritos_map = {}

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        # Lógica para cargar departamentos
        if dep_ids:
            placeholders = ",".join(["%s"] * len(dep_ids))
            cur.execute(
                f"SELECT idDepartamento AS id, departamento AS nombre FROM departamentos WHERE idDepartamento IN ({placeholders})",
                tuple(dep_ids),
            )
            departamentos_map = {
                str(r["id"]): r["nombre"] for r in (cur.fetchall() or [])
            }

        # Lógica para cargar provincias
        if prov_ids:
            placeholders = ",".join(["%s"] * len(prov_ids))
            cur.execute(
                f"SELECT idProvincia AS id, provincia AS nombre FROM provincia WHERE idProvincia IN ({placeholders})",
                tuple(prov_ids),
            )
            provincias_map = {str(r["id"]): r["nombre"] for r in (cur.fetchall() or [])}

        # Lógica para cargar distritos
        if dist_ids:
            placeholders = ",".join(["%s"] * len(dist_ids))
            cur.execute(
                f"SELECT idDistrito AS id, distrito AS nombre FROM distrito WHERE idDistrito IN ({placeholders})",
                tuple(dist_ids),
            )
            distritos_map = {str(r["id"]): r["nombre"] for r in (cur.fetchall() or [])}
    finally:
        cur.close()

    return departamentos_map, provincias_map, distritos_map


def _list_leads_by_status(list_func, template_name):
    """
    Función auxiliar para manejar la lógica de paginación, búsqueda,
    y renderizado para las listas de leads por estado.

    :param list_func: La función del modelo Lead a llamar (ej: Lead.list_unstarted_for_user).
    :param template_name: El nombre de la plantilla a renderizar (ej: "leads/sin_iniciar.html").
    """
    q = (request.args.get("q") or "").strip()
    f_ini = (request.args.get("f_ini") or "").strip() or None
    f_fin = (request.args.get("f_fin") or "").strip() or None
    show_all = request.args.get("show_all") in ("1", "true", "True")
    # Orden (asc / desc) para la columna Fecha. Default: desc (más nuevo → más viejo)
    sort = (request.args.get("sort") or "desc").strip().lower()
    if sort not in ("asc", "desc"):
        sort = "desc"

    # Lógica de Paginación
    try:
        page = int(request.args.get("page", 1))
        if page < 1:
            page = 1
    except (ValueError, TypeError):
        page = 1

    PER_PAGE = 15
    offset = (page - 1) * PER_PAGE

    leads, total = [], 0

    # === INICIO DE LA CORRECCIÓN CLAVE ===
    # 💡 Se construye el diccionario de argumentos condicionalmente.

    # Argumentos comunes a todas las funciones
    kwargs = {
        "id_rol": session["id_rol"],
        "user_id": session["user_id"],
        "q": q,
        "sort": sort,
    }

    # Pasar fechas solo si el list_func las soporta (compatibilidad hacia atrás)
    try:
        sig = inspect.signature(list_func)
        if "start_date" in sig.parameters:
            kwargs["start_date"] = f_ini
        if "end_date" in sig.parameters:
            kwargs["end_date"] = f_fin
    except (TypeError, ValueError):
        # Si no se puede inspeccionar, no enviamos fechas.
        pass

    # Asignar límite/offset de forma condicional para manejar show_all
    if not show_all:
        kwargs["limit"] = PER_PAGE
        kwargs["offset"] = offset
    else:
        # Para show_all, el modelo debe devolver todos, sin limit/offset.
        # Si el modelo tiene valores por defecto para limit/offset, puede que haya que pasar None.
        kwargs["limit"] = None
        kwargs["offset"] = None

    # Llama a la función del modelo
    leads_result = list_func(**kwargs)

    # === FIN DE LA CORRECCIÓN CLAVE ===

    # Procesamiento de resultados
    if isinstance(leads_result, tuple) and len(leads_result) == 2:
        leads, total = leads_result
    elif isinstance(leads_result, list):
        leads = leads_result
        total = len(leads)
    else:
        leads = []
        total = 0

    total = int(total or (len(leads) if leads is not None else 0))

    if show_all:
        total_pages = 1
        page = 1
    else:
        total_pages = max(1, ceil(total / PER_PAGE))  # Usamos ceil importado
        if page > total_pages:
            page = total_pages

    # Cargar los nombres de geolocalización
    departamentos_map, provincias_map, distritos_map = _get_geoloc_maps(leads)
    lead_predictions = prediccion_agente.predict_percentages_for_leads(leads)

    return render_template(
        template_name,
        leads=leads,
        q=q,
        sort=sort,
        total=total,
        f_ini=f_ini,
        f_fin=f_fin,
        page=page,
        total_pages=total_pages,
        per_page=PER_PAGE,
        can_view_assigned=user_can_view_assigned(),
        departamentos_map=departamentos_map,
        provincias_map=provincias_map,
        distritos_map=distritos_map,
        lead_predictions=lead_predictions,
        show_all=show_all,
    )


# Listar leads
@lead_bp.route("/list")
@login_required
def list_leads():
    # ... Tu función list_leads original (SIN CAMBIOS)
    q = (request.args.get("q") or "").strip()
    f_ini = request.args.get("f_ini") or None
    f_fin = request.args.get("f_fin") or None
    show_all = request.args.get("show_all") in ("1", "true", "True")
    # Orden por fecha: 'desc' (por defecto) o 'asc'
    sort = (request.args.get("sort") or "desc").strip().lower()
    if sort not in ("asc", "desc"):
        sort = "desc"

    try:
        page = int(request.args.get("page", 1))
        if page < 1:
            page = 1
    except (ValueError, TypeError):
        page = 1

    PER_PAGE = 15
    offset = (page - 1) * PER_PAGE

    # Si show_all está activo pedimos TODOS los registros (limit=None)
    if show_all:
        if q or f_ini or f_fin:
            leads = Lead.search_for_user(
                session["id_rol"],
                session["user_id"],
                q=q,
                start_date=f_ini,
                end_date=f_fin,
                limit=None,
                offset=None,
                sort=sort,
            )
        else:
            leads = Lead.list_for_user(
                session["id_rol"],
                session["user_id"],
                start_date=f_ini,
                end_date=f_fin,
                limit=None,
                offset=None,
                sort=sort,
            )
        total = len(leads)
        total_pages = 1
        page = 1
    else:
        if q or f_ini or f_fin:
            leads, total = Lead.search_for_user(
                session["id_rol"],
                session["user_id"],
                q=q,
                start_date=f_ini,
                end_date=f_fin,
                limit=PER_PAGE,
                offset=offset,
                sort=sort,
            )
        else:
            leads, total = Lead.list_for_user(
                session["id_rol"],
                session["user_id"],
                start_date=f_ini,
                end_date=f_fin,
                limit=PER_PAGE,
                offset=offset,
                sort=sort,
            )

        total = int(total or (len(leads) if leads is not None else 0))
        total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)

        if page > total_pages:
            page = total_pages

    can_view_assigned = session.get("id_rol") in (ROLE_ADMIN, ROLE_GERENTE, ROLE_RRHH)

    # ========= OPCIÓN 2: solo cargar ids necesarios =========
    departamentos_map, provincias_map, distritos_map = _get_geoloc_maps(leads)
    lead_predictions = prediccion_agente.predict_percentages_for_leads(leads)
    # =======================================================

    return render_template(
        "leads/list.html",
        leads=leads,
        q=q,
        sort=sort,
        total=total,
        f_ini=f_ini,
        f_fin=f_fin,
        page=page,
        total_pages=total_pages,
        per_page=PER_PAGE,
        can_view_assigned=can_view_assigned,
        departamentos_map=departamentos_map,
        provincias_map=provincias_map,
        distritos_map=distritos_map,
        lead_predictions=lead_predictions,
        logged_user_name=session.get("nombre", ""),
        logged_user_username=session.get("username", ""),
    )


# create nuevo lead y jalar el valor del otro lead
@lead_bp.route("/create", methods=["GET", "POST"])
@role_required(ROLE_ADMIN, ROLE_GERENTE, ROLE_RRHH, ROLE_ASESOR)
def create_lead():
    created_by_user_id = session.get("user_id")
    es_asesor = session["id_rol"] == ROLE_ASESOR

    if request.method == "POST":
        codigo = Lead.next_codigo()  # siempre nuevo

        # Validar feria si canal es "Feria"
        canal_id = request.form.get("canal_id")
        feria_id = request.form.get("feria_id", "").strip() or None
        canales_dict = Canal.get_all()

        # Verificar si es canal feria
        is_feria_channel = False
        if canal_id:
            for channel_id, channel_name in (
                canales_dict.items() if isinstance(canales_dict, dict) else []
            ):
                if str(channel_id) == str(canal_id) and "feria" in channel_name.lower():
                    is_feria_channel = True
                    break

        if is_feria_channel and not feria_id:
            flash(
                "⚠️ Cuando selecciona canal 'Feria', debe seleccionar una feria.",
                "warning",
            )
            prefill_data = {
                "nombre": request.form.get("nombre", ""),
                "telefono": request.form.get("telefono", ""),
                "ruc_dni": request.form.get("ruc_dni", ""),
                "contacto": request.form.get("contacto", ""),
                "email": request.form.get("email", ""),
                "direccion": request.form.get("direccion", ""),
                "departamento": request.form.get("departamento", ""),
                "provincia": request.form.get("provincia", ""),
                "distrito": request.form.get("distrito", ""),
                "bien_servicio_id": request.form.get("bien_servicio_id", ""),
                "canal_id": canal_id,
                "comentario": request.form.get("comentario", ""),
                "asignado_a": (
                    created_by_user_id if es_asesor else request.form.get("asignado_a")
                ),
            }
            return render_template(
                "leads/create.html",
                lead_data=prefill_data,
                codigo=codigo,
                fecha_hoy=request.form.get("fecha")
                or date.today().strftime("%Y-%m-%d"),
                canales=canales_dict,
                bienes_servicios=BienServicio.get_all(),
                asesores=(
                    User.get_by_role(ROLE_ASESOR)
                    if not es_asesor
                    else [User.get_by_id(session["user_id"])]
                ),
                es_asesor=es_asesor,
                duplicate_leads=[],
                duplicate_message="",
                show_duplicate_warning=False,
            )

        data = {
            "codigo": codigo,
            "fecha": request.form.get("fecha")
            or date.today().strftime("%Y-%m-%d"),  # 👈 editable
            "nombre": request.form.get("nombre", "").strip(),
            "telefono": request.form.get("telefono", "").strip(),
            "ruc_dni": request.form.get("ruc_dni", "").strip(),
            "email": request.form.get("email", "").strip(),
            "contacto": request.form.get("contacto", "").strip(),
            "direccion": request.form.get("direccion", "").strip(),
            "departamento": request.form.get("departamento", "").strip(),
            "provincia": request.form.get("provincia", "").strip(),
            "distrito": request.form.get("distrito", "").strip(),
            "canal_id": canal_id,
            "bien_servicio_id": request.form.get("bien_servicio_id"),
            "asignado_a": (
                created_by_user_id if es_asesor else request.form.get("asignado_a")
            ),
            "comentario": request.form.get("comentario", "").strip(),
            "feria_id": feria_id,
        }

        force_save = request.form.get("force_save") == "true"

        try:
            Lead.create(
                data, created_by_user_id=created_by_user_id, force_save=force_save
            )
            flash(f"✅ Lead {codigo} creado correctamente.", "lead_created")
            return redirect(url_for("leads.create_lead"))

        except LeadDuplicatedError as e:
            duplicate_leads = e.existing_lead_data or []
            duplicate_field = (
                duplicate_leads[0].get("duplicate_field_used")
                if duplicate_leads
                else ""
            )
            duplicate_message = (
                f"La duplicidad fue detectada usando {duplicate_field} ({data.get(duplicate_field.lower(), '')})."
                if duplicate_field
                else "Se detectó un posible duplicado en los registros."
            )

            flash("⚠️ Se detectó un posible duplicado.", "warning_duplicate")
            return render_template(
                "leads/create.html",
                lead_data=data,
                codigo=codigo,
                fecha_hoy=data["fecha"],
                canales=Canal.get_all(),
                bienes_servicios=BienServicio.get_all(),
                asesores=(
                    User.get_by_role(ROLE_ASESOR)
                    if not es_asesor
                    else [User.get_by_id(session["user_id"])]
                ),
                es_asesor=es_asesor,
                duplicate_leads=duplicate_leads,
                duplicate_message=duplicate_message,
                show_duplicate_warning=True,
            )

        except Exception as e:
            flash(f"❌ Ocurrió un error inesperado: {e}", "danger")
            return render_template(
                "leads/create.html",
                lead_data=data,
                codigo=codigo,
                fecha_hoy=data["fecha"],
                canales=Canal.get_all(),
                bienes_servicios=BienServicio.get_all(),
                asesores=(
                    User.get_by_role(ROLE_ASESOR)
                    if not es_asesor
                    else [User.get_by_id(session["user_id"])]
                ),
                es_asesor=es_asesor,
                duplicate_leads=[],
                duplicate_message="",
                show_duplicate_warning=False,
            )

    # GET: precargar formulario
    # Primero revisamos URL params
    prefill_data = {
        "nombre": request.args.get("nombre", ""),
        "telefono": request.args.get("telefono", ""),
        "ruc_dni": request.args.get("ruc_dni", ""),
        "contacto": request.args.get("contacto", ""),
        "email": request.args.get("email", ""),
        "direccion": request.args.get("direccion", ""),
        "departamento": request.args.get("departamento", ""),
        "provincia": request.args.get("provincia", ""),
        "distrito": request.args.get("distrito", ""),
        "bien_servicio_id": "",  # se llena manual
        "canal_id": "",  # se llena manual
        "comentario": "",  # vacía
        "asignado_a": created_by_user_id if es_asesor else "",
    }

    # Si venimos de un lead existente, jalar sus datos incluyendo departamento/provincia/distrito
    codigo_origen = request.args.get("codigo_origen")
    if codigo_origen:
        lead_origen = Lead.get_by_codigo(codigo_origen)
        if lead_origen:
            prefill_data.update(
                {
                    "nombre": lead_origen.nombre,
                    "telefono": lead_origen.telefono,
                    "ruc_dni": lead_origen.ruc_dni,
                    "contacto": lead_origen.contacto,
                    "email": lead_origen.email,
                    "direccion": lead_origen.direccion,
                    "departamento": lead_origen.departamento_id or "",
                    "provincia": lead_origen.provincia_id or "",
                    "distrito": lead_origen.distrito_id or "",
                    "bien_servicio_id": lead_origen.bien_servicio_id or "",
                    "canal_id": lead_origen.canal_id or "",
                    "comentario": lead_origen.comentario or "",
                    "asignado_a": lead_origen.asignado_a
                    or (created_by_user_id if es_asesor else ""),
                }
            )

    return render_template(
        "leads/create.html",
        lead_data=prefill_data,
        codigo=Lead.next_codigo(),
        fecha_hoy=date.today().strftime("%Y-%m-%d"),
        canales=Canal.get_all(),
        bienes_servicios=BienServicio.get_all(),
        asesores=(
            User.get_by_role(ROLE_ASESOR)
            if not es_asesor
            else [User.get_by_id(session["user_id"])]
        ),
        es_asesor=es_asesor,
        duplicate_leads=[],
        duplicate_message="",
        show_duplicate_warning=False,
    )


# ENCONTRAR DUPLICADO#
@lead_bp.route("/api/duplicates/<value>", methods=["GET"])
@login_required
def api_search_duplicates(value):
    if not value or len(value.strip()) < 1:
        return jsonify([]), 200

    search_val = value.strip()

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        # Usamos una subconsulta para obtener el último seguimiento por lead
        sub_latest = """
            SELECT s1.lead_id, s1.proceso_id, s1.fecha_guardado
            FROM seguimientos s1
            INNER JOIN (
                SELECT lead_id, MAX(id) as max_id
                FROM seguimientos
                GROUP BY lead_id
            ) s2 ON s1.id = s2.max_id AND s1.lead_id = s2.lead_id
        """

        sql = f"""
            SELECT
                l.codigo,
                l.ruc_dni,
                l.telefono,
                p.nombre_proceso AS estado,
                u.nombre AS asignado_a,
                s.fecha_guardado AS ultima_actualizacion
            FROM leads l
            LEFT JOIN ({sub_latest}) s ON s.lead_id = l.id
            LEFT JOIN proceso p ON p.id = s.proceso_id
            LEFT JOIN usuarios u ON u.id = l.asignado_a
            WHERE (l.ruc_dni COLLATE utf8mb4_0900_ai_ci = %s OR l.telefono COLLATE utf8mb4_0900_ai_ci = %s)
            ORDER BY ultima_actualizacion DESC
        """

        cur.execute(sql, (search_val, search_val))
        leads = cur.fetchall() or []

        def format_lead_data(lead):
            return {
                "codigo": lead.get("codigo"),
                "ruc_dni": lead.get("ruc_dni") or "N/A",
                "telefono": lead.get("telefono") or "N/A",
                "estado": lead.get("estado"),
                "asignado_a": lead.get("asignado_a"),
                "ultima_actualizacion": (
                    str(lead.get("ultima_actualizacion")).split(".")[0]
                    if lead.get("ultima_actualizacion")
                    else "N/A"
                ),
            }

        return jsonify([format_lead_data(l) for l in leads]), 200

    except Exception as e:
        print(f"Error en api_search_duplicates: {e}")
        return jsonify({"error": "Error al buscar leads duplicados"}), 500
    finally:
        cur.close()


# API: obtener cliente por RUC/DNI/Teléfono desde tabla `clientes`
@lead_bp.route("/api/cliente/<value>", methods=["GET"])
@login_required
def api_get_cliente(value):
    """Busca en la tabla `clientes` un registro que coincida por ruc, ruc_dni, dni o telefono.
    Devuelve un solo cliente (el primero) con campos comunes para autocompletar el formulario.
    """
    if not value or len(value.strip()) < 1:
        return jsonify({}), 200

    v = value.strip()
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        # La tabla `clientes` de tu esquema contiene columnas: ruc_dni, nombre, direccion,
        # provincia, departamento, distrito, email, telefono, contacto.
        # Buscamos por ruc_dni o telefono.
        sql = """
            SELECT
                id,
                ruc_dni,
                nombre,
                telefono,
                contacto,
                direccion,
                provincia,
                departamento,
                distrito,
                email
            FROM clientes
            WHERE NULLIF(ruc_dni COLLATE utf8mb4_0900_ai_ci, '') = %s
               OR NULLIF(telefono COLLATE utf8mb4_0900_ai_ci, '') = %s
            LIMIT 1
        """
        cur.execute(sql, (v, v))
        row = cur.fetchone()
        if not row:
            return jsonify({}), 404

        # Normalizar salida: convertir claves y retornar
        cliente = {
            "id": row.get("id"),
            "nombre": row.get("nombre"),
            "telefono": row.get("telefono"),
            "contacto": row.get("contacto"),
            "email": row.get("email"),
            "direccion": row.get("direccion"),
            "departamento": row.get("departamento"),
            "provincia": row.get("provincia"),
            "distrito": row.get("distrito"),
            "ruc_dni": row.get("ruc_dni"),
        }
        return jsonify(cliente), 200
    except Exception as e:
        print(f"Error en api_get_cliente: {e}")
        return jsonify({}), 500
    finally:
        cur.close()


@lead_bp.route("/api/equipo-serie/<codigo>", methods=["GET"])
@role_required(ROLE_ADMIN, ROLE_GERENTE, ROLE_RRHH, ROLE_ASESOR)
def api_equipo_por_serie(codigo):
    serie = (request.args.get("serie") or "").strip()
    proceso = _normalize_text(request.args.get("proceso") or "")

    if not serie:
        return jsonify({"ok": False, "message": "Debe ingresar una serie."}), 400
    if not _is_cotizado_or_cerrado(proceso):
        return (
            jsonify(
                {
                    "ok": False,
                    "message": "La consulta por serie solo aplica en Cotizado o Cerrado.",
                }
            ),
            400,
        )

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        cur.execute(
            """
            SELECT l.id, l.codigo, l.bien_servicio_id, b.nombre AS bien_servicio_nombre
            FROM leads l
            LEFT JOIN bienes_servicios b ON b.id = l.bien_servicio_id
            WHERE l.codigo COLLATE utf8mb4_0900_ai_ci = %s
            LIMIT 1
            """,
            (codigo,),
        )
        lead_row = cur.fetchone()
        if not lead_row:
            return jsonify({"ok": False, "message": "Lead no encontrado."}), 404

        if not _is_equipo_bien_servicio(lead_row.get("bien_servicio_nombre")):
            return (
                jsonify(
                    {
                        "ok": False,
                        "message": "Este lead no corresponde a una categoría de equipos.",
                    }
                ),
                400,
            )
    finally:
        cur.close()

    tractor_conn = None
    tractor_cur = None
    try:
        tractor_conn = _get_tractor_db_connection()
        tractor_cur = tractor_conn.cursor()
        tractor_cur.execute(
            """
            SELECT
                serie,
                equipo,
                modelo,
                estado,
                situacion
            FROM tractor
            WHERE UPPER(TRIM(serie)) = UPPER(TRIM(%s))
            LIMIT 1
            """,
            (serie,),
        )
        tractor_row = tractor_cur.fetchone()
    except Exception:
        return (
            jsonify(
                {
                    "ok": False,
                    "message": "No se pudo consultar la base de tractores. Revisa la configuración TRACTOR_DB_*.",
                }
            ),
            200,
        )
    finally:
        if tractor_cur:
            tractor_cur.close()
        if tractor_conn:
            tractor_conn.close()

    if not tractor_row:
        return (
            jsonify(
                {
                    "ok": False,
                    "message": "No se encontró información para esa serie en la tabla tractor.",
                }
            ),
            404,
        )

    equipo = (tractor_row.get("equipo") or "").strip()
    modelo = (tractor_row.get("modelo") or "").strip()
    estado = (tractor_row.get("estado") or tractor_row.get("situacion") or "").strip()

    if not equipo and not modelo and not estado:
        return (
            jsonify(
                {
                    "ok": False,
                    "message": "La tabla tractor no devolvió modelo, equipo ni estado para la serie.",
                }
            ),
            404,
        )

    return (
        jsonify(
            {
                "ok": True,
                "serie": (tractor_row.get("serie") or serie).strip(),
                "equipo": equipo,
                "modelo": modelo,
                "estado": estado,
            }
        ),
        200,
    )


@lead_bp.route("/api/equipo-serie/<codigo>/guardar", methods=["POST"])
@role_required(ROLE_ADMIN, ROLE_GERENTE, ROLE_RRHH, ROLE_ASESOR)
def api_guardar_equipo_por_serie(codigo):
    payload = request.get_json(silent=True) or {}
    serie = (payload.get("serie") or "").strip()
    equipo = (payload.get("equipo") or "").strip()
    modelo = (payload.get("modelo") or "").strip()
    estado = (payload.get("estado") or "").strip()
    proceso = _normalize_text(payload.get("proceso") or "")
    result = _save_tractor_for_lead(
        codigo=codigo,
        serie=serie,
        proceso_value=proceso,
        actor_user_id=session.get("user_id"),
        equipo_hint=equipo,
        modelo_hint=modelo,
        estado_hint=estado,
    )
    return jsonify(result), result.get("status", 200)


@lead_bp.route("/api/tractor-estado/<codigo>", methods=["GET"])
@role_required(ROLE_ADMIN, ROLE_GERENTE, ROLE_RRHH, ROLE_ASESOR)
def api_tractor_estado(codigo):
    serie = (request.args.get("serie") or "").strip()
    proceso = _normalize_text(request.args.get("proceso") or "")

    if not serie:
        return jsonify({"ok": False, "message": "Debe ingresar una serie."}), 400
    if not _is_cotizado_or_cerrado(proceso):
        return (
            jsonify(
                {
                    "ok": False,
                    "message": "El estado del tractor solo aplica en Cotizado o Cerrado.",
                }
            ),
            400,
        )

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        cur.execute(
            """
            SELECT l.id, l.codigo, b.nombre AS bien_servicio_nombre
            FROM leads l
            LEFT JOIN bienes_servicios b ON b.id = l.bien_servicio_id
            WHERE l.codigo COLLATE utf8mb4_0900_ai_ci = %s
            LIMIT 1
            """,
            (codigo,),
        )
        lead_row = cur.fetchone()
    finally:
        cur.close()

    if not lead_row:
        return jsonify({"ok": False, "message": "Lead no encontrado."}), 404

    if not _is_equipo_bien_servicio(lead_row.get("bien_servicio_nombre")):
        return (
            jsonify(
                {
                    "ok": False,
                    "message": "Este lead no corresponde a una categoria de equipos.",
                }
            ),
            400,
        )

    tractor_conn = None
    try:
        tractor_conn = _get_tractor_db_connection()
        agent = TractorStateAgent(tractor_conn)
        result = agent.run(serie)
    except Exception:
        return (
            jsonify(
                {
                    "ok": False,
                    "message": "No se pudo consultar la base de tractores. Revisa la configuracion TRACTOR_DB_*.",
                }
            ),
            200,
        )
    finally:
        if tractor_conn:
            tractor_conn.close()

    if not result.get("ok"):
        return jsonify(result), 404

    return jsonify(result), 200


# ... [El resto de tus APIs y la función notifications_panel siguen aquí] ...


# -------------------------------------------------------
# Helper: registrar cambios de asignación / bien / canal
# -------------------------------------------------------
def _registrar_cambios_lead(
    codigo,
    old_canal_id,
    old_bien_id,
    old_asignado_id,
    new_canal_id,
    new_bien_id,
    new_asignado_id,
    usuario_id,
    usuario_nombre,
):
    """
    Compara los valores anteriores y nuevos de los tres campos rastreados.
    Inserta en lead_cambios solo los campos que realmente cambiaron.
    """

    def _to_int(v):
        try:
            return int(v) if v not in (None, "", "None") else None
        except (ValueError, TypeError):
            return None

    old_canal_id = _to_int(old_canal_id)
    old_bien_id = _to_int(old_bien_id)
    old_asignado_id = _to_int(old_asignado_id)
    new_canal_id = _to_int(new_canal_id)
    new_bien_id = _to_int(new_bien_id)
    new_asignado_id = _to_int(new_asignado_id)

    cambios = []  # list of (campo, valor_anterior_id, valor_nuevo_id)

    if old_canal_id != new_canal_id:
        cambios.append(("canal_id", old_canal_id, new_canal_id))
    if old_bien_id != new_bien_id:
        cambios.append(("bien_servicio_id", old_bien_id, new_bien_id))
    if old_asignado_id != new_asignado_id:
        cambios.append(("asignado_a", old_asignado_id, new_asignado_id))

    if not cambios:
        return

    # Resolver nombres legibles
    def _canal_nombre(cid):
        if cid is None:
            return "—"
        c = Canal.get_by_id(cid)
        return (c.get("nombre") if c else None) or str(cid)

    def _bien_nombre(bid):
        if bid is None:
            return "—"
        b = BienServicio.get_by_id(bid)
        return (b.get("nombre") if b else None) or str(bid)

    def _user_nombre(uid):
        if uid is None:
            return "—"
        u = User.get_by_id(uid)
        if u:
            return getattr(u, "nombre", None) or getattr(u, "usuario", None) or str(uid)
        return str(uid)

    cur = mysql.connection.cursor()
    try:
        cur.execute("SELECT id FROM leads WHERE codigo = %s LIMIT 1", (codigo,))
        row = cur.fetchone()
        if not row:
            return
        lead_id = row[0] if isinstance(row, (tuple, list)) else row.get("id")

        for campo, viejo_id, nuevo_id in cambios:
            if campo == "canal_id":
                viejo_nombre = _canal_nombre(viejo_id)
                nuevo_nombre = _canal_nombre(nuevo_id)
            elif campo == "bien_servicio_id":
                viejo_nombre = _bien_nombre(viejo_id)
                nuevo_nombre = _bien_nombre(nuevo_id)
            else:  # asignado_a
                viejo_nombre = _user_nombre(viejo_id)
                nuevo_nombre = _user_nombre(nuevo_id)

            cur.execute(
                """
                INSERT INTO lead_cambios
                    (lead_id, campo, valor_anterior, valor_nuevo, usuario_id, usuario_nombre, fecha)
                VALUES (%s, %s, %s, %s, %s, %s, NOW())
                """,
                (
                    lead_id,
                    campo,
                    viejo_nombre,
                    nuevo_nombre,
                    usuario_id,
                    usuario_nombre,
                ),
            )
        mysql.connection.commit()
    except Exception:
        mysql.connection.rollback()
    finally:
        cur.close()


# API: historial de cambios de un lead
@lead_bp.route("/api/lead-cambios/<codigo>")
@role_required(ROLE_ADMIN, ROLE_GERENTE, ROLE_RRHH, ROLE_ASESOR)
def api_lead_cambios(codigo):
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        cur.execute("SELECT id FROM leads WHERE codigo = %s LIMIT 1", (codigo,))
        row = cur.fetchone()
        if not row:
            return jsonify([])
        lead_id = row["id"]
        cur.execute(
            """
            SELECT campo, valor_anterior, valor_nuevo, usuario_nombre, fecha
            FROM lead_cambios
            WHERE lead_id = %s
            ORDER BY fecha DESC
            """,
            (lead_id,),
        )
        rows = cur.fetchall()
        result = []
        for r in rows:
            campo_legible = {
                "canal_id": "Canal de recepción",
                "bien_servicio_id": "Bien / Servicio",
                "asignado_a": "Asignación",
            }.get(r["campo"], r["campo"])
            result.append(
                {
                    "campo": campo_legible,
                    "anterior": r["valor_anterior"] or "—",
                    "nuevo": r["valor_nuevo"] or "—",
                    "usuario": r["usuario_nombre"] or "—",
                    "fecha": (
                        r["fecha"].strftime("%d/%m/%Y %H:%M") if r["fecha"] else "—"
                    ),
                }
            )
        return jsonify(result)
    finally:
        cur.close()


# Editar lead
@lead_bp.route("/edit/<codigo>", methods=["GET", "POST"])
@role_required(ROLE_ADMIN, ROLE_GERENTE, ROLE_RRHH, ROLE_ASESOR)
def edit_lead(codigo):
    return_url = _safe_next_url(request.values.get("next"), "leads.list_leads")
    return_label = _lead_return_label(return_url)

    lead = Lead.get_by_codigo(codigo)
    if not lead:
        flash("❌ Lead no encontrado", "danger")
        return redirect(return_url)

    if request.method == "POST":
        # Snapshot de valores anteriores para registrar cambios
        old_lead = lead if isinstance(lead, dict) else lead.__dict__
        old_canal_id = old_lead.get("canal_id")
        old_bien_id = old_lead.get("bien_servicio_id")
        old_asignado_id = old_lead.get("asignado_a")

        data = {
            "codigo": codigo,
            "fecha": request.form.get("fecha") or lead.fecha,  # 👈 Nuevo campo editable
            "nombre": request.form["nombre"],
            "telefono": request.form.get("telefono"),
            "ruc_dni": request.form.get("ruc_dni"),
            "email": request.form.get("email"),
            "contacto": request.form.get("contacto"),
            "direccion": request.form.get("direccion"),
            "departamento": request.form.get("departamento"),
            "provincia": request.form.get("provincia"),
            "distrito": request.form.get("distrito"),
            "canal_id": request.form.get("canal_id"),
            "bien_servicio_id": request.form.get("bien_servicio_id"),
            "asignado_a": (
                session["user_id"]
                if session["id_rol"] == ROLE_ASESOR
                else request.form.get("asignado_a")
            ),
            "comentario": request.form.get("comentario"),
        }
        Lead.update_by_codigo(data)

        # Registrar cambios en lead_cambios (solo asignación, bien/servicio, canal)
        _registrar_cambios_lead(
            codigo=codigo,
            old_canal_id=old_canal_id,
            old_bien_id=old_bien_id,
            old_asignado_id=old_asignado_id,
            new_canal_id=data.get("canal_id"),
            new_bien_id=data.get("bien_servicio_id"),
            new_asignado_id=data.get("asignado_a"),
            usuario_id=session.get("user_id"),
            usuario_nombre=session.get("username"),
        )

        flash("✅ Lead actualizado correctamente.", "success")
        return redirect(url_for("leads.edit_lead", codigo=codigo, next=return_url))

    return render_template(
        "leads/edit.html",
        lead=lead,
        canales=Canal.get_all(),
        bienes_servicios=BienServicio.get_all(),
        asesores=(
            User.get_by_role(ROLE_ASESOR) if session["id_rol"] != ROLE_ASESOR else []
        ),
        es_asesor=(session["id_rol"] == ROLE_ASESOR),
        return_url=return_url,
        return_label=return_label,
    )


# Eliminar lead
@lead_bp.route("/delete/<codigo>", methods=["POST"])
@role_required(ROLE_ADMIN, ROLE_GERENTE, ROLE_RRHH)
def delete_lead(codigo):
    lead = Lead.get_by_codigo(codigo)
    if not lead:
        flash("❌ Lead no encontrado", "danger")
        return redirect(url_for("leads.list_leads"))

    cur = mysql.connection.cursor()
    ventas_deleted = 0
    try:
        # Obtener el id del lead por el código
        cur.execute(
            "SELECT id FROM leads WHERE codigo COLLATE utf8mb4_0900_ai_ci = %s",
            (codigo,),
        )
        lead_row = cur.fetchone()
        if lead_row:
            lead_id = (
                lead_row[0]
                if isinstance(lead_row, (list, tuple))
                else lead_row.get("id")
            )

            # 1. Eliminar ventas_concretadas asociadas primero (si existen)
            cur.execute("DELETE FROM ventas_concretadas WHERE lead_id = %s", (lead_id,))
            ventas_deleted = cur.rowcount

            # 2. Eliminar seguimientos asociados
            cur.execute("DELETE FROM seguimientos WHERE lead_id = %s", (lead_id,))

        # 3. Ahora sí eliminar el lead
        cur.execute(
            "DELETE FROM leads WHERE codigo COLLATE utf8mb4_0900_ai_ci = %s", (codigo,)
        )
        mysql.connection.commit()

        if ventas_deleted > 0:
            flash(
                f"✅ Lead-{codigo} y su venta asociada han sido eliminados exitosamente",
                "success",
            )
        else:
            flash(f"✅ Lead-{codigo} ha sido eliminado exitosamente", "success")

    except Exception as e:
        mysql.connection.rollback()
        flash(f"❌ Error al eliminar el lead: {str(e)}", "danger")
    finally:
        cur.close()

    return redirect(url_for("leads.list_leads"))


# Seguimiento de lead
@lead_bp.route("/seguimiento/<codigo>", methods=["GET", "POST"])
@role_required(ROLE_ADMIN, ROLE_GERENTE, ROLE_RRHH, ROLE_ASESOR)
def seguimiento_lead(codigo):
    return_url = _safe_next_url(request.values.get("next"), "leads.list_leads")
    return_label = _lead_return_label(return_url)

    lead = Lead.get_by_codigo(codigo)
    if not lead:
        flash("❌ Lead no encontrado", "danger")
        return redirect(return_url)

    lead_id = lead["id"]
    usuario_id = lead.get("asignado_a") or session.get("user_id")
    if not usuario_id:
        flash("No se pudo determinar el usuario que registra el seguimiento.", "danger")
        return redirect(
            url_for("leads.seguimiento_lead", codigo=codigo, next=return_url)
        )

    fecha_seguimiento = lead.get("fecha") or date.today().strftime("%Y-%m-%d")

    if request.method == "POST":
        nn = lambda v: (v if v not in ("", None) else None)
        proceso_id = request.form.get("proceso_id", type=int)
        canal_contacto = request.form.get("canal_contacto", type=int)
        comentario = nn(request.form.get("comentario"))
        fecha_programada = nn(request.form.get("fecha_programada"))
        motivo_no_venta_id = request.form.get("motivo_no_venta_id", type=int)
        cotizacion = nn(request.form.get("cotizacion"))
        moneda_id = request.form.get("moneda_id", type=int)
        tractor_serie = nn(request.form.get("serie_equipo_lookup"))
        tractor_equipo = nn(request.form.get("serie_equipo_equipo"))
        tractor_modelo = nn(request.form.get("serie_equipo_modelo"))
        tractor_estado = nn(request.form.get("serie_equipo_estado"))

        monto = None
        monto_raw = nn(request.form.get("monto"))
        if monto_raw is not None:
            try:
                monto = float(monto_raw)
            except ValueError:
                flash("Monto inválido.", "warning")
                return redirect(
                    url_for("leads.seguimiento_lead", codigo=codigo, next=return_url)
                )

        nombre_proceso_seleccionado = ""
        if proceso_id is not None:
            cur_pro = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            try:
                cur_pro.execute(
                    "SELECT nombre_proceso FROM proceso WHERE id = %s LIMIT 1",
                    (proceso_id,),
                )
                row_proc = cur_pro.fetchone()
                nombre_proceso_seleccionado = (
                    row_proc.get("nombre_proceso") if row_proc else ""
                ) or ""
            finally:
                cur_pro.close()

        if tractor_serie and _is_cotizado_or_cerrado(nombre_proceso_seleccionado):
            tractor_result = _save_tractor_for_lead(
                codigo=codigo,
                serie=tractor_serie,
                proceso_value=nombre_proceso_seleccionado,
                actor_user_id=session.get("user_id"),
                equipo_hint=tractor_equipo or "",
                modelo_hint=tractor_modelo or "",
                estado_hint=tractor_estado or "",
            )
            if not tractor_result.get("ok"):
                flash(f"⚠️ {tractor_result.get('message')}", "warning")
                return redirect(
                    url_for("leads.seguimiento_lead", codigo=codigo, next=return_url)
                )

        cur = mysql.connection.cursor()
        try:
            # Insertar seguimiento
            cur.execute(
                """
                INSERT INTO seguimientos
                (lead_id, usuario_id, fecha_seguimiento, proceso_id, fecha_programada,
                 motivo_no_venta_id, cotizacion, monto, moneda_id, comentario,
                 canal_contacto, fecha_guardado)
                VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """,
                (
                    lead_id,
                    usuario_id,
                    fecha_seguimiento,
                    proceso_id,
                    fecha_programada,
                    motivo_no_venta_id,
                    cotizacion,
                    monto,
                    moneda_id,
                    comentario,
                    canal_contacto,
                ),
            )

            # Verificar si es un cierre de venta para mostrar mensaje apropiado
            es_cierre_venta = (
                _is_cotizado_or_cerrado(nombre_proceso_seleccionado)
                and _proceso_bucket(nombre_proceso_seleccionado) == "cerrado"
            )

            mysql.connection.commit()

            postventa_result = None
            if es_cierre_venta:
                try:
                    postventa_result = _run_postventa_close_flow(
                        lead_id=lead_id,
                        codigo=codigo,
                        actor_user_id=session.get("user_id"),
                    )
                except Exception:
                    postventa_result = {
                        "ok": False,
                        "message": "No se pudo notificar a postventa en este momento.",
                    }

            # Mostrar mensaje apropiado
            if es_cierre_venta:
                flash("✅ Venta concretada registrada exitosamente. 🎉", "success")
                if postventa_result and postventa_result.get("ok"):
                    flash(
                        "📌 Datos guardados para que el sistema de postventa los procese.",
                        "info",
                    )
                elif postventa_result and postventa_result.get("message"):
                    flash(f"⚠️ {postventa_result.get('message')}", "warning")
            else:
                flash("✅ Seguimiento guardado.", "success")
        except IntegrityError as e:
            if "uq_cotizacion" in str(e).lower() or "cotizacion" in str(e).lower():
                flash(
                    "⚠️ El código de cotización ya existe. Ingresa uno diferente.",
                    "danger",
                )
            else:
                flash("❌ Error al guardar el seguimiento.", "danger")
        finally:
            cur.close()

        return redirect(
            url_for("leads.seguimiento_lead", codigo=codigo, next=return_url)
        )

    # Cargar catálogos
    procesos = Proceso.get_all()
    canales = CanalContacto.get_all()
    monedas = Moneda.get_all()
    motivos = Motivonoventa.get_all()
    bienes = BienServicio.get_all()

    # Diccionarios de mapeo
    proc_map = {
        (p["id"] if isinstance(p, dict) else p.id): (
            p["nombre_proceso"] if isinstance(p, dict) else p.nombre_proceso
        )
        for p in procesos
    }

    mone_map = {
        (m["id"] if isinstance(m, dict) else m.id): (
            m["nombre_moneda"] if isinstance(m, dict) else m.nombre_moneda
        )
        for m in monedas
    }

    bs_map = {
        (b["id"] if isinstance(b, dict) else b.id): (
            b["nombre"] if isinstance(b, dict) else b.nombre
        )
        for b in bienes
    }

    bien_servicio_nombre = bs_map.get(
        lead.get("bien_servicio_id") or lead.get("bien_servicio")
    )
    puede_consultar_equipo = _is_equipo_bien_servicio(bien_servicio_nombre)
    lead_nombre = (
        lead.get("nombre")
        or lead.get("nombre_completo")
        or lead.get("razon_social")
        or ""
    )
    lead_contacto = lead.get("contacto") or lead.get("persona_contacto") or ""

    # Último tractor guardado para este lead
    tractor_guardado = None
    if puede_consultar_equipo:
        try:
            cur_tg = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
            cur_tg.execute(
                "SELECT serie, equipo, modelo, estado FROM lead_tractor_guardados "
                "WHERE lead_id=%s ORDER BY updated_at DESC, id DESC LIMIT 1",
                (lead_id,),
            )
            tractor_guardado = cur_tg.fetchone()
            cur_tg.close()
        except Exception:
            tractor_guardado = None

    # Obtener seguimientos con nombre de moneda incluido
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute(
        """
        SELECT 
            s.*,
            m.nombre_moneda AS moneda_nombre
        FROM seguimientos s
        LEFT JOIN moneda m ON s.moneda_id = m.id
        WHERE s.lead_id = %s
        ORDER BY s.fecha_guardado DESC, s.id DESC
    """,
        (lead_id,),
    )
    seguimientos = cur.fetchall()
    ultimo = seguimientos[0] if seguimientos else None
    cur.close()

    # Procesos por defecto
    preset = (request.args.get("preset") or "").strip().lower()
    preset_map = {
        "no_iniciado": "no iniciado",
        "seguimiento": "seguimiento",
        "programado": "programado",
        "cotizado": "cotizado",
        "cerrado": "cerrado",
        "cerrado_no_vendido": "cerrado no vendido",
    }

    default_proceso_id = None
    hay_ultimo = bool(ultimo and (ultimo.get("proceso_id") is not None))
    hay_post = False

    if not hay_ultimo and not hay_post:
        target_name = preset_map.get(preset)
        if target_name:
            for p in procesos:
                pname = (
                    p["nombre_proceso"] if isinstance(p, dict) else p.nombre_proceso
                ) or ""
                if pname.strip().lower() == target_name:
                    default_proceso_id = p["id"] if isinstance(p, dict) else p.id
                    break

    cerrado_id = None
    for p in procesos:
        pname = (p["nombre_proceso"] if isinstance(p, dict) else p.nombre_proceso) or ""
        if pname.strip().lower() == "cerrado":
            cerrado_id = p["id"] if isinstance(p, dict) else p.id
            break

    lock_proceso = bool(ultimo and (ultimo.get("proceso_id") == cerrado_id))

    return render_template(
        "leads/seguimiento.html",
        lead=lead,
        procesos=procesos,
        canales=canales,
        monedas=monedas,
        mone_map=mone_map,
        motivos=motivos,
        seguimientos=seguimientos,
        ultimo=ultimo,
        proc_map=proc_map,
        bien_servicio_nombre=bien_servicio_nombre,
        lead_nombre=lead_nombre,
        lead_contacto=lead_contacto,
        date=date,
        default_proceso_id=default_proceso_id,
        lock_proceso=lock_proceso,
        puede_consultar_equipo=puede_consultar_equipo,
        tractor_guardado=tractor_guardado,
        return_url=return_url,
        return_label=return_label,
    )


# --- RUTAS DE LISTAS POR ESTADO CON PAGINACIÓN Y BÚSQUEDA (MODIFICADAS) ---


@lead_bp.route("/sin-iniciar")
@login_required
def list_unstarted():
    return _list_leads_by_status(Lead.list_unstarted_for_user, "leads/sin_iniciar.html")


@lead_bp.route("/en-seguimiento")
@login_required
def list_in_followup():
    return _list_leads_by_status(
        Lead.list_in_followup_for_user, "leads/seguimiento_sidebar.html"
    )


@lead_bp.route("/programados")
@login_required
def list_programmed():
    return _list_leads_by_status(
        Lead.list_programmed_for_user, "leads/programados.html"
    )


@lead_bp.route("/cotizados")
@login_required
def list_quoted():
    return _list_leads_by_status(Lead.list_quoted_for_user, "leads/cotizados.html")


@lead_bp.route("/cerrados")
@login_required
def list_closed():
    return _list_leads_by_status(Lead.list_closed_for_user, "leads/cerrados.html")


@lead_bp.route("/cerrados-no-vendidos")
@login_required
def list_closed_lost():
    return _list_leads_by_status(
        Lead.list_closed_lost_for_user, "leads/cerrados_no_vendidos.html"
    )


# ... [APIs y Notificaciones] ...
# Estas funciones se mantienen sin cambios.

# API: listar departamentos


@lead_bp.route("/api/departamentos", methods=["GET"])
def api_list_departamentos():
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        cur.execute(
            "SELECT idDepartamento, departamento FROM departamentos ORDER BY departamento"
        )
        rows = cur.fetchall() or []
        return (
            jsonify(
                [{"id": r["idDepartamento"], "nombre": r["departamento"]} for r in rows]
            ),
            200,
        )
    except Exception as e:
        # ¡AÑADÍ ESTA LÍNEA CRÍTICA DE DEBUGGING!
        print(f"ERROR DE CONEXIÓN O CONSULTA A LA BASE DE DATOS: {e}")
        # Devolvemos el error real para verlo en la pestaña Network del navegador.
        return jsonify({"error": f"Error de DB: {e}"}), 500
    finally:
        cur.close()


# API: provincias por departamento (por idDepartamento)
@lead_bp.route("/api/provincias/<int:departamento_id>", methods=["GET"])
def api_provincias_by_dep(departamento_id):
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        # columnas reales: idProvincia, provincia, idDepartamento (clave foránea)
        cur.execute(
            "SELECT idProvincia, provincia FROM provincia WHERE idDepartamento = %s ORDER BY provincia",
            (departamento_id,),
        )
        rows = cur.fetchall() or []
        return (
            jsonify([{"id": r["idProvincia"], "nombre": r["provincia"]} for r in rows]),
            200,
        )
    except Exception as e:
        # opcional: print(e)
        return jsonify({"error": "No se pudo obtener provincias"}), 500
    finally:
        cur.close()


# API: distritos por provincia (por idProvincia)
@lead_bp.route("/api/distritos/<int:provincia_id>", methods=["GET"])
def api_distritos_by_prov(provincia_id):
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        # columnas reales: idDistrito, distrito, idProvincia
        cur.execute(
            "SELECT idDistrito, distrito FROM distrito WHERE idProvincia = %s ORDER BY distrito",
            (provincia_id,),
        )
        rows = cur.fetchall() or []
        return (
            jsonify([{"id": r["idDistrito"], "nombre": r["distrito"]} for r in rows]),
            200,
        )
    except Exception as e:
        # opcional: print(e)
        return jsonify({"error": "No se pudo obtener distritos"}), 500
    finally:
        cur.close()


# API: ferias activas en un rango de fechas
@lead_bp.route("/api/ferias-activas", methods=["GET"])
@login_required
def api_ferias_activas():
    """
    Endpoint para obtener ferias activas en un rango de fechas.
    Parámetros query:
    - fecha_inicio: YYYY-MM-DD (inicio del rango)
    - fecha_fin: YYYY-MM-DD (fin del rango)

    Returns: JSON list of { id, nombre, fecha_inicio, fecha_fin }
    """
    try:
        fecha_inicio = request.args.get("fecha_inicio", "").strip()
        fecha_fin = request.args.get("fecha_fin", "").strip()

        if not fecha_inicio or not fecha_fin:
            return jsonify([]), 200

        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            cur.execute("""
                SELECT COUNT(*) AS total
                FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = DATABASE() AND TABLE_NAME = 'marketing_ferias'
                """)
            exists = cur.fetchone() or {}
            if int(exists.get("total") or 0) == 0:
                return jsonify([]), 200

            sql = """
                SELECT id, nombre, fecha_inicio, fecha_fin
                FROM marketing_ferias
                WHERE activo = 1
                  AND fecha_inicio <= %s
                  AND fecha_fin >= %s
                ORDER BY fecha_inicio ASC, nombre ASC
            """
            cur.execute(sql, (fecha_fin, fecha_inicio))
            ferias = cur.fetchall() or []

            # Si la tabla de ferias está vacía, sincroniza automáticamente
            # con campañas de canal Feria para no depender de carga manual inicial.
            if not ferias:
                try:
                    cur.execute("""
                        INSERT IGNORE INTO marketing_ferias (nombre, fecha_inicio, fecha_fin, activo)
                        SELECT
                            TRIM(nombre_campana) AS nombre,
                            MIN(periodo_inicio) AS fecha_inicio,
                            MAX(periodo_fin) AS fecha_fin,
                            1 AS activo
                        FROM marketing_campaigns
                        WHERE LOWER(TRIM(canal)) = 'feria'
                          AND nombre_campana IS NOT NULL
                          AND TRIM(nombre_campana) <> ''
                        GROUP BY TRIM(nombre_campana)
                        """)
                    mysql.connection.commit()
                    cur.execute(sql, (fecha_fin, fecha_inicio))
                    ferias = cur.fetchall() or []
                except Exception:
                    mysql.connection.rollback()

            return (
                jsonify(
                    [
                        {
                            "id": f["id"],
                            "nombre": f["nombre"],
                            "fecha_inicio": str(f["fecha_inicio"]),
                            "fecha_fin": str(f["fecha_fin"]),
                        }
                        for f in ferias
                    ]
                ),
                200,
            )
        finally:
            cur.close()
    except Exception as e:
        print(f"Error en api_ferias_activas: {e}")
        return jsonify({"error": "Error al obtener ferias activas"}), 500


# Endpoint: devuelve programadas para hoy (filtradas por asignado si es ASESOR)
@lead_bp.route("/notifications/panel", methods=["GET"])
def notifications_panel():
    """
    Endpoint JSON para el panel de notificaciones.
    - 'programadas': leads cuyo último seguimiento es 'programado' y fecha_programada = hoy.
      * Si el usuario es ASESOR, se restringe a leads relacionados con él (asignado_a = user_id OR su.usuario_id = user_id).
      * Si es ADMIN/GERENTE/RRHH, se devuelven todas las programadas para hoy.
    - 'sin_iniciar': solo se devuelve si el usuario es ASESOR; para otros roles devuelve lista vacía.
    """
    user_id = session.get("user_id")
    user_role = session.get("id_rol")
    from datetime import date

    hoy = date.today().strftime("%Y-%m-%d")

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        # 1) PROGRAMADAS PARA HOY (tomando el último seguimiento por lead)
        base_sql = """
            SELECT l.id, l.codigo, l.nombre, su.fecha_programada, su.usuario_id, u.nombre AS usuario_nombre
            FROM leads l
            JOIN (
              SELECT s1.lead_id, s1.id AS last_id
              FROM seguimientos s1
              LEFT JOIN seguimientos s2
                ON s2.lead_id = s1.lead_id
               AND (s2.fecha_guardado > s1.fecha_guardado OR (s2.fecha_guardado = s1.fecha_guardado AND s2.id > s1.id))
              WHERE s2.id IS NULL
            ) last ON last.lead_id = l.id
            JOIN seguimientos su ON su.id = last.last_id
            JOIN proceso p ON p.id = su.proceso_id
            LEFT JOIN usuarios u ON u.id = su.usuario_id
            WHERE LOWER(TRIM(p.nombre_proceso)) = 'programado'
              AND DATE(su.fecha_programada) = %s
        """
        params = [hoy]

        # Asesores ven solo sus programadas; roles superiores ven todas
        if user_role == ROLE_ASESOR:
            base_sql += " AND (l.asignado_a = %s OR su.usuario_id = %s)"
            params.extend([user_id, user_id])

        base_sql += " ORDER BY su.fecha_programada ASC, l.id DESC"
        cur.execute(base_sql, params)
        programadas = cur.fetchall() or []

        # 2) SIN INICIAR: **solo** para ASESORES (otros roles no reciben esta lista)
        sin_iniciar = []
        if user_role == ROLE_ASESOR:
            sin_sql = """
                SELECT l.id, l.codigo, l.nombre, l.fecha, u.nombre AS usuario_nombre
                FROM leads l
                JOIN (
                  SELECT s1.lead_id, s1.id AS last_id
                  FROM seguimientos s1
                  LEFT JOIN seguimientos s2
                    ON s2.lead_id = s1.lead_id
                   AND (s2.fecha_guardado > s1.fecha_guardado OR (s2.fecha_guardado = s1.fecha_guardado AND s2.id > s1.id))
                  WHERE s2.id IS NULL
                ) last ON last.lead_id = l.id
                JOIN seguimientos su ON su.id = last.last_id
                JOIN proceso p ON p.id = su.proceso_id
                LEFT JOIN usuarios u ON u.id = l.asignado_a
                WHERE LOWER(TRIM(p.nombre_proceso)) = 'no iniciado'
                  AND l.asignado_a = %s
                ORDER BY su.fecha_guardado DESC, l.id DESC
            """
            cur.execute(sin_sql, (user_id,))
            sin_iniciar = cur.fetchall() or []

        # Normalizar la salida (convertir fechas a string cuando aplique)
        def normalize(rows, date_field=None):
            out = []
            for r in rows:
                item = {
                    "id": r.get("id"),
                    "codigo": r.get("codigo"),
                    "nombre": r.get("nombre"),
                    "usuario_nombre": r.get("usuario_nombre") or "Sin asignar",
                }
                if date_field and r.get(date_field) is not None:
                    item[date_field] = str(r.get(date_field))
                out.append(item)
            return out

        return (
            jsonify(
                {
                    "programadas": normalize(programadas, "fecha_programada"),
                    "sin_iniciar": normalize(sin_iniciar, None),
                }
            ),
            200,
        )

    except Exception as e:
        # Puedes habilitar un print para debug temporalmente:
        # print("notifications_panel error:", e)
        return jsonify({"error": "No se pudo obtener notificaciones"}), 500
    finally:
        cur.close()
