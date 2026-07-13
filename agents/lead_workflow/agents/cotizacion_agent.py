"""Agente de cotización personalizada (multiagente + Cursor API).

Orquesta contexto de:
  - lead_scoring / sub-agentes (costo, adquisición, retención, abandono)
  - comentarios del lead y seguimientos
  - commercial_assistant (prioridad/score)
y genera una cotización JSON vía Cursor SDK únicamente.
"""

from __future__ import annotations

import logging
from datetime import date
from typing import Any

import MySQLdb.cursors

from extensions import mysql
from agents.lead_workflow.agents.lead_scoring import LeadScoringAgent
from services.cursor_llm_client import generate_json
from services.ubigeo_service import enrich_lead_ubicacion, format_ubicacion
from services.inventario_service import (
    catalogo_para_prompt,
    catalogo_para_lead,
    items_fallback,
    normalizar_items_desde_inventario,
)
import re

logger = logging.getLogger(__name__)

_IA_MENTION_RE = re.compile(
    r"(?i)\b(generad[oa]\s+por\s+(ia|inteligencia artificial|el sistema multiagente|chatbot|ai)|"
    r"asistente\s+de\s+ia|multiagente|chatgpt|openai)\b[^.]*\.?"
)
_UBIGEO_CODE_RE = re.compile(r"\b\d{1,3}\s*/\s*\d{1,3}\s*/\s*\d{1,6}\b")


