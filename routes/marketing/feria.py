from routes.marketing import (
    Decimal,
    DictCursor,
    ROLE_ADMIN,
    ROLE_GERENTE,
    ROLE_MARKETING,
    _column_exists,
    _resolve_ubigeo_name,
    _save_feria_kpi_snapshot,
    _table_exists,
    _to_decimal,
    flash,
    jsonify,
    login_required,
    marketing_bp,
    mysql,
    redirect,
    render_template,
    request,
    session,
    role_required,
    url_for,
)
from utils.security import check_password
import time
import secrets
from urllib.parse import urlsplit, parse_qsl, urlencode


def _resolve_negocio_id(brand_slug):
    if not _table_exists("negocios"):
        return None

    cur = mysql.connection.cursor(DictCursor)
    try:
        cur.execute("SELECT id FROM negocios WHERE slug = %s LIMIT 1", (brand_slug,))
        row = cur.fetchone() or {}
        return row.get("id")
    except Exception:
        return None
    finally:
        cur.close()


def _inventory_scope_where(brand_slug, negocio_id):
    if _column_exists("marketing_inventario_mercaderia", "negocio_id") and negocio_id:
        return "negocio_id = %s", [negocio_id]
    if _column_exists("marketing_inventario_mercaderia", "brand"):
        return "brand = %s", [brand_slug]
    return "1=1", []


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
    if path.startswith("/marketing/ferias"):
        return "Volver a Ferias"
    if path.startswith("/marketing/campanas"):
        return "Volver a Campanas Publicitarias"
    return fallback_label

# Rutas separadas: ferias de marketing
# ======================================================================
# RUTAS PARA FERIAS (MARKETING)
# ======================================================================

