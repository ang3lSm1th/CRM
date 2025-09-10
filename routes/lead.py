# routes/lead.py
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
import io, base64
import matplotlib
matplotlib.use("Agg")  # backend sin ventana para servidores
import matplotlib.pyplot as plt


# 🔹 NUEVO: catálogo específico para seguimiento
from models.canal_contacto import CanalContacto

lead_bp = Blueprint("leads", __name__)

@lead_bp.route("/list")
@login_required
def list_leads():
    q      = (request.args.get("q") or "").strip()
    f_ini  = request.args.get("f_ini") or None
    f_fin  = request.args.get("f_fin") or None

    if q or f_ini or f_fin:
        leads = Lead.search_for_user(
            session["id_rol"], session["user_id"], q=q, start_date=f_ini, end_date=f_fin
        )
    else:
        leads = Lead.list_for_user(
            session["id_rol"], session["user_id"], start_date=f_ini, end_date=f_fin
        )

    return render_template("leads/list.html", leads=leads, q=q, total=len(leads), f_ini=f_ini, f_fin=f_fin)


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
        canales=Canal.get_all(),  # recepción
        bienes_servicios=BienServicio.get_all(),
        asesores=(User.get_by_role(ROLE_ASESOR) if session["id_rol"] != ROLE_ASESOR else [User.get_by_id(session["user_id"])]),
        es_asesor=(session["id_rol"] == ROLE_ASESOR),
    )


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


# ==========================
# SEGUIMIENTO
# ==========================
@lead_bp.route("/seguimiento/<codigo>", methods=["GET", "POST"])
@role_required(ROLE_ADMIN, ROLE_GERENTE, ROLE_RRHH, ROLE_ASESOR)
def seguimiento_lead(codigo):
    lead = Lead.get_by_codigo(codigo)  # dict
    if not lead:
        flash("❌ Lead no encontrado", "danger")
        return redirect(url_for("leads.list_leads"))

    lead_id = lead["id"]

    # usuario que registra (asignado o el logueado)
    usuario_id = lead.get("asignado_a") or session.get("user_id")
    if not usuario_id:
        flash("No se pudo determinar el usuario que registra el seguimiento.", "danger")
        return redirect(url_for("leads.seguimiento_lead", codigo=codigo))

    fecha_seguimiento = lead.get("fecha") or date.today().strftime("%Y-%m-%d")

    if request.method == "POST":
        nn = lambda v: (v if v not in ("", None) else None)

        proceso_id         = request.form.get("proceso_id", type=int)
        canal_contacto_id  = request.form.get("canal_contacto", type=int)  # <— CORREGIDO
        comentario         = nn(request.form.get("comentario"))
        fecha_programada   = nn(request.form.get("fecha_programada"))
        motivo_no_venta_id = request.form.get("motivo_no_venta_id", type=int)
        cotizacion         = nn(request.form.get("cotizacion"))
        moneda_id          = request.form.get("moneda_id", type=int)

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
                lead_id, usuario_id, fecha_seguimiento, proceso_id, fecha_programada,
                motivo_no_venta_id, cotizacion, monto, moneda_id, comentario,
                canal_contacto_id  # <— CORREGIDO
            ))
            mysql.connection.commit()
            flash("✅ Seguimiento guardado.", "success")
        except IntegrityError:
            flash("❌ Error al guardar el seguimiento.", "danger")
        finally:
            cur.close()

        return redirect(url_for("leads.seguimiento_lead", codigo=codigo))

    # GET: combos y tabla
    procesos = Proceso.get_all()
    canales_contacto = CanalContacto.get_all()  # <— catálogo para seguimiento
    monedas  = Moneda.get_all()
    motivos  = Motivonoventa.get_all()
    bienes   = BienServicio.get_all()

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
    lead_nombre   = lead.get("nombre") or lead.get("nombre_completo") or lead.get("razon_social") or ""
    lead_contacto = lead.get("contacto") or lead.get("persona_contacto") or ""

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("""
        SELECT s.* FROM seguimientos s
        WHERE s.lead_id = %s
        ORDER BY s.fecha_guardado DESC, s.id DESC
    """, (lead_id,))
    seguimientos = cur.fetchall()
    ultimo = seguimientos[0] if seguimientos else None
    cur.close()

    # preset por query param (opcional)
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
    if not hay_ultimo:
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
        canales_contacto=canales_contacto,  # <— pasa al template
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

#Reporte rapido

