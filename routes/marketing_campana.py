from routes.marketing import (
    CAMPAIGN_CHANNELS,
    DictCursor,
    ROLE_ADMIN,
    ROLE_GERENTE,
    ROLE_MARKETING,
    _append_channel_filter,
    _campaign_financial_snapshot,
    _get_lineas_negocio_options,
    _get_linea_familia_options,
    _get_linea_producto_options,
    _latest_seguimiento_subquery,
    _resolve_negocio_id_by_brand,
    _resolve_line_selection,
    _table_exists,
    _column_exists,
    _to_decimal,
    flash,
    jsonify,
    login_required,
    marketing_bp,
    mysql,
    redirect,
    render_template,
    request,
    role_required,
    session,
    url_for,
)
from utils.security import check_password
import time
import secrets
from urllib.parse import urlsplit, parse_qsl, urlencode


def _safe_internal_next(next_raw, fallback_url):
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


def _marketing_return_label(next_url, fallback_label):
    path = (urlsplit(next_url).path or "").lower()
    if path.startswith("/marketing/roadmap"):
        return "Volver a Roadmap Marketing"
    if path.startswith("/marketing/campanas"):
        return "Volver a Campanas Publicitarias"
    if path.startswith("/marketing/ferias"):
        return "Volver a Ferias"
    return fallback_label


def _campaign_target_negocio_id(campaign, fallback_brand_slug=None):
    """Resuelve negocio objetivo de campaña para filtrar leads por asesor."""
    campaign = campaign or {}
    negocio_raw = campaign.get("negocio_id")
    if negocio_raw not in (None, ""):
        try:
            return int(negocio_raw)
        except (TypeError, ValueError):
            pass

    campaign_brand = (campaign.get("brand") or "").strip().lower()
    if campaign_brand:
        resolved = _resolve_negocio_id_by_brand(campaign_brand)
        if resolved:
            return resolved

    fallback_brand = (fallback_brand_slug or "").strip().lower()
    if fallback_brand:
        return _resolve_negocio_id_by_brand(fallback_brand)
    return None


# Rutas separadas: campanas de marketing
@marketing_bp.route("/campanas/<int:campaign_id>/campo", methods=["POST"])
@login_required
@role_required(ROLE_ADMIN, ROLE_GERENTE, ROLE_MARKETING)
def marketing_campaign_update_campo(campaign_id):
    """Actualiza un campo específico de la campaña via AJAX"""
    campo = request.form.get("campo", "").strip()
    valor = request.form.get("valor", "").strip()

    campos_permitidos = ["nombre_campana", "producto"]
    if campo not in campos_permitidos:
        return jsonify({"ok": False, "message": "Campo no permitido"}), 400

    if not valor:
        return (
            jsonify({"ok": False, "message": f"El campo {campo} no puede estar vacío"}),
            400,
        )

    cur = mysql.connection.cursor(DictCursor)
    try:
        cur.execute(
            "SELECT id, nombre_campana FROM marketing_campaigns WHERE id = %s",
            (campaign_id,),
        )
        campaign = cur.fetchone()
    finally:
        cur.close()

    if not campaign:
        return jsonify({"ok": False, "message": "Campaña no encontrada"}), 404

    cur = mysql.connection.cursor()
    try:
        cur.execute(
            f"UPDATE marketing_campaigns SET {campo} = %s WHERE id = %s",
            (valor, campaign_id),
        )
        mysql.connection.commit()
        return (
            jsonify(
                {
                    "ok": True,
                    "message": "Campaña actualizada correctamente",
                    "value": valor,
                }
            ),
            200,
        )
    except Exception as ex:
        mysql.connection.rollback()
        return jsonify({"ok": False, "message": f"Error al actualizar: {ex}"}), 500
    finally:
        cur.close()