@marketing_bp.route("/ferias", methods=["GET", "POST"])
@login_required
@role_required(ROLE_ADMIN, ROLE_GERENTE, ROLE_MARKETING)
def marketing_ferias():
    """Lista de ferias con opcion de crear nuevas"""
    if request.method == "POST":
        # Brand chosen by the user (persisted in cookie). Default to 'orbes'.
        brand = request.cookies.get('brand') or 'orbes'
        # Resolve negocio_id from slug if possible
        negocio_id = None
        try:
            nc = mysql.connection.cursor(DictCursor)
            try:
                nc.execute("SELECT id FROM negocios WHERE slug = %s LIMIT 1", (brand,))
                nr = nc.fetchone()
                negocio_id = nr.get('id') if nr else None
            finally:
                nc.close()
        except Exception:
            negocio_id = None
        nombre = request.form.get("nombre_feria", "").strip()
        tipo = request.form.get("tipo", "").strip()
        detalles = request.form.get("detalles", "").strip()
        departamento_id = request.form.get("departamento_id", "").strip()
        provincia_id = request.form.get("provincia_id", "").strip()
        distrito_id = request.form.get("distrito_id", "").strip()

        # Compatibilidad por si aun llega texto directo desde formularios antiguos.
        departamento_txt = request.form.get("departamento", "").strip()
        provincia_txt = request.form.get("provincia", "").strip()
        distrito_txt = request.form.get("distrito", "").strip()

        departamento = _resolve_ubigeo_name("departamento", departamento_id or departamento_txt)
        provincia = _resolve_ubigeo_name("provincia", provincia_id or provincia_txt)
        distrito = _resolve_ubigeo_name("distrito", distrito_id or distrito_txt)
        fecha_inicio = request.form.get("fecha_inicio", "").strip()
        fecha_fin = request.form.get("fecha_fin", "").strip()

        # New: select a predefined tipo_gasto via combo box
        tipos_gastos_id_raw = request.form.get("tipos_gastos_id", "").strip() or None
        tipos_gastos_id = int(tipos_gastos_id_raw) if tipos_gastos_id_raw and tipos_gastos_id_raw.isdigit() else None

        # Legacy support: gastos arrays or individual inversion_* fields
        gasto_tipos = request.form.getlist("gasto_tipo") or request.form.getlist("gasto_tipo[]") or []
        gasto_facturas = request.form.getlist("gasto_factura") or request.form.getlist("gasto_factura[]") or []
        gasto_montos = request.form.getlist("gasto_monto") or request.form.getlist("gasto_monto[]") or []
        gasto_detalles = request.form.getlist("gasto_detalle") or request.form.getlist("gasto_detalle[]") or []
        gasto_mercaderia_ids = request.form.getlist("gasto_mercaderia_id") or request.form.getlist("gasto_mercaderia_id[]") or []
        gasto_cantidades = request.form.getlist("gasto_cantidad") or request.form.getlist("gasto_cantidad[]") or []
        gasto_precios = request.form.getlist("gasto_precio") or request.form.getlist("gasto_precio[]") or []

        if gasto_montos:
            total_inversion = sum((_to_decimal(m) or Decimal("0")) for m in gasto_montos)
        else:
            inversion_transporte = _to_decimal(request.form.get("inversion_transporte")) or Decimal("0")
            inversion_viaticos = _to_decimal(request.form.get("inversion_viaticos")) or Decimal("0")
            inversion_pagos = _to_decimal(request.form.get("inversion_pagos")) or Decimal("0")
            inversion_obsequios = _to_decimal(request.form.get("inversion_obsequios")) or Decimal("0")
            inversion_otros = _to_decimal(request.form.get("inversion_otros")) or Decimal("0")
            total_inversion = (
                inversion_transporte
                + inversion_viaticos
                + inversion_pagos
                + inversion_obsequios
                + inversion_otros
            )

        # If a tipos_gastos_id was selected: currently tipos_gastos is a lookup
        # that contains only `tipo_factura`. We do not override `total_inversion` here.

        factura_general = request.form.get("factura", "").strip() or None

        if not nombre or not fecha_inicio or not fecha_fin or not departamento or not provincia or not distrito:
            flash("Todos los campos son requeridos", "warning")
            return redirect(url_for("marketing.marketing_ferias"))

        has_extended_columns = all(
            _column_exists("marketing_ferias", col)
            for col in (
                "tipo",
                "detalles",
                "departamento",
                "provincia",
                "distrito",
                "total_inversion",
                "factura",
                "tipos_gastos_id",
            )
        )

        cur = mysql.connection.cursor()
        try:
            if has_extended_columns:
                # Prefer normalized FK when available
                if _column_exists('marketing_ferias', 'negocio_id'):
                    cur.execute(
                        """
                        INSERT INTO marketing_ferias (
                            nombre, tipo, detalles, departamento, provincia, distrito,
                            fecha_inicio, fecha_fin,
                            total_inversion, factura, tipos_gastos_id,
                            negocio_id,
                            activo
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1)
                        """,
                        (
                            nombre,
                            tipo or None,
                            detalles or None,
                            departamento,
                            provincia,
                            distrito,
                            fecha_inicio,
                            fecha_fin,
                            total_inversion,
                            factura_general,
                            tipos_gastos_id,
                            negocio_id,
                        ),
                    )
                elif _column_exists('marketing_ferias', 'brand'):
                    cur.execute(
                        """
                        INSERT INTO marketing_ferias (
                            nombre, tipo, detalles, departamento, provincia, distrito,
                            fecha_inicio, fecha_fin,
                            total_inversion, factura, tipos_gastos_id,
                            brand,
                            activo
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1)
                        """,
                        (
                            nombre,
                            tipo or None,
                            detalles or None,
                            departamento,
                            provincia,
                            distrito,
                            fecha_inicio,
                            fecha_fin,
                            total_inversion,
                            factura_general,
                            tipos_gastos_id,
                            brand,
                        ),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO marketing_ferias (
                            nombre, tipo, detalles, departamento, provincia, distrito,
                            fecha_inicio, fecha_fin,
                            total_inversion, factura, tipos_gastos_id,
                            activo
                        )
                        VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, %s, 1)
                        """,
                        (
                            nombre,
                            tipo or None,
                            detalles or None,
                            departamento,
                            provincia,
                            distrito,
                            fecha_inicio,
                            fecha_fin,
                            total_inversion,
                            factura_general,
                            tipos_gastos_id,
                        ),
                    )
                feria_id = cur.lastrowid
                # persist gastos if present
                gasto_tipos = request.form.getlist("gasto_tipo") or request.form.getlist("gasto_tipo[]") or []
                gasto_facturas = request.form.getlist("gasto_factura") or request.form.getlist("gasto_factura[]") or []
                gasto_montos = request.form.getlist("gasto_monto") or request.form.getlist("gasto_monto[]") or []
                gasto_detalles = request.form.getlist("gasto_detalle") or request.form.getlist("gasto_detalle[]") or []
                gasto_mercaderia_ids = request.form.getlist("gasto_mercaderia_id") or request.form.getlist("gasto_mercaderia_id[]") or []
                gasto_cantidades = request.form.getlist("gasto_cantidad") or request.form.getlist("gasto_cantidad[]") or []
                gasto_precios = request.form.getlist("gasto_precio") or request.form.getlist("gasto_precio[]") or []
                if _table_exists("marketing_feria_gastos"):
                    # Persist gasto rows (delete any leftover and insert new ones)
                    gcur = mysql.connection.cursor()
                    try:
                        gcur.execute("DELETE FROM marketing_feria_gastos WHERE feria_id = %s", (feria_id,))
                        max_rows = max(len(gasto_montos), len(gasto_tipos), len(gasto_facturas), len(gasto_detalles), len(gasto_mercaderia_ids))
                        for i in range(max_rows):
                            raw_tipo = gasto_tipos[i] if i < len(gasto_tipos) else ""
                            raw_factura = gasto_facturas[i] if i < len(gasto_facturas) else ""
                            raw_monto = gasto_montos[i] if i < len(gasto_montos) else ""
                            raw_detalle = gasto_detalles[i] if i < len(gasto_detalles) else ""
                            raw_mercaderia_id = gasto_mercaderia_ids[i] if i < len(gasto_mercaderia_ids) else ""
                            raw_cantidad = gasto_cantidades[i] if i < len(gasto_cantidades) else ""
                            raw_precio = gasto_precios[i] if i < len(gasto_precios) else ""
                            monto_dec = _to_decimal(raw_monto) or Decimal("0")
                            if raw_tipo == "Mercaderia":
                                if not raw_mercaderia_id or not raw_cantidad:
                                    continue
                                # Check stock
                                cur_check = mysql.connection.cursor(DictCursor)
                                try:
                                    cur_check.execute("SELECT cantidad FROM marketing_inventario_mercaderia WHERE id = %s", (raw_mercaderia_id,))
                                    stock_row = cur_check.fetchone()
                                    if not stock_row or stock_row['cantidad'] < int(raw_cantidad):
                                        flash(f"Stock insuficiente para el producto seleccionado.", "danger")
                                        return redirect(url_for("marketing.marketing_ferias"))
                                finally:
                                    cur_check.close()
                                # Set detalle to mercaderia_id:cantidad
                                raw_detalle = f"{raw_mercaderia_id}:{raw_cantidad}"
                                tipo_text = "Mercaderia"
                                tipos_gastos_id_val = None
                            else:
                                # Normal gasto
                                tipos_gastos_id_val = int(raw_tipo) if raw_tipo and str(raw_tipo).isdigit() else None
                                if tipos_gastos_id_val:
                                    tmp2 = mysql.connection.cursor(DictCursor)
                                    try:
                                        tmp2.execute("SELECT tipo_factura FROM tipos_gastos WHERE id = %s LIMIT 1", (tipos_gastos_id_val,))
                                        rowtg = tmp2.fetchone()
                                        tipo_text = rowtg.get("tipo_factura") if rowtg else None
                                    finally:
                                        tmp2.close()
                                else:
                                    tipo_text = raw_tipo or None
                            # skip empty rows
                            if (not tipo_text and not raw_factura and monto_dec == Decimal("0") and not raw_detalle):
                                continue
                            # Insert including detalle if the column exists
                            if _column_exists('marketing_feria_gastos', 'detalle'):
                                gcur.execute(
                                    "INSERT INTO marketing_feria_gastos (feria_id, tipos_gastos_id, tipo, factura, detalle, monto) VALUES (%s, %s, %s, %s, %s, %s)",
                                    (
                                        feria_id,
                                        tipos_gastos_id_val,
                                        tipo_text,
                                        raw_factura or None,
                                        raw_detalle or None,
                                        monto_dec,
                                    ),
                                )
                            else:
                                gcur.execute(
                                    "INSERT INTO marketing_feria_gastos (feria_id, tipos_gastos_id, tipo, factura, monto) VALUES (%s, %s, %s, %s, %s)",
                                    (
                                        feria_id,
                                        tipos_gastos_id_val,
                                        tipo_text,
                                        raw_factura or None,
                                        monto_dec,
                                    ),
                                )
                    finally:
                        gcur.close()
            else:
                if _column_exists('marketing_ferias', 'negocio_id'):
                    cur.execute(
                        """
                        INSERT INTO marketing_ferias (nombre, fecha_inicio, fecha_fin, negocio_id, activo)
                        VALUES (%s, %s, %s, %s, 1)
                        """,
                        (nombre, fecha_inicio, fecha_fin, negocio_id),
                    )
                elif _column_exists('marketing_ferias', 'brand'):
                    cur.execute(
                        """
                        INSERT INTO marketing_ferias (nombre, fecha_inicio, fecha_fin, brand, activo)
                        VALUES (%s, %s, %s, %s, 1)
                        """,
                        (nombre, fecha_inicio, fecha_fin, brand),
                    )
                else:
                    cur.execute(
                        """
                        INSERT INTO marketing_ferias (nombre, fecha_inicio, fecha_fin, activo)
                        VALUES (%s, %s, %s, 1)
                        """,
                        (nombre, fecha_inicio, fecha_fin),
                    )
            mysql.connection.commit()
            if not has_extended_columns:
                flash("Feria creada, pero faltan columnas nuevas. Ejecuta el script SQL final en servidor.", "warning")
            flash(f"Feria '{nombre}' creada exitosamente", "success")
        except Exception as e:
            mysql.connection.rollback()
            flash(f"Error al crear la feria: {e}", "danger")
        finally:
            cur.close()
        return redirect(url_for("marketing.marketing_ferias"))
    
    # GET: mostrar lista de ferias
    cur = mysql.connection.cursor(DictCursor)
    try:
        has_extended_columns = all(
            _column_exists("marketing_ferias", col)
            for col in (
                "tipo",
                "detalles",
                "departamento",
                "provincia",
                "distrito",
                "total_inversion",
                "factura",
                "tipos_gastos_id",
            )
        )

        # Obtener ferias con contador de leads vinculados
        brand = request.cookies.get('brand') or 'orbes'
        # Resolve negocio_id from slug
        negocio_id = None
        try:
            nc = mysql.connection.cursor(DictCursor)
            try:
                nc.execute("SELECT id FROM negocios WHERE slug = %s LIMIT 1", (brand,))
                nr = nc.fetchone()
                negocio_id = nr.get('id') if nr else None
            finally:
                nc.close()
        except Exception:
            negocio_id = None

        if has_extended_columns:
            if _column_exists('marketing_ferias', 'negocio_id') and negocio_id:
                cur.execute(
                    """
                    SELECT
                        f.id, f.nombre, f.tipo, f.detalles,
                        f.departamento, f.provincia, f.distrito,
                        f.fecha_inicio, f.fecha_fin, f.activo,
                        f.total_inversion,
                        COALESCE(COUNT(DISTINCT l.id), 0) AS leads_vinculados
                    FROM marketing_ferias f
                    LEFT JOIN leads l ON l.feria_id = f.id
                    WHERE f.negocio_id = %s
                    GROUP BY f.id
                    ORDER BY f.fecha_inicio DESC, f.nombre ASC
                    """,
                    (negocio_id,)
                )
            elif _column_exists('marketing_ferias', 'brand'):
                cur.execute(
                    """
                    SELECT
                        f.id, f.nombre, f.tipo, f.detalles,
                        f.departamento, f.provincia, f.distrito,
                        f.fecha_inicio, f.fecha_fin, f.activo,
                        f.total_inversion,
                        COALESCE(COUNT(DISTINCT l.id), 0) AS leads_vinculados
                    FROM marketing_ferias f
                    LEFT JOIN leads l ON l.feria_id = f.id
                    WHERE f.brand = %s
                    GROUP BY f.id
                    ORDER BY f.fecha_inicio DESC, f.nombre ASC
                    """,
                    (brand,)
                )
            else:
                cur.execute(
                    """
                    SELECT
                        f.id, f.nombre, f.tipo, f.detalles,
                        f.departamento, f.provincia, f.distrito,
                        f.fecha_inicio, f.fecha_fin, f.activo,
                        f.total_inversion,
                        COALESCE(COUNT(DISTINCT l.id), 0) AS leads_vinculados
                    FROM marketing_ferias f
                    LEFT JOIN leads l ON l.feria_id = f.id
                    GROUP BY f.id
                    ORDER BY f.fecha_inicio DESC, f.nombre ASC
                    """
                )
        else:
            if _column_exists('marketing_ferias', 'negocio_id') and negocio_id:
                cur.execute(
                    """
                    SELECT
                        f.id, f.nombre,
                        NULL AS tipo,
                        NULL AS detalles,
                        NULL AS departamento,
                        NULL AS provincia,
                        NULL AS distrito,
                        f.fecha_inicio, f.fecha_fin, f.activo,
                        0 AS total_inversion,
                        COALESCE(COUNT(DISTINCT l.id), 0) AS leads_vinculados
                    FROM marketing_ferias f
                    LEFT JOIN leads l ON l.feria_id = f.id
                    WHERE f.negocio_id = %s
                    GROUP BY f.id
                    ORDER BY f.fecha_inicio DESC, f.nombre ASC
                    """,
                    (negocio_id,)
                )
            elif _column_exists('marketing_ferias', 'brand'):
                cur.execute(
                    """
                    SELECT
                        f.id, f.nombre,
                        NULL AS tipo,
                        NULL AS detalles,
                        NULL AS departamento,
                        NULL AS provincia,
                        NULL AS distrito,
                        f.fecha_inicio, f.fecha_fin, f.activo,
                        0 AS total_inversion,
                        COALESCE(COUNT(DISTINCT l.id), 0) AS leads_vinculados
                    FROM marketing_ferias f
                    LEFT JOIN leads l ON l.feria_id = f.id
                    WHERE f.brand = %s
                    GROUP BY f.id
                    ORDER BY f.fecha_inicio DESC, f.nombre ASC
                    """,
                    (brand,)
                )
            else:
                cur.execute(
                    """
                    SELECT
                        f.id, f.nombre,
                        NULL AS tipo,
                        NULL AS detalles,
                        NULL AS departamento,
                        NULL AS provincia,
                        NULL AS distrito,
                        f.fecha_inicio, f.fecha_fin, f.activo,
                        0 AS total_inversion,
                        COALESCE(COUNT(DISTINCT l.id), 0) AS leads_vinculados
                    FROM marketing_ferias f
                    LEFT JOIN leads l ON l.feria_id = f.id
                    GROUP BY f.id
                    ORDER BY f.fecha_inicio DESC, f.nombre ASC
                    """
                )
        ferias = cur.fetchall() or []
    finally:
        cur.close()
    
    # cargar lista maestra de tipos de gasto para poblar combo box en el formulario
    tipos_gastos = []
    if _table_exists("tipos_gastos"):
        cur2 = mysql.connection.cursor(DictCursor)
        try:
            cur2.execute("SELECT id, tipo_factura FROM tipos_gastos ORDER BY tipo_factura")
            tipos_gastos = cur2.fetchall() or []
        finally:
            cur2.close()

    return render_template("marketing/ferias.html", ferias=ferias, tipos_gastos=tipos_gastos)


@marketing_bp.route("/ferias/<int:feria_id>/estado", methods=["POST"])
@login_required
@role_required(ROLE_ADMIN, ROLE_GERENTE, ROLE_MARKETING)
def marketing_feria_toggle_estado(feria_id):
    """Activa o desactiva una feria desde la lista."""
    wants_json = request.headers.get("X-Requested-With") == "XMLHttpRequest"

    cur = mysql.connection.cursor(DictCursor)
    try:
        cur.execute(
            """
            SELECT id, nombre, activo
            FROM marketing_ferias
            WHERE id = %s
            LIMIT 1
            """,
            (feria_id,),
        )
        feria = cur.fetchone()
    finally:
        cur.close()

    if not feria:
        if wants_json:
            return jsonify({"ok": False, "message": "Feria no encontrada"}), 404
        flash("Feria no encontrada", "warning")
        return redirect(url_for("marketing.marketing_ferias"))

    nuevo_estado = 0 if int(feria.get("activo") or 0) == 1 else 1

    cur = mysql.connection.cursor()
    try:
        cur.execute(
            "UPDATE marketing_ferias SET activo = %s WHERE id = %s",
            (nuevo_estado, feria_id),
        )
        mysql.connection.commit()
        estado_texto = "activada" if nuevo_estado == 1 else "desactivada"
        if wants_json:
            return jsonify(
                {
                    "ok": True,
                    "message": f"Feria '{feria.get('nombre')}' {estado_texto} correctamente",
                    "activo": nuevo_estado,
                    "feria_id": feria_id,
                }
            )
        flash(f"Feria '{feria.get('nombre')}' {estado_texto} correctamente", "success")
    except Exception as ex:
        mysql.connection.rollback()
        if wants_json:
            return jsonify({"ok": False, "message": f"No se pudo actualizar el estado de la feria: {ex}"}), 500
        flash(f"No se pudo actualizar el estado de la feria: {ex}", "danger")
    finally:
        cur.close()

    return redirect(url_for("marketing.marketing_ferias"))

@marketing_bp.route("/ferias/<int:feria_id>/editar", methods=["GET", "POST"])
@login_required
@role_required(ROLE_ADMIN, ROLE_GERENTE, ROLE_MARKETING)
def marketing_feria_edit(feria_id):
    """Editar una feria existente"""
    fallback_return_url = url_for("marketing.marketing_ferias")
    next_url = _safe_internal_next(request.values.get("next"), fallback_return_url)
    return_label = _marketing_return_label(next_url, "Volver")
    if request.method == "POST":
        nombre = request.form.get("nombre_feria", "").strip()
        tipo = request.form.get("tipo", "").strip()
        detalles = request.form.get("detalles", "").strip()
        departamento_id = request.form.get("departamento_id", "").strip()
        provincia_id = request.form.get("provincia_id", "").strip()
        distrito_id = request.form.get("distrito_id", "").strip()
        fecha_inicio = request.form.get("fecha_inicio", "").strip()
        fecha_fin = request.form.get("fecha_fin", "").strip()

        departamento = _resolve_ubigeo_name("departamento", departamento_id)
        provincia = _resolve_ubigeo_name("provincia", provincia_id)
        distrito = _resolve_ubigeo_name("distrito", distrito_id)

        # leer si se seleccionó un tipo de gasto predefinido
        tipos_gastos_id_raw = request.form.get("tipos_gastos_id", "").strip() or None
        tipos_gastos_id = int(tipos_gastos_id_raw) if tipos_gastos_id_raw and tipos_gastos_id_raw.isdigit() else None

        # leer gastos desde tabla: intento soportar nombres con o sin corchetes
        gasto_tipos = request.form.getlist("gasto_tipo") or request.form.getlist("gasto_tipo[]") or []
        gasto_facturas = request.form.getlist("gasto_factura") or request.form.getlist("gasto_factura[]") or []
        gasto_montos = request.form.getlist("gasto_monto") or request.form.getlist("gasto_monto[]") or []

        if gasto_montos:
            total_inversion = sum((_to_decimal(m) or Decimal("0")) for m in gasto_montos)
        else:
            # compatibilidad con campos antiguos
            inversion_transporte = _to_decimal(request.form.get("inversion_transporte")) or Decimal("0")
            inversion_viaticos = _to_decimal(request.form.get("inversion_viaticos")) or Decimal("0")
            inversion_pagos = _to_decimal(request.form.get("inversion_pagos")) or Decimal("0")
            inversion_obsequios = _to_decimal(request.form.get("inversion_obsequios")) or Decimal("0")
            inversion_otros = _to_decimal(request.form.get("inversion_otros")) or Decimal("0")
            total_inversion = (
                inversion_transporte
                + inversion_viaticos
                + inversion_pagos
                + inversion_obsequios
                + inversion_otros
            )

        # If a tipos_gastos_id was selected: tipos_gastos is a lookup table (id, tipo_factura).
        # Do not override `total_inversion` from the lookup.

        if not nombre or not fecha_inicio or not fecha_fin or not departamento or not provincia or not distrito:
            flash("Todos los campos obligatorios son requeridos", "warning")
            return redirect(url_for("marketing.marketing_feria_edit", feria_id=feria_id))

        cur = mysql.connection.cursor()
        try:
            # actualizar datos principales
            cur.execute(
                """
                UPDATE marketing_ferias
                SET nombre = %s, tipo = %s, detalles = %s,
                    departamento = %s, provincia = %s, distrito = %s,
                    fecha_inicio = %s, fecha_fin = %s,
                    total_inversion = %s, tipos_gastos_id = %s
                WHERE id = %s
                """,
                (
                    nombre, tipo or None, detalles or None,
                    departamento, provincia, distrito,
                    fecha_inicio, fecha_fin,
                    total_inversion,
                    tipos_gastos_id,
                    feria_id,
                ),
            )
            # persist gastos if table exists: delete previous and insert new rows
            if _table_exists("marketing_feria_gastos"):
                gasto_tipos = request.form.getlist("gasto_tipo") or request.form.getlist("gasto_tipo[]") or []
                gasto_facturas = request.form.getlist("gasto_factura") or request.form.getlist("gasto_factura[]") or []
                gasto_montos = request.form.getlist("gasto_monto") or request.form.getlist("gasto_monto[]") or []
                gasto_detalles = request.form.getlist("gasto_detalle") or request.form.getlist("gasto_detalle[]") or []
                gasto_mercaderia_ids = request.form.getlist("gasto_mercaderia_id") or request.form.getlist("gasto_mercaderia_id[]") or []
                gasto_cantidades = request.form.getlist("gasto_cantidad") or request.form.getlist("gasto_cantidad[]") or []
                gasto_precios = request.form.getlist("gasto_precio") or request.form.getlist("gasto_precio[]") or []
                gcur = mysql.connection.cursor()
                try:
                    gcur.execute("DELETE FROM marketing_feria_gastos WHERE feria_id = %s", (feria_id,))
                    max_rows = max(len(gasto_montos), len(gasto_tipos), len(gasto_facturas), len(gasto_detalles), len(gasto_mercaderia_ids))
                    for i in range(max_rows):
                        raw_tipo = gasto_tipos[i] if i < len(gasto_tipos) else ""
                        raw_factura = gasto_facturas[i] if i < len(gasto_facturas) else ""
                        raw_monto = gasto_montos[i] if i < len(gasto_montos) else ""
                        raw_detalle = gasto_detalles[i] if i < len(gasto_detalles) else ""
                        raw_mercaderia_id = gasto_mercaderia_ids[i] if i < len(gasto_mercaderia_ids) else ""
                        raw_cantidad = gasto_cantidades[i] if i < len(gasto_cantidades) else ""
                        raw_precio = gasto_precios[i] if i < len(gasto_precios) else ""
                        monto_dec = _to_decimal(raw_monto) or Decimal("0")
                        if raw_tipo == "Mercaderia":
                            if not raw_mercaderia_id or not raw_cantidad:
                                continue
                            # Check stock
                            cur_check = mysql.connection.cursor(DictCursor)
                            try:
                                cur_check.execute("SELECT cantidad FROM marketing_inventario_mercaderia WHERE id = %s", (raw_mercaderia_id,))
                                stock_row = cur_check.fetchone()
                                if not stock_row or stock_row['cantidad'] < int(raw_cantidad):
                                    flash(f"Stock insuficiente para el producto seleccionado.", "danger")
                                    return redirect(url_for("marketing.marketing_feria_edit", feria_id=feria_id))
                            finally:
                                cur_check.close()
                            # Set detalle to mercaderia_id:cantidad
                            raw_detalle = f"{raw_mercaderia_id}:{raw_cantidad}"
                            tipo_text = "Mercaderia"
                            tipos_gastos_id_val = None
                        else:
                            # Normal gasto
                            tipos_gastos_id_val = int(raw_tipo) if raw_tipo and str(raw_tipo).isdigit() else None
                            if tipos_gastos_id_val:
                                tmp2 = mysql.connection.cursor(DictCursor)
                                try:
                                    tmp2.execute("SELECT tipo_factura FROM tipos_gastos WHERE id = %s LIMIT 1", (tipos_gastos_id_val,))
                                    rowtg = tmp2.fetchone()
                                    tipo_text = rowtg.get("tipo_factura") if rowtg else None
                                finally:
                                    tmp2.close()
                            else:
                                tipo_text = raw_tipo or None
                        if (not tipo_text and not raw_factura and monto_dec == Decimal("0") and not raw_detalle):
                            continue
                        # Insert including detalle if available
                        if _column_exists('marketing_feria_gastos', 'detalle'):
                            gcur.execute(
                                "INSERT INTO marketing_feria_gastos (feria_id, tipos_gastos_id, tipo, factura, detalle, monto) VALUES (%s, %s, %s, %s, %s, %s)",
                                (
                                    feria_id,
                                    tipos_gastos_id_val,
                                    tipo_text,
                                    raw_factura or None,
                                    raw_detalle or None,
                                    monto_dec,
                                ),
                            )
                        else:
                            gcur.execute(
                                "INSERT INTO marketing_feria_gastos (feria_id, tipos_gastos_id, tipo, factura, monto) VALUES (%s, %s, %s, %s, %s)",
                                (
                                    feria_id,
                                    tipos_gastos_id_val,
                                    tipo_text,
                                    raw_factura or None,
                                    monto_dec,
                                ),
                            )
                    # Deduct inventory for mercaderia
                    for i in range(max_rows):
                        if gasto_tipos[i] == "Mercaderia" and i < len(gasto_mercaderia_ids) and i < len(gasto_cantidades):
                            mercaderia_id = gasto_mercaderia_ids[i]
                            cantidad = int(gasto_cantidades[i])
                            gcur.execute("UPDATE marketing_inventario_mercaderia SET cantidad = cantidad - %s WHERE id = %s", (cantidad, mercaderia_id))
                finally:
                    gcur.close()

            mysql.connection.commit()
            flash(f"Feria '{nombre}' actualizada exitosamente", "success")
        except Exception as e:
            mysql.connection.rollback()
            flash(f"Error al actualizar la feria: {e}", "danger")
        finally:
            cur.close()
        # Stay on the same edit page after saving, preserve next param for the Volver button
        next_raw = request.form.get("next") or request.args.get("next")
        safe_next = _safe_internal_next(next_raw, fallback_return_url)
        return redirect(url_for("marketing.marketing_feria_edit", feria_id=feria_id, next=safe_next))

    # GET: mostrar formulario de edición
    cur = mysql.connection.cursor(DictCursor)
    try:
        cur.execute("SELECT * FROM marketing_ferias WHERE id = %s", (feria_id,))
        feria = cur.fetchone()
    finally:
        cur.close()

    if not feria:
        flash("Feria no encontrada", "warning")
        return redirect(url_for("marketing.marketing_ferias"))

    # obtener lista maestra de tipos_gastos para poblar combo box en el formulario
    tipos_gastos = []
    if _table_exists("tipos_gastos"):
        cur = mysql.connection.cursor(DictCursor)
        try:
            cur.execute("SELECT id, tipo_factura FROM tipos_gastos ORDER BY tipo_factura")
            tipos_gastos = cur.fetchall() or []
        finally:
            cur.close()

    # obtener inventario disponible
    brand = request.cookies.get("brand") or "orbes"
    negocio_id = _resolve_negocio_id(brand)
    scope_where, scope_params = _inventory_scope_where(brand, negocio_id)
    inventory_rows = []
    if _table_exists("marketing_inventario_mercaderia"):
        cur = mysql.connection.cursor(DictCursor)
        try:
            cur.execute(
                f"""
                SELECT
                    id,
                    producto,
                    precio,
                    cantidad
                FROM marketing_inventario_mercaderia
                WHERE {scope_where} AND cantidad > 0
                ORDER BY producto
                """,
                tuple(scope_params),
            )
            inventory_rows = cur.fetchall() or []
        finally:
            cur.close()

    # Preparar datos iniciales para los desgloses (editar): preferimos leer filas
    # desde marketing_feria_gastos si la tabla existe; si no, mostramos la fila
    # fallback usando feria.factura y feria.total_inversion.
    initial_gastos = []
    try:
        if _table_exists("marketing_feria_gastos"):
            gcur = mysql.connection.cursor(DictCursor)
            try:
                # Select detalle column only if present
                if _column_exists('marketing_feria_gastos', 'detalle'):
                    gcur.execute(
                        "SELECT tipos_gastos_id, tipo, factura, detalle, monto FROM marketing_feria_gastos WHERE feria_id = %s ORDER BY id ASC",
                        (feria_id,),
                    )
                    rows = gcur.fetchall() or []
                    for r in rows:
                        tipo_val = r.get("tipos_gastos_id") if r.get("tipos_gastos_id") is not None else (r.get("tipo") or "")
                        initial_gastos.append({
                            "tipo": str(tipo_val) if tipo_val is not None else "",
                            "factura": r.get("factura") or "",
                            "detalle": r.get("detalle") or "",
                            "monto": float(r.get("monto") or 0),
                        })
                else:
                    gcur.execute(
                        "SELECT tipos_gastos_id, tipo, factura, monto FROM marketing_feria_gastos WHERE feria_id = %s ORDER BY id ASC",
                        (feria_id,),
                    )
                    rows = gcur.fetchall() or []
                    for r in rows:
                        tipo_val = r.get("tipos_gastos_id") if r.get("tipos_gastos_id") is not None else (r.get("tipo") or "")
                        initial_gastos.append({
                            "tipo": str(tipo_val) if tipo_val is not None else "",
                            "factura": r.get("factura") or "",
                            "detalle": "",
                            "monto": float(r.get("monto") or 0),
                        })
            finally:
                gcur.close()
        else:
            # Fallback single row
            initial_gastos.append({
                "tipo": str(feria.get("tipos_gastos_id")) if feria.get("tipos_gastos_id") else "",
                "factura": feria.get("factura") or "",
                "detalle": "",
                "monto": float(feria.get("total_inversion") or 0),
            })
    except Exception:
        initial_gastos = []

    return render_template(
        "marketing/feria_edit.html",
        feria=feria,
        tipos_gastos=tipos_gastos,
        initial_gastos=initial_gastos,
        inventory_rows=inventory_rows,
        UBIGEO_API={"departamentos": "/api/ubigeo/departamentos"},
        next_url=next_url,
        return_label=return_label,
    )

@marketing_bp.route("/ferias/<int:feria_id>/campo", methods=["POST"])
@login_required
@role_required(ROLE_ADMIN, ROLE_GERENTE, ROLE_MARKETING)
def marketing_feria_update_campo(feria_id):
    """Actualiza un campo específico de la feria via AJAX"""
    campo = request.form.get("campo", "").strip()
    valor = request.form.get("valor", "").strip()

    campos_permitidos = ["nombre", "tipo", "detalles"]
    if campo not in campos_permitidos:
        return jsonify({"ok": False, "message": "Campo no permitido"}), 400

    if not valor:
        return jsonify({"ok": False, "message": f"El campo {campo} no puede estar vacío"}), 400

    cur = mysql.connection.cursor(DictCursor)
    try:
        cur.execute("SELECT id, nombre FROM marketing_ferias WHERE id = %s", (feria_id,))
        feria = cur.fetchone()
    finally:
        cur.close()

    if not feria:
        return jsonify({"ok": False, "message": "Feria no encontrada"}), 404

    cur = mysql.connection.cursor()
    try:
        cur.execute(f"UPDATE marketing_ferias SET {campo} = %s WHERE id = %s", (valor, feria_id))
        mysql.connection.commit()
        return jsonify({"ok": True, "message": "Feria actualizada correctamente", "value": valor}), 200
    except Exception as ex:
        mysql.connection.rollback()
        return jsonify({"ok": False, "message": f"Error al actualizar: {ex}"}), 500
    finally:
        cur.close()


@marketing_bp.route("/ferias/<int:feria_id>/leads", methods=["GET"])
@login_required
@role_required(ROLE_ADMIN, ROLE_GERENTE, ROLE_MARKETING)
def marketing_feria_leads(feria_id):
    """Vista de leads vinculados a una feria"""
    fallback_return_url = url_for("marketing.marketing_ferias")
    return_url = _safe_internal_next(request.args.get("next"), fallback_return_url)
    return_label = _marketing_return_label(return_url, "Volver a Ferias")

    has_extended_columns = all(
        _column_exists("marketing_ferias", col)
        for col in (
            "tipo",
            "detalles",
            "departamento",
            "provincia",
            "distrito",
            "total_inversion",
            "factura",
        )
    )

    cur = mysql.connection.cursor(DictCursor)
    try:
        # Obtener datos de la feria
        if has_extended_columns:
            cur.execute(
                """
                SELECT
                    id, nombre, tipo, detalles, departamento, provincia, distrito,
                    fecha_inicio, fecha_fin,
                    COALESCE(total_inversion, 0) AS total_inversion,
                    factura
                FROM marketing_ferias
                WHERE id = %s
                """,
                (feria_id,),
            )
        else:
            cur.execute(
                """
                SELECT
                    id,
                    nombre,
                    NULL AS tipo,
                    NULL AS detalles,
                    NULL AS departamento,
                    NULL AS provincia,
                    NULL AS distrito,
                    fecha_inicio,
                    fecha_fin,
                    0 AS total_inversion,
                    NULL AS factura
                FROM marketing_ferias
                WHERE id = %s
                """,
                (feria_id,),
            )
        feria = cur.fetchone()
    finally:
        cur.close()
    
    if not feria:
        flash("Feria no encontrada", "warning")
        return redirect(url_for("marketing.marketing_ferias"))
    
    # Obtener leads vinculados
    cur = mysql.connection.cursor(DictCursor)
    try:
        latest_seg = """
            SELECT s1.lead_id, s1.proceso_id, s1.fecha_guardado, s1.monto, s1.moneda_id, s1.comentario, s1.cotizacion
            FROM seguimientos s1
            INNER JOIN (
                SELECT lead_id, MAX(id) as max_id
                FROM seguimientos
                GROUP BY lead_id
            ) s2 ON s1.id = s2.max_id AND s1.lead_id = s2.lead_id
        """
        
        cur.execute(
            f"""
            SELECT
                l.id, l.codigo, l.nombre, l.telefono, l.ruc_dni,
                bs.nombre AS bien_servicio_nombre,
                cr.nombre AS canal_nombre,
                u.nombre AS asesor_nombre,
                COALESCE(p.nombre_proceso, 'No iniciado') AS proceso_actual,
                s.fecha_guardado,
                s.monto, s.moneda_id, m.nombre_moneda,
                s.comentario
            FROM leads l
            LEFT JOIN bienes_servicios bs ON bs.id = l.bien_servicio_id
            LEFT JOIN canales_recepcion cr ON cr.id = l.canal_id
            LEFT JOIN usuarios u ON u.id = l.asignado_a
            LEFT JOIN ({latest_seg}) s ON s.lead_id = l.id
            LEFT JOIN proceso p ON p.id = s.proceso_id
            LEFT JOIN moneda m ON m.id = s.moneda_id
            WHERE l.feria_id = %s
            ORDER BY s.fecha_guardado DESC, l.fecha DESC
            """,
            (feria_id,),
        )
        leads = cur.fetchall() or []
    finally:
        cur.close()
    
    # Estadisticas
    total_leads = len(leads)
    leads_por_proceso = {}
    ingresos_total = 0
    
    for lead in leads:
        proceso = lead.get("proceso_actual") or "No iniciado"
        leads_por_proceso[proceso] = leads_por_proceso.get(proceso, 0) + 1
        
        if lead.get("monto"):
            ingresos_total += float(lead["monto"] or 0)
    
    stats = {
        "total_leads": total_leads,
        "leads_por_proceso": leads_por_proceso,
        "ingresos_total": ingresos_total,
    }
    
    return render_template(
        "marketing/feria_leads.html",
        feria=feria,
        leads=leads,
        stats=stats,
        return_url=return_url,
        return_label=return_label,
    )


@marketing_bp.route("/ferias/<int:feria_id>/resultados", methods=["GET"])
@login_required
@role_required(ROLE_ADMIN, ROLE_GERENTE, ROLE_MARKETING)
def marketing_feria_resultados(feria_id):
    """Vista de resultados de una feria"""
    fallback_return_url = url_for("marketing.marketing_ferias")
    return_url = _safe_internal_next(request.args.get("next"), fallback_return_url)
    return_label = _marketing_return_label(return_url, "Volver a Ferias")

    has_extended_columns = all(
        _column_exists("marketing_ferias", col)
        for col in (
            "tipo",
            "detalles",
            "departamento",
            "provincia",
            "distrito",
            "total_inversion",
            "factura",
        )
    )

    cur = mysql.connection.cursor(DictCursor)
    try:
        if has_extended_columns:
            cur.execute(
                """
                SELECT
                    id, nombre, tipo, detalles, departamento, provincia, distrito,
                    fecha_inicio, fecha_fin,
                    COALESCE(total_inversion, 0) AS total_inversion,
                    factura
                FROM marketing_ferias
                WHERE id = %s
                """,
                (feria_id,),
            )
        else:
            cur.execute(
                """
                SELECT
                    id,
                    nombre,
                    NULL AS tipo,
                    NULL AS detalles,
                    NULL AS departamento,
                    NULL AS provincia,
                    NULL AS distrito,
                    fecha_inicio,
                    fecha_fin,
                    0 AS total_inversion,
                    NULL AS factura
                FROM marketing_ferias
                WHERE id = %s
                """,
                (feria_id,),
            )
        feria = cur.fetchone()
    finally:
        cur.close()
    
    if not feria:
        flash("Feria no encontrada", "warning")
        return redirect(url_for("marketing.marketing_ferias"))

    # obtener tipo_gasto seleccionado (si aplica)
    tipo_gasto = None
    if _table_exists("tipos_gastos") and feria.get("tipos_gastos_id"):
        cur = mysql.connection.cursor(DictCursor)
        try:
            cur.execute("SELECT id, tipo_factura FROM tipos_gastos WHERE id = %s LIMIT 1", (feria.get("tipos_gastos_id"),))
            tipo_gasto = cur.fetchone()
        finally:
            cur.close()

    # Obtener KPIs de la feria
    cur = mysql.connection.cursor(DictCursor)
    try:
        latest_seg = """
            SELECT s1.lead_id, s1.proceso_id, s1.monto, s1.moneda_id
            FROM seguimientos s1
            INNER JOIN (
                SELECT lead_id, MAX(id) as max_id
                FROM seguimientos
                GROUP BY lead_id
            ) s2 ON s1.id = s2.max_id AND s1.lead_id = s2.lead_id
        """
        
        cur.execute(
            f"""
            SELECT
                COALESCE(p.nombre_proceso, 'No iniciado') AS proceso_actual,
                COUNT(DISTINCT l.id) AS total,
                COALESCE(SUM(s.monto), 0) AS monto_total
            FROM leads l
            LEFT JOIN ({latest_seg}) s ON s.lead_id = l.id
            LEFT JOIN proceso p ON p.id = s.proceso_id
            WHERE l.feria_id = %s
            GROUP BY p.id
            ORDER BY total DESC
            """,
            (feria_id,),
        )
        kpis_by_process = cur.fetchall() or []
    finally:
        cur.close()
    
    # Procesar datos
    total_leads = sum(int(k["total"] or 0) for k in kpis_by_process)
    cerrados = sum(int(k["total"] or 0) for k in kpis_by_process if "cerrado" in str(k.get("proceso_actual") or "").lower() and "no" not in str(k.get("proceso_actual") or "").lower())
    ingresos = sum(float(k["monto_total"] or 0) for k in kpis_by_process)
    
    conversion_rate = (cerrados / total_leads * 100) if total_leads else 0

    # Persistencia historica (snapshot diario) para analisis futuro.
    _save_feria_kpi_snapshot(feria_id, total_leads, cerrados, ingresos)
    
    # Obtener gastos persistidos por feria (si aplica)
    gastos = []
    if _table_exists("marketing_feria_gastos"):
        curg = mysql.connection.cursor(DictCursor)
        try:
            # Include detalle column if available
            if _column_exists('marketing_feria_gastos', 'detalle'):
                curg.execute(
                    """
                    SELECT mfg.id, mfg.tipos_gastos_id, COALESCE(tg.tipo_factura, mfg.tipo) AS tipo, mfg.factura, mfg.detalle, mfg.monto
                    FROM marketing_feria_gastos mfg
                    LEFT JOIN tipos_gastos tg ON tg.id = mfg.tipos_gastos_id
                    WHERE mfg.feria_id = %s
                    ORDER BY mfg.id ASC
                    """,
                    (feria_id,),
                )
            else:
                curg.execute(
                    """
                    SELECT mfg.id, mfg.tipos_gastos_id, COALESCE(tg.tipo_factura, mfg.tipo) AS tipo, mfg.factura, mfg.monto
                    FROM marketing_feria_gastos mfg
                    LEFT JOIN tipos_gastos tg ON tg.id = mfg.tipos_gastos_id
                    WHERE mfg.feria_id = %s
                    ORDER BY mfg.id ASC
                    """,
                    (feria_id,),
                )
            gastos = curg.fetchall() or []
        finally:
            curg.close()
    
    return render_template(
        "marketing/feria_resultados.html",
        feria=feria,
        tipo_gasto=tipo_gasto,
        kpis_by_process=kpis_by_process,
        total_leads=total_leads,
        cerrados=cerrados,
        ingresos=ingresos,
        conversion_rate=conversion_rate,
        gastos=gastos,
        return_url=return_url,
        return_label=return_label,
    )


# API: obtener ferias activas en un periodo
@marketing_bp.route("/api/ferias-activas", methods=["GET"])
@login_required
def marketing_ferias_activas_api():
    """
    Endpoint para obtener ferias activas en un periodo
    Parametros query:
    - periodo_inicio: YYYY-MM-DD
    - periodo_fin: YYYY-MM-DD
    """
    try:
        periodo_inicio = request.args.get("periodo_inicio", "").strip()
        periodo_fin = request.args.get("periodo_fin", "").strip()
        
        if not periodo_inicio or not periodo_fin:
            return jsonify([]), 200
        
        if not _table_exists("marketing_ferias"):
            return jsonify([]), 200
        
        cur = mysql.connection.cursor(DictCursor)
        try:
            sql = """
                SELECT id, nombre, fecha_inicio, fecha_fin 
                FROM marketing_ferias 
                WHERE activo = 1 
                AND fecha_inicio <= %s 
                AND fecha_fin >= %s
                ORDER BY fecha_inicio ASC, nombre ASC
            """
            cur.execute(sql, (periodo_fin, periodo_inicio))
            ferias = cur.fetchall() or []
            
            return jsonify([
                {
                    "id": f["id"],
                    "nombre": f["nombre"],
                    "fecha_inicio": str(f["fecha_inicio"]),
                    "fecha_fin": str(f["fecha_fin"])
                }
                for f in ferias
            ]), 200
        finally:
            cur.close()
    except Exception as e:
        print(f"Error en marketing_ferias_activas_api: {e}")
        return jsonify({"error": "Error al obtener ferias"}), 500


@marketing_bp.route("/ferias/<int:feria_id>/delete/init", methods=["POST"])
@login_required
@role_required(ROLE_ADMIN, ROLE_GERENTE, ROLE_MARKETING)
def marketing_feria_delete_init(feria_id):
    """Inicia proceso seguro de borrado para ferias: devuelve token y cuenta de leads vinculados."""
    cur = mysql.connection.cursor(DictCursor)
    try:
        cur.execute("SELECT id, nombre FROM marketing_ferias WHERE id = %s LIMIT 1", (feria_id,))
        feria = cur.fetchone()
        if not feria:
            return jsonify({"ok": False, "message": "Feria no encontrada"}), 404
        cur.execute("SELECT COUNT(*) AS total FROM leads WHERE feria_id = %s", (feria_id,))
        linked = (cur.fetchone() or {}).get("total", 0)
    finally:
        cur.close()

    token = secrets.token_urlsafe(24)
    pending = session.get("pending_delete", {})
    key = f"feria:{feria_id}"
    pending[key] = {"token": token, "time": int(time.time()), "user_id": int(session.get("user_id") or 0)}
    session["pending_delete"] = pending
    return jsonify({"ok": True, "token": token, "linked_leads": int(linked or 0), "confirm_name": feria.get("nombre")}), 200


@marketing_bp.route("/ferias/<int:feria_id>/delete/confirm", methods=["POST"])
@login_required
@role_required(ROLE_ADMIN, ROLE_GERENTE, ROLE_MARKETING)
def marketing_feria_delete_confirm(feria_id):
    """Confirma y ejecuta borrado seguro de una feria (token + confirm_name + password)."""
    data = request.get_json(silent=True) or request.form
    token = (data.get("token") or "").strip()
    confirm_name = (data.get("confirm_name") or "").strip()
    password = data.get("password") or ""
    force = str(data.get("force") or "").lower() in ("1", "true", "yes")

    pending = session.get("pending_delete", {})
    key = f"feria:{feria_id}"
    entry = pending.get(key) if isinstance(pending, dict) else None
    if not entry or entry.get("token") != token or int(entry.get("user_id") or 0) != int(session.get("user_id") or 0):
        return jsonify({"ok": False, "message": "Token inválido o expirado"}), 400
    if int(time.time()) - int(entry.get("time") or 0) > 300:
        pending.pop(key, None)
        session["pending_delete"] = pending
        return jsonify({"ok": False, "message": "Token expirado"}), 400

    cur = mysql.connection.cursor(DictCursor)
    try:
        cur.execute("SELECT id, nombre FROM marketing_ferias WHERE id = %s LIMIT 1", (feria_id,))
        feria = cur.fetchone()
        if not feria:
            return jsonify({"ok": False, "message": "Feria no encontrada"}), 404
        if feria.get("nombre") != confirm_name:
            return jsonify({"ok": False, "message": "El nombre de confirmación no coincide"}), 400

        # Verificar contraseña del usuario actual
        cur.execute("SELECT id, password FROM usuarios WHERE id = %s LIMIT 1", (session.get("user_id"),))
        u = cur.fetchone()
        if not u or not check_password(u.get("password") or "", password):
            return jsonify({"ok": False, "message": "Contraseña incorrecta"}), 403

        # Revisar leads vinculados y requerir flag 'force' si existen
        cur.execute("SELECT COUNT(*) AS total FROM leads WHERE feria_id = %s", (feria_id,))
        linked = int((cur.fetchone() or {}).get("total") or 0)
        if linked > 0 and not force:
            return jsonify({"ok": False, "requires_force": True, "linked_leads": linked, "message": "Existen leads vinculados. Requiere fuerza para eliminar."}), 400

        # Ejecutar borrado: si force, despegar leads y eliminar gastos asociados y la feria
        try:
            cur2 = mysql.connection.cursor()
            try:
                if linked > 0:
                    # Desvincular leads en lugar de borrarlos
                    cur2.execute("UPDATE leads SET feria_id = NULL WHERE feria_id = %s", (feria_id,))
                if _table_exists("marketing_feria_gastos"):
                    cur2.execute("DELETE FROM marketing_feria_gastos WHERE feria_id = %s", (feria_id,))
                cur2.execute("DELETE FROM marketing_ferias WHERE id = %s", (feria_id,))
                mysql.connection.commit()
            finally:
                cur2.close()
        except Exception as ex:
            mysql.connection.rollback()
            return jsonify({"ok": False, "message": f"Error al eliminar feria: {ex}"}), 500
    finally:
        cur.close()

    # Limpieza de token pendiente
    pending.pop(key, None)
    session["pending_delete"] = pending

    return jsonify({"ok": True, "message": "Feria eliminada correctamente", "deleted_id": feria_id}), 200

