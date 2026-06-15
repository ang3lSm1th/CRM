from routes.marketing.shared import (
    DEPARTAMENTOS,
    DictCursor,
    ROLE_ADMIN,
    ROLE_GERENTE,
    ROLE_MARKETING,
    login_required,
    marketing_bp,
    mysql,
    obtener_nombre_departamento,
    render_template,
    request,
    role_required,
)


@marketing_bp.route("/clientes")
@login_required
@role_required(ROLE_ADMIN, ROLE_GERENTE, ROLE_MARKETING)
def marketing_clientes():
    from flask import Response

    q = (request.args.get("q") or "").strip()
    bien_servicio_id = request.args.get("bien_servicio_id") or None
    departamento = request.args.get("departamento") or None
    f_ini = request.args.get("f_ini") or None
    f_fin = request.args.get("f_fin") or None
    export = (request.args.get("export") or "").strip().lower() == "csv"

    cur = mysql.connection.cursor(DictCursor)
    try:
        subquery_latest = """
            SELECT s1.*
            FROM seguimientos s1
            INNER JOIN (
                SELECT lead_id, MAX(id) AS max_id
                FROM seguimientos
                GROUP BY lead_id
            ) s2 ON s1.id = s2.max_id
        """

        sql = f"""
            SELECT
                c.id AS cliente_id,
                c.nombre AS cliente_nombre,
                c.ruc_dni,
                c.email,
                c.telefono,
                c.departamento,
                c.provincia,
                c.distrito,
                COUNT(DISTINCT l.id) AS compras,
                COALESCE(SUM(CASE WHEN p.nombre_proceso = 'Cerrado' THEN s.monto ELSE 0 END), 0) AS monto_total,
                MAX(CASE WHEN p.nombre_proceso = 'Cerrado' THEN s.fecha_guardado END) AS ultima_compra,
                GROUP_CONCAT(DISTINCT bs.nombre ORDER BY bs.nombre SEPARATOR ', ') AS lineas
            FROM clientes c
            JOIN leads l ON l.cliente_id = c.id
            LEFT JOIN ({subquery_latest}) s ON s.lead_id = l.id
            LEFT JOIN proceso p ON p.id = s.proceso_id
            LEFT JOIN bienes_servicios bs ON bs.id = l.bien_servicio_id
            WHERE p.nombre_proceso = 'Cerrado'
        """
        params = []

        if bien_servicio_id:
            sql += " AND l.bien_servicio_id = %s"
            params.append(bien_servicio_id)

        if departamento:
            sql += " AND NULLIF(c.departamento,'') = %s"
            params.append(departamento)

        if f_ini:
            sql += " AND s.fecha_guardado >= %s"
            params.append(f_ini)
        if f_fin:
            sql += " AND s.fecha_guardado <= %s"
            params.append(f_fin)

        if q:
            like = f"%{q}%"
            sql += """
                AND (
                    COALESCE(c.nombre,'') LIKE %s OR
                    COALESCE(c.ruc_dni,'') LIKE %s OR
                    COALESCE(c.email,'') LIKE %s OR
                    COALESCE(c.telefono,'') LIKE %s
                )
            """
            params.extend([like, like, like, like])

        sql += """
            GROUP BY c.id, c.nombre, c.ruc_dni, c.email, c.telefono, c.departamento, c.provincia, c.distrito
            ORDER BY ultima_compra DESC, monto_total DESC
        """

        cur.execute(sql, params)
        clientes = cur.fetchall() or []

        for cliente in clientes:
            cliente["departamento_nombre"] = obtener_nombre_departamento(cliente.get("departamento"))

        if export:
            import csv
            import io

            output = io.StringIO()
            writer = csv.writer(output)
            writer.writerow([
                "Cliente",
                "RUC/DNI",
                "Email",
                "Telefono",
                "Departamento",
                "Compras",
                "Monto Total",
                "Ultima Compra",
                "Lineas",
            ])
            for row in clientes:
                writer.writerow([
                    row.get("cliente_nombre") or "",
                    row.get("ruc_dni") or "",
                    row.get("email") or "",
                    row.get("telefono") or "",
                    row.get("departamento_nombre") or "",
                    row.get("compras") or 0,
                    f"{(row.get('monto_total') or 0):.2f}",
                    row.get("ultima_compra") or "",
                    row.get("lineas") or "",
                ])
            csv_data = output.getvalue()
            output.close()
            return Response(
                csv_data,
                mimetype="text/csv",
                headers={"Content-Disposition": "attachment; filename=marketing_clientes.csv"},
            )
    finally:
        cur.close()

    from models.bien_servicio import BienServicio

    bienes_servicios = BienServicio.get_all()
    departamentos_list = [{"id": key, "nombre": value} for key, value in DEPARTAMENTOS.items()]
    departamentos_list.sort(key=lambda item: item["nombre"])

    return render_template(
        "reportes/marketing_clientes.html",
        clientes=clientes,
        bienes_servicios=bienes_servicios,
        departamentos=departamentos_list,
        q=q,
        bien_servicio_id=bien_servicio_id,
        departamento=departamento,
        f_ini=f_ini,
        f_fin=f_fin,
    )