@marketing_bp.route("/campanas", methods=["GET", "POST"])
@login_required
@role_required(ROLE_ADMIN, ROLE_GERENTE, ROLE_MARKETING)
def marketing_campaigns():
    if request.method == "POST":
        # Brand chosen by the user (persisted in cookie). Default to 'orbes'.
        brand = request.cookies.get("brand") or "orbes"
        # Resolve negocio_id from slug (if table exists and slug matches)
        negocio_id = None
        try:
            nc = mysql.connection.cursor(DictCursor)
            try:
                nc.execute("SELECT id FROM negocios WHERE slug = %s LIMIT 1", (brand,))
                nr = nc.fetchone()
                negocio_id = nr.get("id") if nr else None
            finally:
                nc.close()
        except Exception:
            negocio_id = None
        nombre_campana = (request.form.get("nombre_campana") or "").strip()
        fecha_lanzamiento = (request.form.get("fecha_lanzamiento") or "").strip()
        periodo_inicio = (request.form.get("periodo_inicio") or "").strip()
        periodo_fin = (request.form.get("periodo_fin") or "").strip()
        linea_negocio_id = request.form.get("linea_negocio_id")
        linea_familia_id = request.form.get("linea_familia_id")
        linea_producto_id = request.form.get("linea_producto_id")
        producto = (request.form.get("producto") or "").strip()
        canal = (request.form.get("canal") or "").strip()

        line_selection = _resolve_line_selection(
            linea_negocio_id, linea_familia_id, linea_producto_id
        )
        linea_negocio = (line_selection or {}).get("linea_negocio")
        linea_familia = (line_selection or {}).get("linea_familia")
        linea_producto = (line_selection or {}).get("linea_producto")

        conversion_cp = _to_decimal(request.form.get("conversion_cp"))
        costo_por_resultado = _to_decimal(request.form.get("costo_por_resultado"))
        inversion = _to_decimal(request.form.get("inversion"))

        impresiones_raw = (request.form.get("impresiones") or "").strip()
        alcance_raw = (request.form.get("alcance") or "").strip()
        try:
            impresiones = int(impresiones_raw) if impresiones_raw else None
            alcance = int(alcance_raw) if alcance_raw else None
        except ValueError:
            flash("Impresiones y alcance deben ser enteros validos.", "danger")
            return redirect(url_for("marketing.marketing_campaigns"))

        if (
            not nombre_campana
            or not fecha_lanzamiento
            or not periodo_inicio
            or not periodo_fin
            or not producto
        ):
            flash(
                "Campana, producto, fecha de lanzamiento y periodo son obligatorios.",
                "warning",
            )
            return redirect(url_for("marketing.marketing_campaigns"))

        if canal not in CAMPAIGN_CHANNELS:
            flash("Selecciona un canal valido (Meta, Google Ads o Correo).", "warning")
            return redirect(url_for("marketing.marketing_campaigns"))

        if not line_selection:
            flash(
                "Selecciona linea de negocio, linea de familia y linea de producto desde las tablas vinculadas.",
                "warning",
            )
            return redirect(url_for("marketing.marketing_campaigns"))

        if periodo_fin < periodo_inicio:
            flash("El fin del periodo no puede ser menor al inicio.", "warning")
            return redirect(url_for("marketing.marketing_campaigns"))

        cur = mysql.connection.cursor()
        try:
            insert_columns = [
                "nombre_campana",
                "fecha_lanzamiento",
                "periodo_inicio",
                "periodo_fin",
                "linea_negocio",
                "linea_familia",
                "linea_producto",
                "producto",
                "canal",
            ]
            insert_values = [
                nombre_campana,
                fecha_lanzamiento,
                periodo_inicio,
                periodo_fin,
                linea_negocio,
                linea_familia,
                linea_producto,
                producto,
                canal,
            ]

            if _column_exists("marketing_campaigns", "conversion_cp"):
                insert_columns.append("conversion_cp")
                insert_values.append(conversion_cp)
            if _column_exists("marketing_campaigns", "costo_por_resultado"):
                insert_columns.append("costo_por_resultado")
                insert_values.append(costo_por_resultado)
            if _column_exists("marketing_campaigns", "inversion"):
                insert_columns.append("inversion")
                insert_values.append(inversion)
            if _column_exists("marketing_campaigns", "impresiones"):
                insert_columns.append("impresiones")
                insert_values.append(impresiones)
            if _column_exists("marketing_campaigns", "alcance"):
                insert_columns.append("alcance")
                insert_values.append(alcance)

            insert_columns.append("created_by")
            insert_values.append(session.get("user_id"))

            # Prefer storing negocio_id when the column exists (normalized FK).
            if _column_exists("marketing_campaigns", "negocio_id"):
                insert_columns.append("negocio_id")
                insert_values.append(negocio_id)
            # Fallback: keep existing `brand` column if present.
            elif _column_exists("marketing_campaigns", "brand"):
                insert_columns.append("brand")
                insert_values.append(brand)

            placeholders = ", ".join(["%s"] * len(insert_values))
            columns_sql = ", ".join(insert_columns)
            cur.execute(
                f"""
                INSERT INTO marketing_campaigns (
                    {columns_sql},
                    created_at,
                    updated_at
                ) VALUES ({placeholders}, NOW(), NOW())
                """,
                tuple(insert_values),
            )
            mysql.connection.commit()
            flash("Campana creada correctamente.", "success")
        except Exception as ex:
            mysql.connection.rollback()
            flash(f"No se pudo crear la campana: {ex}", "danger")
        finally:
            cur.close()

        return redirect(url_for("marketing.marketing_campaigns"))

    cur = mysql.connection.cursor(DictCursor)
    try:
        brand = request.cookies.get("brand") or "orbes"
        conversion_cp_select = (
            "c.conversion_cp AS conversion_cp"
            if _column_exists("marketing_campaigns", "conversion_cp")
            else "NULL AS conversion_cp"
        )
        costo_por_resultado_select = (
            "c.costo_por_resultado AS costo_por_resultado"
            if _column_exists("marketing_campaigns", "costo_por_resultado")
            else "NULL AS costo_por_resultado"
        )
        inversion_select = (
            "c.inversion AS inversion"
            if _column_exists("marketing_campaigns", "inversion")
            else "NULL AS inversion"
        )
        impresiones_select = (
            "c.impresiones AS impresiones"
            if _column_exists("marketing_campaigns", "impresiones")
            else "NULL AS impresiones"
        )
        alcance_select = (
            "c.alcance AS alcance"
            if _column_exists("marketing_campaigns", "alcance")
            else "NULL AS alcance"
        )
        # Try to resolve negocio_id from slug
        negocio_id = None
        try:
            nc = mysql.connection.cursor(DictCursor)
            try:
                nc.execute("SELECT id FROM negocios WHERE slug = %s LIMIT 1", (brand,))
                nr = nc.fetchone()
                negocio_id = nr.get("id") if nr else None
            finally:
                nc.close()
        except Exception:
            negocio_id = None

        # Prefer filtering by negocio_id when available (normalized FK)
        if _column_exists("marketing_campaigns", "negocio_id") and negocio_id:
            cur.execute(
                f"""
                SELECT
                    c.id,
                    c.nombre_campana,
                    c.fecha_lanzamiento,
                    c.periodo_inicio,
                    c.periodo_fin,
                    c.linea_negocio,
                    c.linea_familia,
                    c.linea_producto,
                    c.producto,
                    c.canal,
                    {conversion_cp_select},
                    {costo_por_resultado_select},
                    {inversion_select},
                    {impresiones_select},
                    {alcance_select},
                    c.created_at,
                    COALESCE(COUNT(mcl.id), 0) AS leads_vinculados
                FROM marketing_campaigns c
                LEFT JOIN marketing_campaign_leads mcl ON mcl.campaign_id = c.id
                WHERE c.negocio_id = %s
                GROUP BY c.id
                ORDER BY c.fecha_lanzamiento DESC, c.id DESC
                """,
                (negocio_id,),
            )
        elif _column_exists("marketing_campaigns", "brand"):
            cur.execute(
                f"""
                SELECT
                    c.id,
                    c.nombre_campana,
                    c.fecha_lanzamiento,
                    c.periodo_inicio,
                    c.periodo_fin,
                    c.linea_negocio,
                    c.linea_familia,
                    c.linea_producto,
                    c.producto,
                    c.canal,
                    {conversion_cp_select},
                    {costo_por_resultado_select},
                    {inversion_select},
                    {impresiones_select},
                    {alcance_select},
                    c.created_at,
                    COALESCE(COUNT(mcl.id), 0) AS leads_vinculados
                FROM marketing_campaigns c
                LEFT JOIN marketing_campaign_leads mcl ON mcl.campaign_id = c.id
                WHERE c.brand = %s
                GROUP BY c.id
                ORDER BY c.fecha_lanzamiento DESC, c.id DESC
                """,
                (brand,),
            )
        else:
            cur.execute(
                f"""
                SELECT
                    c.id,
                    c.nombre_campana,
                    c.fecha_lanzamiento,
                    c.periodo_inicio,
                    c.periodo_fin,
                    c.linea_negocio,
                    c.linea_familia,
                    c.linea_producto,
                    c.producto,
                    c.canal,
                    {conversion_cp_select},
                    {costo_por_resultado_select},
                    {inversion_select},
                    {impresiones_select},
                    {alcance_select},
                    c.created_at,
                    COALESCE(COUNT(mcl.id), 0) AS leads_vinculados
                FROM marketing_campaigns c
                LEFT JOIN marketing_campaign_leads mcl ON mcl.campaign_id = c.id
                GROUP BY c.id
                ORDER BY c.fecha_lanzamiento DESC, c.id DESC
                """,
            )
        campaigns = cur.fetchall() or []
    finally:
        cur.close()

    lineas_negocio = _get_lineas_negocio_options()

    return render_template(
        "marketing/campanas.html",
        canales=CAMPAIGN_CHANNELS,
        lineas_negocio=lineas_negocio,
        campaigns=campaigns,
    )


