from extensions import mysql
import MySQLdb.cursors
from MySQLdb.cursors import DictCursor
from MySQLdb import IntegrityError
import re

# Resolver nombres sin acoplar al esquema exacto
from models.canal import Canal
from models.user import User
from models.proceso import Proceso

# ============================================================
# EXCEPCIÓN PERSONALIZADA PARA DUPLICADOS
# ============================================================
class LeadDuplicatedError(Exception):
    """Excepción lanzada cuando se intenta crear un lead con DNI/RUC o Teléfono duplicado."""
    def __init__(self, message, existing_lead_data=None):
        super().__init__(message)
        # existing_lead_data ahora es una LISTA de leads duplicados
        self.existing_lead_data = existing_lead_data 


class Lead:
    _leads_has_feria_column_cache = None

    # (El método __init__ sigue igual)
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

    @staticmethod
    def _leads_has_feria_column():
        if Lead._leads_has_feria_column_cache is not None:
            return Lead._leads_has_feria_column_cache

        cur = mysql.connection.cursor(DictCursor)
        try:
            cur.execute(
                """
                SELECT COUNT(*) AS total
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = 'leads'
                  AND COLUMN_NAME = 'feria_id'
                """
            )
            row = cur.fetchone() or {}
            Lead._leads_has_feria_column_cache = int(row.get("total") or 0) > 0
        except Exception:
            Lead._leads_has_feria_column_cache = False
        finally:
            cur.close()

        return Lead._leads_has_feria_column_cache

    @staticmethod
    def _find_active_campaign_for_lead(cur, bien_servicio_id, fecha_lead):
        if not bien_servicio_id or not fecha_lead:
            return None

        cur.execute(
            """
            SELECT c.id
            FROM marketing_campaigns c
            INNER JOIN bienes_servicios bs ON bs.id = %s
            WHERE c.activo = 1
              AND %s BETWEEN c.periodo_inicio AND c.periodo_fin
                            AND LOWER(TRIM(CONVERT(c.linea_negocio USING utf8mb4))) COLLATE utf8mb4_unicode_ci =
                                    LOWER(TRIM(CONVERT(bs.nombre USING utf8mb4))) COLLATE utf8mb4_unicode_ci
            ORDER BY c.fecha_lanzamiento DESC, c.id DESC
            LIMIT 1
            """,
            (bien_servicio_id, fecha_lead),
        )
        row = cur.fetchone()
        if not row:
            return None
        return row[0] if isinstance(row, (tuple, list)) else row.get("id")

    @staticmethod
    def _auto_link_campaign(cur, lead_id, data, created_by_user_id=None):
        campaign_id = Lead._find_active_campaign_for_lead(
            cur,
            data.get("bien_servicio_id"),
            data.get("fecha"),
        )
        if not campaign_id:
            return None

        cur.execute(
            """
            INSERT IGNORE INTO marketing_campaign_leads
            (campaign_id, lead_id, fecha_atribucion, metodo_atribucion, created_by, created_at)
            VALUES (%s, %s, CURDATE(), %s, %s, NOW())
            """,
            (campaign_id, lead_id, "periodo_automatico", created_by_user_id),
        )
        return campaign_id if cur.rowcount > 0 else None
    
    # ============================================================
    # FUNCIÓN CLAVE: Buscar duplicados y obtener sus datos
    # ============================================================
    @staticmethod
    def find_duplicate_lead_data(ruc_dni: str, telefono: str):
        ruc_dni_search = (ruc_dni or "").strip()
        telefono_search = (telefono or "").strip()

        if not ruc_dni_search and not telefono_search:
            return None

        cur = mysql.connection.cursor(DictCursor)
        subquery_latest_seguimiento = """
            SELECT
                s1.lead_id, s1.proceso_id, s1.fecha_guardado, s1.usuario_id
            FROM seguimientos s1
            INNER JOIN (
                SELECT lead_id, MAX(id) as max_id
                FROM seguimientos
                GROUP BY lead_id
            ) s2 ON s1.id = s2.max_id AND s1.lead_id = s2.lead_id
        """

        sql = f"""
            SELECT 
                l.id, l.codigo, l.asignado_a, 
                l.ruc_dni, l.telefono,
                s.fecha_guardado AS ultima_actualizacion, 
                p.nombre_proceso AS estado_actual,
                s.usuario_id AS ultimo_seguimiento_usuario_id
            FROM leads l
            LEFT JOIN ({subquery_latest_seguimiento}) s ON s.lead_id = l.id
            LEFT JOIN proceso p ON p.id = s.proceso_id
            WHERE 
                (NULLIF(l.ruc_dni, '') = %s AND NULLIF(%s, '') IS NOT NULL)
                OR (NULLIF(l.telefono, '') = %s AND NULLIF(%s, '') IS NOT NULL)
            ORDER BY l.id DESC
        """
        params = [ruc_dni_search, ruc_dni_search, telefono_search, telefono_search]

        try:
            cur.execute(sql, params)
            lead_list = cur.fetchall()
        finally:
            cur.close()

        if not lead_list:
            return None

        processed_list = Lead._apply_name_resolution(lead_list)

        for result in processed_list:
            result["duplicate_field_used"] = (
                "DNI/RUC" if ruc_dni_search and ruc_dni_search == result.get("ruc_dni") else
                "Teléfono" if telefono_search and telefono_search == result.get("telefono") else
                "Desconocido"
            )

        return processed_list


    # ------------------------
    # Crear lead (+ seguimiento "No iniciado")
    # ------------------------
    # Función corregida para models/lead.py

    @staticmethod
    def create(data, created_by_user_id=None, force_save: bool = False):
        """
        Crea el lead. Antes de insertar, verifica duplicados. 
        Si hay duplicados:
            - Si force_save es False, lanza LeadDuplicatedError.
            - Si force_save es True, omite la excepción y guarda el lead.
        """
        
        # 0) VALIDACIÓN DE DUPLICADOS: Ahora devuelve una lista si hay coincidencias
        existing_leads_list = Lead.find_duplicate_lead_data(
            data.get("ruc_dni", "").strip(), 
            data.get("telefono", "").strip()
        )
        
        if existing_leads_list:
            # --- CORRECCIÓN CLAVE: Integrar el flag force_save ---
            if not force_save:
                # Lanza una excepción con la LISTA de leads duplicados solo si NO se fuerza el guardado
                msg = "El DNI/RUC o el Teléfono ya existen en otros leads."
                raise LeadDuplicatedError(msg, existing_lead_data=existing_leads_list)
            
            # Si force_save es True, el flujo de ejecución CONTINÚA A LA INSERCIÓN.

        cur = mysql.connection.cursor()
        try:
            # Ensure negocio_id is resolved from assigned user when not provided
            try:
                assigned = data.get('asignado_a')
            except Exception:
                assigned = None
            if ('negocio_id' not in data or data.get('negocio_id') in (None, '')) and assigned:
                try:
                    cur2 = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
                    try:
                        cur2.execute("SELECT negocio_id FROM usuarios WHERE id = %s LIMIT 1", (assigned,))
                        row = cur2.fetchone()
                        if row:
                            data['negocio_id'] = row.get('negocio_id')
                        else:
                            data['negocio_id'] = None
                    finally:
                        cur2.close()
                except Exception:
                    data['negocio_id'] = None
            else:
                # Normalize empty to None
                if data.get('negocio_id') == '':
                    data['negocio_id'] = None

            has_feria_column = Lead._leads_has_feria_column()
            if has_feria_column:
                cur.execute(
                    """
                    INSERT INTO leads
                    (codigo, fecha, nombre, telefono, ruc_dni, email, contacto, direccion,
                    departamento, provincia, distrito, canal_id, bien_servicio_id, asignado_a, comentario, feria_id, negocio_id)
                    VALUES (%(codigo)s, %(fecha)s, %(nombre)s, %(telefono)s, %(ruc_dni)s,
                            %(email)s, %(contacto)s, %(direccion)s, %(departamento)s, %(provincia)s,
                            %(distrito)s, %(canal_id)s, %(bien_servicio_id)s, %(asignado_a)s, %(comentario)s, %(feria_id)s, %(negocio_id)s)
                    """,
                    data,
                )
            else:
                cur.execute(
                    """
                    INSERT INTO leads
                    (codigo, fecha, nombre, telefono, ruc_dni, email, contacto, direccion,
                    departamento, provincia, distrito, canal_id, bien_servicio_id, asignado_a, comentario, negocio_id)
                    VALUES (%(codigo)s, %(fecha)s, %(nombre)s, %(telefono)s, %(ruc_dni)s,
                            %(email)s, %(contacto)s, %(direccion)s, %(departamento)s, %(provincia)s,
                            %(distrito)s, %(canal_id)s, %(bien_servicio_id)s, %(asignado_a)s, %(comentario)s, %(negocio_id)s)
                    """,
                    data,
                )
            lead_id = cur.lastrowid

            # 2) Seguimiento "No iniciado" (Este código no fue modificado)
            if created_by_user_id:
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

            Lead._auto_link_campaign(cur, lead_id, data, created_by_user_id)

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
        return "LED-0000001"

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
    def _nullable_int(value):
        if value is None:
            return None
        text = str(value).strip()
        if text == "":
            return None
        return int(text)

    @staticmethod
    def update(data):
        cur = mysql.connection.cursor()
        try:
            safe_data = dict(data)
            safe_data["canal_id"] = Lead._nullable_int(safe_data.get("canal_id"))
            safe_data["bien_servicio_id"] = Lead._nullable_int(
                safe_data.get("bien_servicio_id")
            )
            safe_data["asignado_a"] = Lead._nullable_int(safe_data.get("asignado_a"))

            if Lead._leads_has_feria_column():
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
                        comentario=%(comentario)s,
                        feria_id=%(feria_id)s
                    WHERE id=%(id)s
                    """,
                    safe_data,
                )
            else:
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
                    safe_data,
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
            canal_id = Lead._nullable_int(data.get("canal_id"))
            bien_servicio_id = Lead._nullable_int(data.get("bien_servicio_id"))
            asignado_a = Lead._nullable_int(data.get("asignado_a"))

            cur.execute(
                """
                UPDATE leads SET
                    fecha=%s,
                    nombre=%s,
                    telefono=%s,
                    ruc_dni=%s,
                    email=%s,
                    contacto=%s,
                    direccion=%s,
                    departamento=%s,
                    provincia=%s,
                    distrito=%s,
                    canal_id=%s,
                    bien_servicio_id=%s,
                    asignado_a=%s,
                    comentario=%s
                WHERE codigo = %s
                """,
                (
                    data.get("fecha"),
                    data.get("nombre"),
                    data.get("telefono"),
                    data.get("ruc_dni"),
                    data.get("email"),
                    data.get("contacto"),
                    data.get("direccion"),
                    data.get("departamento"),
                    data.get("provincia"),
                    data.get("distrito"),
                    canal_id,
                    bien_servicio_id,
                    asignado_a,
                    data.get("comentario"),
                    data.get("codigo"),
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
            # Aseguramos string y evitamos None si la búsqueda falló
            cache[uid] = str(display) if display is not None else str(uid) 
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
            pass 
            
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
    def list_for_user(id_rol, user_id, q="", start_date=None, end_date=None, limit=None, offset=None, sort='desc'):
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
            sort=sort,
        )

    
    @staticmethod
# ...existing code...
    def search_for_user(id_rol, user_id, q="", start_date=None, end_date=None, limit=None, offset=None, sort='desc'):
        """
        Búsqueda libre en 'Todos los leads' con rango de fechas opcional y paginación opcional.
        Incluye búsqueda por usuario asignado (u.usuario, u.nombre).
        """
        cur = mysql.connection.cursor(DictCursor)
        try:
            # Normaliza entradas
            q = (q or "").strip()
            start_date = (start_date or "").strip() or None
            end_date  = (end_date or "").strip() or None

            # Usaremos FOUND_ROWS sólo si solicitamos paginación
            use_count = (limit is not None)
            has_feria_column = Lead._leads_has_feria_column()

            # Subconsulta para obtener los datos del ÚLTIMO seguimiento
            subquery_latest_seguimiento = Lead._SUBQUERY_LATEST_SEGUIMIENTO_BASE 
            
            select_clause = "SELECT "
            if use_count:
                select_clause += "SQL_CALC_FOUND_ROWS "

            select_clause += """
                        l.id, l.codigo, l.fecha, l.telefono, l.ruc_dni, l.nombre,
                        l.canal_id, l.contacto, l.direccion, l.departamento, l.provincia,
                        l.distrito, l.bien_servicio_id, l.email, l.comentario, l.asignado_a,
                        l.negocio_id,
                        n.slug AS negocio_slug, n.nombre AS negocio_nombre,
                        bs.nombre AS bien_servicio,
                        
                        -- Campos solicitados del último seguimiento y sus tablas relacionadas
                        s.monto AS ultimo_monto,
                        m.nombre_moneda AS ultimo_moneda_nombre,
                        p.nombre_proceso AS ultimo_proceso_nombre,
                        s.comentario AS ultimo_comentario,
                        s.usuario_id AS ultimo_seguimiento_usuario_id,
                        u.usuario AS usuario_usuario,
                        u.nombre  AS usuario_nombre
            """

            sql = select_clause + f"""
                FROM leads l
                LEFT JOIN bienes_servicios bs ON bs.id = l.bien_servicio_id
                LEFT JOIN negocios n ON n.id = l.negocio_id
                -- LEFT JOIN con la subconsulta del último seguimiento
                LEFT JOIN ({subquery_latest_seguimiento}) s ON s.lead_id = l.id
                -- LEFT JOIN para obtener el nombre de la moneda
                LEFT JOIN moneda m ON m.id = s.moneda_id
                -- LEFT JOIN para obtener el nombre del proceso
                LEFT JOIN proceso p ON p.id = s.proceso_id
                -- LEFT JOIN para obtener datos del usuario asignado (permite buscar por usuario/nombre)
                LEFT JOIN usuarios u ON u.id = l.asignado_a
                LEFT JOIN canales_recepcion cr ON cr.id = l.canal_id
                LEFT JOIN canal_contacto cc ON cc.id = s.canal_contacto
                LEFT JOIN motivo_no_venta mnv ON mnv.id = s.motivo_no_venta_id
                WHERE 1=1
            """
            if has_feria_column:
                sql = sql.replace(
                    "WHERE 1=1",
                    "LEFT JOIN marketing_ferias mf ON mf.id = l.feria_id\n                WHERE 1=1",
                    1,
                )
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

            # Búsqueda libre (incluye l.comentario, s.comentario y usuario.usuario/usuario.nombre)
            if q:
                like = f"%{q}%"
                search_fields = [
                    "COALESCE(l.codigo,'')",
                    "COALESCE(CAST(l.id AS CHAR),'')",
                    "COALESCE(CAST(l.fecha AS CHAR),'')",
                    "COALESCE(l.telefono,'')",
                    "COALESCE(l.ruc_dni,'')",
                    "COALESCE(l.nombre,'')",
                    "COALESCE(l.contacto,'')",
                    "COALESCE(l.direccion,'')",
                    "COALESCE(l.departamento,'')",
                    "COALESCE(l.provincia,'')",
                    "COALESCE(l.distrito,'')",
                    "COALESCE(l.email,'')",
                    "COALESCE(l.comentario,'')",
                    "COALESCE(CAST(l.canal_id AS CHAR),'')",
                    "COALESCE(CAST(l.bien_servicio_id AS CHAR),'')",
                    "COALESCE(CAST(l.asignado_a AS CHAR),'')",
                    "COALESCE(CAST(l.negocio_id AS CHAR),'')",
                    "COALESCE(bs.nombre,'')",
                    "COALESCE(n.slug,'')",
                    "COALESCE(n.nombre,'')",
                    "COALESCE(u.usuario,'')",
                    "COALESCE(u.nombre,'')",
                    "COALESCE(cr.nombre,'')",
                    "COALESCE(CAST(s.fecha_guardado AS CHAR),'')",
                    "COALESCE(CAST(s.fecha_programada AS CHAR),'')",
                    "COALESCE(CAST(s.cotizacion AS CHAR),'')",
                    "COALESCE(CAST(s.monto AS CHAR),'')",
                    "COALESCE(s.comentario,'')",
                    "COALESCE(CAST(s.canal_contacto AS CHAR),'')",
                    "COALESCE(cc.nombre,'')",
                    "COALESCE(p.nombre_proceso,'')",
                    "COALESCE(m.nombre_moneda,'')",
                    "COALESCE(mnv.motivo_no_venta,'')",
                ]
                if has_feria_column:
                    search_fields.extend([
                        "COALESCE(CAST(l.feria_id AS CHAR),'')",
                        "COALESCE(mf.nombre,'')",
                    ])

                sql += "\n                AND (" + " OR ".join(f"{field} LIKE %s" for field in search_fields) + ")"
                params.extend([like] * len(search_fields))

            sql += " ORDER BY l.fecha DESC, l.id DESC"
            # Aplicar orden según parámetro 'sort' (default DESC)
            sort_dir = (sort or 'desc').strip().lower()
            if sort_dir not in ('asc', 'desc'):
                sort_dir = 'desc'
            # Reemplazamos el ORDER BY con la dirección solicitada
            sql = sql.rsplit('ORDER BY', 1)[0]
            sql += f" ORDER BY l.fecha {sort_dir.upper()}, l.id {sort_dir.upper()}"

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
        
# ...existing code...


    # ============================================================
    # Funciones de listado por proceso (refactorizadas con un helper)
    # ============================================================

    # Plantilla de consulta para procesos específicos (SIN el WHERE base)
    _BASE_PROCESS_LIST_SQL = """
        SELECT
            l.id, l.codigo, l.fecha, l.telefono, l.ruc_dni, l.nombre, l.contacto,
            l.direccion, l.departamento, l.provincia, l.distrito, l.email,
            su.comentario AS comentario,
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
    
    @staticmethod
