from flask import Blueprint, render_template, request, redirect, url_for, session, flash, jsonify, Response
from utils.security import login_required, role_required, ROLE_ADMIN, ROLE_GERENTE, ROLE_RRHH, ROLE_ASESOR
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
matplotlib.use("Agg") # backend sin ventana para servidores
import matplotlib.pyplot as plt
from math import ceil
from models.canal_contacto import CanalContacto
from functools import wraps


# Blueprint principal de leads (namespace 'leads')
lead_bp = Blueprint("leads", __name__)


# --- helper permiso columna "Asignado a" ---
def user_can_view_assigned():
    """
    Devuelve True si el rol actual puede ver la columna 'Asignado a'.
    Roles permitidos: ADMIN, GERENTE, RRHH
    """
    return session.get("id_rol") in (ROLE_ADMIN, ROLE_GERENTE, ROLE_RRHH)


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
    
    for l in (leads or []):
        # Lógica de extracción de IDs de tu código original
        try:
            dep_val = l.get("departamento") if isinstance(l, dict) else getattr(l, "departamento", None)
            prov_val = l.get("provincia") if isinstance(l, dict) else getattr(l, "provincia", None)
            dist_val = l.get("distrito") if isinstance(l, dict) else getattr(l, "distrito", None)
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
                tuple(dep_ids)
            )
            departamentos_map = { str(r["id"]): r["nombre"] for r in (cur.fetchall() or []) }

        # Lógica para cargar provincias
        if prov_ids:
            placeholders = ",".join(["%s"] * len(prov_ids))
            cur.execute(
                f"SELECT idProvincia AS id, provincia AS nombre FROM provincia WHERE idProvincia IN ({placeholders})",
                tuple(prov_ids)
            )
            provincias_map = { str(r["id"]): r["nombre"] for r in (cur.fetchall() or []) }

        # Lógica para cargar distritos
        if dist_ids:
            placeholders = ",".join(["%s"] * len(dist_ids))
            cur.execute(
                f"SELECT idDistrito AS id, distrito AS nombre FROM distrito WHERE idDistrito IN ({placeholders})",
                tuple(dist_ids)
            )
            distritos_map = { str(r["id"]): r["nombre"] for r in (cur.fetchall() or []) }
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
    f_ini = request.args.get("f_ini") or None
    f_fin = request.args.get("f_fin") or None
    show_all = (request.args.get("show_all") in ('1','true','True'))

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
        'id_rol': session["id_rol"],
        'user_id': session["user_id"],
        'q': q,
    }

    # Asumimos que Lead.search_for_user es la única que soporta f_ini/f_fin.
    # Si la función es *diferente* a Lead.search_for_user (es decir, una de estado),
    # NO añadimos start_date ni end_date.

    # Solo las funciones de lista general o búsqueda (list_for_user, search_for_user)
    # deberían recibir fechas. Las de estado (unstarted, quoted) no.
    if hasattr(list_func, '__name__') and ('search_for_user' in list_func.__name__ or 'list_for_user' in list_func.__name__):
          kwargs['start_date'] = f_ini
          kwargs['end_date'] = f_fin
    
    # Asignar límite/offset de forma condicional para manejar show_all
    if not show_all:
        kwargs['limit'] = PER_PAGE
        kwargs['offset'] = offset
    else:
        # Para show_all, el modelo debe devolver todos, sin limit/offset.
        # Si el modelo tiene valores por defecto para limit/offset, puede que haya que pasar None.
        kwargs['limit'] = None
        kwargs['offset'] = None


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
        total_pages = max(1, ceil(total / PER_PAGE)) # Usamos ceil importado
        if page > total_pages:
            page = total_pages
        
    # Cargar los nombres de geolocalización
    departamentos_map, provincias_map, distritos_map = _get_geoloc_maps(leads)


    return render_template(
        template_name,
        leads=leads,
        q=q,
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
        show_all=show_all
    )