@marketing_bp.route("/campanas/<int:campaign_id>/editar", methods=["GET", "POST"])
@login_required
@role_required(ROLE_ADMIN, ROLE_GERENTE, ROLE_MARKETING)
def marketing_campaign_edit(campaign_id):
    """Editar una campaña existente"""
    fallback_return_url = url_for("marketing.marketing_campaigns")
    next_url = _safe_internal_next(request.values.get("next"), fallback_return_url)
    return_label = _marketing_return_label(next_url, "Volver")
    if request.method == "POST":
        nombre_campana = (request.form.get("nombre_campana") or "").strip()
        fecha_lanzamiento = (request.form.get("fecha_lanzamiento") or "").strip()
        periodo_inicio = (request.form.get("periodo_inicio") or "").strip()
        periodo_fin = (request.form.get("periodo_fin") or "").strip()
        linea_negocio_id = request.form.get("linea_negocio_id")
        linea_familia_id = request.form.get("linea_familia_id")
        linea_producto_id = request.form.get("linea_producto_id")
        producto = (request.form.get("producto") or "").strip()
        canal = (request.form.get("canal") or "").strip()

        line_selection = _resolve_line_selection(
            linea_negocio_id, linea_familia_id, linea_producto_id
        )
        linea_negocio = (line_selection or {}).get("linea_negocio")
        linea_familia = (line_selection or {}).get("linea_familia")
        linea_producto = (line_selection or {}).get("linea_producto")

        conversion_cp = _to_decimal(request.form.get("conversion_cp"))
        costo_por_resultado = _to_decimal(request.form.get("costo_por_resultado"))
        inversion = _to_decimal(request.form.get("inversion"))

        impresiones_raw = (request.form.get("impresiones") or "").strip()
        alcance_raw = (request.form.get("alcance") or "").strip()
        try:
            impresiones = int(impresiones_raw) if impresiones_raw else None
            alcance = int(alcance_raw) if alcance_raw else None
        except ValueError:
            flash("Impresiones y alcance deben ser enteros validos.", "danger")
            return redirect(
                url_for("marketing.marketing_campaign_edit", campaign_id=campaign_id)
            )

        if (
            not nombre_campana
            or not fecha_lanzamiento
            or not periodo_inicio
            or not periodo_fin
            or not producto
        ):
            flash("Campos obligatorios faltando.", "warning")
            return redirect(
                url_for("marketing.marketing_campaign_edit", campaign_id=campaign_id)
            )

        if canal not in CAMPAIGN_CHANNELS:
            flash("Selecciona un canal valido.", "warning")
            return redirect(
                url_for("marketing.marketing_campaign_edit", campaign_id=campaign_id)
            )

        if not line_selection:
            flash("Selecciona linea de negocio, familia y producto validos.", "warning")
            return redirect(
                url_for("marketing.marketing_campaign_edit", campaign_id=campaign_id)
            )

        if periodo_fin < periodo_inicio:
            flash("El fin del periodo no puede ser menor al inicio.", "warning")
            return redirect(
                url_for("marketing.marketing_campaign_edit", campaign_id=campaign_id)
            )

        cur = mysql.connection.cursor()
        try:
            set_parts = [
                "nombre_campana = %s",
                "fecha_lanzamiento = %s",
                "periodo_inicio = %s",
                "periodo_fin = %s",
                "linea_negocio = %s",
                "linea_familia = %s",
                "linea_producto = %s",
                "producto = %s",
                "canal = %s",
            ]
            update_values = [
                nombre_campana,
                fecha_lanzamiento,
                periodo_inicio,
                periodo_fin,
                linea_negocio,
                linea_familia,
                linea_producto,
                producto,
                canal,
            ]

            if _column_exists("marketing_campaigns", "conversion_cp"):
                set_parts.append("conversion_cp = %s")
                update_values.append(conversion_cp)
            if _column_exists("marketing_campaigns", "costo_por_resultado"):
                set_parts.append("costo_por_resultado = %s")
                update_values.append(costo_por_resultado)
            if _column_exists("marketing_campaigns", "inversion"):
                set_parts.append("inversion = %s")
                update_values.append(inversion)
            if _column_exists("marketing_campaigns", "impresiones"):
                set_parts.append("impresiones = %s")
                update_values.append(impresiones)
            if _column_exists("marketing_campaigns", "alcance"):
                set_parts.append("alcance = %s")
                update_values.append(alcance)

            set_parts.append("updated_at = NOW()")
            update_values.append(campaign_id)

            cur.execute(
                f"""
                UPDATE marketing_campaigns
                SET {", ".join(set_parts)}
                WHERE id = %s
                """,
                tuple(update_values),
            )
            mysql.connection.commit()
            flash(f"Campaña '{nombre_campana}' actualizada correctamente.", "success")
        except Exception as ex:
            mysql.connection.rollback()
            flash(f"No se pudo actualizar la campaña: {ex}", "danger")
        finally:
            cur.close()

        # After saving, stay on the same edit page. Preserve the safe next param so
        # the template can render a "Volver" button back to the origin.
        next_raw = request.form.get("next") or request.args.get("next")
        safe_next = _safe_internal_next(next_raw, fallback_return_url)
        return redirect(
            url_for(
                "marketing.marketing_campaign_edit",
                campaign_id=campaign_id,
                next=safe_next,
            )
        )

    # GET: mostrar formulario de edición
    cur = mysql.connection.cursor(DictCursor)
    try:
        cur.execute("SELECT * FROM marketing_campaigns WHERE id = %s", (campaign_id,))
        campaign = cur.fetchone()
    finally:
        cur.close()

    if not campaign:
        flash("Campaña no encontrada", "warning")
        return redirect(url_for("marketing.marketing_campaigns"))

    # Obtener IDs reales de familia y producto si existen, robusto
    familia_id = None
    producto_id = None
    linea_negocio_id = None
    lineas_negocio = _get_lineas_negocio_options()
    for ln in lineas_negocio:
        if ln["nombre"] == campaign.get("linea_negocio"):
            linea_negocio_id = ln["id"]
            break

    # Obtener todas las opciones de familia por línea de negocio
    familia_items = []
    if linea_negocio_id:
        familia_items = _get_linea_familia_options(linea_negocio_id)

    # Obtener todas las opciones de producto por línea de negocio (ignorar id_familia)
    producto_items = []
    if linea_negocio_id:
        producto_items = _get_linea_producto_options(linea_negocio_id)

    # Intentar resolver IDs de familia y producto actuales (si la campaña guarda los nombres)
    # para que el formulario de edición seleccione correctamente las opciones por ID.
    if familia_items:
        for f in familia_items:
            if f.get("nombre") == campaign.get("linea_familia"):
                familia_id = f.get("id")
                break

    if producto_items:
        for p in producto_items:
            if p.get("nombre") == campaign.get("linea_producto"):
                producto_id = p.get("id")
                break

    # lineas_negocio ya está definido arriba

    return render_template(
        "marketing/campana_edit.html",
        canales=CAMPAIGN_CHANNELS,
        lineas_negocio=lineas_negocio,
        linea_negocio_id=linea_negocio_id,
        campaign=campaign,
        familia_items=familia_items,
        producto_items=producto_items,
        familia_id=familia_id,
        producto_id=producto_id,
        next_url=next_url,
        return_label=return_label,
    )


