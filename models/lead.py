# models/lead.py
from extensions import mysql
import MySQLdb.cursors
from MySQLdb.cursors import DictCursor
from MySQLdb import IntegrityError  # <— añade esto arriba
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

    # ------------------------
    # Crear lead
    # ------------------------
    @staticmethod
    def create(data):
        cur = mysql.connection.cursor()
        try:
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
            mysql.connection.commit()
            return cur.lastrowid
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
        cur.execute("SELECT codigo FROM leads ORDER BY id DESC LIMIT 1")
        row = cur.fetchone()
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
        cur.execute("SELECT * FROM leads WHERE id = %s", (id,))
        lead = cur.fetchone()
        cur.close()
        return lead

    # ------------------------
    # Obtener por CÓDIGO
    # ------------------------
    @staticmethod
    def get_by_codigo(codigo):
        cur = mysql.connection.cursor(DictCursor)
        cur.execute("SELECT * FROM leads WHERE codigo = %s", (codigo,))
        row = cur.fetchone()
        cur.close()
        return row

    # ------------------------
    # Actualizar por ID
    # ------------------------
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
                canal_map[cid] = cname
        return canal_map

    @staticmethod
    def _build_user_cache(user_ids):
        cache = {}
        for uid in (uid for uid in user_ids if uid):
            try:
                u = User.get_by_id(uid)
            except Exception:
                u = None
            if isinstance(u, dict):
                display = (
                    u.get("username")
                    or u.get("usuario")
                    or u.get("nombre")
                    or u.get("email")
                    or str(uid)
                )
            else:
                display = (
                    getattr(u, "username", None)
                    or getattr(u, "usuario", None)
                    or getattr(u, "nombre", None)
                    or getattr(u, "email", None)
                    or str(uid)
                )
            cache[uid] = display
        return cache

    @staticmethod
    def _apply_name_resolution(rows):
        """Agrega `canal` y normaliza `asignado_a` en las filas ya obtenidas."""
        canal_map = Lead._build_canal_map()
        user_ids = {r.get("asignado_a") for r in rows if r.get("asignado_a")}
        user_cache = Lead._build_user_cache(user_ids)
        for r in rows:
            r["canal"] = canal_map.get(r.get("canal_id")) or ""
            uid = r.get("asignado_a")
            r["asignado_a"] = user_cache.get(uid, "") if uid else ""
        return rows

    @staticmethod
    def _is_asesor(id_rol):
        """Soporta 'asesor' como string o constante ROLE_ASESOR."""
        try:
            from utils.security import ROLE_ASESOR

            if id_rol == ROLE_ASESOR:
                return True
        except Exception:
            pass
        return str(id_rol).strip().lower() in ("asesor", "role_asesor")

