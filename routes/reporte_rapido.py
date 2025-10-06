# routes/reporte_rapido.py
from flask import Blueprint, render_template, request
from utils.security import role_required, ROLE_ADMIN, ROLE_GERENTE, ROLE_RRHH
from extensions import mysql
import MySQLdb.cursors
import io, base64
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt

# Blueprint para reporte rápido (namespace 'reporte_rapido')
reporte_rapido_bp = Blueprint("reporte_rapido", __name__)

ROLES_LIST = (ROLE_ADMIN, ROLE_GERENTE, ROLE_RRHH)

@reporte_rapido_bp.route("/reporte-rapido", methods=["GET"])
@role_required(*ROLES_LIST)
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
    proc_counts, recep_counts = {}, {}

    total_no_iniciados = total_seguimiento = total_programados = total_cotizados = total_cerrados = total_cerrados_no_vendidos = 0
    elppa = {}
    cotizado_tbl = {
        "Cotizado": {"cant": 0, "usd": 0.0, "pen": 0.0},
        "Cotizado Cerrado": {"cant": 0, "usd": 0.0, "pen": 0.0},
        "Cotizado Cerrado no vendido": {"cant": 0, "usd": 0.0, "pen": 0.0},
    }
    USD_ID, PEN_ID = 1, 2

    for r in rows:
        pname = procesos.get(r.get("proceso_id"), "Sin proceso")
        proc_counts[pname] = proc_counts.get(pname, 0) + 1

        rid = r.get("canal_recepcion_id")
        rname = canales_recepcion.get(rid)
        if rname:
            recep_counts[rname] = recep_counts.get(rname, 0) + 1

        pnorm = (pname or "").strip().lower()
        asesor_id   = r.get("asignado_a")
        asesor      = (r.get("asesor_nombre") or "").strip()
        asesor_user = (r.get("asesor_usuario") or "").strip()
        incluir_en_elppa = bool(asesor_id and asesor)

        estado_key = None
        cotizado_key = None
        if r.get("proceso_id") is None or "no iniciado" in pnorm:
            estado_key = "no_iniciados"; total_no_iniciados += 1
        elif "seguimiento" in pnorm:
            estado_key = "seguimiento"; total_seguimiento += 1
        elif "programado" in pnorm:
            estado_key = "programados"; total_programados += 1
        elif "cotizado" in pnorm:
            estado_key = "cotizados"; total_cotizados += 1; cotizado_key = "Cotizado"
        elif "cerrado no vendido" in pnorm:
            estado_key = "cerrados_no_vendidos"; total_cerrados_no_vendidos += 1; cotizado_key = "Cotizado Cerrado no vendido"
        elif "cerrado" in pnorm:
            estado_key = "cerrados"; total_cerrados += 1; cotizado_key = "Cotizado Cerrado"

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
    canal_counts = sorted(recep_counts.items(), key=lambda x: x[1], reverse=True)

    cotizado_rows = [
        ("Cotizado", cotizado_tbl["Cotizado"]),
        ("Cotizado Cerrado", cotizado_tbl["Cotizado Cerrado"]),
        ("Cotizado Cerrado no vendido", cotizado_tbl["Cotizado Cerrado no vendido"]),
    ]

    # ==== funciones de gráfico (generan base64 PNG)
    def make_grouped_bar_base64(labels, pen_vals, usd_vals, xlabel="Monto total"):
        if not labels: return None
        n = len(labels)
        ys = list(range(n))
        h = 0.36
        ys_pen = [y - h/2 for y in ys]
        ys_usd = [y + h/2 for y in ys]
        fig_h = max(3.8, 0.60 * n + 1.8)
        fig, ax = plt.subplots(figsize=(9.5, fig_h), dpi=160)
        ax.barh(ys_pen, pen_vals, height=h, label="Soles",  color="#10b981")
        ax.barh(ys_usd, usd_vals, height=h, label="Dólares", color="#6366f1")
        ax.set_yticks(ys); ax.set_yticklabels(labels); ax.invert_yaxis()
        ax.set_xlabel(xlabel); ax.grid(True, axis="x", alpha=.25)
        maxv = max([0] + pen_vals + usd_vals); x_pad = max(1, maxv * 0.10); x_right = maxv + x_pad
        ax.set_xlim(0, x_right)
        def annotate(bars):
            for r in bars:
                v = r.get_width()
                if v <= 0: continue
                x_label = min(v + x_pad * 0.10, x_right - x_pad * 0.06)
                ax.text(x_label, r.get_y() + r.get_height()/2, f"{v:,.2f}", va="center", ha="left", fontsize=9, color="#111")
        # annotate(ax.containers[0] if ax.containers else [])
        plt.tight_layout()
        buf = io.BytesIO(); fig.savefig(buf, format="png", bbox_inches="tight", transparent=True); plt.close(fig)
        return base64.b64encode(buf.getvalue()).decode("ascii")

    def make_single_bar_base64(labels, values, top_n=12, xlabel="Cantidad de leads", bar_color=None):
        items = [(lbl, val) for lbl, val in zip(labels, values) if lbl and str(lbl).strip()]
        if not items: return None
        items.sort(key=lambda x: x[1], reverse=True)
        if top_n and len(items) > top_n: items = items[:top_n]
        labels = [it[0] for it in items]; values = [it[1] for it in items]
        n = len(labels); ys = list(range(n)); fig_h = max(3.5, 0.48 * n + 1.5)
        fig, ax = plt.subplots(figsize=(9.5, fig_h), dpi=160)
        ax.barh(ys, values, color=(bar_color or "#2563eb"))
        ax.set_yticks(ys); ax.set_yticklabels(labels); ax.invert_yaxis()
        ax.set_xlabel(xlabel); ax.grid(True, axis="x", alpha=.25)
        maxv = max([0] + values); x_pad = max(1, maxv * 0.10); x_right = maxv + x_pad
        ax.set_xlim(0, x_right)
        for y, v in zip(ys, values):
            if v <= 0: continue
            x_label = v + x_pad * 0.10; ha = "left"; color = "#111"
            if v >= x_right * 0.92: x_label = v - x_pad * 0.12; ha = "right"; color = "white"
            x_label = min(x_label, x_right - x_pad * 0.06)
            ax.text(x_label, y, f"{v}", va="center", ha=ha, fontsize=9, color=color)
        plt.tight_layout()
        buf = io.BytesIO(); fig.savefig(buf, format="png", bbox_inches="tight", transparent=True); plt.close(fig)
        return base64.b64encode(buf.getvalue()).decode("ascii")

    names_recep = list(recep_counts.keys())
    vals_recep  = [recep_counts[n] for n in names_recep]

    BLUE = "#2563eb"
    bar_recepcion_png = make_single_bar_base64(names_recep, vals_recep, top_n=12, xlabel="Leads por canal de recepción", bar_color=BLUE)

    labels_cot = [lbl for (lbl, _) in cotizado_rows]
    pen_vals   = [row["pen"] for (_, row) in cotizado_rows]
    usd_vals   = [row["usd"] for (_, row) in cotizado_rows]
    cotizado_bar_png = make_grouped_bar_base64(labels_cot, pen_vals, usd_vals, xlabel="Monto total por estado")

    return render_template(
        "leads/rapido.html",
        f_ini=f_ini, f_fin=f_fin,
        total_leads=len(rows),
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
        cotizado_bar_png=cotizado_bar_png,
        bar_recepcion_png=bar_recepcion_png,
    )