@marketing_bp.route("/api/lineas-familia", methods=["GET"])
@login_required
@role_required(ROLE_ADMIN, ROLE_GERENTE, ROLE_MARKETING)
def marketing_lineas_familia_api():
    linea_negocio_id = request.args.get("linea_negocio_id")
    if not linea_negocio_id:
        return jsonify({"ok": True, "items": []}), 200
    if not _table_exists("linea_familia"):
        return (
            jsonify(
                {
                    "ok": False,
                    "message": "La tabla linea_familia no existe en la BD.",
                    "items": [],
                }
            ),
            200,
        )
    items = _get_linea_familia_options(linea_negocio_id)
    return jsonify({"ok": True, "items": items}), 200


@marketing_bp.route("/api/lineas-producto", methods=["GET"])
@login_required
@role_required(ROLE_ADMIN, ROLE_GERENTE, ROLE_MARKETING)
def marketing_lineas_producto_api():
    linea_negocio_id = request.args.get("linea_negocio_id")
    if not linea_negocio_id:
        return jsonify({"ok": True, "items": []}), 200
    if not _table_exists("linea_producto"):
        return (
            jsonify(
                {
                    "ok": False,
                    "message": "La tabla linea_producto no existe en la BD.",
                    "items": [],
                }
            ),
            200,
        )
    items = _get_linea_producto_options(linea_negocio_id)
    return jsonify({"ok": True, "items": items}), 200