@lead_bp.route("/reporte-rapido", methods=["GET"])
@login_required
@role_required(ROLE_ADMIN, ROLE_GERENTE, ROLE_RRHH)
def reporte_rapido():
    f_ini = (request.args.get("f_ini") or "").strip() or None
    f_fin = (request.args.get("f_fin") or "").strip() or None

    last_sql = """
      SELECT s1.*
      FROM seguimientos s1
      LEFT JOIN seguimientos s2
        ON s2.lead_id = s1.lead_id
       AND (s2.fecha_guardado > s1.fecha_guardado
         OR (s2.fecha_guardado = s1.fecha_guardado AND s2.id > s1.id))
      WHERE s2.id IS NULL
    """

    base_sql = f"""
      SELECT
        l.id AS lead_id,
        l.codigo,
        l.fecha AS fecha_lead,
        l.nombre,
        l.contacto,
        l.telefono,
        l.asignado_a,
        u.nombre  AS asesor_nombre,
        u.usuario AS asesor_usuario,
        l.canal_id AS canal_recepcion_id,
        ls.proceso_id,
        ls.canal_contacto,
        ls.monto,
        ls.moneda_id
      FROM leads l
      LEFT JOIN ({last_sql}) ls ON ls.lead_id = l.id
      LEFT JOIN usuarios u ON u.id = l.asignado_a
      WHERE 1=1
    """
    params = []
    if f_ini:
        base_sql += " AND l.fecha >= %s"
        params.append(f_ini)
    if f_fin:
        base_sql += " AND l.fecha <= %s"
        params.append(f_fin)

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute(base_sql, params)
    rows = cur.fetchall()
    cur.close()

    total_leads = len(rows)

    # Catálogos
    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("SELECT id, nombre_proceso FROM proceso")
    procesos = {r["id"]: r["nombre_proceso"] for r in cur.fetchall()}
    cur.close()

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("SELECT id, nombre FROM canal_contacto")
    canales_contacto = {r["id"]: r["nombre"] for r in cur.fetchall()}
    cur.close()

    cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
    cur.execute("SELECT id, nombre FROM canales_recepcion")
    canales_recepcion = {r["id"]: r["nombre"] for r in cur.fetchall()}
    cur.close()

    # Agregados
    proc_counts, canal_counts = {}, {}

    total_no_iniciados = 0
    total_seguimiento = 0
    total_programados = 0
    total_cotizados = 0
    total_cerrados = 0
    total_cerrados_no_vendidos = 0

    # ELPPA por asesor
    elppa = {}

    # Resumen Cotizado
    cotizado_tbl = {
        "Cotizado": {"cant": 0, "usd": 0.0, "pen": 0.0},
        "Cotizado Cerrado": {"cant": 0, "usd": 0.0, "pen": 0.0},
        "Cotizado Cerrado no vendido": {"cant": 0, "usd": 0.0, "pen": 0.0},
    }
    USD_ID, PEN_ID = 1, 2

    # Conteo comparativo para gráficos por canal
    recep_counts = {}     # canales de recepción
    contacto_counts = {}  # canales de contacto (seguimiento)

    for r in rows:
        pname = procesos.get(r.get("proceso_id"), "Sin proceso")
        proc_counts[pname] = proc_counts.get(pname, 0) + 1

        # Para la tabla "Por Canal" (mantenemos “Sin canal” aquí)
        cname_tabla = canales_contacto.get(r.get("canal_contacto"), "Sin canal")
        canal_counts[cname_tabla] = canal_counts.get(cname_tabla, 0) + 1

        # Para los gráficos: NO contamos "Sin canal"
        rid = r.get("canal_recepcion_id")
        rname = canales_recepcion.get(rid)
        if rname:
            recep_counts[rname] = recep_counts.get(rname, 0) + 1

        cid = r.get("canal_contacto")
        cname = canales_contacto.get(cid)
        if cname:
            contacto_counts[cname] = contacto_counts.get(cname, 0) + 1

        pnorm = (pname or "").strip().lower()

        # Datos del asesor
        asesor_id   = r.get("asignado_a")
        asesor      = (r.get("asesor_nombre") or "").strip()
        asesor_user = (r.get("asesor_usuario") or "").strip()
        incluir_en_elppa = bool(asesor_id and asesor)

        # Estado + totales globales
        estado_key = None
        cotizado_key = None
        if "no iniciado" in pnorm:
            estado_key = "no_iniciados";            total_no_iniciados += 1
        elif "seguimiento" in pnorm:
            estado_key = "seguimiento";             total_seguimiento += 1
        elif "programado" in pnorm:
            estado_key = "programados";             total_programados += 1
        elif "cotizado" in pnorm:
            estado_key = "cotizados";               total_cotizados += 1
            cotizado_key = "Cotizado"
        elif "cerrado no vendido" in pnorm:
            estado_key = "cerrados_no_vendidos";    total_cerrados_no_vendidos += 1
            cotizado_key = "Cotizado Cerrado no vendido"
        elif "cerrado" in pnorm:
            estado_key = "cerrados";                total_cerrados += 1
            cotizado_key = "Cotizado Cerrado"

        # ELPPA (solo asesores válidos)
        if incluir_en_elppa and estado_key:
            if asesor not in elppa:
                elppa[asesor] = {
                    "usuario": asesor_user,
                    "no_iniciados": 0,
                    "seguimiento": 0,
                    "programados": 0,
                    "cotizados": 0,
                    "cerrados": 0,
                    "cerrados_no_vendidos": 0,
                }
            elppa[asesor][estado_key] += 1

        # Montos para "Cotizado"
        if cotizado_key:
            monto = r.get("monto")
            moneda_id = r.get("moneda_id")
            cotizado_tbl[cotizado_key]["cant"] += 1
            if monto is not None:
                try:
                    m = float(monto)
                    if moneda_id == USD_ID:
                        cotizado_tbl[cotizado_key]["usd"] += m
                    elif moneda_id == PEN_ID:
                        cotizado_tbl[cotizado_key]["pen"] += m
                except (TypeError, ValueError):
                    pass

    proc_counts = sorted(proc_counts.items(), key=lambda x: x[1], reverse=True)
    canal_counts = sorted(canal_counts.items(), key=lambda x: x[1], reverse=True)

    cotizado_rows = [
        ("Cotizado", cotizado_tbl["Cotizado"]),
        ("Cotizado Cerrado", cotizado_tbl["Cotizado Cerrado"]),
        ("Cotizado Cerrado no vendido", cotizado_tbl["Cotizado Cerrado no vendido"]),
    ]

    # === Barras agrupadas para "Cotizado" (montos S/ vs $ por estado)
    def make_grouped_bar_base64(labels, pen_vals, usd_vals, xlabel="Monto total"):
        if not labels:
            return None

        n = len(labels)
        ys = list(range(n))
        h = 0.36
        ys_pen = [y - h/2 for y in ys]
        ys_usd = [y + h/2 for y in ys]

        fig_h = max(3.8, 0.60 * n + 1.8)
        fig, ax = plt.subplots(figsize=(9.5, fig_h), dpi=160)

        b_pen = ax.barh(ys_pen, pen_vals, height=h, label="Soles",   color="#10b981")
        b_usd = ax.barh(ys_usd, usd_vals, height=h, label="Dólares", color="#6366f1")

        ax.set_yticks(ys)
        ax.set_yticklabels(labels)
        ax.invert_yaxis()
        ax.set_xlabel(xlabel)
        ax.grid(True, axis="x", alpha=.25)

        maxv = max([0] + pen_vals + usd_vals)
        x_pad = max(1, maxv * 0.10)
        x_right = maxv + x_pad
        ax.set_xlim(0, x_right)

        def annotate(bars):
            for r in bars:
                v = r.get_width()
                if v <= 0:
                    continue
                x_label = min(v + x_pad * 0.10, x_right - x_pad * 0.06)
                ax.text(x_label, r.get_y() + r.get_height()/2, f"{v:,.2f}",
                        va="center", ha="left", fontsize=9, color="#111")

        annotate(b_pen)
        annotate(b_usd)

        ax.legend(loc="lower right")
        plt.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", transparent=True)
        plt.close(fig)
        return base64.b64encode(buf.getvalue()).decode("ascii")

    labels_cot = [lbl for (lbl, _) in cotizado_rows]
    pen_vals   = [row["pen"] for (_, row) in cotizado_rows]
    usd_vals   = [row["usd"] for (_, row) in cotizado_rows]
    cotizado_bar_png = make_grouped_bar_base64(labels_cot, pen_vals, usd_vals, xlabel="Monto total por estado")

    # ===== Barras horizontales (una serie) para canales (con etiquetas que no se salen)
    def make_single_bar_base64(labels, values, top_n=12, xlabel="Cantidad de leads", bar_color=None):
        items = [(lbl, val) for lbl, val in zip(labels, values) if lbl and str(lbl).strip()]
        if not items:
            return None
        items.sort(key=lambda x: x[1], reverse=True)
        if top_n and len(items) > top_n:
            items = items[:top_n]

        labels = [it[0] for it in items]
        values = [it[1] for it in items]

        n = len(labels)
        ys = list(range(n))
        fig_h = max(3.5, 0.48 * n + 1.5)
        fig, ax = plt.subplots(figsize=(9.5, fig_h), dpi=160)

        ax.barh(ys, values, color=(bar_color or "#2563eb"))

        ax.set_yticks(ys)
        ax.set_yticklabels(labels)
        ax.invert_yaxis()
        ax.set_xlabel(xlabel)
        ax.grid(True, axis="x", alpha=.25)

        maxv = max([0] + values)
        x_pad = max(1, maxv * 0.10)
        x_right = maxv + x_pad
        ax.set_xlim(0, x_right)

        for y, v in zip(ys, values):
            if v <= 0:
                continue
            x_label = v + x_pad * 0.10
            ha = "left"
            color = "#111"
            if v >= x_right * 0.92:
                x_label = v - x_pad * 0.12
                ha = "right"
                color = "white"
            x_label = min(x_label, x_right - x_pad * 0.06)
            ax.text(x_label, y, f"{v}", va="center", ha=ha, fontsize=9, color=color)

        plt.tight_layout()
        buf = io.BytesIO()
        fig.savefig(buf, format="png", bbox_inches="tight", transparent=True)
        plt.close(fig)
        return base64.b64encode(buf.getvalue()).decode("ascii")

    # Datos para cada gráfico de canales
    names_recep = list(recep_counts.keys())
    vals_recep  = [recep_counts[n] for n in names_recep]

    names_contacto = list(contacto_counts.keys())
    vals_contacto  = [contacto_counts[n] for n in names_contacto]

    BLUE   = "#2563eb"
    ORANGE = "#f59e0b"

    bar_recepcion_png = make_single_bar_base64(
        names_recep, vals_recep, top_n=12,
        xlabel="Leads por canal de recepción",
        bar_color=BLUE
    )
    bar_contacto_png = make_single_bar_base64(
        names_contacto, vals_contacto, top_n=12,
        xlabel="Leads por canal de contacto",
        bar_color=ORANGE
    )

    return render_template(
        "leads/rapido.html",
        f_ini=f_ini, f_fin=f_fin,
        total_leads=total_leads,
        proc_counts=proc_counts,
        canal_counts=canal_counts,
        total_no_iniciados=total_no_iniciados,
        total_seguimiento=total_seguimiento,
        total_programados=total_programados,
        total_cotizados=total_cotizados,
        total_cerrados=total_cerrados,
        total_cerrados_no_vendidos=total_cerrados_no_vendidos,
        elppa=elppa,
        cotizado_rows=cotizado_rows,
        cotizado_bar_png=cotizado_bar_png,   # gráfico de montos S/ vs $
        bar_recepcion_png=bar_recepcion_png, # barras por canal de recepción
        bar_contacto_png=bar_contacto_png,   # barras por canal de contacto
    )