# Listar leads
@lead_bp.route("/list")
@login_required
def list_leads():
    # ... Tu función list_leads original (SIN CAMBIOS)
    q = (request.args.get("q") or "").strip()
    f_ini = request.args.get("f_ini") or None
    f_fin = request.args.get("f_fin") or None
    show_all = (request.args.get("show_all") in ('1','true','True'))

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
                offset=None
            )
        else:
            leads = Lead.list_for_user(
                session["id_rol"],
                session["user_id"],
                start_date=f_ini,
                end_date=f_fin,
                limit=None,
                offset=None
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
                offset=offset
            )
        else:
            leads, total = Lead.list_for_user(
                session["id_rol"],
                session["user_id"],
                start_date=f_ini,
                end_date=f_fin,
                limit=PER_PAGE,
                offset=offset
            )

        total = int(total or (len(leads) if leads is not None else 0))
        total_pages = max(1, (total + PER_PAGE - 1) // PER_PAGE)

        if page > total_pages:
            page = total_pages

    can_view_assigned = session.get("id_rol") in (ROLE_ADMIN, ROLE_GERENTE, ROLE_RRHH)

    # ========= OPCIÓN 2: solo cargar ids necesarios =========
    departamentos_map, provincias_map, distritos_map = _get_geoloc_maps(leads)
    # =======================================================

    return render_template(
        "leads/list.html",
        leads=leads,
        q=q,
        total=total,
        f_ini=f_ini,
        f_fin=f_fin,
        page=page,
        total_pages=total_pages,
        per_page=PER_PAGE,
        can_view_assigned=can_view_assigned,
        departamentos_map=departamentos_map,
        provincias_map=provincias_map,
        distritos_map=distritos_map
    )

# ... [edit_lead, delete_lead, seguimiento_lead] ...
# Crear lead (MODIFICADA para manejar LeadDuplicatedError Y force_save)
# --- RUTA DE CREACIÓN DE LEAD (CORREGIDA PARA MANEJAR LeadDuplicatedError) ---
# --- RUTA DE CREACIÓN DE LEAD (CORREGIDA PARA MANEJAR LeadDuplicatedError Y UndefinedError) ---
@lead_bp.route("/create", methods=["GET", "POST"])
@role_required(ROLE_ADMIN, ROLE_GERENTE, ROLE_RRHH, ROLE_ASESOR)
def create_lead():
    
    # ----------------------------------------------------------------------
    # 1. Bloque POST (El usuario intenta crear un Lead)
    # ----------------------------------------------------------------------
    if request.method == "POST":
        codigo = Lead.next_codigo()
        created_by_user_id = session.get("user_id")
        
        # Recolección de datos del formulario (para usar en repoblación si falla)
        data = {
            "codigo": codigo,
            "fecha": request.form.get("fecha") or date.today().strftime("%Y-%m-%d"), 
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
            "asignado_a": (created_by_user_id if session["id_rol"] == ROLE_ASESOR else request.form.get("asignado_a")),
            "comentario": request.form.get("comentario"),
        }
        
        force_save = request.form.get("force_save") == 'true'

        try:
            Lead.create(data, created_by_user_id=created_by_user_id, force_save=force_save)
            
            flash(f"✅ Lead {codigo} creado correctamente. ¿Qué deseas hacer ahora?", "lead_created") 
            
            return redirect(url_for("leads.create_lead"))

        except LeadDuplicatedError as e:
            # Lógica de manejo de duplicados (ya corregida)
            duplicate_leads = e.existing_lead_data
            lead_data_first = duplicate_leads[0] if duplicate_leads else {}
            duplicate_field = lead_data_first.get('duplicate_field_used') 
            
            if duplicate_field == 'DNI/RUC':
                duplicate_message = f"La duplicidad fue detectada usando DNI/RUC ({data.get('ruc_dni')})."
            elif duplicate_field == 'Teléfono':
                duplicate_message = f"La duplicidad fue detectada usando Teléfono ({data.get('telefono')})."
            else:
                duplicate_message = "La duplicidad fue detectada, pero el campo de coincidencia es desconocido."

            flash(f"⚠️ {e.args[0]}", "warning_duplicate") 
            
            # Recargar datos de selección para repoblar el formulario
            canales = Canal.get_all()
            bienes_servicios = BienServicio.get_all()
            asesores = User.get_by_role(ROLE_ASESOR) if session["id_rol"] != ROLE_ASESOR else [User.get_by_id(session["user_id"])]
            
            # 5. Renderizamos el formulario, pasando TODOS los datos necesarios
            return render_template(
                "leads/create.html",
                # PASAMOS LOS DATOS INGRESADOS para repoblar el formulario (data)
                lead_data=data,  
                
                duplicate_leads=duplicate_leads,
                duplicate_message=duplicate_message,
                show_duplicate_warning=True,
                
                # Datos de selección necesarios
                codigo=data.get("codigo"),
                fecha_hoy=data.get("fecha") or date.today().strftime("%Y-%m-%d"),
                canales=canales,
                bienes_servicios=bienes_servicios,
                asesores=asesores,
                es_asesor=(session["id_rol"] == ROLE_ASESOR),
            )
        
        except Exception as e:
            flash(f"❌ Ocurrió un error inesperado al crear el Lead: {e}", "danger")
            # En caso de otro error, pasamos 'data' para que los campos no se borren
            return render_template(
                "leads/create.html",
                lead_data=data,
                codigo=data.get("codigo"),
                fecha_hoy=data.get("fecha") or date.today().strftime("%Y-%m-%d"),
                canales=Canal.get_all(),
                bienes_servicios=BienServicio.get_all(),
                asesores=( User.get_by_role(ROLE_ASESOR) if session["id_rol"] != ROLE_ASESOR else [User.get_by_id(session["user_id"])] ),
                es_asesor=(session["id_rol"] == ROLE_ASESOR),
                # Variables de duplicado vacías para evitar UndefinedError
                duplicate_leads=[], 
                duplicate_message="",
                show_duplicate_warning=False,
            )
    
    # ----------------------------------------------------------------------
    # 2. Bloque GET (Carga inicial del formulario)
    # ----------------------------------------------------------------------
    
    # PASAMOS lead_data como un DICCIONARIO VACÍO.
    # Esto evita el Jinja2 UndefinedError en la carga inicial (GET).
    return render_template(
        "leads/create.html",
        lead_data={}, # <--- CORRECCIÓN CLAVE
        codigo=Lead.next_codigo(),
        fecha_hoy=date.today().strftime("%Y-%m-%d"),
        canales=Canal.get_all(),
        bienes_servicios=BienServicio.get_all(),
        asesores=( User.get_by_role(ROLE_ASESOR) if session["id_rol"] != ROLE_ASESOR else [User.get_by_id(session["user_id"])] ),
        es_asesor=(session["id_rol"] == ROLE_ASESOR),
        
        # Variables de duplicado vacías para evitar UndefinedError
        duplicate_leads=[], 
        duplicate_message="",
        show_duplicate_warning=False,
    )

# API: Busca todos los leads duplicados por DNI/RUC o Teléfono (¡NUEVA RUTA!)
@lead_bp.route("/api/duplicates/<value>", methods=["GET"])
@login_required
def api_search_duplicates(value):
    """
    Busca leads que coincidan con el DNI/RUC o Teléfono proporcionado en 'value'.
    Devuelve una lista JSON de leads con campos clave para el modal.
    """
    if not value or len(value.strip()) < 1:
        return jsonify([]), 200

    search_val = value.strip()
    
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        # Se asume que el 'value' puede ser DNI/RUC o Teléfono. Buscamos por ambos.
        # Solo trae los datos necesarios para la tabla del modal.
        sql = """
            SELECT 
                l.codigo, 
                p.nombre_proceso AS estado, 
                u.nombre AS asignado_a,
                MAX(s.fecha_guardado) AS ultima_actualizacion
            FROM leads l
            JOIN usuarios u ON u.id = l.asignado_a
            JOIN seguimientos s ON s.lead_id = l.id
            JOIN proceso p ON p.id = s.proceso_id
            WHERE 
                l.ruc_dni = %s OR l.telefono = %s
            GROUP BY l.id
            ORDER BY ultima_actualizacion DESC
        """
        cur.execute(sql, (search_val, search_val))
        leads = cur.fetchall() or []
        
        # Formatear la fecha para que sea más legible en JavaScript
        def format_lead_data(lead):
            return {
                "codigo": lead["codigo"],
                "estado": lead["estado"],
                "asignado_a": lead["asignado_a"],
                "ultima_actualizacion": str(lead["ultima_actualizacion"]).split('.')[0] if lead["ultima_actualizacion"] else "N/A"
            }
            
        return jsonify([format_lead_data(l) for l in leads]), 200
    
    except Exception as e:
        print(f"Error en api_search_duplicates: {e}")
        return jsonify({"error": "Error al buscar leads duplicados"}), 500
    finally:
        cur.close()

# ... [El resto de tus APIs y la función notifications_panel siguen aquí] ...

# Editar lead
@lead_bp.route("/edit/<codigo>", methods=["GET", "POST"])
@role_required(ROLE_ADMIN, ROLE_GERENTE, ROLE_RRHH, ROLE_ASESOR)
def edit_lead(codigo):
    lead = Lead.get_by_codigo(codigo)
    if not lead:
        flash("❌ Lead no encontrado", "danger")
        return redirect(url_for("leads.list_leads"))

    if request.method == "POST":
        data = {
            "codigo": codigo,
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
            "asignado_a": (session["user_id"] if session["id_rol"] == ROLE_ASESOR else request.form.get("asignado_a")),
            "comentario": request.form.get("comentario"),
        }
        Lead.update_by_codigo(data)
        flash("✅ Lead actualizado correctamente.", "success")
        # Redirige a la misma vista de edición para permanecer en la página edit
        return redirect(url_for("leads.edit_lead", codigo=codigo))

    return render_template(
        "leads/edit.html",
        lead=lead,
        canales=Canal.get_all(),
        bienes_servicios=BienServicio.get_all(),
        asesores=User.get_by_role(ROLE_ASESOR) if session["id_rol"] != ROLE_ASESOR else [],
        es_asesor=(session["id_rol"] == ROLE_ASESOR),
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
    cur.execute("DELETE FROM leads WHERE codigo = %s", (codigo,))
    mysql.connection.commit()
    cur.close()

    flash("🗑️ Lead eliminado correctamente", "success")
    return redirect(url_for("leads.list_leads"))

# Seguimiento de lead
@lead_bp.route("/seguimiento/<codigo>", methods=["GET", "POST"])
@role_required(ROLE_ADMIN, ROLE_GERENTE, ROLE_RRHH, ROLE_ASESOR)
def seguimiento_lead(codigo):
    lead = Lead.get_by_codigo(codigo)
    if not lead:
        flash("❌ Lead no encontrado", "danger")
        return redirect(url_for("leads.list_leads"))

    lead_id = lead["id"]
    usuario_id = lead.get("asignado_a") or session.get("user_id")
    if not usuario_id:
        flash("No se pudo determinar el usuario que registra el seguimiento.", "danger")
        return redirect(url_for("leads.seguimiento_lead", codigo=codigo))

    fecha_seguimiento = lead.get("fecha") or date.today().strftime("%Y-%m-%d")

    if request.method == "POST":
        nn = lambda v: (v if v not in ("", None) else None)
        proceso_id = request.form.get("proceso_id", type=int)
        canal_contacto = request.form.get("canal_contacto", type=int) # <- corregido
        comentario = nn(request.form.get("comentario"))
        fecha_programada = nn(request.form.get("fecha_programada"))
        motivo_no_venta_id = request.form.get("motivo_no_venta_id", type=int)
        cotizacion = nn(request.form.get("cotizacion"))
        moneda_id = request.form.get("moneda_id", type=int)

        monto = None
        monto_raw = nn(request.form.get("monto"))
        if monto_raw is not None:
            try:
                monto = float(monto_raw)
            except ValueError:
                flash("Monto inválido.", "warning")
                return redirect(url_for("leads.seguimiento_lead", codigo=codigo))

        cur = mysql.connection.cursor()
        try:
            cur.execute("""
                INSERT INTO seguimientos
                (lead_id, usuario_id, fecha_seguimiento, proceso_id, fecha_programada,
                motivo_no_venta_id, cotizacion, monto, moneda_id, comentario,
                canal_contacto, fecha_guardado)
                VALUES
                (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW())
            """, (
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
                canal_contacto
            ))
            mysql.connection.commit()
            flash("✅ Seguimiento guardado.", "success")
        except IntegrityError as e:
            if "uq_cotizacion" in str(e).lower() or "cotizacion" in str(e).lower():
                flash("⚠️ El código de cotización ya existe. Ingresa uno diferente.", "danger")
            else:
                flash("❌ Error al guardar el seguimiento.", "danger")
        finally:
            cur.close()

        return redirect(url_for("leads.seguimiento_lead", codigo=codigo))


    procesos = Proceso.get_all()
    canales = CanalContacto.get_all()
    monedas = Moneda.get_all()
    motivos = Motivonoventa.get_all()
    bienes = BienServicio.get_all()

    proc_map = {}
    for p in procesos:
        pid = p["id"] if isinstance(p, dict) else p.id
        pname = p["nombre_proceso"] if isinstance(p, dict) else p.nombre_proceso
        proc_map[pid] = pname

    bs_map = {}
    for b in bienes:
        bid = b["id"] if isinstance(b, dict) else b.id
        bname = b["nombre"] if isinstance(b, dict) else b.nombre
        bs_map[bid] = bname

    bien_servicio_nombre = bs_map.get(lead.get("bien_servicio_id") or lead.get("bien_servicio"))
    lead_nombre = lead.get("nombre") or lead.get("nombre_completo") or lead.get("razon_social") or ""
    lead_contacto = lead.get("contacto") or lead.get("persona_contacto") or ""

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("""
        SELECT s.*
        FROM seguimientos s
        WHERE s.lead_id = %s
        ORDER BY s.fecha_guardado DESC, s.id DESC
    """, (lead_id,))
    seguimientos = cur.fetchall()
    ultimo = seguimientos[0] if seguimientos else None
    cur.close()

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
                pname = (p["nombre_proceso"] if isinstance(p, dict) else p.nombre_proceso) or ""
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
    )

# --- RUTAS DE LISTAS POR ESTADO CON PAGINACIÓN Y BÚSQUEDA (MODIFICADAS) ---

@lead_bp.route("/sin-iniciar")
@login_required
def list_unstarted():
    return _list_leads_by_status(
        Lead.list_unstarted_for_user, 
        "leads/sin_iniciar.html"
    )

@lead_bp.route("/en-seguimiento")
@login_required
def list_in_followup():
    return _list_leads_by_status(
        Lead.list_in_followup_for_user, 
        "leads/seguimiento_sidebar.html"
    )

@lead_bp.route("/programados")
@login_required
def list_programmed():
    return _list_leads_by_status(
        Lead.list_programmed_for_user, 
        "leads/programados.html"
    )

@lead_bp.route("/cotizados")
@login_required
def list_quoted():
    return _list_leads_by_status(
        Lead.list_quoted_for_user, 
        "leads/cotizados.html"
    )

@lead_bp.route("/cerrados")
@login_required
def list_closed():
    return _list_leads_by_status(
        Lead.list_closed_for_user, 
        "leads/cerrados.html"
    )

@lead_bp.route("/cerrados-no-vendidos")
@login_required
def list_closed_lost():
    return _list_leads_by_status(
        Lead.list_closed_lost_for_user, 
        "leads/cerrados_no_vendidos.html"
    )

# ... [APIs y Notificaciones] ...
# Estas funciones se mantienen sin cambios.

# API: listar departamentos

@lead_bp.route("/api/departamentos", methods=["GET"])
def api_list_departamentos():
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    try:
        cur.execute("SELECT idDepartamento, departamento FROM departamentos ORDER BY departamento")
        rows = cur.fetchall() or []
        return jsonify([{"id": r["idDepartamento"], "nombre": r["departamento"]} for r in rows]), 200
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
        return jsonify([{"id": r["idProvincia"], "nombre": r["provincia"]} for r in rows]), 200
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
        return jsonify([{"id": r["idDistrito"], "nombre": r["distrito"]} for r in rows]), 200
    except Exception as e:
        # opcional: print(e)
        return jsonify({"error": "No se pudo obtener distritos"}), 500
    finally:
        cur.close()


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
            SELECT l.id, l.codigo, l.nombre, su.fecha_programada, su.usuario_id
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
                SELECT l.id, l.codigo, l.nombre, l.fecha
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
                }
                if date_field and r.get(date_field) is not None:
                    item[date_field] = str(r.get(date_field))
                out.append(item)
            return out


        return jsonify({
            "programadas": normalize(programadas, "fecha_programada"),
            "sin_iniciar": normalize(sin_iniciar, None)
        }), 200


    except Exception as e:
        # Puedes habilitar un print para debug temporalmente:
        # print("notifications_panel error:", e)
        return jsonify({"error": "No se pudo obtener notificaciones"}), 500
    finally:
        cur.close()

        