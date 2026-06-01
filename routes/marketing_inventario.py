from datetime import date

from routes.marketing import (
    DictCursor,
    ROLE_ADMIN,
    ROLE_GERENTE,
    ROLE_MARKETING,
    _column_exists,
    _table_exists,
    _to_decimal,
    flash,
    login_required,
    marketing_bp,
    mysql,
    jsonify,
    redirect,
    render_template,
    request,
    role_required,
    session,
    url_for,
)

ALLOWED_TIPOS = {"Merchadising", "Comunicacion", "Publicidad"}


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


@marketing_bp.route("/inventario-mercaderia", methods=["GET", "POST"])
@login_required
@role_required(ROLE_ADMIN, ROLE_GERENTE, ROLE_MARKETING)
def marketing_inventario_mercaderia():
    if not _table_exists("marketing_inventario_mercaderia"):
        flash("No existe la tabla marketing_inventario_mercaderia. Ejecuta la migracion correspondiente.", "danger")
        return render_template("marketing/inventario_mercaderia.html", inventory_rows=[], today=date.today().isoformat(), allowed_tipos=sorted(ALLOWED_TIPOS))

    brand = request.cookies.get("brand") or "orbes"
    negocio_id = _resolve_negocio_id(brand)

    if request.method == "POST":
        fecha = (request.form.get("fecha") or "").strip() or date.today().isoformat()
        tipo = (request.form.get("tipo") or "").strip()
        producto = (request.form.get("producto") or "").strip()
        precio = _to_decimal(request.form.get("precio"))
        cantidad_raw = (request.form.get("cantidad") or "").strip()
        factura = (request.form.get("factura") or "").strip()

        try:
            cantidad = int(cantidad_raw)
        except ValueError:
            cantidad = 0

        if tipo not in ALLOWED_TIPOS:
            flash("Selecciona un tipo valido para inventario.", "warning")
            return redirect(url_for("marketing.marketing_inventario_mercaderia"))

        if not producto:
            flash("El producto es obligatorio.", "warning")
            return redirect(url_for("marketing.marketing_inventario_mercaderia"))

        if precio is None or precio < 0:
            flash("El precio debe ser un numero valido mayor o igual a 0.", "warning")
            return redirect(url_for("marketing.marketing_inventario_mercaderia"))

        if cantidad <= 0:
            flash("La cantidad debe ser un entero mayor a 0.", "warning")
            return redirect(url_for("marketing.marketing_inventario_mercaderia"))

        # Validar campo factura (debe ser Boleta o Factura)
        if factura not in ("Boleta", "Factura"):
            flash("Selecciona 'Boleta' o 'Factura' en el campo Factura.", "warning")
            return redirect(url_for("marketing.marketing_inventario_mercaderia"))

        total = precio * cantidad

        cur = mysql.connection.cursor()
        try:
            cur.execute(
                """
                INSERT INTO marketing_inventario_mercaderia (
                    fecha,
                    tipo,
                    factura,
                    producto,
                    precio,
                    cantidad,
                    total,
                    created_by,
                    negocio_id,
                    brand,
                    created_at,
                    updated_at
                ) VALUES (%s, %s, %s, %s, %s, %s, %s, %s, %s, %s, NOW(), NOW())
                """,
                (
                    fecha,
                    tipo,
                    factura,
                    producto,
                    precio,
                    cantidad,
                    total,
                    session.get("user_id"),
                    negocio_id,
                    brand,
                ),
            )
            mysql.connection.commit()
            flash("Producto agregado al inventario correctamente.", "success")
        except Exception as ex:
            mysql.connection.rollback()
            flash(f"No se pudo guardar el producto: {ex}", "danger")
        finally:
            cur.close()

        return redirect(url_for("marketing.marketing_inventario_mercaderia"))

    scope_where, scope_params = _inventory_scope_where(brand, negocio_id)

    cur = mysql.connection.cursor(DictCursor)
    try:
        cur.execute(
            f"""
            SELECT
                id,
                DATE_FORMAT(fecha, '%%Y-%%m-%%d') AS fecha,
                tipo,
                factura,
                producto,
                precio,
                cantidad,
                total
            FROM marketing_inventario_mercaderia
            WHERE {scope_where}
            ORDER BY fecha DESC, id DESC
            """,
            tuple(scope_params),
        )
        inventory_rows = cur.fetchall() or []
    finally:
        cur.close()

    return render_template(
        "marketing/inventario_mercaderia.html",
        inventory_rows=inventory_rows,
        today=date.today().isoformat(),
        allowed_tipos=sorted(ALLOWED_TIPOS),
    )


@marketing_bp.route("/inventario-mercaderia/<int:item_id>/delete", methods=["POST"])
@login_required
@role_required(ROLE_ADMIN, ROLE_GERENTE, ROLE_MARKETING)
def marketing_inventario_mercaderia_delete(item_id):
    if not _table_exists("marketing_inventario_mercaderia"):
        flash("No existe la tabla de inventario de mercaderia.", "danger")
        return redirect(url_for("marketing.marketing_inventario_mercaderia"))

    brand = request.cookies.get("brand") or "orbes"
    negocio_id = _resolve_negocio_id(brand)
    scope_where, scope_params = _inventory_scope_where(brand, negocio_id)

    cur = mysql.connection.cursor(DictCursor)
    try:
        cur.execute(
            f"""
            SELECT id, producto
            FROM marketing_inventario_mercaderia
            WHERE id = %s AND {scope_where}
            LIMIT 1
            """,
            tuple([item_id] + scope_params),
        )
        item = cur.fetchone() or None
    finally:
        cur.close()

    if not item:
        flash("No se encontro el producto solicitado.", "warning")
        return redirect(url_for("marketing.marketing_inventario_mercaderia"))

    if _table_exists("marketing_feria_gastos") and _column_exists("marketing_feria_gastos", "detalle"):
        ref_cur = mysql.connection.cursor(DictCursor)
        try:
            ref_cur.execute(
                """
                SELECT COUNT(*) AS total
                FROM marketing_feria_gastos
                WHERE LOWER(COALESCE(tipo, '')) = 'mercaderia'
                  AND detalle LIKE %s
                """,
                (f"{item_id}:%",),
            )
            ref_row = ref_cur.fetchone() or {}
            linked_total = int(ref_row.get("total") or 0)
        finally:
            ref_cur.close()

        if linked_total > 0:
            flash("No se puede eliminar el producto porque ya fue usado en otros gastos o ferias.", "warning")
            return redirect(url_for("marketing.marketing_inventario_mercaderia"))

    delete_cur = mysql.connection.cursor()
    try:
        delete_cur.execute("DELETE FROM marketing_inventario_mercaderia WHERE id = %s", (item_id,))
        mysql.connection.commit()
        flash(f"Producto '{item.get('producto')}' eliminado correctamente.", "success")
    except Exception as ex:
        mysql.connection.rollback()
        flash(f"No se pudo eliminar el producto: {ex}", "danger")
    finally:
        delete_cur.close()

    return redirect(url_for("marketing.marketing_inventario_mercaderia"))