@marketing_bp.route("/campanas/<int:campaign_id>/leads", methods=["GET", "POST"])
@login_required
@role_required(ROLE_ADMIN, ROLE_GERENTE, ROLE_MARKETING)
def marketing_campaign_leads(campaign_id):
    fallback_return_url = url_for("marketing.marketing_campaigns")
    next_url = _safe_internal_next(request.values.get("next"), fallback_return_url)
    return_label = _marketing_return_label(next_url, "Volver a Campanas")
    current_brand = (request.cookies.get("brand") or "orbes").strip().lower()

    if request.method == "POST":
        wants_json = request.headers.get("X-Requested-With") == "XMLHttpRequest"
        action = (request.form.get("action") or "").strip()
        replace_existing = request.form.get("replace_existing") == "1"
        user_id = session.get("user_id")

        cur = mysql.connection.cursor(DictCursor)
        try:
            cur.execute(
                """
                SELECT c.*
                FROM marketing_campaigns c
                WHERE id = %s
                """,
                (campaign_id,),
            )
            campaign = cur.fetchone()
        finally:
            cur.close()

        if not campaign:
            if wants_json:
                return (
                    jsonify(
                        {
                            "ok": False,
                            "message": "Campana no encontrada.",
                            "level": "warning",
                        }
                    ),
                    404,
                )
            flash("Campana no encontrada.", "warning")
            return redirect(url_for("marketing.marketing_campaigns"))

        if action == "desvincular":
            lead_id = request.form.get("lead_id")
            cur = mysql.connection.cursor()
            try:
                cur.execute(
                    "DELETE FROM marketing_campaign_leads WHERE campaign_id = %s AND lead_id = %s",
                    (campaign_id, lead_id),
                )
                mysql.connection.commit()
                if wants_json:
                    return (
                        jsonify(
                            {
                                "ok": True,
                                "message": "Lead desvinculado correctamente.",
                                "level": "success",
                            }
                        ),
                        200,
                    )
                flash("Lead desvinculado correctamente.", "success")
            except Exception as ex:
                mysql.connection.rollback()
                if wants_json:
                    return (
                        jsonify(
                            {
                                "ok": False,
                                "message": f"No se pudo desvincular el lead: {ex}",
                                "level": "danger",
                            }
                        ),
                        500,
                    )
                flash(f"No se pudo desvincular el lead: {ex}", "danger")
            finally:
                cur.close()
            return redirect(
                url_for(
                    "marketing.marketing_campaign_leads",
                    campaign_id=campaign_id,
                    next=next_url,
                )
            )

        if action == "desvincular_seleccion":
            unlink_ids = [x for x in request.form.getlist("unlink_ids") if x]
            if not unlink_ids:
                if wants_json:
                    return (
                        jsonify(
                            {
                                "ok": False,
                                "message": "Selecciona al menos un lead para desvincular.",
                                "level": "warning",
                            }
                        ),
                        400,
                    )
                flash("Selecciona al menos un lead para desvincular.", "warning")
                return redirect(
                    url_for(
                        "marketing.marketing_campaign_leads",
                        campaign_id=campaign_id,
                        next=next_url,
                    )
                )
            cur = mysql.connection.cursor()
            try:
                placeholders = ",".join(["%s"] * len(unlink_ids))
                cur.execute(
                    f"DELETE FROM marketing_campaign_leads WHERE campaign_id = %s AND lead_id IN ({placeholders})",
                    (campaign_id, *unlink_ids),
                )
                mysql.connection.commit()
                if wants_json:
                    return (
                        jsonify(
                            {
                                "ok": True,
                                "message": f"{cur.rowcount} lead(s) desvinculado(s) correctamente.",
                                "level": "success",
                            }
                        ),
                        200,
                    )
                flash(
                    f"{cur.rowcount} lead(s) desvinculado(s) correctamente.", "success"
                )
            except Exception as ex:
                mysql.connection.rollback()
                if wants_json:
                    return (
                        jsonify(
                            {
                                "ok": False,
                                "message": f"No se pudo desvincular: {ex}",
                                "level": "danger",
                            }
                        ),
                        500,
                    )
                flash(f"No se pudo desvincular: {ex}", "danger")
            finally:
                cur.close()
            return redirect(
                url_for(
                    "marketing.marketing_campaign_leads",
                    campaign_id=campaign_id,
                    next=next_url,
                )
            )

        target_negocio_id = _campaign_target_negocio_id(campaign, current_brand)

        selected_ids = [x for x in request.form.getlist("lead_ids") if x]
        if action == "vincular_seleccion" and not selected_ids:
            if wants_json:
                return (
                    jsonify(
                        {
                            "ok": False,
                            "message": "Selecciona al menos un lead para vincular.",
                            "level": "warning",
                        }
                    ),
                    400,
                )
            flash("Selecciona al menos un lead para vincular.", "warning")
            return redirect(
                url_for(
                    "marketing.marketing_campaign_leads",
                    campaign_id=campaign_id,
                    next=next_url,
                )
            )

        lead_ids_to_link = []
        if action == "vincular_seleccion":
            lead_ids_to_link = selected_ids
            if target_negocio_id:
                cur = mysql.connection.cursor(DictCursor)
                try:
                    placeholders = ",".join(["%s"] * len(lead_ids_to_link))
                    cur.execute(
                        f"""
                        SELECT l.id
                        FROM leads l
                        INNER JOIN usuarios ua ON ua.id = l.asignado_a
                        WHERE l.id IN ({placeholders})
                          AND ua.negocio_id = %s
                        """,
                        (*lead_ids_to_link, target_negocio_id),
                    )
                    lead_ids_to_link = [str(r["id"]) for r in (cur.fetchall() or [])]
                finally:
                    cur.close()
        elif action == "auto_periodo":
            q = (request.form.get("q") or "").strip()
            cur = mysql.connection.cursor(DictCursor)
            try:
                sql = """
                    SELECT l.id
                    FROM leads l
                    LEFT JOIN usuarios ua ON ua.id = l.asignado_a
                    LEFT JOIN bienes_servicios bs ON bs.id = l.bien_servicio_id
                    LEFT JOIN canales_recepcion cr_filter ON cr_filter.id = l.canal_id
                    LEFT JOIN marketing_campaign_leads mcl ON mcl.lead_id = l.id
                    WHERE l.fecha BETWEEN %s AND %s
                """
                params = [campaign["periodo_inicio"], campaign["periodo_fin"]]
                if campaign.get("canal"):
                    sql, params = _append_channel_filter(sql, params, campaign["canal"])
                if campaign.get("linea_negocio"):
                    sql += " AND bs.nombre = %s"
                    params.append(campaign["linea_negocio"])
                if target_negocio_id:
                    sql += " AND l.asignado_a IS NOT NULL AND ua.negocio_id = %s"
                    params.append(target_negocio_id)
                if q:
                    like = f"%{q}%"
                    sql += " AND (l.nombre LIKE %s OR COALESCE(l.ruc_dni, '') LIKE %s OR COALESCE(l.telefono, '') LIKE %s OR l.codigo LIKE %s)"
                    params.extend([like, like, like, like])
                if not replace_existing:
                    sql += " AND mcl.lead_id IS NULL"
                cur.execute(sql, tuple(params))
                lead_ids_to_link = [str(r["id"]) for r in (cur.fetchall() or [])]
            finally:
                cur.close()
        else:
            if wants_json:
                return (
                    jsonify(
                        {
                            "ok": False,
                            "message": "Accion no valida.",
                            "level": "warning",
                        }
                    ),
                    400,
                )
            flash("Accion no valida.", "warning")
            return redirect(
                url_for(
                    "marketing.marketing_campaign_leads",
                    campaign_id=campaign_id,
                    next=next_url,
                )
            )

        if not lead_ids_to_link:
            if wants_json:
                return (
                    jsonify(
                        {
                            "ok": False,
                            "message": "No hay leads para vincular con los filtros actuales.",
                            "level": "info",
                        }
                    ),
                    200,
                )
            flash("No hay leads para vincular con los filtros actuales.", "info")
            return redirect(
                url_for(
                    "marketing.marketing_campaign_leads",
                    campaign_id=campaign_id,
                    next=next_url,
                )
            )

        cur = mysql.connection.cursor()
        vinc_count = 0
        try:
            if replace_existing:
                for lead_id in lead_ids_to_link:
                    cur.execute(
                        """
                        INSERT INTO marketing_campaign_leads (campaign_id, lead_id, fecha_atribucion, metodo_atribucion, created_by, created_at)
                        VALUES (%s, %s, CURDATE(), %s, %s, NOW())
                        ON DUPLICATE KEY UPDATE
                            campaign_id = VALUES(campaign_id),
                            fecha_atribucion = VALUES(fecha_atribucion),
                            metodo_atribucion = VALUES(metodo_atribucion),
                            created_by = VALUES(created_by)
                        """,
                        (
                            campaign_id,
                            lead_id,
                            (
                                "periodo_automatico"
                                if action == "auto_periodo"
                                else "manual"
                            ),
                            user_id,
                        ),
                    )
                    vinc_count += 1
            else:
                for lead_id in lead_ids_to_link:
                    cur.execute(
                        """
                        INSERT IGNORE INTO marketing_campaign_leads (campaign_id, lead_id, fecha_atribucion, metodo_atribucion, created_by, created_at)
                        VALUES (%s, %s, CURDATE(), %s, %s, NOW())
                        """,
                        (
                            campaign_id,
                            lead_id,
                            (
                                "periodo_automatico"
                                if action == "auto_periodo"
                                else "manual"
                            ),
                            user_id,
                        ),
                    )
                    if cur.rowcount > 0:
                        vinc_count += 1

            mysql.connection.commit()
            if wants_json:
                return (
                    jsonify(
                        {
                            "ok": True,
                            "message": f"Leads vinculados: {vinc_count}",
                            "level": "success",
                        }
                    ),
                    200,
                )
            flash(f"Leads vinculados: {vinc_count}", "success")
        except Exception as ex:
            mysql.connection.rollback()
            if wants_json:
                return (
                    jsonify(
                        {
                            "ok": False,
                            "message": f"No se pudo vincular leads: {ex}",
                            "level": "danger",
                        }
                    ),
                    500,
                )
            flash(f"No se pudo vincular leads: {ex}", "danger")
        finally:
            cur.close()

        return redirect(
            url_for(
                "marketing.marketing_campaign_leads",
                campaign_id=campaign_id,
                next=next_url,
            )
        )

    q = (request.args.get("q") or "").strip()

    cur = mysql.connection.cursor(DictCursor)
    try:
        cur.execute(
            """
            SELECT
                c.*
            FROM marketing_campaigns c
            WHERE c.id = %s
            """,
            (campaign_id,),
        )
        campaign = cur.fetchone()
        if not campaign:
            flash("Campana no encontrada.", "warning")
            return redirect(url_for("marketing.marketing_campaigns"))

        target_negocio_id = _campaign_target_negocio_id(campaign, current_brand)

        cur.execute(
            """
            SELECT
                l.id,
                l.codigo,
                l.fecha,
                l.nombre,
                l.telefono,
                l.ruc_dni,
                bs.nombre AS bien_servicio_nombre,
                cr.nombre AS canal_nombre,
                n.nombre AS negocio_nombre,
                mcl.fecha_atribucion,
                mcl.metodo_atribucion
            FROM marketing_campaign_leads mcl
            INNER JOIN leads l ON l.id = mcl.lead_id
            LEFT JOIN usuarios ua ON ua.id = l.asignado_a
            LEFT JOIN negocios n ON n.id = ua.negocio_id
            LEFT JOIN bienes_servicios bs ON bs.id = l.bien_servicio_id
            LEFT JOIN canales_recepcion cr ON cr.id = l.canal_id
            WHERE mcl.campaign_id = %s
            ORDER BY mcl.fecha_atribucion DESC, l.id DESC
            """,
            (campaign_id,),
        )
        linked_leads = cur.fetchall() or []

        sql_candidates = """
            SELECT
                l.id,
                l.codigo,
                l.fecha,
                l.nombre,
                l.telefono,
                l.ruc_dni,
                bs.nombre AS bien_servicio_nombre,
                cr.nombre AS canal_nombre,
                n.nombre AS negocio_nombre,
                mcl.campaign_id AS linked_campaign_id,
                mc.nombre_campana AS linked_campaign_nombre
            FROM leads l
            LEFT JOIN usuarios ua ON ua.id = l.asignado_a
            LEFT JOIN negocios n ON n.id = ua.negocio_id
            LEFT JOIN bienes_servicios bs ON bs.id = l.bien_servicio_id
            LEFT JOIN canales_recepcion cr ON cr.id = l.canal_id
            LEFT JOIN canales_recepcion cr_filter ON cr_filter.id = l.canal_id
            LEFT JOIN marketing_campaign_leads mcl ON mcl.lead_id = l.id
            LEFT JOIN marketing_campaigns mc ON mc.id = mcl.campaign_id
            WHERE l.fecha BETWEEN %s AND %s
        """
        params = [campaign["periodo_inicio"], campaign["periodo_fin"]]
        if campaign.get("canal"):
            sql_candidates, params = _append_channel_filter(
                sql_candidates, params, campaign["canal"]
            )
        if q:
            like = f"%{q}%"
            sql_candidates += " AND (l.nombre LIKE %s OR COALESCE(l.ruc_dni, '') LIKE %s OR COALESCE(l.telefono, '') LIKE %s OR l.codigo LIKE %s)"
            params.extend([like, like, like, like])

        if campaign.get("linea_negocio"):
            sql_candidates += " AND bs.nombre = %s"
            params.append(campaign["linea_negocio"])
        if target_negocio_id:
            sql_candidates += " AND l.asignado_a IS NOT NULL AND ua.negocio_id = %s"
            params.append(target_negocio_id)

        cur.execute(
            f"SELECT COUNT(*) AS total FROM ({sql_candidates}) AS _cnt",
            tuple(params),
        )
        candidate_total = (cur.fetchone() or {}).get("total", 0)

        sql_candidates += " ORDER BY l.fecha DESC, l.id DESC LIMIT 500"
        cur.execute(sql_candidates, tuple(params))
        candidate_leads = cur.fetchall() or []
    finally:
        cur.close()

    return render_template(
        "marketing/campana_leads.html",
        campaign=campaign,
        canales=CAMPAIGN_CHANNELS,
        linked_leads=linked_leads,
        candidate_leads=candidate_leads,
        candidate_total=candidate_total,
        q=q,
        return_url=next_url,
        return_label=return_label,
    )


