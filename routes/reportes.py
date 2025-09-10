from flask import Blueprint, render_template, request, redirect, url_for, session, flash
from utils.security import login_required, role_required, ROLE_ADMIN, ROLE_GERENTE, ROLE_RRHH, ROLE_ASESOR
from models.lead import Lead
from models.canal import Canal
from models.bien_servicio import BienServicio
from models.user import User
import MySQLdb.cursors
from datetime import date
from models.proceso import Proceso
from models.moneda import Moneda
from models.motivonoventa import Motivonoventa
from MySQLdb import IntegrityError
from extensions import mysql

# -----------------------------
# Blueprint de Leads
# -----------------------------
lead_bp = Blueprint("leads", __name__)

# -----------------------------
# Listar leads
# -----------------------------
@lead_bp.route("/list")
@login_required
def list_leads():
    q      = (request.args.get("q") or "").strip()
    f_ini  = request.args.get("f_ini") or None  # YYYY-MM-DD
    f_fin  = request.args.get("f_fin") or None  # YYYY-MM-DD

    # Si hay filtro (q o fechas) usamos search_for_user; si no, list_for_user
    if q or f_ini or f_fin:
        leads = Lead.search_for_user(
            session["id_rol"],
            session["user_id"],
            q=q,
            start_date=f_ini,
            end_date=f_fin
        )
    else:
        leads = Lead.list_for_user(
            session["id_rol"],
            session["user_id"],
            start_date=f_ini,
            end_date=f_fin
        )

    return render_template(
        "leads/list.html",
        leads=leads,
        q=q,
        total=len(leads),
        f_ini=f_ini,
        f_fin=f_fin
    )


# -----------------------------
# Crear lead
# -----------------------------
@lead_bp.route("/create", methods=["GET", "POST"])
@role_required(ROLE_ADMIN, ROLE_GERENTE, ROLE_RRHH, ROLE_ASESOR)
def create_lead():
    if request.method == "POST":
        codigo = Lead.next_codigo()
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
            "asignado_a": (session["user_id"] if session["id_rol"] == ROLE_ASESOR else request.form.get("asignado_a")),
            "comentario": request.form.get("comentario"),
        }
        Lead.create(data)
        flash("✅ Lead creado correctamente", "success")
        return redirect(url_for("leads.list_leads"))

    return render_template(
        "leads/create.html",
        codigo=Lead.next_codigo(),
        fecha_hoy=date.today().strftime("%Y-%m-%d"),
        canales=Canal.get_all(),
        bienes_servicios=BienServicio.get_all(),
        asesores=(
            User.get_by_role(ROLE_ASESOR)
            if session["id_rol"] != ROLE_ASESOR
            else [User.get_by_id(session["user_id"])]
        ),
        es_asesor=(session["id_rol"] == ROLE_ASESOR),
    )

# -----------------------------
# Editar lead
# -----------------------------
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
        return redirect(url_for("leads.list_leads"))

    return render_template(
        "leads/edit.html",
        lead=lead,
        canales=Canal.get_all(),
        bienes_servicios=BienServicio.get_all(),
        asesores=User.get_by_role(ROLE_ASESOR) if session["id_rol"] != ROLE_ASESOR else [],
        es_asesor=(session["id_rol"] == ROLE_ASESOR),
    )

# -----------------------------
# Eliminar lead
# -----------------------------
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