class CotizacionAgent:
    AGENT_NAME = "cotizacion_agent"

    def __init__(self):
        self.scoring = LeadScoringAgent()

    def _fetch_recent_comments(self, lead_id: int, limit: int = 5) -> list[str]:
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            comments = []
            cur.execute(
                "SELECT comentario FROM leads WHERE id = %s LIMIT 1",
                (lead_id,),
            )
            lead = cur.fetchone() or {}
            if (lead.get("comentario") or "").strip():
                comments.append(f"Lead: {lead['comentario'].strip()}")

            cur.execute(
                """
                SELECT comentario, fecha_guardado
                FROM seguimientos
                WHERE lead_id = %s
                  AND comentario IS NOT NULL
                  AND TRIM(comentario) <> ''
                ORDER BY id DESC
                LIMIT %s
                """,
                (lead_id, limit),
            )
            for row in cur.fetchall() or []:
                comments.append(
                    f"Seguimiento ({row.get('fecha_guardado') or '-'}): "
                    f"{(row.get('comentario') or '').strip()}"
                )
            return comments
        finally:
            cur.close()

    def _bien_nombre(self, lead_row: dict) -> str:
        bien_id = lead_row.get("bien_servicio_id")
        if not bien_id:
            return "producto agrícola"
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            cur.execute(
                "SELECT nombre FROM bienes_servicios WHERE id = %s LIMIT 1",
                (bien_id,),
            )
            row = cur.fetchone() or {}
            return (row.get("nombre") or "producto agrícola").strip()
        except Exception:
            return "producto agrícola"
        finally:
            cur.close()

    def _next_cotizacion_code(self) -> str:
        today = date.today()
        prefix = f"V{today.strftime('%y%m%d')}"
        cur = mysql.connection.cursor(MySQLdb.cursors.DictCursor)
        try:
            cur.execute(
                """
                SELECT cotizacion FROM seguimientos
                WHERE cotizacion LIKE %s
                ORDER BY id DESC
                LIMIT 1
                """,
                (f"{prefix}%",),
            )
            row = cur.fetchone() or {}
            last = (row.get("cotizacion") or "").strip()
            seq = 1
            if last.startswith(prefix) and last[len(prefix) :].isdigit():
                seq = int(last[len(prefix) :]) + 1
            return f"{prefix}{seq:03d}"
        except Exception:
            return f"{prefix}001"
        finally:
            cur.close()

    def _build_prompt(
        self,
        lead_row: dict,
        score_data: dict,
        comments: list[str],
        bien: str,
        catalogo_txt: str,
    ) -> str:
        lead_row = enrich_lead_ubicacion(lead_row)
        nombre = (lead_row.get("nombre") or "Cliente").strip()
        ubicacion = format_ubicacion(lead_row, include_direccion=True)
        outputs = score_data.get("agent_outputs") or {}
        return f"""
Eres el asesor comercial de Orbes Agrícola S.A.C. (Perú).
NO modifiques archivos. NO uses herramientas de edición.
Redacta en tono FORMAL comercial (usted), claro y profesional.
Responde ÚNICAMENTE con un JSON válido (sin markdown) con esta forma:
{{
  "titulo": "string",
  "resumen_cliente": "string corto",
  "mensaje_comercial": "carta formal breve al cliente (español, trato de usted)",
  "items": [
    {{"codigo": "CODIGO_DEL_INVENTARIO", "cantidad": 1}}
  ],
  "moneda": "PEN",
  "condiciones": ["Validez de la cotización: 15 días calendario.", "..."],
  "siguiente_accion": "string"
}}

Contexto del lead:
- Código: {lead_row.get('codigo')}
- Nombre: {nombre}
- Teléfono: {lead_row.get('telefono') or '-'}
- Email: {lead_row.get('email') or '-'}
- Ubicación (usar SOLO estos nombres geográficos): {ubicacion}
- Bien/servicio de interés: {bien}
- Score global: {score_data.get('global_score')}
- Prioridad: {score_data.get('priority_label')}
- Recomendación scoring: {score_data.get('recommendation')}

Señales de otros agentes:
- Costo adquisición: {outputs.get('costo_adquisicion') or {}}
- Tasa adquisición: {outputs.get('tasa_adquisicion') or {}}
- Retención: {outputs.get('tasa_retencion') or {}}
- Abandono: {outputs.get('tasa_abandono') or {}}

Comentarios comerciales (para elegir productos y cantidades):
{chr(10).join(f'- {c}' for c in comments) if comments else '- Sin comentarios; elija 1 o 2 productos representativos del inventario.'}

INVENTARIO REAL DISPONIBLE (única fuente permitida de productos y precios):
{catalogo_txt}

Reglas OBLIGATORIAS:
1) Solo puedes cotizar productos del INVENTARIO REAL usando su "codigo" exacto.
2) NUNCA inventes productos, descripciones ni precios. El sistema aplicará el precio oficial del inventario.
3) Devuelve 1 a 4 ítems; cada ítem SOLO con {{"codigo","cantidad"}}.
4) Cantidad <= stock del producto (si stock > 0).
5) En ubicación escribe SOLO nombres (distrito, provincia, departamento). NUNCA códigos ubigeo.
6) El mensaje debe parecer carta comercial de Orbes Agrícola S.A.C. NUNCA menciones IA ni sistemas automáticos.
7) Cierra el mensaje_comercial con: "Atentamente, Orbes Agrícola S.A.C. — Área Comercial".
""".strip()

    def generate(self, lead_row: dict, score_data: dict | None = None) -> dict[str, Any]:
        lead_row = enrich_lead_ubicacion(dict(lead_row or {}))
        lead_id = int(lead_row.get("id") or 0)
        score_data = score_data or {}
        if not score_data.get("agent_outputs"):
            try:
                score_data = self.scoring.analyze(lead_row)
            except Exception as exc:
                logger.warning("Scoring falló para cotización lead=%s: %s", lead_id, exc)
                score_data = score_data or {
                    "global_score": 50,
                    "priority_label": "Media",
                    "recommendation": "",
                    "agent_outputs": {},
                }

        comments = self._fetch_recent_comments(lead_id)
        bien = self._bien_nombre(lead_row)
        bien_id = lead_row.get("bien_servicio_id")
        try:
            bien_id_int = int(bien_id) if bien_id else None
        except Exception:
            bien_id_int = None

        catalogo = catalogo_para_lead(bien_id_int)
        catalogo_txt = catalogo_para_prompt(catalogo)
        prompt = self._build_prompt(lead_row, score_data, comments, bien, catalogo_txt)

        provider = "fallback"
        used_fallback = False
        try:
            cotizacion, provider = generate_json(prompt)
        except Exception as exc:
            logger.error("LLM cotización falló lead=%s: %s", lead_id, exc)
            used_fallback = True
            cotizacion = {
                "titulo": f"Propuesta {bien}",
                "resumen_cliente": (lead_row.get("nombre") or "Cliente").strip(),
                "mensaje_comercial": (
                    f"Estimado/a {(lead_row.get('nombre') or 'cliente').strip()}, "
                    f"según su interés en {bien}, le enviamos una cotización formal "
                    "con productos de nuestro inventario Orbes. "
                    "Quedamos atentos para ajustar cantidades y plazo de entrega."
                ),
                "items": [],
                "moneda": "PEN",
                "condiciones": [
                    "Validez de la cotización: 15 días calendario.",
                    "Precios en soles (PEN) e incluyen IGV.",
                    "Entrega sujeta a stock confirmado.",
                ],
                "siguiente_accion": "Confirmar interés y agendar cierre",
            }
            provider = "respaldo"

        items = normalizar_items_desde_inventario(
            cotizacion.get("items") or [],
            catalogo,
            max_items=4,
        )
        if not items:
            items = items_fallback(catalogo, max_items=2)
            if used_fallback is False and provider != "respaldo":
                # LLM respondió pero sin códigos válidos
                logger.warning(
                    "Cotización lead=%s sin ítems de inventario válidos; usando respaldo de catálogo",
                    lead_id,
                )

        monto = round(sum(float(i.get("total") or 0) for i in items), 2)

        code = self._next_cotizacion_code()
        mensaje = (cotizacion.get("mensaje_comercial") or "").strip()
        mensaje = _IA_MENTION_RE.sub("", mensaje).strip()
        ubi = format_ubicacion(lead_row, include_direccion=False)
        if ubi and ubi != "—":
            mensaje = re.sub(
                r"(?i)(zona|ubicaci[oó]n|parcela\s+ubicada\s+en)[:\s]*\d{1,3}\s*/\s*\d{1,3}\s*/\s*\d{1,6}",
                f"ubicación en {ubi}",
                mensaje,
            )
            mensaje = _UBIGEO_CODE_RE.sub(ubi, mensaje)
        if "Orbes Agrícola" not in mensaje and "Atentamente" not in mensaje:
            mensaje = (
                f"{mensaje.rstrip()}\n\nAtentamente,\nOrbes Agrícola S.A.C. — Área Comercial"
            ).strip()

        return {
            "agent": self.AGENT_NAME,
            "ok": True,
            "lead_id": lead_id,
            "provider": provider,
            "used_fallback": used_fallback,
            "aviso_usuario": (
                "No se pudo conectar con el asistente de IA. "
                "Se generó una cotización de respaldo con inventario Orbes; revise montos e ítems."
                if used_fallback
                else None
            ),
            "cotizacion_codigo": code,
            "moneda": "PEN",
            "monto_total": monto,
            "titulo": cotizacion.get("titulo") or f"Cotización {bien}",
            "resumen_cliente": cotizacion.get("resumen_cliente"),
            "mensaje_comercial": mensaje,
            "items": items,
            "condiciones": cotizacion.get("condiciones") or [
                "Validez de la cotización: 15 días calendario.",
                "Precios en soles (PEN) e incluyen IGV.",
                "Entrega sujeta a stock confirmado.",
            ],
            "siguiente_accion": cotizacion.get("siguiente_accion"),
            "score_snapshot": {
                "global_score": score_data.get("global_score"),
                "priority_label": score_data.get("priority_label"),
            },
            "comentarios_usados": comments,
            "ubicacion": ubi,
            "inventario_usado": True,
            "inventario_skus": len(catalogo),
        }