"Vista de resultados de campana: muestra KPIs clave, desglose por proceso, ingresos por moneda, cronologia de leads y lista detallada de leads vinculados a la campana."


@marketing_bp.route("/campanas/<int:campaign_id>/resultados", methods=["GET"])
@login_required
@role_required(ROLE_ADMIN, ROLE_GERENTE, ROLE_MARKETING)
def marketing_campaign_results(campaign_id):
    fallback_return_url = url_for("marketing.marketing_campaigns")
    return_url = _safe_internal_next(request.args.get("next"), fallback_return_url)
    return_label = _marketing_return_label(return_url, "Volver a Campanas")

    latest_seg = _latest_seguimiento_subquery()
    cur = mysql.connection.cursor(DictCursor)
    try:
        cur.execute(
            """
            SELECT *
            FROM marketing_campaigns
            WHERE id = %s
            """,
            (campaign_id,),
        )
        campaign = cur.fetchone()
        if not campaign:
            flash("Campana no encontrada.", "warning")
            return redirect(url_for("marketing.marketing_campaigns"))

        cur.execute(
            f"""
            SELECT
                COUNT(mcl.lead_id) AS total_leads,
                SUM(CASE WHEN LOWER(TRIM(COALESCE(p.nombre_proceso, ''))) = 'cerrado' THEN 1 ELSE 0 END) AS ventas_cerradas,
                SUM(CASE WHEN LOWER(TRIM(COALESCE(p.nombre_proceso, ''))) = 'cotizado' THEN 1 ELSE 0 END) AS cotizados,
                SUM(CASE WHEN LOWER(TRIM(COALESCE(p.nombre_proceso, ''))) = 'cerrado no vendido' THEN 1 ELSE 0 END) AS cerrados_no_vendidos,
                COALESCE(c.inversion, 0) AS inversion
            FROM marketing_campaigns c
            LEFT JOIN marketing_campaign_leads mcl ON mcl.campaign_id = c.id
            LEFT JOIN leads l ON l.id = mcl.lead_id
            LEFT JOIN ({latest_seg}) s ON s.lead_id = l.id
            LEFT JOIN proceso p ON p.id = s.proceso_id
            WHERE c.id = %s
            GROUP BY c.id, c.inversion
            """,
            (campaign_id,),
        )
        kpis = cur.fetchone() or {}

        cur.execute(
            f"""
            SELECT
                COALESCE(p.nombre_proceso, 'No iniciado') AS proceso,
                COUNT(*) AS total,
                SUM(CASE WHEN LOWER(TRIM(COALESCE(p.nombre_proceso, ''))) = 'cerrado' THEN COALESCE(s.monto, 0) ELSE 0 END) AS ingresos
            FROM marketing_campaign_leads mcl
            INNER JOIN leads l ON l.id = mcl.lead_id
            LEFT JOIN ({latest_seg}) s ON s.lead_id = l.id
            LEFT JOIN proceso p ON p.id = s.proceso_id
            WHERE mcl.campaign_id = %s
            GROUP BY COALESCE(p.nombre_proceso, 'No iniciado')
            ORDER BY total DESC, proceso ASC
            """,
            (campaign_id,),
        )
        proceso_breakdown = cur.fetchall() or []

        cur.execute(
            f"""
            SELECT
                COALESCE(m.nombre_moneda, 'Sin moneda') AS moneda,
                COUNT(*) AS ventas,
                SUM(COALESCE(s.monto, 0)) AS ingresos
            FROM marketing_campaign_leads mcl
            INNER JOIN leads l ON l.id = mcl.lead_id
            INNER JOIN ({latest_seg}) s ON s.lead_id = l.id
            INNER JOIN proceso p ON p.id = s.proceso_id
            LEFT JOIN moneda m ON m.id = s.moneda_id
            WHERE mcl.campaign_id = %s
              AND LOWER(TRIM(COALESCE(p.nombre_proceso, ''))) = 'cerrado'
            GROUP BY COALESCE(m.nombre_moneda, 'Sin moneda')
            ORDER BY ingresos DESC, moneda ASC
            """,
            (campaign_id,),
        )
        ingresos_por_moneda = cur.fetchall() or []

        cur.execute(
            f"""
            SELECT
                DATE_FORMAT(l.fecha, '%%Y-%%m') AS periodo,
                COUNT(*) AS leads,
                SUM(CASE WHEN LOWER(TRIM(COALESCE(p.nombre_proceso, ''))) = 'cerrado' THEN 1 ELSE 0 END) AS ventas,
                SUM(CASE WHEN LOWER(TRIM(COALESCE(p.nombre_proceso, ''))) = 'cerrado' THEN COALESCE(s.monto, 0) ELSE 0 END) AS ingresos
            FROM marketing_campaign_leads mcl
            INNER JOIN leads l ON l.id = mcl.lead_id
            LEFT JOIN ({latest_seg}) s ON s.lead_id = l.id
            LEFT JOIN proceso p ON p.id = s.proceso_id
            WHERE mcl.campaign_id = %s
            GROUP BY DATE_FORMAT(l.fecha, '%%Y-%%m')
            ORDER BY periodo ASC
            """,
            (campaign_id,),
        )
        timeline = cur.fetchall() or []

        cur.execute(
            f"""
            SELECT
                l.codigo,
                l.fecha,
                l.nombre,
                l.telefono,
                l.ruc_dni,
                bs.nombre AS bien_servicio_nombre,
                cr.nombre AS canal_nombre,
                u.nombre AS asesor_nombre,
                COALESCE(p.nombre_proceso, 'No iniciado') AS proceso_actual,
                s.fecha_guardado AS fecha_ultimo_movimiento,
                s.cotizacion,
                s.monto,
                m.nombre_moneda,
                s.comentario,
                mcl.fecha_atribucion,
                mcl.metodo_atribucion
            FROM marketing_campaign_leads mcl
            INNER JOIN leads l ON l.id = mcl.lead_id
            LEFT JOIN bienes_servicios bs ON bs.id = l.bien_servicio_id
            LEFT JOIN canales_recepcion cr ON cr.id = l.canal_id
            LEFT JOIN usuarios u ON u.id = l.asignado_a
            LEFT JOIN ({latest_seg}) s ON s.lead_id = l.id
            LEFT JOIN proceso p ON p.id = s.proceso_id
            LEFT JOIN moneda m ON m.id = s.moneda_id
            WHERE mcl.campaign_id = %s
            ORDER BY
                FIELD(LOWER(TRIM(COALESCE(p.nombre_proceso, 'no iniciado'))), 'cerrado', 'cotizado', 'programado', 'seguimiento', 'no iniciado', 'cerrado no vendido'),
                l.fecha DESC,
                l.id DESC
            """,
            (campaign_id,),
        )
        lead_results = cur.fetchall() or []
    finally:
        cur.close()

    total_leads = int(kpis.get("total_leads") or 0)
    ventas_cerradas = int(kpis.get("ventas_cerradas") or 0)
    cotizados = int(kpis.get("cotizados") or 0)
    cerrados_no_vendidos = int(kpis.get("cerrados_no_vendidos") or 0)
    conversion_rate = (ventas_cerradas / total_leads * 100) if total_leads else 0
    quote_rate = (cotizados / total_leads * 100) if total_leads else 0
    loss_rate = (cerrados_no_vendidos / total_leads * 100) if total_leads else 0
    financials = _campaign_financial_snapshot(kpis, ingresos_por_moneda)

    return render_template(
        "marketing/campana_resultados.html",
        campaign=campaign,
        canales=CAMPAIGN_CHANNELS,
        kpis=kpis,
        process_breakdown=proceso_breakdown,
        ingresos_por_moneda=ingresos_por_moneda,
        timeline=timeline,
        lead_results=lead_results,
        conversion_rate=conversion_rate,
        quote_rate=quote_rate,
        loss_rate=loss_rate,
        financials=financials,
        return_url=return_url,
        return_label=return_label,
    )