# ============================================================
# Listados generales
# ============================================================
    @staticmethod
    def list_for_user(id_rol, user_id, q="", start_date=None, end_date=None):
        """
        Lista 'Todos los leads' con filtros opcionales:
        - q: búsqueda libre
        - start_date / end_date: rango por l.fecha (YYYY-MM-DD)
        """
        # Delegamos en search_for_user para no duplicar lógica
        return Lead.search_for_user(
            id_rol=id_rol,
            user_id=user_id,
            q=q,
            start_date=start_date,
            end_date=end_date,
        )

    @staticmethod
    def search_for_user(id_rol, user_id, q="", start_date=None, end_date=None):
        """Búsqueda libre en 'Todos los leads' con rango de fechas opcional."""
        cur = mysql.connection.cursor(DictCursor)

        # Normaliza entradas
        q = (q or "").strip()
        start_date = (start_date or "").strip() or None
        end_date   = (end_date or "").strip() or None

        sql = """
            SELECT 
                l.id, l.codigo, l.fecha, l.telefono, l.ruc_dni, l.nombre,
                l.canal_id, l.contacto, l.direccion, l.departamento, l.provincia,
                l.distrito, l.bien_servicio_id, l.email, l.comentario, l.asignado_a,
                bs.nombre AS bien_servicio
            FROM leads l
            LEFT JOIN bienes_servicios bs ON bs.id = l.bien_servicio_id
            WHERE 1=1
        """
        params = []

        # Si es asesor: solo sus leads
        if Lead._is_asesor(id_rol):
            sql += " AND l.asignado_a = %s"
            params.append(user_id)

        # Filtro por rango de fechas
        if start_date:
            sql += " AND l.fecha >= %s"
            params.append(start_date)
        if end_date:
            sql += " AND l.fecha <= %s"
            params.append(end_date)

        # Búsqueda libre
        if q:
            like = f"%{q}%"
            sql += """
            AND (
            l.codigo LIKE %s OR l.telefono LIKE %s OR l.ruc_dni LIKE %s OR
            l.nombre LIKE %s OR l.contacto LIKE %s OR l.direccion LIKE %s OR
            l.departamento LIKE %s OR l.provincia LIKE %s OR l.distrito LIKE %s OR
            l.email LIKE %s OR COALESCE(bs.nombre,'') LIKE %s
            )
            """
            params.extend([like] * 11)

        sql += " ORDER BY l.fecha DESC, l.id DESC"

        cur.execute(sql, params)
        rows = cur.fetchall()
        cur.close()

        return Lead._apply_name_resolution(rows)



        

    # ============================================================
    # Último seguimiento = "No iniciado"
    # ============================================================
    @staticmethod
    def list_unstarted_for_user(id_rol, user_id, q=""):
        procesos = Proceso.get_all()
        no_iniciado_id = None
        for p in procesos:
            pname = (
                p["nombre_proceso"]
                if isinstance(p, dict)
                else getattr(p, "nombre_proceso", "")
            ) or ""
            if pname.strip().lower() == "no iniciado":
                no_iniciado_id = p["id"] if isinstance(p, dict) else getattr(p, "id", None)
                break
        if no_iniciado_id is None:
            return []

        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        sql = """
        SELECT
          l.id, l.codigo, l.fecha, l.telefono, l.ruc_dni, l.nombre, l.contacto,
          l.direccion, l.departamento, l.provincia, l.distrito, l.email, l.comentario,
          l.canal_id, l.asignado_a,
          bs.nombre AS bien_servicio,
          su.fecha_guardado AS ultimo_guardado
        FROM leads l
        JOIN (
          SELECT s1.lead_id, s1.id AS last_id
          FROM seguimientos s1
          LEFT JOIN seguimientos s2
            ON s2.lead_id = s1.lead_id
           AND (
                s2.fecha_guardado > s1.fecha_guardado
                OR (s2.fecha_guardado = s1.fecha_guardado AND s2.id > s1.id)
           )
          WHERE s2.id IS NULL
        ) last ON last.lead_id = l.id
        JOIN seguimientos su ON su.id = last.last_id
        LEFT JOIN bienes_servicios bs ON bs.id = l.bien_servicio_id
        WHERE su.proceso_id = %s
        """
        params = [no_iniciado_id]

        if Lead._is_asesor(id_rol):
            sql += " AND l.asignado_a = %s"
            params.append(user_id)

        q = (q or "").strip()
        if q:
            like = f"%{q}%"
            sql += """
            AND (
              l.codigo LIKE %s OR l.telefono LIKE %s OR l.ruc_dni LIKE %s OR
              l.nombre LIKE %s OR l.contacto LIKE %s OR l.direccion LIKE %s OR
              l.departamento LIKE %s OR l.provincia LIKE %s OR l.distrito LIKE %s OR
              l.email LIKE %s OR COALESCE(bs.nombre,'') LIKE %s
            )
            """
            params.extend([like] * 11)

        sql += " ORDER BY su.fecha_guardado DESC, l.id DESC"
        cur.execute(sql, params)
        rows = cur.fetchall()
        cur.close()
        return Lead._apply_name_resolution(rows)

    # ============================================================
    # Último seguimiento = "Seguimiento"
    # ============================================================
    @staticmethod
    def list_in_followup_for_user(id_rol, user_id, q=""):
        procesos = Proceso.get_all()
        seguimiento_id = None
        for p in procesos:
            pname = (p["nombre_proceso"] if isinstance(p, dict) else getattr(p, "nombre_proceso", "")) or ""
            if pname.strip().lower() == "seguimiento":
                seguimiento_id = p["id"] if isinstance(p, dict) else getattr(p, "id", None)
                break
        if seguimiento_id is None:
            return []

        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        sql = """
        SELECT
          l.id, l.codigo, l.fecha, l.telefono, l.ruc_dni, l.nombre, l.contacto,
          l.direccion, l.departamento, l.provincia, l.distrito, l.email, l.comentario,
          l.canal_id, l.asignado_a,
          bs.nombre AS bien_servicio,
          su.fecha_guardado AS ultimo_guardado
        FROM leads l
        JOIN (
          SELECT s1.lead_id, s1.id AS last_id
          FROM seguimientos s1
          LEFT JOIN seguimientos s2
            ON s2.lead_id = s1.lead_id
           AND (
                s2.fecha_guardado > s1.fecha_guardado
                OR (s2.fecha_guardado = s1.fecha_guardado AND s2.id > s1.id)
           )
          WHERE s2.id IS NULL
        ) last ON last.lead_id = l.id
        JOIN seguimientos su ON su.id = last.last_id
        LEFT JOIN bienes_servicios bs ON bs.id = l.bien_servicio_id
        WHERE su.proceso_id = %s
        """
        params = [seguimiento_id]

        if Lead._is_asesor(id_rol):
            sql += " AND l.asignado_a = %s"
            params.append(user_id)

        q = (q or "").strip()
        if q:
            like = f"%{q}%"
            sql += """
            AND (
              l.codigo LIKE %s OR l.telefono LIKE %s OR l.ruc_dni LIKE %s OR
              l.nombre LIKE %s OR l.contacto LIKE %s OR l.direccion LIKE %s OR
              l.departamento LIKE %s OR l.provincia LIKE %s OR l.distrito LIKE %s OR
              l.email LIKE %s OR COALESCE(bs.nombre,'') LIKE %s
            )
            """
            params.extend([like] * 11)

        sql += " ORDER BY su.fecha_guardado DESC, l.id DESC"
        cur.execute(sql, params)
        rows = cur.fetchall()
        cur.close()
        return Lead._apply_name_resolution(rows)

    # ============================================================
    # Último seguimiento = "Programado"
    # ============================================================
    @staticmethod
    def list_programmed_for_user(id_rol, user_id, q=""):
        procesos = Proceso.get_all()
        programado_id = None
        for p in procesos:
            pname = (p["nombre_proceso"] if isinstance(p, dict) else getattr(p, "nombre_proceso", "")) or ""
            if pname.strip().lower() == "programado":
                programado_id = p["id"] if isinstance(p, dict) else getattr(p, "id", None)
                break
        if programado_id is None:
            return []

        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        sql = """
        SELECT
          l.id, l.codigo, l.fecha, l.telefono, l.ruc_dni, l.nombre, l.contacto,
          l.direccion, l.departamento, l.provincia, l.distrito, l.email, l.comentario,
          l.canal_id, l.asignado_a,
          bs.nombre AS bien_servicio,
          su.fecha_programada AS fecha_programada,
          su.fecha_guardado   AS ultimo_guardado
        FROM leads l
        JOIN (
          SELECT s1.lead_id, s1.id AS last_id
          FROM seguimientos s1
          LEFT JOIN seguimientos s2
            ON s2.lead_id = s1.lead_id
           AND (
                s2.fecha_guardado > s1.fecha_guardado
                OR (s2.fecha_guardado = s1.fecha_guardado AND s2.id > s1.id)
           )
          WHERE s2.id IS NULL
        ) last ON last.lead_id = l.id
        JOIN seguimientos su ON su.id = last.last_id
        LEFT JOIN bienes_servicios bs ON bs.id = l.bien_servicio_id
        WHERE su.proceso_id = %s
        """
        params = [programado_id]

        if Lead._is_asesor(id_rol):
            sql += " AND l.asignado_a = %s"
            params.append(user_id)

        q = (q or "").strip()
        if q:
            like = f"%{q}%"
            sql += """
            AND (
              l.codigo LIKE %s OR l.telefono LIKE %s OR l.ruc_dni LIKE %s OR
              l.nombre LIKE %s OR l.contacto LIKE %s OR l.direccion LIKE %s OR
              l.departamento LIKE %s OR l.provincia LIKE %s OR l.distrito LIKE %s OR
              l.email LIKE %s OR COALESCE(bs.nombre,'') LIKE %s
            )
            """
            params.extend([like] * 11)

        # Próximos primero por fecha_programada, luego reciente por último guardado
        sql += " ORDER BY su.fecha_programada ASC, su.fecha_guardado DESC, l.id DESC"
        cur.execute(sql, params)
        rows = cur.fetchall()
        cur.close()
        return Lead._apply_name_resolution(rows)

    # ============================================================
    # Último seguimiento = "Cotizado"
    # ============================================================
    @staticmethod
    def list_quoted_for_user(id_rol, user_id, q=""):
        procesos = Proceso.get_all()
        cotizado_id = None
        for p in procesos:
            pname = (p["nombre_proceso"] if isinstance(p, dict) else getattr(p, "nombre_proceso", "")) or ""
            if pname.strip().lower() == "cotizado":
                cotizado_id = p["id"] if isinstance(p, dict) else getattr(p, "id", None)
                break
        if cotizado_id is None:
            return []

        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        sql = """
        SELECT
          l.id, l.codigo, l.fecha, l.telefono, l.ruc_dni, l.nombre, l.contacto,
          l.direccion, l.departamento, l.provincia, l.distrito, l.email, l.comentario,
          l.canal_id, l.asignado_a,
          bs.nombre AS bien_servicio,
          su.cotizacion, su.monto, m.nombre_moneda AS moneda,
          su.fecha_guardado AS ultimo_guardado
        FROM leads l
        JOIN (
          SELECT s1.lead_id, s1.id AS last_id
          FROM seguimientos s1
          LEFT JOIN seguimientos s2
            ON s2.lead_id = s1.lead_id
           AND (
                s2.fecha_guardado > s1.fecha_guardado
                OR (s2.fecha_guardado = s1.fecha_guardado AND s2.id > s1.id)
           )
          WHERE s2.id IS NULL
        ) last ON last.lead_id = l.id
        JOIN seguimientos su ON su.id = last.last_id
        LEFT JOIN bienes_servicios bs ON bs.id = l.bien_servicio_id
        LEFT JOIN moneda m ON m.id = su.moneda_id
        WHERE su.proceso_id = %s
        """
        params = [cotizado_id]

        if Lead._is_asesor(id_rol):
            sql += " AND l.asignado_a = %s"
            params.append(user_id)

        q = (q or "").strip()
        if q:
            like = f"%{q}%"
            sql += """
            AND (
              l.codigo LIKE %s OR l.telefono LIKE %s OR l.ruc_dni LIKE %s OR
              l.nombre LIKE %s OR l.contacto LIKE %s OR l.direccion LIKE %s OR
              l.departamento LIKE %s OR l.provincia LIKE %s OR l.distrito LIKE %s OR
              l.email LIKE %s OR COALESCE(bs.nombre,'') LIKE %s OR
              COALESCE(su.cotizacion,'') LIKE %s OR
              COALESCE(m.nombre_moneda,'') LIKE %s OR
              CAST(COALESCE(su.monto,0) AS CHAR) LIKE %s
            )
            """
            params.extend([like] * 14)

        sql += " ORDER BY su.fecha_guardado DESC, l.id DESC"
        cur.execute(sql, params)
        rows = cur.fetchall()
        cur.close()
        return Lead._apply_name_resolution(rows)

    # ============================================================
    # Último seguimiento = "Cerrado"
    # ============================================================
    @staticmethod
    def list_closed_for_user(id_rol, user_id, q=""):
        procesos = Proceso.get_all()
        cerrado_id = None
        for p in procesos:
            pname = (p["nombre_proceso"] if isinstance(p, dict) else getattr(p, "nombre_proceso", "")) or ""
            if pname.strip().lower() == "cerrado":
                cerrado_id = p["id"] if isinstance(p, dict) else getattr(p, "id", None)
                break
        if cerrado_id is None:
            return []

        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        sql = """
        SELECT
          l.id, l.codigo, l.fecha, l.telefono, l.ruc_dni, l.nombre, l.contacto,
          l.direccion, l.departamento, l.provincia, l.distrito, l.email, l.comentario,
          l.canal_id, l.asignado_a,
          bs.nombre AS bien_servicio,
          su.fecha_programada, su.cotizacion, su.monto, m.nombre_moneda AS moneda,
          su.fecha_guardado AS ultimo_guardado
        FROM leads l
        JOIN (
          SELECT s1.lead_id, s1.id AS last_id
          FROM seguimientos s1
          LEFT JOIN seguimientos s2
            ON s2.lead_id = s1.lead_id
           AND (
                s2.fecha_guardado > s1.fecha_guardado
                OR (s2.fecha_guardado = s1.fecha_guardado AND s2.id > s1.id)
           )
          WHERE s2.id IS NULL
        ) last ON last.lead_id = l.id
        JOIN seguimientos su ON su.id = last.last_id
        LEFT JOIN bienes_servicios bs ON bs.id = l.bien_servicio_id
        LEFT JOIN moneda m ON m.id = su.moneda_id
        WHERE su.proceso_id = %s
        """
        params = [cerrado_id]

        if Lead._is_asesor(id_rol):
            sql += " AND l.asignado_a = %s"
            params.append(user_id)

        q = (q or "").strip()
        if q:
            like = f"%{q}%"
            sql += """
            AND (
              l.codigo LIKE %s OR l.telefono LIKE %s OR l.ruc_dni LIKE %s OR
              l.nombre LIKE %s OR l.contacto LIKE %s OR l.direccion LIKE %s OR
              l.departamento LIKE %s OR l.provincia LIKE %s OR l.distrito LIKE %s OR
              l.email LIKE %s OR COALESCE(bs.nombre,'') LIKE %s OR
              COALESCE(su.cotizacion,'') LIKE %s OR
              COALESCE(m.nombre_moneda,'') LIKE %s OR
              CAST(COALESCE(su.monto,0) AS CHAR) LIKE %s
            )
            """
            params.extend([like] * 14)

        sql += " ORDER BY su.fecha_guardado DESC, l.id DESC"
        cur.execute(sql, params)
        rows = cur.fetchall()
        cur.close()
        return Lead._apply_name_resolution(rows)

    # ============================================================
    # Último seguimiento = "Cerrado No Vendido"
    # ============================================================
    @staticmethod
    def list_closed_lost_for_user(id_rol, user_id, q=""):
        procesos = Proceso.get_all()
        cnv_id = None
        for p in procesos:
            pname = (p["nombre_proceso"] if isinstance(p, dict) else getattr(p, "nombre_proceso", "")) or ""
            if pname.strip().lower() == "cerrado no vendido":
                cnv_id = p["id"] if isinstance(p, dict) else getattr(p, "id", None)
                break
        if cnv_id is None:
            return []

        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        sql = """
        SELECT
          l.id, l.codigo, l.fecha, l.telefono, l.ruc_dni, l.nombre, l.contacto,
          l.direccion, l.departamento, l.provincia, l.distrito, l.email, l.comentario,
          l.canal_id, l.asignado_a,
          bs.nombre AS bien_servicio,
          mnv.motivo_no_venta AS motivo_no_venta,
          su.fecha_guardado AS ultimo_guardado
        FROM leads l
        JOIN (
          SELECT s1.lead_id, s1.id AS last_id
          FROM seguimientos s1
          LEFT JOIN seguimientos s2
            ON s2.lead_id = s1.lead_id
           AND (
                s2.fecha_guardado > s1.fecha_guardado
                OR (s2.fecha_guardado = s1.fecha_guardado AND s2.id > s1.id)
           )
          WHERE s2.id IS NULL
        ) last ON last.lead_id = l.id
        JOIN seguimientos su ON su.id = last.last_id
        LEFT JOIN bienes_servicios bs ON bs.id = l.bien_servicio_id
        LEFT JOIN motivo_no_venta mnv ON mnv.id = su.motivo_no_venta_id
        WHERE su.proceso_id = %s
        """
        params = [cnv_id]

        if Lead._is_asesor(id_rol):
            sql += " AND l.asignado_a = %s"
            params.append(user_id)

        q = (q or "").strip()
        if q:
            like = f"%{q}%"
            sql += """
            AND (
              l.codigo LIKE %s OR l.telefono LIKE %s OR l.ruc_dni LIKE %s OR
              l.nombre LIKE %s OR l.contacto LIKE %s OR l.direccion LIKE %s OR
              l.departamento LIKE %s OR l.provincia LIKE %s OR l.distrito LIKE %s OR
              l.email LIKE %s OR COALESCE(bs.nombre,'') LIKE %s OR
              COALESCE(mnv.motivo_no_venta,'') LIKE %s
            )
            """
            params.extend([like] * 12)

        sql += " ORDER BY su.fecha_guardado DESC, l.id DESC"
        cur.execute(sql, params)
        rows = cur.fetchall()
        cur.close()
        return Lead._apply_name_resolution(rows)