# ...existing code...
    def _execute_process_list_query(
        process_name,
        id_rol,
        user_id,
        q="",
        custom_order_field=None,
        extra_search_fields=None,
        limit=None,
        offset=None,
        sort='desc',
        start_date=None,
        end_date=None,
    ):
        """
        Helper interno para manejar la lógica repetitiva de listado por proceso,
        SOPORTA PAGINACIÓN (limit y offset) y devuelve (leads, total).
        Incluye JOIN a usuarios para permitir búsqueda por asesor sin romper la consulta de conteo.
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
            has_feria_column = Lead._leads_has_feria_column()
            
            # 1. CONSTRUIR CLÁUSULAS (WHERE, PARAMS)
            
            # === INICIO DE CONSTRUCCIÓN DE LA CLÁUSULA WHERE (Común a SELECT y COUNT) ===
            where_clause = " WHERE su.proceso_id = %s"
            params = [proc_id]

            if Lead._is_asesor(id_rol):
                where_clause += " AND l.asignado_a = %s"
                params.append(user_id)

            q = (q or "").strip()
            start_date = (start_date or "").strip() or None
            end_date = (end_date or "").strip() or None

            # Filtro por rango de fechas sobre la fecha de creación del lead (l.fecha)
            if start_date:
                where_clause += " AND l.fecha >= %s"
                params.append(start_date)
            if end_date:
                where_clause += " AND l.fecha <= %s"
                params.append(end_date)
            
            if q:
                like = f"%{q}%"
                search_fields = [
                    "COALESCE(l.codigo,'')",
                    "COALESCE(CAST(l.id AS CHAR),'')",
                    "COALESCE(CAST(l.fecha AS CHAR),'')",
                    "COALESCE(l.telefono,'')",
                    "COALESCE(l.ruc_dni,'')",
                    "COALESCE(l.nombre,'')",
                    "COALESCE(l.contacto,'')",
                    "COALESCE(l.direccion,'')",
                    "COALESCE(l.departamento,'')",
                    "COALESCE(l.provincia,'')",
                    "COALESCE(l.distrito,'')",
                    "COALESCE(l.email,'')",
                    "COALESCE(l.comentario,'')",
                    "COALESCE(CAST(l.canal_id AS CHAR),'')",
                    "COALESCE(CAST(l.bien_servicio_id AS CHAR),'')",
                    "COALESCE(CAST(l.asignado_a AS CHAR),'')",
                    "COALESCE(CAST(l.negocio_id AS CHAR),'')",
                    "COALESCE(bs.nombre,'')",
                    "COALESCE(n.slug,'')",
                    "COALESCE(n.nombre,'')",
                    "COALESCE(cr.nombre,'')",
                    "COALESCE(u.usuario,'')",
                    "COALESCE(u.nombre,'')",
                    "COALESCE(pp.nombre_proceso,'')",
                    "COALESCE(CAST(su.fecha_guardado AS CHAR),'')",
                    "COALESCE(CAST(su.fecha_programada AS CHAR),'')",
                    "COALESCE(CAST(su.cotizacion AS CHAR),'')",
                    "COALESCE(CAST(su.monto AS CHAR),'')",
                    "COALESCE(su.comentario,'')",
                    "COALESCE(CAST(su.canal_contacto AS CHAR),'')",
                    "COALESCE(cc.nombre,'')",
                    "COALESCE(m.nombre_moneda,'')",
                    "COALESCE(mnv.motivo_no_venta,'')",
                ]
                if has_feria_column:
                    search_fields.extend([
                        "COALESCE(CAST(l.feria_id AS CHAR),'')",
                        "COALESCE(mf.nombre,'')",
                    ])
                if extra_search_fields:
                    search_fields.extend(extra_search_fields)

                where_clause += "\n                    AND (" + " OR ".join(f"{field} LIKE %s" for field in search_fields) + ")"
                params.extend([like] * len(search_fields))
            
            # === FIN DE CONSTRUCCIÓN DE LA CLÁUSULA WHERE ===

            # 💡 CORRECCIÓN DE JOIN EN COUNT: incluir LEFT JOIN usuarios u para que WHERE pueda referenciar u.* 
            count_sql = f"""
                SELECT COUNT(l.id) AS total_count
                FROM leads l
                JOIN ({Lead._SUBQUERY_LATEST_SEGUIMIENTO_BASE}) AS latest_seg 
                    ON latest_seg.lead_id = l.id
                JOIN seguimientos su 
                    ON su.id = latest_seg.last_id
                LEFT JOIN bienes_servicios bs 
                    ON bs.id = l.bien_servicio_id
                LEFT JOIN usuarios u ON u.id = l.asignado_a
                LEFT JOIN negocios n ON n.id = l.negocio_id
                LEFT JOIN canales_recepcion cr ON cr.id = l.canal_id
                LEFT JOIN proceso pp ON pp.id = su.proceso_id
                LEFT JOIN canal_contacto cc ON cc.id = su.canal_contacto
                LEFT JOIN moneda m ON m.id = su.moneda_id
                LEFT JOIN motivo_no_venta mnv ON mnv.id = su.motivo_no_venta_id
                {where_clause}
            """
            if has_feria_column:
                count_sql = count_sql.replace(
                    "LEFT JOIN motivo_no_venta mnv ON mnv.id = su.motivo_no_venta_id",
                    "LEFT JOIN motivo_no_venta mnv ON mnv.id = su.motivo_no_venta_id\n                LEFT JOIN marketing_ferias mf ON mf.id = l.feria_id",
                    1,
                )
            
            # 2. Ejecutar conteo
            cur.execute(count_sql, params)
            tr = cur.fetchone()
            total = int(tr['total_count']) if tr and 'total_count' in tr else 0

            # 3. OBTENER LOS LEADS PAGINADOS (con límite/offset)
            
            # Aseguramos que la consulta final también tenga JOIN a usuarios (para coherencia)
            # Rebuild select base agregando usuarios join si no está (BASE_PROCESS_LIST_SQL no incluye usuarios)
            sql_final = (
                base_sql_select
                + " LEFT JOIN usuarios u ON u.id = l.asignado_a"
                + " LEFT JOIN negocios n ON n.id = l.negocio_id"
                + " LEFT JOIN canales_recepcion cr ON cr.id = l.canal_id"
                + " LEFT JOIN proceso pp ON pp.id = su.proceso_id"
                + " LEFT JOIN canal_contacto cc ON cc.id = su.canal_contacto"
            )
            if has_feria_column:
                sql_final += " LEFT JOIN marketing_ferias mf ON mf.id = l.feria_id"
            sql_final += " " + where_clause

            # Definir orden según parámetro 'sort'
            sort_dir = (sort or 'desc').strip().lower()
            if sort_dir not in ('asc', 'desc'):
                sort_dir = 'desc'

            # Si el campo personalizado ya contiene ASC/DESC explícito, lo respetamos.
            if custom_order_field:
                # Si custom_order_field contiene una dirección explícita (ASC/DESC),
                # la reemplazamos por la solicitada en `sort_dir` para permitir
                # que la UI invierta el orden cuando el campo es por fecha programada.
                try:
                    # Reemplaza la última ocurrencia de ASC|DESC (ignorando mayúsc/minúsc)
                    def _replace_dir(match):
                        return ' ' + sort_dir.upper()

                    if re.search(r"\b(ASC|DESC)\b", custom_order_field, flags=re.IGNORECASE):
                        # Reemplazar solamente la última dirección encontrada
                        custom_order_field_repl = re.sub(r"\s+(ASC|DESC)\s*$", ' ' + sort_dir.upper(), custom_order_field, flags=re.IGNORECASE)
                    else:
                        custom_order_field_repl = f"{custom_order_field} {sort_dir.upper()}"
                except Exception:
                    custom_order_field_repl = f"{custom_order_field} {sort_dir.upper()}"

                order_by_clause = f" ORDER BY {custom_order_field_repl}, su.fecha_guardado {sort_dir.upper()}, l.id {sort_dir.upper()}"
            else:
                order_by_clause = f" ORDER BY su.fecha_guardado {sort_dir.upper()}, l.id {sort_dir.upper()}"
            sql_final += order_by_clause

            # Agregar paginación
            exec_params = list(params)  # copiar lista
            if limit is not None:
                sql_final += " LIMIT %s"
                exec_params.append(limit)
                if offset is not None:
                    sql_final += " OFFSET %s"
                    exec_params.append(offset)
            
            cur.execute(sql_final, exec_params)
            rows = cur.fetchall()
            
        finally:
            cur.close()
            
        return Lead._apply_name_resolution(rows), total
# ...existing code...

    # ============================================================
    # Último seguimiento = "No iniciado"
    # ============================================================
    @staticmethod
    def list_unstarted_for_user(id_rol, user_id, q=None, limit=None, offset=None, sort='desc', start_date=None, end_date=None):
        """
        Lista leads en proceso 'No Iniciado'.
        Ahora acepta limit y offset para paginación.
        """
        # Llama al helper que ahora debe aceptar limit y offset
        return Lead._execute_process_list_query(
            'no iniciado',
            id_rol,
            user_id,
            q,
            limit=limit,
            offset=offset,
            sort=sort,
            start_date=start_date,
            end_date=end_date,
        )

    # ============================================================
    # Último seguimiento = "Seguimiento"
    # ============================================================
    @staticmethod
    def list_in_followup_for_user(id_rol, user_id, q="", limit=None, offset=None, sort='desc', start_date=None, end_date=None):
        """Lista leads cuyo último seguimiento es 'Seguimiento'."""
        return Lead._execute_process_list_query(
            "seguimiento",
            id_rol,
            user_id,
            q,
            limit=limit,
            offset=offset,
            sort=sort,
            start_date=start_date,
            end_date=end_date,
        )

    # ============================================================
    # Último seguimiento = "Programado"
    # ============================================================
    @staticmethod
    def list_programmed_for_user(id_rol, user_id, q="", limit=None, offset=None, sort='desc', start_date=None, end_date=None):
        """Lista leads cuyo último seguimiento es 'Programado' (ordenados por fecha programada ascendente)."""
        return Lead._execute_process_list_query(
            "programado", 
            id_rol, 
            user_id, 
            q, 
            custom_order_field="su.fecha_programada ASC",
            limit=limit, 
            offset=offset,
            sort=sort,
            start_date=start_date,
            end_date=end_date,
        )

    # ============================================================
    # Último seguimiento = "Cotizado"
    # ============================================================
    @staticmethod
    def list_quoted_for_user(id_rol, user_id, q="", limit=None, offset=None, sort='desc', start_date=None, end_date=None):
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
            offset=offset,
            sort=sort,
            start_date=start_date,
            end_date=end_date,
        )

    # ============================================================
    # Último seguimiento = "Cerrado"
    # ============================================================
    @staticmethod
    def list_closed_for_user(id_rol, user_id, q="", limit=None, offset=None, sort='desc', start_date=None, end_date=None):
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
            offset=offset,
            sort=sort,
            start_date=start_date,
            end_date=end_date,
        )

    # ============================================================
    # Último seguimiento = "Cerrado No Vendido"
    # ============================================================
    @staticmethod
    def list_closed_lost_for_user(id_rol, user_id, q="", limit=None, offset=None, sort='desc', start_date=None, end_date=None):
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
            offset=offset,
            sort=sort,
            start_date=start_date,
            end_date=end_date,
        )