@marketing_bp.route("/campanas/<int:campaign_id>/delete/init", methods=["POST"])
@login_required
@role_required(ROLE_ADMIN, ROLE_GERENTE, ROLE_MARKETING)
def marketing_campaign_delete_init(campaign_id):
    """Inicia proceso seguro de borrado: devuelve token y cuenta de leads vinculados."""
    cur = mysql.connection.cursor(DictCursor)
    try:
        cur.execute(
            "SELECT id, nombre_campana FROM marketing_campaigns WHERE id = %s LIMIT 1",
            (campaign_id,),
        )
        campaign = cur.fetchone()
        if not campaign:
            return jsonify({"ok": False, "message": "Campaña no encontrada"}), 404
        cur.execute(
            "SELECT COUNT(*) AS total FROM marketing_campaign_leads WHERE campaign_id = %s",
            (campaign_id,),
        )
        linked = (cur.fetchone() or {}).get("total", 0)
    finally:
        cur.close()

    token = secrets.token_urlsafe(24)
    pending = session.get("pending_delete", {})
    key = f"campaign:{campaign_id}"
    pending[key] = {
        "token": token,
        "time": int(time.time()),
        "user_id": int(session.get("user_id") or 0),
    }
    session["pending_delete"] = pending
    return (
        jsonify(
            {
                "ok": True,
                "token": token,
                "linked_leads": int(linked or 0),
                "confirm_name": campaign.get("nombre_campana"),
            }
        ),
        200,
    )