# -----------------------------
# Seguimiento de lead
# -----------------------------
@lead_bp.route("/seguimiento/<codigo>", methods=["GET", "POST"])
@role_required(ROLE_ADMIN, ROLE_GERENTE, ROLE_RRHH, ROLE_ASESOR)
def seguimiento_lead(codigo):
    # --- Lead base ---
    lead = Lead.get_by_codigo(codigo)  # dict
    if not lead:
        flash("❌ Lead no encontrado", "danger")
        return redirect(url_for("leads.list_leads"))

    lead_id = lead["id"]

    # Usuario que registra (prioriza asignado; si no hay, el usuario logueado)
    usuario_id = lead.get("asignado_a") or session.get("user_id")
    if not usuario_id:
        flash("No se pudo determinar el usuario que registra el seguimiento.", "danger")
        return redirect(url_for("leads.seguimiento_lead", codigo=codigo))

    # Usa fecha del lead si existe; si no, hoy
    fecha_seguimiento = lead.get("fecha") or date.today().strftime("%Y-%m-%d")

    # =====================
    # POST: insertar seguimiento
    # =====================
    if request.method == "POST":
        nn = lambda v: (v if v not in ("", None) else None)

        proceso_id         = request.form.get("proceso_id", type=int)
        canal_emision      = request.form.get("canal_emision", type=int)  # FK canales_recepcion.id
        comentario         = nn(request.form.get("comentario"))
        fecha_programada   = nn(request.form.get("fecha_programada"))     # puede ser NULL
        motivo_no_venta_id = request.form.get("motivo_no_venta_id", type=int)
        cotizacion         = nn(request.form.get("cotizacion"))           # texto
        moneda_id          = request.form.get("moneda_id", type=int)

        # monto numérico (o NULL)
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
                   canal_emision, fecha_guardado)
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
                canal_emision
            ))
            mysql.connection.commit()
            flash("✅ Seguimiento guardado.", "success")
        except IntegrityError as e:
            # Por si tienes una UNIQUE en 'cotizacion'
            if "uq_cotizacion" in str(e).lower() or "cotizacion" in str(e).lower():
                flash("⚠️ El código de cotización ya existe. Ingresa uno diferente.", "danger")
            else:
                flash("❌ Error al guardar el seguimiento.", "danger")
        finally:
            cur.close()

        # PRG: evita repost al recargar
        return redirect(url_for("leads.seguimiento_lead", codigo=codigo))

    # =====================
    # GET: combos, mapas y lista de seguimientos
    # =====================
    procesos = Proceso.get_all()
    canales  = Canal.get_all()
    monedas  = Moneda.get_all()
    motivos  = Motivonoventa.get_all()
    bienes   = BienServicio.get_all()

    # Map proceso_id -> nombre
    proc_map = {}
    for p in procesos:
        pid = p["id"] if isinstance(p, dict) else p.id
        pname = p["nombre_proceso"] if isinstance(p, dict) else p.nombre_proceso
        proc_map[pid] = pname

    # Map bien_servicio_id -> nombre
    bs_map = {}
    for b in bienes:
        bid = b["id"] if isinstance(b, dict) else b.id
        bname = b["nombre"] if isinstance(b, dict) else b.nombre
        bs_map[bid] = bname

    # Nombre del bien/servicio del lead
    bien_servicio_nombre = bs_map.get(lead.get("bien_servicio_id") or lead.get("bien_servicio"))

    # Nombre y Contacto con fallbacks
    lead_nombre   = lead.get("nombre") or lead.get("nombre_completo") or lead.get("razon_social") or ""
    lead_contacto = lead.get("contacto") or lead.get("persona_contacto") or ""

    # Lista de seguimientos (más nuevos primero) + último
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

    # =====================
    # Preset para el <select> Proceso (solo si NO hay último ni POST)
    # =====================
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
    # hay_post siempre False aquí (estamos en GET), pero dejo la variable por claridad
    hay_post   = False

    if not hay_ultimo and not hay_post:
        target_name = preset_map.get(preset)  # puede ser None
        if target_name:
            for p in procesos:
                pname = (p["nombre_proceso"] if isinstance(p, dict) else p.nombre_proceso) or ""
                if pname.strip().lower() == target_name:
                    default_proceso_id = p["id"] if isinstance(p, dict) else p.id
                    break

    # =====================
    # Bloquear el <select> Proceso si el último estado es "Cerrado"
    # =====================
    cerrado_id = None
    for p in procesos:
        pname = (p["nombre_proceso"] if isinstance(p, dict) else p.nombre_proceso) or ""
        if pname.strip().lower() == "cerrado":
            cerrado_id = p["id"] if isinstance(p, dict) else p.id
            break
    lock_proceso = bool(ultimo and (ultimo.get("proceso_id") == cerrado_id))

    # Render
    return render_template(
        "leads/seguimiento.html",
        lead=lead,
        procesos=procesos,
        canales=canales,
        monedas=monedas,
        motivos=motivos,
        seguimientos=seguimientos,   # DESC ya ordenado (más nuevo primero)
        ultimo=ultimo,               # para prellenar el form
        proc_map=proc_map,
        bien_servicio_nombre=bien_servicio_nombre,
        lead_nombre=lead_nombre,
        lead_contacto=lead_contacto,
        date=date,
        default_proceso_id=default_proceso_id,  # para el default del select (si aplica)
        lock_proceso=lock_proceso,              # para deshabilitar el select si quedó Cerrado
    )


# -----------------------------
# Leads SIN iniciar (último seguimiento = "No iniciado")
# -----------------------------
@lead_bp.route("/sin-iniciar")
@login_required
def list_unstarted():
    q = (request.args.get("q") or "").strip()
    leads = Lead.list_unstarted_for_user(session["id_rol"], session["user_id"], q)
    return render_template("leads/sin_iniciar.html", leads=leads, q=q, total=len(leads))

# -----------------------------
# Leads en Seguimiento (último seguimiento = "Seguimiento")
# -----------------------------

@lead_bp.route("/en-seguimiento")
@login_required
def list_in_followup():
    q = (request.args.get("q") or "").strip()
    leads = Lead.list_in_followup_for_user(session["id_rol"], session["user_id"], q)
    return render_template("leads/seguimiento_sidebar.html", leads=leads, q=q, total=len(leads))

# -----------------------------
# Leads en Programado (último Programado = "Programado")
# -----------------------------

@lead_bp.route("/programados")
@login_required
def list_programmed():
    q = (request.args.get("q") or "").strip()
    leads = Lead.list_programmed_for_user(session["id_rol"], session["user_id"], q)
    return render_template("leads/programados.html", leads=leads, q=q, total=len(leads))

# -----------------------------
# Leads en Cotizado (último Cotizado = "Cotizado")
# -----------------------------

@lead_bp.route("/cotizados")
@login_required
def list_quoted():
    q = (request.args.get("q") or "").strip()
    leads = Lead.list_quoted_for_user(session["id_rol"], session["user_id"], q)
    return render_template("leads/cotizados.html", leads=leads, q=q, total=len(leads))

# -----------------------------
# Leads en cerrados (último cerrados = "cerrados")
# -----------------------------

@lead_bp.route("/cerrados")
@login_required
def list_closed():
    q = (request.args.get("q") or "").strip()
    leads = Lead.list_closed_for_user(session["id_rol"], session["user_id"], q)
    return render_template("leads/cerrados.html", leads=leads, q=q, total=len(leads))

# -----------------------------
# Leads en cerrado no vendido (último cerrado no vendido = "cerrado no vendido")
# -----------------------------

@lead_bp.route("/cerrados-no-vendidos")
@login_required
def list_closed_lost():
    q = (request.args.get("q") or "").strip()
    leads = Lead.list_closed_lost_for_user(session["id_rol"], session["user_id"], q)
    return render_template("leads/cerrados_no_vendidos.html", leads=leads, q=q, total=len(leads))


