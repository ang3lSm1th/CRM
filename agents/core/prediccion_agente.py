import os
import re
import logging
from pathlib import Path

import joblib
import MySQLdb.cursors

from extensions import mysql
from utils.text_normalizer import normalize_user_text

logger = logging.getLogger(__name__)


class PrediccionCompraAgente:
    """Predice probabilidad de compra para un lead usando modelo ML entrenado."""

    def __init__(self):
        self.model_path = Path("models/ml_models/compra_model.pkl")
        self._model = None
        self._load_model()

    def _table_exists(self, table_name):
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            cur.execute(
                """
                SELECT COUNT(*) AS total
                FROM information_schema.TABLES
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = %s
                """,
                (table_name,),
            )
            row = cur.fetchone() or {}
            return int(row.get("total", 0)) > 0
        finally:
            cur.close()

    def _column_exists(self, table_name, column_name):
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            cur.execute(
                """
                SELECT COUNT(*) AS total
                FROM information_schema.COLUMNS
                WHERE TABLE_SCHEMA = DATABASE()
                  AND TABLE_NAME = %s
                  AND COLUMN_NAME = %s
                """,
                (table_name, column_name),
            )
            row = cur.fetchone() or {}
            return int(row.get("total", 0)) > 0
        finally:
            cur.close()

    def _load_model(self):
        if self.model_path.exists():
            try:
                self._model = joblib.load(self.model_path)
            except Exception:
                self._model = None

    def _extract_lead_id(self, question):
        q = normalize_user_text(question)
        patterns = [r"lead\s*#\s*(\d+)", r"lead\s*(\d+)", r"#(\d+)"]
        for pattern in patterns:
            m = re.search(pattern, q)
            if m:
                return int(m.group(1))
        return None

    def _fetch_lead_features(self, lead_id):
        if not self._table_exists("leads"):
            return None, "No existe la tabla leads en este esquema."

        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            cur.execute(
                """
                SELECT
                    l.id,
                    DATEDIFF(CURDATE(), l.fecha) AS dias_desde_alta,
                    CASE WHEN l.cliente_id IS NULL THEN 0 ELSE 1 END AS tiene_cliente,
                    COALESCE(s.total_seguimientos, 0) AS total_seguimientos,
                    COALESCE(s.dias_desde_ultimo_seguimiento, 999) AS dias_desde_ultimo_seguimiento,
                    COALESCE(s.monto_promedio, 0) AS monto_promedio_seguimiento
                FROM leads l
                LEFT JOIN (
                    SELECT
                        lead_id,
                        COUNT(*) AS total_seguimientos,
                        DATEDIFF(CURDATE(), MAX(fecha_guardado)) AS dias_desde_ultimo_seguimiento,
                        AVG(COALESCE(monto, 0)) AS monto_promedio
                    FROM seguimientos
                    GROUP BY lead_id
                ) s ON s.lead_id = l.id
                WHERE l.id = %s
                LIMIT 1
                """,
                (lead_id,),
            )
            row = cur.fetchone()
            if not row:
                return None, f"No se encontró el lead #{lead_id}."

            features = [
                float(row.get("dias_desde_alta") or 0),
                float(row.get("tiene_cliente") or 0),
                float(row.get("total_seguimientos") or 0),
                float(row.get("dias_desde_ultimo_seguimiento") or 999),
                float(row.get("monto_promedio_seguimiento") or 0),
            ]
            return {"lead_id": lead_id, "features": features}, None
        finally:
            cur.close()

    def _cache_prediction(self, lead_id, probabilidad, modelo_version):
        if not self._table_exists("predicciones_compra"):
            return

        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            cur.execute(
                """
                INSERT INTO predicciones_compra
                (lead_id, probabilidad_compra, modelo_version, created_at)
                VALUES (%s, %s, %s, NOW())
                """,
                (lead_id, probabilidad, modelo_version),
            )
            mysql.connection.commit()
        finally:
            cur.close()

    def _fetch_lead_engagement_metrics(self, lead_ids):
        """
        Obtiene métricas de engagement para cada lead:
        - Compras históricas (cliente recurrente): cuenta seguimientos CERRADOS de otros leads del mismo cliente
        - Cantidad de seguimientos totales (engagement): TODOS los seguimientos del cliente
        - Días desde último seguimiento (recencia): más reciente de cualquier lead del cliente
        - Monto promedio (seriedad/capacidad): promedio de montos en seguimientos del cliente
        - Proceso actual (estado del pipeline): proceso más reciente del lead actual
        """
        if not lead_ids or not self._table_exists("leads"):
            return {}

        unique_ids = []
        for lead_id in lead_ids:
            try:
                unique_ids.append(int(lead_id))
            except (TypeError, ValueError):
                continue
        unique_ids = list(dict.fromkeys(unique_ids))

        if not unique_ids:
            return {}

        placeholders = ",".join(["%s"] * len(unique_ids))
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            sql = f"""
                SELECT
                    l.id AS lead_id,
                    -- Compras del cliente: COUNT de seguimientos cerrados (excluyendo "cerrado no vendido")
                    COALESCE(
                        SUM(
                            CASE WHEN LOWER(TRIM(COALESCE(p.nombre_proceso, ''))) = 'cerrado'
                                 AND LOWER(TRIM(COALESCE(p.nombre_proceso, ''))) <> 'cerrado no vendido'
                                 THEN 1 ELSE 0 END
                        ),
                        0
                    ) AS compras_historicas,
                    -- Engagement: total de seguimientos del cliente (incluyendo otros leads)
                    COALESCE(COUNT(DISTINCT s.id), 0) AS total_seguimientos,
                    -- Recencia: días desde el último seguimiento del cliente
                    COALESCE(DATEDIFF(CURDATE(), MAX(s.fecha_guardado)), 999) AS dias_ultimo_seg,
                    -- Monto promedio de todos los seguimientos del cliente
                    COALESCE(AVG(CASE WHEN s.monto > 0 THEN s.monto END), 0) AS monto_promedio,
                    -- Proceso actual del lead específico (no del cliente)
                    COALESCE(p_actual.nombre_proceso, 'No iniciado') AS proceso_actual
                FROM leads l
                -- Encontrar todos los leads del mismo cliente (por RUC/DNI o teléfono)
                INNER JOIN leads cliente_leads ON (
                    (NULLIF(TRIM(l.ruc_dni), '') IS NOT NULL
                     AND TRIM(cliente_leads.ruc_dni) = TRIM(l.ruc_dni)
                     AND TRIM(l.ruc_dni) <> '')
                    OR
                    (NULLIF(TRIM(l.telefono), '') IS NOT NULL
                     AND TRIM(cliente_leads.telefono) = TRIM(l.telefono)
                     AND TRIM(l.telefono) <> '')
                )
                -- Todos los seguimientos del cliente
                LEFT JOIN seguimientos s ON s.lead_id = cliente_leads.id
                LEFT JOIN proceso p ON p.id = s.proceso_id
                -- Proceso actual del lead específico
                LEFT JOIN (
                    SELECT s2.lead_id, s2.proceso_id
                    FROM seguimientos s2
                    WHERE s2.id = (
                        SELECT MAX(id)
                        FROM seguimientos
                        WHERE lead_id = s2.lead_id
                    )
                ) s_actual ON s_actual.lead_id = l.id
                LEFT JOIN proceso p_actual ON p_actual.id = s_actual.proceso_id
                WHERE l.id IN ({placeholders})
                GROUP BY l.id, p_actual.nombre_proceso
            """
            cur.execute(sql, tuple(unique_ids))
            rows = cur.fetchall() or []

            metrics = {}
            for r in rows:
                if r.get("lead_id") is not None:
                    metrics[int(r["lead_id"])] = {
                        "compras_historicas": int(r.get("compras_historicas") or 0),
                        "total_seguimientos": int(r.get("total_seguimientos") or 0),
                        "dias_ultimo_seg": int(r.get("dias_ultimo_seg") or 999),
                        "monto_promedio": float(r.get("monto_promedio") or 0),
                        "proceso_actual": (r.get("proceso_actual") or "No iniciado")
                        .strip()
                        .lower(),
                    }

            # Asegurar que todos los leads tienen entrada
            for lid in unique_ids:
                if lid not in metrics:
                    metrics[lid] = {
                        "compras_historicas": 0,
                        "total_seguimientos": 0,
                        "dias_ultimo_seg": 999,
                        "monto_promedio": 0,
                        "proceso_actual": "no iniciado",
                    }
            return metrics
        finally:
            cur.close()

    def _calculate_prediction_score(self, metrics):
        """
        Calcula porcentaje de probabilidad de compra combinando múltiples factores:

        - Historial de compras (30%): cliente recurrente
        - Engagement/Seguimientos (25%): interacción activa
        - Recencia (20%): qué tan reciente fue el contacto
        - Proceso actual (15%): etapa del pipeline
        - Monto/Seriedad (10%): capacidad/seriedad de compra
        """
        compras = max(0, int(metrics.get("compras_historicas") or 0))
        seguimientos = max(0, int(metrics.get("total_seguimientos") or 0))
        dias_ultimo = min(999, int(metrics.get("dias_ultimo_seg") or 999))
        monto = max(0, float(metrics.get("monto_promedio") or 0))
        proceso = (metrics.get("proceso_actual") or "no iniciado").lower().strip()

        # ═════════════════════════════════════════════════════════════
        # FACTOR 1: Historial de compras (30%) — cliente recurrente
        # ═════════════════════════════════════════════════════════════
        # 0 compras: 0 pts  |  1: 10  |  2: 20  |  3+: 30
        score_compras = min(30, compras * 10)

        # ═════════════════════════════════════════════════════════════
        # FACTOR 2: Engagement (25%) — cantidad de seguimientos
        # ═════════════════════════════════════════════════════════════
        # 0 seg: 0 pts  |  1-2: 10  |  3-5: 15  |  6+: 25
        if seguimientos == 0:
            score_engagement = 0
        elif seguimientos <= 2:
            score_engagement = 8
        elif seguimientos <= 5:
            score_engagement = 15
        else:
            score_engagement = 25

        # ═════════════════════════════════════════════════════════════
        # FACTOR 3: Recencia (20%) — días desde último contacto
        # ═════════════════════════════════════════════════════════════
        # < 7 días: 20 pts  |  7-30: 15  |  31-60: 10  |  61-90: 5  |  90+: 0
        if dias_ultimo < 7:
            score_recencia = 20
        elif dias_ultimo < 30:
            score_recencia = 15
        elif dias_ultimo < 60:
            score_recencia = 10
        elif dias_ultimo < 90:
            score_recencia = 5
        else:
            score_recencia = 0

        # ═════════════════════════════════════════════════════════════
        # FACTOR 4: Proceso actual (15%) — etapa del pipeline
        # ═════════════════════════════════════════════════════════════
        # Cerrado: 15 (ya compró)  |  Cotizado: 12  |  Programado: 10
        # Seguimiento: 8  |  No iniciado: 2  |  Cerrado no vendido: 0
        process_map = {
            "cerrado": 15,
            "cotizado": 12,
            "programado": 10,
            "seguimiento": 8,
            "no iniciado": 2,
            "cerrado no vendido": 0,
        }
        score_proceso = process_map.get(proceso, 2)

        # ═════════════════════════════════════════════════════════════
        # FACTOR 5: Monto/Seriedad (10%) — capacidad de compra
        # ═════════════════════════════════════════════════════════════
        # Sin monto: 0 pts  |  > 0: 10 pts (tiene registro de dinero)
        score_monto = 10 if monto > 0 else 0

        # ═════════════════════════════════════════════════════════════
        # SUMA PONDERADA (máximo 100%)
        # ═════════════════════════════════════════════════════════════
        porcentaje = round(
            (
                score_compras
                + score_engagement
                + score_recencia
                + score_proceso
                + score_monto
            ),
            2,
        )
        return round(min(100.0, max(15.0, porcentaje)), 2)  # Mínimo 15%, máximo 100%

    def _fallback_metrics_for_lead(self, lead_id):
        """
        Fallback por lead para evitar dejar todos los leads en 15% cuando falla el query batch.
        """
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            cur.execute(
                """
                SELECT id, TRIM(COALESCE(ruc_dni, '')) AS ruc_dni, TRIM(COALESCE(telefono, '')) AS telefono
                FROM leads
                WHERE id = %s
                LIMIT 1
                """,
                (lead_id,),
            )
            lead_row = cur.fetchone() or {}
            ruc_dni = (lead_row.get("ruc_dni") or "").strip()
            telefono = (lead_row.get("telefono") or "").strip()

            if not ruc_dni and not telefono:
                cur.execute(
                    """
                    SELECT
                        COALESCE(SUM(CASE WHEN LOWER(TRIM(COALESCE(p.nombre_proceso, ''))) = 'cerrado' THEN 1 ELSE 0 END), 0) AS compras_historicas,
                        COALESCE(COUNT(s.id), 0) AS total_seguimientos,
                        COALESCE(DATEDIFF(CURDATE(), MAX(s.fecha_guardado)), 999) AS dias_ultimo_seg,
                        COALESCE(AVG(CASE WHEN s.monto > 0 THEN s.monto END), 0) AS monto_promedio
                    FROM seguimientos s
                    LEFT JOIN proceso p ON p.id = s.proceso_id
                    WHERE s.lead_id = %s
                    """,
                    (lead_id,),
                )
            else:
                clauses = []
                params = []
                if ruc_dni:
                    clauses.append("TRIM(COALESCE(h.ruc_dni, '')) = %s")
                    params.append(ruc_dni)
                if telefono:
                    clauses.append("TRIM(COALESCE(h.telefono, '')) = %s")
                    params.append(telefono)

                where_expr = " OR ".join(clauses) if clauses else "h.id = %s"
                if not clauses:
                    params.append(lead_id)

                cur.execute(
                    f"""
                    SELECT
                        COALESCE(SUM(CASE WHEN LOWER(TRIM(COALESCE(p.nombre_proceso, ''))) = 'cerrado' THEN 1 ELSE 0 END), 0) AS compras_historicas,
                        COALESCE(COUNT(s.id), 0) AS total_seguimientos,
                        COALESCE(DATEDIFF(CURDATE(), MAX(s.fecha_guardado)), 999) AS dias_ultimo_seg,
                        COALESCE(AVG(CASE WHEN s.monto > 0 THEN s.monto END), 0) AS monto_promedio
                    FROM leads h
                    LEFT JOIN seguimientos s ON s.lead_id = h.id
                    LEFT JOIN proceso p ON p.id = s.proceso_id
                    WHERE {where_expr}
                    """,
                    tuple(params),
                )

            agg = cur.fetchone() or {}

            cur.execute(
                """
                SELECT COALESCE(p.nombre_proceso, 'No iniciado') AS proceso_actual
                FROM seguimientos s
                LEFT JOIN proceso p ON p.id = s.proceso_id
                WHERE s.lead_id = %s
                ORDER BY s.id DESC
                LIMIT 1
                """,
                (lead_id,),
            )
            process_row = cur.fetchone() or {}

            return {
                "compras_historicas": int(agg.get("compras_historicas") or 0),
                "total_seguimientos": int(agg.get("total_seguimientos") or 0),
                "dias_ultimo_seg": int(agg.get("dias_ultimo_seg") or 999),
                "monto_promedio": float(agg.get("monto_promedio") or 0),
                "proceso_actual": (process_row.get("proceso_actual") or "No iniciado")
                .strip()
                .lower(),
            }
        finally:
            cur.close()

    def _generate_recommendation_message(self, metrics, porcentaje):
        """
        Genera un mensaje de recomendación para el asesor basado en la situación del cliente.
        """
        compras = int(metrics.get("compras_historicas") or 0)
        seguimientos = int(metrics.get("total_seguimientos") or 0)
        dias_ultimo = int(metrics.get("dias_ultimo_seg") or 999)
        monto = float(metrics.get("monto_promedio") or 0)
        proceso = (metrics.get("proceso_actual") or "no iniciado").lower().strip()

        messages = []

        # ═══════════════════════════════════════════════════════════
        # Mensajes por historial de compras
        # ═══════════════════════════════════════════════════════════
        if compras >= 3:
            messages.append(
                "🔄 Cliente VIP recurrente - Ofrecer paquete de renovación/upgrade"
            )
        elif compras == 2:
            messages.append("🔄 Cliente con 2 compras - Proponer ampliar pedido")
        elif compras == 1:
            messages.append(
                "🔄 Cliente que ya compró - Oferta de mantenimiento/servicio adicional"
            )

        # ═══════════════════════════════════════════════════════════
        # Mensajes por etapa del proceso
        # ═══════════════════════════════════════════════════════════
        if proceso == "cotizado":
            messages.append(
                "📋 Cotización lista - Hacer seguimiento en 2-3 días para aclarar dudas"
            )
        elif proceso == "programado":
            messages.append(
                "📅 Cita programada - Confirmar 24h antes, traer material de cierre"
            )
        elif proceso == "seguimiento":
            if seguimientos <= 2:
                messages.append(
                    "📞 Primer contacto - Enviar propuesta y presentación inicial"
                )
            elif seguimientos <= 4:
                messages.append(
                    "📞 En gestión - Aclarar objeciones y mantener presión positiva"
                )
            else:
                messages.append(
                    "📞 Alto engagement - Presionar cierre, ofrecer facilidades"
                )
        elif proceso == "no iniciado":
            messages.append(
                "⚠️ Lead sin gestionar - Contactar urgentemente, presentar propuesta"
            )
        elif proceso == "cerrado":
            messages.append(
                "🛒 Cliente en cierre confirmado - Enfocar estrategia en siguiente compra"
            )
        elif proceso == "cerrado no vendido":
            messages.append(
                "❌ Venta perdida - Investigar por qué, ofrecer alternativa diferente"
            )

        # ═══════════════════════════════════════════════════════════
        # Mensajes por recencia/inactividad
        # ═══════════════════════════════════════════════════════════
        if dias_ultimo < 3:
            messages.append(
                "🔥 Contacto muy reciente - Mantener el momentum, no dejar enfriar"
            )
        elif dias_ultimo >= 60 and dias_ultimo < 90:
            messages.append(
                "❄️ Lead algo frío - Reactivar con llamada o email de valor"
            )
        elif dias_ultimo >= 90:
            messages.append(
                "🧊 Lead muy frío - Reactivar con oferta especial o descuento"
            )

        # ═══════════════════════════════════════════════════════════
        # Mensajes por engagement/seguimientos
        # ═══════════════════════════════════════════════════════════
        if seguimientos == 0:
            messages.append("👤 Primer contacto pendiente - Llamar hoy mismo")
        elif seguimientos >= 6:
            messages.append(
                "🚀 Alta interacción - Cliente muy interesado, cerrar esta semana"
            )

        # ═══════════════════════════════════════════════════════════
        # Mensajes por monto registrado
        # ═══════════════════════════════════════════════════════════
        if monto > 0:
            messages.append(
                f"💰 Capacidad compra: ${monto:,.0f} promedio - Ajustar propuesta"
            )
        elif seguimientos > 0 and compras == 0:
            messages.append(
                "💡 Sin monto registrado - Pedir presupuesto o rango de inversión"
            )

        # ═══════════════════════════════════════════════════════════
        # Prioridad general según porcentaje
        # ═══════════════════════════════════════════════════════════
        if porcentaje >= 75:
            messages.insert(0, "🎯 PRIORIDAD ALTA - Enfocarse en cierre esta semana")
        elif porcentaje >= 50:
            messages.insert(
                0, "📌 PRIORIDAD MEDIA - Seguimiento constante, presionar suavemente"
            )
        elif porcentaje >= 30:
            messages.insert(
                0, "📊 POTENCIAL MODERADO - Nutrir con información, construir relación"
            )
        else:
            messages.insert(
                0, "⏳ POTENCIAL BAJO - Automatizar follow-up, buscar nuevos contactos"
            )

        return messages

    def _build_prediction_reasons(self, metrics, porcentaje):
        """
        Construye motivos explicables de la predicción para mostrar al asesor.
        """
        compras = int(metrics.get("compras_historicas") or 0)
        seguimientos = int(metrics.get("total_seguimientos") or 0)
        dias_ultimo = int(metrics.get("dias_ultimo_seg") or 999)
        monto = float(metrics.get("monto_promedio") or 0)
        proceso = (metrics.get("proceso_actual") or "no iniciado").lower().strip()

        reasons = []

        if compras >= 3:
            reasons.append("Cliente recurrente VIP con 3 o más compras históricas")
        elif compras == 2:
            reasons.append("Cliente recurrente con 2 compras históricas")
        elif compras == 1:
            reasons.append("Cliente con compra previa confirmada")
        else:
            reasons.append("Sin compras históricas registradas")

        if seguimientos >= 6:
            reasons.append("Engagement alto: 6 o más seguimientos")
        elif seguimientos >= 3:
            reasons.append("Engagement medio: seguimiento comercial activo")
        elif seguimientos > 0:
            reasons.append("Engagement inicial: primeros seguimientos")
        else:
            reasons.append("Aún no tiene seguimientos")

        if dias_ultimo < 7:
            reasons.append("Contacto reciente: menos de 7 días")
        elif dias_ultimo < 30:
            reasons.append("Contacto vigente: menos de 30 días")
        elif dias_ultimo < 90:
            reasons.append("Cliente tibio: requiere reactivación")
        else:
            reasons.append("Cliente frío por inactividad")

        if proceso == "cerrado":
            reasons.append("Etapa actual cerrada: se proyecta la siguiente compra")
        else:
            reasons.append(f"Etapa actual del pipeline: {proceso}")

        if monto > 0:
            reasons.append("Existe capacidad de compra por montos registrados")
        else:
            reasons.append("Sin monto registrado: oportunidad de calificar presupuesto")

        reasons.append(f"Score final calculado: {porcentaje:.0f}%")
        return reasons

    def predict_percentages_for_leads(self, leads):
        """
        Calcula porcentaje de predicción de compra para una lista de leads,
        basándose en múltiples factores de engagement y historial.
        """
        lead_ids = []
        for lead in leads or []:
            if isinstance(lead, dict):
                lid = lead.get("id")
            else:
                lid = getattr(lead, "id", None)
            if lid is not None:
                lead_ids.append(lid)

        if not lead_ids:
            return {}

        try:
            metrics_map = self._fetch_lead_engagement_metrics(lead_ids)
        except Exception:
            logger.exception(
                "Fallo query batch de metricas de prediccion; usando fallback por lead"
            )
            metrics_map = {}
            for lead_id in lead_ids:
                try:
                    numeric_id = int(lead_id)
                except (TypeError, ValueError):
                    continue
                try:
                    metrics_map[numeric_id] = self._fallback_metrics_for_lead(
                        numeric_id
                    )
                except Exception:
                    logger.exception(
                        "Fallo fallback de metricas para lead_id=%s", lead_id
                    )

        predictions = {}
        for lead_id in lead_ids:
            try:
                numeric_id = int(lead_id)
            except (TypeError, ValueError):
                continue

            metrics = metrics_map.get(
                numeric_id,
                {
                    "compras_historicas": 0,
                    "total_seguimientos": 0,
                    "dias_ultimo_seg": 999,
                    "monto_promedio": 0,
                    "proceso_actual": "no iniciado",
                },
            )

            porcentaje = self._calculate_prediction_score(metrics)
            recommendations = self._generate_recommendation_message(metrics, porcentaje)
            reasons = self._build_prediction_reasons(metrics, porcentaje)
            proceso_actual = metrics.get("proceso_actual", "no iniciado")
            prediction_kind = (
                "siguiente_compra"
                if str(proceso_actual).strip().lower() == "cerrado"
                else "compra_inicial"
            )

            predictions[numeric_id] = {
                "porcentaje": porcentaje,
                "compras_historicas": metrics.get("compras_historicas", 0),
                "total_seguimientos": metrics.get("total_seguimientos", 0),
                "dias_ultimo_seg": metrics.get("dias_ultimo_seg", 999),
                "proceso_actual": proceso_actual,
                "monto_promedio": metrics.get("monto_promedio", 0),
                "metodo": "multiplex_engagement",
                "recomendaciones": recommendations,
                "motivos": reasons,
                "tipo_prediccion": prediction_kind,
            }

        return predictions

    def handle(self, question):
        lead_id = self._extract_lead_id(question)
        if not lead_id:
            return {
                "ok": False,
                "agent": "prediccion_compra_agente",
                "intent": "prediccion",
                "error": "Indica un lead con formato como 'Lead #123 probabilidad de compra'.",
            }

        if self._model is None:
            return {
                "ok": False,
                "agent": "prediccion_compra",
                "intent": "prediccion",
                "error": (
                    "No hay modelo entrenado. Ejecuta scripts/entrenar_modelo_compra.py "
                    "para generar models/ml_models/compra_model.pkl."
                ),
            }

        payload, err = self._fetch_lead_features(lead_id)
        if err:
            return {
                "ok": False,
                "agent": "prediccion_compra",
                "intent": "prediccion",
                "error": err,
            }

        x_input = [payload["features"]]

        try:
            prob = float(self._model.predict_proba(x_input)[0][1])
        except Exception as exc:
            return {
                "ok": False,
                "agent": "prediccion_compra",
                "intent": "prediccion",
                "error": f"Error al inferir con el modelo: {exc}",
            }

        confidence = max(prob, 1.0 - prob)
        pct = round(prob * 100.0, 2)
        conf_pct = round(confidence * 100.0, 2)
        model_version = os.getenv("COMPRA_MODEL_VERSION", "rf_v1")
        self._cache_prediction(lead_id, prob, model_version)

        return {
            "ok": True,
            "agent": "prediccion_compra",
            "intent": "prediccion",
            "answer": (
                f"Lead #{lead_id}: probabilidad estimada de compra {pct}%. "
                f"Confianza del modelo {conf_pct}%."
            ),
            "data": {
                "lead_id": lead_id,
                "probabilidad_compra": prob,
                "features": payload["features"],
                "modelo_version": model_version,
            },
            "confidence": confidence,
        }