@marketing_bp.route("/campanas/<int:campaign_id>/delete/confirm", methods=["POST"])
@login_required
@role_required(ROLE_ADMIN, ROLE_GERENTE, ROLE_MARKETING)
def marketing_campaign_delete_confirm(campaign_id):
    """Confirma y ejecuta borrado seguro de una campaña (token + confirm_name + password)."""
    data = request.get_json(silent=True) or request.form
    token = (data.get("token") or "").strip()
    confirm_name = (data.get("confirm_name") or "").strip()
    password = data.get("password") or ""
    force = str(data.get("force") or "").lower() in ("1", "true", "yes")

    pending = session.get("pending_delete", {})
    key = f"campaign:{campaign_id}"
    entry = pending.get(key) if isinstance(pending, dict) else None
    if (
        not entry
        or entry.get("token") != token
        or int(entry.get("user_id") or 0) != int(session.get("user_id") or 0)
    ):
        return jsonify({"ok": False, "message": "Token inválido o expirado"}), 400
    if int(time.time()) - int(entry.get("time") or 0) > 300:
        pending.pop(key, None)
        session["pending_delete"] = pending
        return jsonify({"ok": False, "message": "Token expirado"}), 400

    cur = mysql.connection.cursor(DictCursor)
    try:
        cur.execute(
            "SELECT id, nombre_campana FROM marketing_campaigns WHERE id = %s LIMIT 1",
            (campaign_id,),
        )
        campaign = cur.fetchone()
        if not campaign:
            return jsonify({"ok": False, "message": "Campaña no encontrada"}), 404
        if campaign.get("nombre_campana") != confirm_name:
            return (
                jsonify(
                    {"ok": False, "message": "El nombre de confirmación no coincide"}
                ),
                400,
            )

        # Verificar contraseña del usuario actual
        cur.execute(
            "SELECT id, password FROM usuarios WHERE id = %s LIMIT 1",
            (session.get("user_id"),),
        )
        u = cur.fetchone()
        if not u or not check_password(u.get("password") or "", password):
            return jsonify({"ok": False, "message": "Contraseña incorrecta"}), 403

        # Revisar leads vinculados y requerir flag 'force' si existen
        cur.execute(
            "SELECT COUNT(*) AS total FROM marketing_campaign_leads WHERE campaign_id = %s",
            (campaign_id,),
        )
        linked = int((cur.fetchone() or {}).get("total") or 0)
        if linked > 0 and not force:
            return (
                jsonify(
                    {
                        "ok": False,
                        "requires_force": True,
                        "linked_leads": linked,
                        "message": "Existen leads vinculados. Requiere fuerza para eliminar.",
                    }
                ),
                400,
            )

        # Ejecutar borrado: eliminar mapeos y la campaña
        try:
            cur2 = mysql.connection.cursor()
            try:
                if linked > 0:
                    cur2.execute(
                        "DELETE FROM marketing_campaign_leads WHERE campaign_id = %s",
                        (campaign_id,),
                    )
                cur2.execute(
                    "DELETE FROM marketing_campaigns WHERE id = %s", (campaign_id,)
                )
                mysql.connection.commit()
            finally:
                cur2.close()
        except Exception as ex:
            mysql.connection.rollback()
            return (
                jsonify({"ok": False, "message": f"Error al eliminar campaña: {ex}"}),
                500,
            )
    finally:
        cur.close()

    # Limpieza de token pendiente
    pending.pop(key, None)
    session["pending_delete"] = pending

    return (
        jsonify(
            {
                "ok": True,
                "message": "Campaña eliminada correctamente",
                "deleted_id": campaign_id,
            }
        ),
        200,
    )