# Rutas de listas por estado (sin cambios)
@lead_bp.route("/sin-iniciar")
@login_required
def list_unstarted():
    q = (request.args.get("q") or "").strip()
    leads = Lead.list_unstarted_for_user(session["id_rol"], session["user_id"], q)
    return render_template("leads/sin_iniciar.html", leads=leads, q=q, total=len(leads))

@lead_bp.route("/en-seguimiento")
@login_required
def list_in_followup():
    q = (request.args.get("q") or "").strip()
    leads = Lead.list_in_followup_for_user(session["id_rol"], session["user_id"], q)
    return render_template("leads/seguimiento_sidebar.html", leads=leads, q=q, total=len(leads))

@lead_bp.route("/programados")
@login_required
def list_programmed():
    q = (request.args.get("q") or "").strip()
    leads = Lead.list_programmed_for_user(session["id_rol"], session["user_id"], q)
    return render_template("leads/programados.html", leads=leads, q=q, total=len(leads))

@lead_bp.route("/cotizados")
@login_required
def list_quoted():
    q = (request.args.get("q") or "").strip()
    leads = Lead.list_quoted_for_user(session["id_rol"], session["user_id"], q)
    return render_template("leads/cotizados.html", leads=leads, q=q, total=len(leads))

@lead_bp.route("/cerrados")
@login_required
def list_closed():
    q = (request.args.get("q") or "").strip()
    leads = Lead.list_closed_for_user(session["id_rol"], session["user_id"], q)
    return render_template("leads/cerrados.html", leads=leads, q=q, total=len(leads))

@lead_bp.route("/cerrados-no-vendidos")
@login_required
def list_closed_lost():
    q = (request.args.get("q") or "").strip()
    leads = Lead.list_closed_lost_for_user(session["id_rol"], session["user_id"], q)
    return render_template("leads/cerrados_no_vendidos.html", leads=leads, q=q, total=len(leads))



