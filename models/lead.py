from extensions import mysql
import MySQLdb.cursors
from MySQLdb.cursors import DictCursor
from MySQLdb import IntegrityError

# Resolver nombres sin acoplar al esquema exacto
from models.canal import Canal
from models.user import User
from models.proceso import Proceso


class Lead:
    def __init__(
        self,
        id,
        codigo,
        fecha,
        nombre,
        telefono,
        ruc_dni,
        email,
        contacto,
        direccion,
        departamento,
        provincia,
        distrito,
        canal_id,
        bien_servicio_id,
        asignado_a,
        comentario,
    ):
        self.id = id
        self.codigo = codigo
        self.fecha = fecha
        self.nombre = nombre
        self.telefono = telefono
        self.ruc_dni = ruc_dni
        self.email = email
        self.contacto = contacto
        self.direccion = direccion
        self.departamento = departamento
        self.provincia = provincia
        self.distrito = distrito
        self.canal_id = canal_id
        self.bien_servicio_id = bien_servicio_id
        self.asignado_a = asignado_a
        self.comentario = comentario

    # -------------------------------------------------------
    # Helper: id de proceso por nombre (case-insensitive)
    # -------------------------------------------------------
    @staticmethod
    def _get_proceso_id_by_name(name: str):
        """Busca y devuelve el ID de un proceso por su nombre, ignorando mayúsculas y espacios."""
        for p in Proceso.get_all():
            pname = (p["nombre_proceso"] if isinstance(p, dict) else getattr(p, "nombre_proceso", "")) or ""
            if pname.strip().lower() == name.strip().lower():
                return p["id"] if isinstance(p, dict) else getattr(p, "id", None)
        return None

    # ------------------------
    # Crear lead (+ seguimiento "No iniciado")
    # ------------------------
    @staticmethod
    def create(data, created_by_user_id=None):
        """
        Crea el lead y, si se pasa created_by_user_id, inserta un seguimiento
        inicial con proceso 'No iniciado' para que aparezca en la vista.
        """
        cur = mysql.connection.cursor()
        try:
            # 1) Insertar el lead
            cur.execute(
                """
                INSERT INTO leads
                (codigo, fecha, nombre, telefono, ruc_dni, email, contacto, direccion,
                 departamento, provincia, distrito, canal_id, bien_servicio_id, asignado_a, comentario)
                VALUES (%(codigo)s, %(fecha)s, %(nombre)s, %(telefono)s, %(ruc_dni)s,
                         %(email)s, %(contacto)s, %(direccion)s, %(departamento)s, %(provincia)s,
                         %(distrito)s, %(canal_id)s, %(bien_servicio_id)s, %(asignado_a)s, %(comentario)s)
                """,
                data,
            )
            lead_id = cur.lastrowid

            # 2) Seguimiento "No iniciado"
            if created_by_user_id:
                # Usar el helper centralizado
                proc_id = Lead._get_proceso_id_by_name("no iniciado")
                if proc_id:
                    cur.execute(
                        """
                        INSERT INTO seguimientos
                          (lead_id, usuario_id, fecha_seguimiento, proceso_id, fecha_programada,
                            motivo_no_venta_id, cotizacion, monto, moneda_id, comentario,
                            canal_contacto, fecha_guardado)
                        VALUES
                          (%s, %s, %s, %s, NULL, NULL, NULL, NULL, NULL, %s, NULL, NOW())
                        """,
                        (
                            lead_id,
                            created_by_user_id,
                            data.get("fecha"),
                            proc_id,
                            "Creación automática",
                        ),
                    )

            mysql.connection.commit()
            return lead_id
        except IntegrityError:
            mysql.connection.rollback()
            raise
        finally:
            cur.close()

    # ------------------------
    # Generar código auto-incrementable
    # ------------------------
    @staticmethod
    def next_codigo():
        cur = mysql.connection.cursor(DictCursor)
        try:
            cur.execute("SELECT codigo FROM leads ORDER BY id DESC LIMIT 1")
            row = cur.fetchone()
        finally:
            cur.close()

        if row and row["codigo"] and row["codigo"].startswith("LED-"):
            try:
                last_num = int(row["codigo"].split("-")[1])
            except Exception:
                last_num = 0
            return f"LED-{last_num + 1:04d}"
        return "LED-0001"

    # ------------------------
    # Obtener por ID
    # ------------------------
    @staticmethod
    def get_by_id(id):
        cur = mysql.connection.cursor(DictCursor)
        try:
            cur.execute("SELECT * FROM leads WHERE id = %s", (id,))
            lead = cur.fetchone()
        finally:
            cur.close()
        return lead

    # ------------------------
    # Obtener por CÓDIGO
    # ------------------------
    @staticmethod
    def get_by_codigo(codigo):
        cur = mysql.connection.cursor(DictCursor)
        try:
            cur.execute("SELECT * FROM leads WHERE codigo = %s", (codigo,))
            row = cur.fetchone()
        finally:
            cur.close()
        return row

    # ------------------------
    # Actualizar por ID
    # ------------------------
    @staticmethod
    def update(data):
        cur = mysql.connection.cursor()
        try:
            cur.execute(
                """
                UPDATE leads SET
                    nombre=%(nombre)s,
                    telefono=%(telefono)s,
                    ruc_dni=%(ruc_dni)s,
                    email=%(email)s,
                    contacto=%(contacto)s,
                    direccion=%(direccion)s,
                    departamento=%(departamento)s,
                    provincia=%(provincia)s,
                    distrito=%(distrito)s,
                    canal_id=%(canal_id)s,
                    bien_servicio_id=%(bien_servicio_id)s,
                    asignado_a=%(asignado_a)s,
                    comentario=%(comentario)s
                WHERE id=%(id)s
                """,
                data,
            )
            mysql.connection.commit()
        except IntegrityError:
            mysql.connection.rollback()
            raise
        finally:
            cur.close()

    # ------------------------
    # Actualizar por CÓDIGO
    # ------------------------
    @staticmethod
    def update_by_codigo(data):
        cur = mysql.connection.cursor()
        try:
            cur.execute(
                """
                UPDATE leads SET
                    nombre=%s, telefono=%s, ruc_dni=%s, email=%s,
                    contacto=%s, direccion=%s, departamento=%s,
                    provincia=%s, distrito=%s, canal_id=%s,
                    bien_servicio_id=%s, asignado_a=%s, comentario=%s
                WHERE codigo=%s
                """,
                (
                    data["nombre"], data["telefono"], data["ruc_dni"], data["email"],
                    data["contacto"], data["direccion"], data["departamento"], data["provincia"],
                    data["distrito"], data["canal_id"], data["bien_servicio_id"],
                    data["asignado_a"], data["comentario"], data["codigo"],
                ),
            )
            mysql.connection.commit()
        except IntegrityError:
            mysql.connection.rollback()
            raise
        finally:
            cur.close()

    # ============================================================
    # Helpers: resolver nombres (canal y asignado_a)
    # ============================================================
    @staticmethod
    def _build_canal_map():
        canales = Canal.get_all()
        canal_map = {}
        for c in canales:
            if isinstance(c, dict):
                cid = c.get("id")
                cname = c.get("nombre") or c.get("canal") or c.get("nombre_canal")
            else:
                cid = getattr(c, "id", None)
                cname = (
                    getattr(c, "nombre", None)
                    or getattr(c, "canal", None)
                    or getattr(c, "nombre_canal", None)
                )
            if cid is not None:
                # Nos aseguramos de tener una cadena para evitar errores de mapeo
                canal_map[cid] = str(cname) if cname is not None else ""
        return canal_map

    @staticmethod
    def _build_user_cache(user_ids):
        cache = {}
        # Filtrar None o IDs falsy para evitar llamadas a get_by_id innecesarias
        for uid in (uid for uid in user_ids if uid):
            try:
                # Nota: User.get_by_id debería devolver un diccionario (DictCursor) o una instancia de User
                u = User.get_by_id(uid)
            except Exception:
                u = None
            
            display = str(uid) # Default fallback
            
            if isinstance(u, dict):
                display = (
                    u.get("username")
                    or u.get("usuario")
                    or u.get("nombre")
                    or u.get("email")
                    or str(uid)
                )
            elif u: # Si es una instancia
                display = (
                    getattr(u, "username", None)
                    or getattr(u, "usuario", None)
                    or getattr(u, "nombre", None)
                    or getattr(u, "email", None)
                    or str(uid)
                )
                
            cache[uid] = str(display) # Aseguramos string
        return cache

    @staticmethod
    def _apply_name_resolution(rows):
        """Agrega `canal`, normaliza `asignado_a` y resuelve el usuario del último seguimiento en las filas ya obtenidas."""
        if not rows:
            return []
            
        canal_map = Lead._build_canal_map()
        # IDs del usuario asignado
        user_ids = {r.get("asignado_a") for r in rows if r.get("asignado_a")}
        # IDs del usuario que hizo el último seguimiento (si existe el campo)
        user_ids.update({r.get("ultimo_seguimiento_usuario_id") for r in rows if r.get("ultimo_seguimiento_usuario_id")})
        
        user_cache = Lead._build_user_cache(user_ids)
        
        for r in rows:
            # 1. Resolver nombre del canal
            r["canal"] = canal_map.get(r.get("canal_id")) or ""
            
            # 2. Resolver nombre del usuario asignado
            uid_asignado = r.get("asignado_a")
            # Dejamos 'asignado_a' con el ID y creamos 'asignado_a_nombre'
            r["asignado_a_nombre"] = user_cache.get(uid_asignado, "") if uid_asignado else ""
            # Para mantener compatibilidad con el código original, actualizamos 'asignado_a' con el nombre
            r["asignado_a"] = r["asignado_a_nombre"] 
            
            # 3. Resolver nombre del usuario del último seguimiento (si existe el campo en la fila)
            uid_ultimo_seg = r.get("ultimo_seguimiento_usuario_id")
            if uid_ultimo_seg is not None:
                r["ultimo_seguimiento_usuario_nombre"] = user_cache.get(uid_ultimo_seg, "")
                
        return rows

    @staticmethod
    def _is_asesor(id_rol):
        """Soporta 'asesor' como string o constante ROLE_ASESOR."""
        try:
            from utils.security import ROLE_ASESOR
            if id_rol == ROLE_ASESOR:
                return True
        except ImportError:
            pass # Si falla la importación, asumimos que ROLE_ASESOR no está definido
            
        return str(id_rol).strip().lower() in ("asesor", "role_asesor")
    
    # -------------------------------------------------------
    # Subconsulta genérica para el último seguimiento (OPTIMIZADA)
    # -------------------------------------------------------
    _SUBQUERY_LATEST_SEGUIMIENTO_BASE = """
        SELECT
            s1.lead_id, s1.monto, s1.moneda_id, s1.proceso_id, s1.comentario, s1.usuario_id,
            s1.fecha_programada, s1.cotizacion, s1.motivo_no_venta_id, s1.canal_contacto, s1.fecha_guardado,
            s1.id AS last_id
        FROM seguimientos s1
        INNER JOIN (
            SELECT lead_id, MAX(id) as max_id
            FROM seguimientos
            GROUP BY lead_id
        ) s2 ON s1.id = s2.max_id AND s1.lead_id = s2.lead_id
    """

    @staticmethod
    def list_for_user(id_rol, user_id, q="", start_date=None, end_date=None, limit=None, offset=None):
        """
        Wrapper de compatibilidad para listar leads según el rol del usuario.
        - Si limit es None devuelve la lista completa (sin paginación).
        - Si limit es int devuelve (rows, total) para paginación.
        """
        return Lead.search_for_user(
            id_rol=id_rol,
            user_id=user_id,
            q=q,
            start_date=start_date,
            end_date=end_date,
            limit=limit,
            offset=offset,
        )

    
    @staticmethod
    def search_for_user(id_rol, user_id, q="", start_date=None, end_date=None, limit=None, offset=None):
        """
        Búsqueda libre en 'Todos los leads' con rango de fechas opcional y paginación opcional.
        """
        cur = mysql.connection.cursor(DictCursor)
        try:
            # Normaliza entradas
            q = (q or "").strip()
            start_date = (start_date or "").strip() or None
            end_date   = (end_date or "").strip() or None

            # Usaremos FOUND_ROWS sólo si solicitamos paginación
            use_count = (limit is not None)

            # Subconsulta para obtener los datos del ÚLTIMO seguimiento (el MAX(id)) para cada lead
            subquery_latest_seguimiento = """
                SELECT
                    s1.lead_id, s1.monto, s1.moneda_id, s1.proceso_id, s1.comentario, s1.usuario_id
                FROM seguimientos s1
                INNER JOIN (
                    SELECT lead_id, MAX(id) as max_id
                    FROM seguimientos
                    GROUP BY lead_id
                ) s2 ON s1.id = s2.max_id AND s1.lead_id = s2.lead_id
            """
            
            select_clause = "SELECT "
            if use_count:
                select_clause += "SQL_CALC_FOUND_ROWS "

            select_clause += """
                        l.id, l.codigo, l.fecha, l.telefono, l.ruc_dni, l.nombre,
                        l.canal_id, l.contacto, l.direccion, l.departamento, l.provincia,
                        l.distrito, l.bien_servicio_id, l.email, l.comentario, l.asignado_a,
                        bs.nombre AS bien_servicio,
                        
                        -- Campos solicitados del último seguimiento y sus tablas relacionadas
                        s.monto AS ultimo_monto,
                        m.nombre_moneda AS ultimo_moneda_nombre,
                        p.nombre_proceso AS ultimo_proceso_nombre,
                        s.comentario AS ultimo_comentario,
                        s.usuario_id AS ultimo_seguimiento_usuario_id
            """

            sql = select_clause + f"""
                FROM leads l
                LEFT JOIN bienes_servicios bs ON bs.id = l.bien_servicio_id
                -- LEFT JOIN con la subconsulta del último seguimiento
                LEFT JOIN ({subquery_latest_seguimiento}) s ON s.lead_id = l.id
                -- LEFT JOIN para obtener el nombre de la moneda
                LEFT JOIN moneda m ON m.id = s.moneda_id
                -- LEFT JOIN para obtener el nombre del proceso
                LEFT JOIN proceso p ON p.id = s.proceso_id
                WHERE 1=1
            """
            params = []

            # Si es asesor: solo sus leads
            if Lead._is_asesor(id_rol):
                sql += " AND l.asignado_a = %s"
                params.append(user_id)

            # Filtro por fechas
            if start_date:
                sql += " AND l.fecha >= %s"
                params.append(start_date)
            if end_date:
                sql += " AND l.fecha <= %s"
                params.append(end_date)

            # Búsqueda libre (incluye l.comentario y s.comentario)
            if q:
                like = f"%{q}%"
                sql += """
                AND (
                l.codigo LIKE %s OR l.telefono LIKE %s OR l.ruc_dni LIKE %s OR
                l.nombre LIKE %s OR l.contacto LIKE %s OR l.direccion LIKE %s OR
                l.departamento LIKE %s OR l.provincia LIKE %s OR l.distrito LIKE %s OR
                l.email LIKE %s OR COALESCE(bs.nombre,'') LIKE %s OR
                l.comentario LIKE %s OR COALESCE(s.comentario,'') LIKE %s
                )
                """
                # 13 comodines en total
                params.extend([like] * 13) 

            sql += " ORDER BY l.fecha DESC, l.id DESC"

            # Agregar LIMIT/OFFSET si se solicitó paginación
            if limit is not None:
                if offset is None:
                    offset = 0
                sql += " LIMIT %s OFFSET %s"
                params.extend([limit, offset])

            cur.execute(sql, params)
            rows = cur.fetchall() or []

            total = None
            if use_count:
                # Obtener el total ignorando LIMIT (MySQL)
                cur.execute("SELECT FOUND_ROWS() AS total")
                tr = cur.fetchone()
                try:
                    # DictCursor devuelve dict
                    total = tr.get("total") if isinstance(tr, dict) else (tr["total"] if tr else 0)
                except Exception:
                    total = 0
        finally:
            cur.close()

        rows = Lead._apply_name_resolution(rows)

        if use_count:
            return rows, int(total or 0)
        else:
            return rows


    # ============================================================
    # Funciones de listado por proceso (refactorizadas con un helper)
    # ============================================================

    # Plantilla de consulta para procesos específicos (SIN el WHERE base)
    _BASE_PROCESS_LIST_SQL = """
        SELECT
            l.id, l.codigo, l.fecha, l.telefono, l.ruc_dni, l.nombre, l.contacto,
            l.direccion, l.departamento, l.provincia, l.distrito, l.email, l.comentario,
            l.canal_id, l.asignado_a,
            bs.nombre AS bien_servicio,
            su.fecha_guardado AS ultimo_guardado,
            su.fecha_programada, su.cotizacion, su.monto, su.motivo_no_venta_id,
            m.nombre_moneda AS moneda, mnv.motivo_no_venta
        FROM leads l
        LEFT JOIN bienes_servicios bs ON bs.id = l.bien_servicio_id
        JOIN ({subquery_latest_seguimiento}) last ON last.lead_id = l.id
        JOIN seguimientos su ON su.id = last.last_id
        LEFT JOIN moneda m ON m.id = su.moneda_id
        LEFT JOIN motivo_no_venta mnv ON mnv.id = su.motivo_no_venta_id
    """
    
    # models/lead.py (Función _execute_process_list_query CORREGIDA)

    @staticmethod
    def _execute_process_list_query(process_name, id_rol, user_id, q="", custom_order_field=None, extra_search_fields=None, limit=None, offset=None):
        """
        Helper interno para manejar la lógica repetitiva de listado por proceso,
        SOPORTA PAGINACIÓN (limit y offset) y devuelve (leads, total).
        """
        
        proc_id = Lead._get_proceso_id_by_name(process_name)
        if proc_id is None:
            return [], 0

        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            # Usar la subconsulta base para el último seguimiento
            subquery_with_alias = f"({Lead._SUBQUERY_LATEST_SEGUIMIENTO_BASE})" 
            base_sql_select = Lead._BASE_PROCESS_LIST_SQL.format(
                subquery_latest_seguimiento=subquery_with_alias
            )
            
            # 1. CONSTRUIR CLÁUSULAS (WHERE, PARAMS)
            
            # === INICIO DE CONSTRUCCIÓN DE LA CLÁUSULA WHERE (Común a SELECT y COUNT) ===
            where_clause = " WHERE su.proceso_id = %s"
            params = [proc_id]

            if Lead._is_asesor(id_rol):
                where_clause += " AND l.asignado_a = %s"
                params.append(user_id)

            q = (q or "").strip()
            
            num_base_search_fields = 13 # 11 campos Lead + l.comentario + su.comentario
            
            if q:
                like = f"%{q}%"
                
                search_clause = """
                    AND (
                        l.codigo LIKE %s OR l.telefono LIKE %s OR l.ruc_dni LIKE %s OR
                        l.nombre LIKE %s OR l.contacto LIKE %s OR l.direccion LIKE %s OR
                        l.departamento LIKE %s OR l.provincia LIKE %s OR l.distrito LIKE %s OR
                        l.email LIKE %s OR COALESCE(bs.nombre,'') LIKE %s OR
                        COALESCE(l.comentario,'') LIKE %s OR 
                        COALESCE(su.comentario,'') LIKE %s 
                """
                
                num_extra_search_fields = 0
                if extra_search_fields:
                    for field in extra_search_fields:
                        search_clause += f" OR {field} LIKE %s"
                        num_extra_search_fields += 1
                        
                search_clause += "\n)" 
                where_clause += search_clause
                
                params.extend([like] * (num_base_search_fields + num_extra_search_fields))
            
            # === FIN DE CONSTRUCCIÓN DE LA CLÁUSULA WHERE ===

            # 💡 SOLUCIÓN OPERATIONALERROR: Determinar qué JOINs necesita el COUNT basado en extra_search_fields
            count_join_clauses = ""
            if extra_search_fields:
                extra_search_fields_str = str(extra_search_fields)
                
                # Necesita JOIN con 'moneda' (m) si busca en moneda, monto o cotizacion
                if any(f in extra_search_fields_str for f in ["m.nombre_moneda", "su.monto", "su.cotizacion"]):
                    count_join_clauses += " LEFT JOIN moneda m ON m.id = su.moneda_id"
                    
                # Necesita JOIN con 'motivos_no_venta' (mnv) si busca en ese campo
                if "mnv.motivo_no_venta" in extra_search_fields_str:
                    # NOTA: Usamos LEFT JOIN para que el COUNT no se rompa si el lead no tiene un mnv_id, 
                    # aunque es poco probable en Cerrado No Vendido.
                    count_join_clauses += " LEFT JOIN motivo_no_venta mnv ON mnv.id = su.motivo_no_venta_id"


            # 2. OBTENER EL TOTAL DE REGISTROS (sin límite/offset)
            count_sql = f"""
                SELECT COUNT(l.id) 
                FROM leads l
                JOIN ({Lead._SUBQUERY_LATEST_SEGUIMIENTO_BASE}) AS latest_seg 
                    ON latest_seg.lead_id = l.id
                JOIN seguimientos su 
                    ON su.id = latest_seg.last_id
                LEFT JOIN bienes_servicios bs 
                    ON bs.id = l.bien_servicio_id
                {count_join_clauses} 
                {where_clause}
            """
            
            cur.execute(count_sql, params)
            total = cur.fetchone()['COUNT(l.id)'] or 0

            # 3. OBTENER LOS LEADS PAGINADOS (con límite/offset)
            
            # Definir orden
            order_by_clause = " ORDER BY su.fecha_guardado DESC, l.id DESC"
            if custom_order_field:
                order_by_clause = f" ORDER BY {custom_order_field}, su.fecha_guardado DESC, l.id DESC"
            
            # 💡 CORRECCIÓN CLAVE: Concatenar where_clause directamente.
            sql_final = base_sql_select + where_clause + order_by_clause 

            # Agregar paginación
            if limit is not None:
                sql_final += " LIMIT %s"
                params.append(limit)
                if offset is not None:
                    sql_final += " OFFSET %s"
                    params.append(offset)
            
            cur.execute(sql_final, params)
            rows = cur.fetchall()
            
        finally:
            cur.close()
            
        return Lead._apply_name_resolution(rows), total

    # ============================================================
    # Último seguimiento = "No iniciado"
    # ============================================================
    @staticmethod
    def list_unstarted_for_user(id_rol, user_id, q=None, limit=None, offset=None):
        """
        Lista leads en proceso 'No Iniciado'.
        Ahora acepta limit y offset para paginación.
        """
        # Llama al helper que ahora debe aceptar limit y offset
        return Lead._execute_process_list_query(
            'no iniciado', id_rol, user_id, q, limit=limit, offset=offset
        )

    # ============================================================
    # Último seguimiento = "Seguimiento"
    # ============================================================
    @staticmethod
    def list_in_followup_for_user(id_rol, user_id, q="", limit=None, offset=None):
        """Lista leads cuyo último seguimiento es 'Seguimiento'."""
        return Lead._execute_process_list_query("seguimiento", id_rol, user_id, q, limit=limit, offset=offset)

    # ============================================================
    # Último seguimiento = "Programado"
    # ============================================================
    @staticmethod
    def list_programmed_for_user(id_rol, user_id, q="", limit=None, offset=None):
        """Lista leads cuyo último seguimiento es 'Programado' (ordenados por fecha programada ascendente)."""
        return Lead._execute_process_list_query(
            "programado", 
            id_rol, 
            user_id, 
            q, 
            custom_order_field="su.fecha_programada ASC",
            limit=limit, 
            offset=offset
        )

    # ============================================================
    # Último seguimiento = "Cotizado"
    # ============================================================
    @staticmethod
    def list_quoted_for_user(id_rol, user_id, q="", limit=None, offset=None):
        """Lista leads cuyo último seguimiento es 'Cotizado' (incluye búsqueda en cotización, monto y moneda)."""
        return Lead._execute_process_list_query(
            "cotizado", 
            id_rol, 
            user_id, 
            q,
            extra_search_fields=[
                "COALESCE(su.cotizacion,'')", 
                "COALESCE(m.nombre_moneda,'')", 
                "CAST(COALESCE(su.monto,0) AS CHAR)"
            ],
            limit=limit, 
            offset=offset
        )

    # ============================================================
    # Último seguimiento = "Cerrado"
    # ============================================================
    @staticmethod
    def list_closed_for_user(id_rol, user_id, q="", limit=None, offset=None):
        """Lista leads cuyo último seguimiento es 'Cerrado' (incluye búsqueda en cotización, monto y moneda)."""
        return Lead._execute_process_list_query(
            "cerrado", 
            id_rol, 
            user_id, 
            q,
            extra_search_fields=[
                "COALESCE(su.cotizacion,'')", 
                "COALESCE(m.nombre_moneda,'')", 
                "CAST(COALESCE(su.monto,0) AS CHAR)"
            ],
            limit=limit, 
            offset=offset
        )

    # ============================================================
    # Último seguimiento = "Cerrado No Vendido"
    # ============================================================
    @staticmethod
    def list_closed_lost_for_user(id_rol, user_id, q="", limit=None, offset=None):
        """Lista leads cuyo último seguimiento es 'Cerrado No Vendido' (incluye búsqueda en motivo de no venta)."""
        return Lead._execute_process_list_query(
            "cerrado no vendido", 
            id_rol, 
            user_id, 
            q,
            extra_search_fields=[
                "COALESCE(mnv.motivo_no_venta,'')"
            ],
            limit=limit, 
            offset=offset
        )