"""PDF formal de cotización Orbes Agrícola con logo institucional."""

from __future__ import annotations

import io
import os
import re
from datetime import date, timedelta
from pathlib import Path
from typing import Any

from reportlab.lib import colors
from reportlab.lib.enums import TA_CENTER, TA_JUSTIFY, TA_LEFT, TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle, getSampleStyleSheet
from reportlab.lib.units import cm
from reportlab.platypus import (
    Flowable,
    HRFlowable,
    KeepTogether,
    Paragraph,
    SimpleDocTemplate,
    Spacer,
    Table,
    TableStyle,
)


from services.ubigeo_service import enrich_lead_ubicacion, format_ubicacion

ROOT = Path(__file__).resolve().parents[1]
LOGO_CANDIDATES = [
    ROOT / "docs" / "acta" / "logo_orbes.png",
    ROOT / "static" / "img" / "logo_orbes.png",
    ROOT / "static" / "logo_orbes.png",
]

BLUE = colors.HexColor("#0a3d8f")
BLUE_DARK = colors.HexColor("#062a63")
GREEN = colors.HexColor("#2e7d32")
ORANGE = colors.HexColor("#e65100")
LIGHT = colors.HexColor("#f3f7fc")
LIGHT_GREEN = colors.HexColor("#f1f8f2")
GRAY = colors.HexColor("#546e7a")
LINE = colors.HexColor("#cfd8dc")

MONTHS_ES = (
    "enero",
    "febrero",
    "marzo",
    "abril",
    "mayo",
    "junio",
    "julio",
    "agosto",
    "septiembre",
    "octubre",
    "noviembre",
    "diciembre",
)


def _logo_path() -> Path | None:
    env = (os.getenv("ORBES_LOGO_PATH") or "").strip()
    if env and Path(env).exists():
        return Path(env)
    for p in LOGO_CANDIDATES:
        if p.exists():
            return p
    return None


class _FixedLogo(Flowable):
    """Logo con tamaño fijo (evita overflow de Image dentro de Table)."""

    def __init__(self, path: Path, width: float, height: float):
        super().__init__()
        self.path = str(path)
        self._w = width
        self._h = height
        self._img_bytes: bytes | None = None
        try:
            from PIL import Image as PILImage

            pil = PILImage.open(path)
            if pil.mode in ("RGBA", "LA") or (pil.mode == "P" and "transparency" in pil.info):
                rgba = pil.convert("RGBA")
                bg = PILImage.new("RGB", rgba.size, (255, 255, 255))
                bg.paste(rgba, mask=rgba.split()[-1])
                pil = bg
            else:
                pil = pil.convert("RGB")
            buf = io.BytesIO()
            pil.save(buf, format="PNG", optimize=True)
            self._img_bytes = buf.getvalue()
        except Exception:
            self._img_bytes = None

    def wrap(self, availWidth, availHeight):  # noqa: N803
        return self._w, self._h

    def draw(self):
        from reportlab.lib.utils import ImageReader

        try:
            src = ImageReader(io.BytesIO(self._img_bytes)) if self._img_bytes else ImageReader(self.path)
            self.canv.drawImage(
                src,
                0,
                0,
                width=self._w,
                height=self._h,
                preserveAspectRatio=True,
                mask="auto",
                anchor="c",
            )
        except Exception:
            self.canv.setFillColor(BLUE)
            self.canv.setFont("Helvetica-Bold", 11)
            self.canv.drawString(0, self._h / 2, "ORBES AGRICOLA S.A.C.")


def _logo_flowable(width_cm: float = 7.2, height_cm: float = 1.7) -> Flowable | None:
    path = _logo_path()
    if not path:
        return None
    return _FixedLogo(path, width_cm * cm, height_cm * cm)


def _money(v) -> str:
    try:
        return f"{float(v):,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
    except Exception:
        return "0,00"


def _safe(v: Any, default: str = "—") -> str:
    s = str(v or "").strip()
    return s if s else default


def _ubicacion(lead: dict[str, Any]) -> str:
    return format_ubicacion(lead, include_direccion=True)


def _ubicacion_corta(lead: dict[str, Any]) -> str:
    row = enrich_lead_ubicacion(lead)
    parts = [
        str(row.get("distrito") or "").strip(),
        str(row.get("provincia") or "").strip(),
        str(row.get("departamento") or "").strip(),
    ]
    parts = [p for p in parts if p]
    return " ".join(parts) if parts else "SIN_UBICACION"


def _slug_filename(text: str, max_len: int = 50) -> str:
    text = (text or "").strip()
    text = text.replace("á", "a").replace("é", "e").replace("í", "i")
    text = text.replace("ó", "o").replace("ú", "u").replace("ñ", "n")
    text = text.replace("Á", "A").replace("É", "E").replace("Í", "I")
    text = text.replace("Ó", "O").replace("Ú", "U").replace("Ñ", "N")
    text = re.sub(r"[^\w\-.]+", "_", text, flags=re.UNICODE)
    text = re.sub(r"_+", "_", text).strip("._")
    return (text or "NA")[:max_len]


def cotizacion_pdf_filename(lead: dict[str, Any], quote: dict[str, Any] | None = None) -> str:
    """Nombre de descarga: RUC_Nombre_Ubicacion.pdf"""
    lead = enrich_lead_ubicacion(lead)
    ruc = _slug_filename(_safe(lead.get("ruc_dni"), "SIN_RUC"), 20)
    nombre = _slug_filename(_safe(lead.get("nombre"), "Cliente"), 45)
    ubic = _slug_filename(_ubicacion_corta(lead), 55)
    codigo = _slug_filename(str((quote or {}).get("cotizacion_codigo") or ""), 16)
    base = f"Cotizacion_{ruc}_{nombre}_{ubic}"
    if codigo and codigo != "NA":
        base = f"{base}_{codigo}"
    return f"{base}.pdf"


def build_cotizacion_pdf(
    *,
    lead: dict[str, Any],
    quote: dict[str, Any],
    asesor_nombre: str | None = None,
) -> bytes:
    lead = enrich_lead_ubicacion(lead)
    buffer = io.BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=A4,
        rightMargin=1.5 * cm,
        leftMargin=1.5 * cm,
        topMargin=1.1 * cm,
        bottomMargin=1.3 * cm,
        title=f"Cotización {(quote.get('cotizacion_codigo') or '')}".strip(),
        author="Orbes Agrícola S.A.C.",
    )
    styles = getSampleStyleSheet()
    title = ParagraphStyle(
        "OrbesTitle",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=12,
        textColor=BLUE_DARK,
        spaceBefore=2,
        spaceAfter=4,
    )
    company = ParagraphStyle(
        "OrbesCompany",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=11,
        textColor=BLUE,
    )
    slogan = ParagraphStyle(
        "OrbesSlogan",
        parent=styles["Normal"],
        fontName="Helvetica-Oblique",
        fontSize=7.5,
        textColor=GREEN,
        leading=9,
    )
    meta = ParagraphStyle(
        "OrbesMeta",
        parent=styles["Normal"],
        fontName="Helvetica",
        fontSize=8,
        textColor=GRAY,
        leading=10,
        alignment=TA_RIGHT,
    )
    meta_bold = ParagraphStyle(
        "OrbesMetaBold",
        parent=meta,
        fontName="Helvetica-Bold",
        fontSize=10,
        textColor=BLUE_DARK,
    )
    normal = ParagraphStyle(
        "OrbesBody",
        parent=styles["Normal"],
        fontSize=9,
        leading=12,
        textColor=colors.HexColor("#263238"),
        alignment=TA_JUSTIFY,
    )
    label = ParagraphStyle(
        "OrbesLabel",
        parent=styles["Normal"],
        fontName="Helvetica-Bold",
        fontSize=8.5,
        textColor=BLUE_DARK,
        leading=11,
    )
    value = ParagraphStyle(
        "OrbesValue",
        parent=styles["Normal"],
        fontSize=8.5,
        leading=11,
        textColor=colors.HexColor("#263238"),
    )
    small = ParagraphStyle(
        "OrbesSmall",
        parent=styles["Normal"],
        fontSize=8,
        leading=10,
        textColor=GRAY,
    )
    small_white = ParagraphStyle(
        "OrbesSmallWhite",
        parent=small,
        textColor=colors.white,
        fontName="Helvetica-Bold",
        alignment=TA_CENTER,
    )
    right = ParagraphStyle("OrbesRight", parent=normal, alignment=TA_RIGHT)
    center = ParagraphStyle("OrbesCenter", parent=small, alignment=TA_CENTER)

    elements: list[Any] = []

    # —— Encabezado con logo ——
    logo_cell: Any = _logo_flowable(7.2, 1.7)
    if logo_cell is None:
        logo_cell = KeepTogether(
            [
                Paragraph("ORBES AGRÍCOLA S.A.C.", company),
                Paragraph("Comprometido con la prosperidad del agro peruano", slogan),
            ]
        )

    codigo = _safe(quote.get("cotizacion_codigo"), "S/N")
    today = date.today()
    validez = today + timedelta(days=15)
    fecha_es = f"Lima, {today.day} de {MONTHS_ES[today.month - 1]} de {today.year}"
    header_right = Paragraph(
        f"<b>COTIZACIÓN N° {codigo}</b><br/>"
        f"{fecha_es}<br/>"
        f"Válida hasta: {validez.strftime('%d/%m/%Y')}<br/>"
        f"Lead: {_safe(lead.get('codigo') or lead.get('id'))}",
        meta,
    )

    head = Table([[logo_cell, header_right]], colWidths=[11 * cm, 6.5 * cm])
    head.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
                ("TOPPADDING", (0, 0), (-1, -1), 0),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    elements.append(head)
    elements.append(HRFlowable(width="100%", thickness=2.2, color=BLUE, spaceBefore=2, spaceAfter=1))
    elements.append(HRFlowable(width="100%", thickness=1.2, color=GREEN, spaceBefore=0, spaceAfter=10))

    # —— Datos del cliente ——
    nombre = _safe(lead.get("nombre"), "Cliente")
    ruc = _safe(lead.get("ruc_dni"))
    direccion = _ubicacion(lead)
    telefono = _safe(lead.get("telefono"))
    email = _safe(lead.get("email"))
    contacto = _safe(lead.get("contacto"), "")

    cliente_title = Table(
        [[Paragraph("<b>DATOS DEL CLIENTE</b>", small_white)]],
        colWidths=[17.5 * cm],
    )
    cliente_title.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, -1), BLUE),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    elements.append(cliente_title)

    cliente_rows = [
        [Paragraph("Señor(es)", label), Paragraph(nombre, value)],
        [Paragraph("RUC / DNI", label), Paragraph(ruc, value)],
        [Paragraph("Ubicación", label), Paragraph(direccion, value)],
        [Paragraph("Teléfono", label), Paragraph(telefono, value)],
        [Paragraph("Email", label), Paragraph(email, value)],
    ]
    if contacto:
        cliente_rows.append([Paragraph("Contacto", label), Paragraph(contacto, value)])

    t_cli = Table(cliente_rows, colWidths=[3.2 * cm, 14.3 * cm])
    t_cli.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (0, -1), LIGHT),
                ("BACKGROUND", (1, 0), (1, -1), colors.white),
                ("BOX", (0, 0), (-1, -1), 0.6, LINE),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 7),
                ("RIGHTPADDING", (0, 0), (-1, -1), 7),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
            ]
        )
    )
    elements.append(t_cli)
    elements.append(Spacer(1, 0.4 * cm))

    # —— Presentación comercial ——
    mensaje = _safe(quote.get("mensaje_comercial"), "")
    if mensaje and mensaje != "—":
        elements.append(Paragraph("PRESENTACIÓN COMERCIAL", title))
        elements.append(HRFlowable(width="100%", thickness=0.6, color=LINE, spaceAfter=6))
        # Evitar HTML crudo del LLM y menciones no profesionales
        mensaje_html = (
            mensaje.replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        mensaje_html = re.sub(
            r"(?i)\b(generad[oa]\s+por\s+(ia|inteligencia artificial|el sistema multiagente|chatbot|ai)|"
            r"asistente\s+de\s+ia|multiagente|chatgpt|openai|cursor\s+ai)\b[^.]*\.?",
            "",
            mensaje_html,
        )
        # Reemplazar menciones de códigos tipo "zona 5 / 44 / 447" por ubicación real si aplica
        ubi_txt = format_ubicacion(lead, include_direccion=False)
        if ubi_txt and ubi_txt != "—":
            mensaje_html = re.sub(
                r"(?i)(zona|ubicaci[oó]n|parcela\s+ubicada\s+en)[:\s]*\d{1,3}\s*/\s*\d{1,3}\s*/\s*\d{1,6}",
                rf"ubicación en {ubi_txt}",
                mensaje_html,
            )
            mensaje_html = re.sub(
                r"\b\d{1,3}\s*/\s*\d{1,3}\s*/\s*\d{1,6}\b",
                ubi_txt,
                mensaje_html,
            )
        mensaje_html = re.sub(r"\n{3,}", "\n\n", mensaje_html).replace("\n", "<br/>").strip()
        elements.append(Paragraph(mensaje_html, normal))
        elements.append(Spacer(1, 0.35 * cm))

    # —— Detalle ——
    elements.append(Paragraph("DETALLE DE LA OFERTA", title))
    elements.append(HRFlowable(width="100%", thickness=0.6, color=LINE, spaceAfter=6))

    data = [
        [
            Paragraph("<b>It</b>", small_white),
            Paragraph("<b>Descripción</b>", small_white),
            Paragraph("<b>U.M.</b>", small_white),
            Paragraph("<b>Cant.</b>", small_white),
            Paragraph("<b>P. Unitario</b>", small_white),
            Paragraph("<b>Total</b>", small_white),
        ]
    ]
    items = list(quote.get("items") or [])
    if not items:
        items = [
            {
                "descripcion": quote.get("titulo") or "Producto/servicio agrícola",
                "unidad": "UND",
                "cantidad": 1,
                "precio_unitario": quote.get("monto_total") or 0,
                "total": quote.get("monto_total") or 0,
            }
        ]

    total = 0.0
    for idx, item in enumerate(items, start=1):
        try:
            line_total = float(item.get("total") or 0)
        except Exception:
            line_total = 0.0
        total += line_total
        desc_raw = str(item.get("descripcion") or "—")
        codigo = str(item.get("codigo") or "").strip()
        if codigo:
            desc_raw = f"[{codigo}] {desc_raw}"
        desc = (
            desc_raw.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")
        )
        data.append(
            [
                Paragraph(str(idx).zfill(3), small),
                Paragraph(desc, small),
                Paragraph(str(item.get("unidad") or "UND"), small),
                Paragraph(str(item.get("cantidad") or 1), small),
                Paragraph(_money(item.get("precio_unitario") or 0), small),
                Paragraph(_money(line_total), small),
            ]
        )

    t_items = Table(
        data,
        colWidths=[1.1 * cm, 8.4 * cm, 1.4 * cm, 1.5 * cm, 2.5 * cm, 2.6 * cm],
        repeatRows=1,
    )
    t_items.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), BLUE),
                ("TEXTCOLOR", (0, 0), (-1, 0), colors.white),
                ("GRID", (0, 0), (-1, -1), 0.45, LINE),
                ("ROWBACKGROUNDS", (0, 1), (-1, -1), [colors.white, LIGHT]),
                ("ALIGN", (0, 0), (0, -1), "CENTER"),
                ("ALIGN", (2, 0), (-1, -1), "CENTER"),
                ("ALIGN", (4, 1), (-1, -1), "RIGHT"),
                ("VALIGN", (0, 0), (-1, -1), "MIDDLE"),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("LEFTPADDING", (0, 0), (-1, -1), 4),
                ("RIGHTPADDING", (0, 0), (-1, -1), 4),
            ]
        )
    )
    elements.append(t_items)
    elements.append(Spacer(1, 0.25 * cm))

    monto = quote.get("monto_total")
    try:
        monto_f = float(monto if monto is not None else total)
    except Exception:
        monto_f = total

    # Totales con IGV (precios ya incluyen IGV)
    base_sin_igv = round(monto_f / 1.18, 2) if monto_f else 0.0
    igv = round(monto_f - base_sin_igv, 2)

    tot_rows = [
        [
            Paragraph("Subtotal (sin IGV)", small),
            Paragraph(f"S/. {_money(base_sin_igv)}", right),
        ],
        [
            Paragraph("IGV (18%)", small),
            Paragraph(f"S/. {_money(igv)}", right),
        ],
        [
            Paragraph("<b>TOTAL A PAGAR (incluye IGV)</b>", value),
            Paragraph(f"<b>S/. {_money(monto_f)}</b>", right),
        ],
    ]
    tot = Table(tot_rows, colWidths=[11.5 * cm, 6 * cm])
    tot.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 1), LIGHT),
                ("BACKGROUND", (0, 2), (-1, 2), colors.HexColor("#e3f2fd")),
                ("BOX", (0, 0), (-1, -1), 1, BLUE),
                ("INNERGRID", (0, 0), (-1, -1), 0.4, LINE),
                ("LEFTPADDING", (0, 0), (-1, -1), 8),
                ("RIGHTPADDING", (0, 0), (-1, -1), 8),
                ("TOPPADDING", (0, 0), (-1, -1), 5),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 5),
                ("ALIGN", (1, 0), (1, -1), "RIGHT"),
            ]
        )
    )
    elements.append(tot)
    elements.append(Spacer(1, 0.4 * cm))

    # —— Términos ——
    elements.append(Paragraph("TÉRMINOS GENERALES", title))
    elements.append(HRFlowable(width="100%", thickness=0.6, color=LINE, spaceAfter=4))
    condiciones = quote.get("condiciones") or [
        "Validez de la cotización: 15 días calendario.",
        "Precios en soles (PEN) e incluyen IGV (18%).",
        "Plazos de entrega sujetos a stock y confirmación de pedido.",
        "No hay cambios ni devoluciones tras la conformidad del cliente.",
    ]
    for i, c in enumerate(condiciones, start=1):
        texto = (
            str(c)
            .replace("&", "&amp;")
            .replace("<", "&lt;")
            .replace(">", "&gt;")
        )
        # Normalizar inconsistencia típica del LLM
        if re.search(r"sin\s+igv", texto, re.I) and "incluyendo" not in texto.lower():
            texto = "Precios expresados en soles peruanos (PEN), incluyen IGV."
        elements.append(Paragraph(f"{i}. {texto}", small))

    elements.append(Spacer(1, 0.35 * cm))
    elements.append(Paragraph("CUENTAS BANCARIAS — ORBES AGRÍCOLA S.A.C.", title))
    elements.append(HRFlowable(width="100%", thickness=0.6, color=LINE, spaceAfter=4))
    bancos = Table(
        [
            [
                Paragraph("<b>Banco</b>", small_white),
                Paragraph("<b>Cuenta soles</b>", small_white),
                Paragraph("<b>CCI soles</b>", small_white),
            ],
            [
                Paragraph("BCP", small),
                Paragraph("191-1052045-0-16", small),
                Paragraph("002-191-001052045016-53", small),
            ],
            [
                Paragraph("BBVA", small),
                Paragraph("0011-0109-0100034231", small),
                Paragraph("011-109-000100034231-69", small),
            ],
        ],
        colWidths=[3.2 * cm, 6.3 * cm, 8 * cm],
    )
    bancos.setStyle(
        TableStyle(
            [
                ("BACKGROUND", (0, 0), (-1, 0), GREEN),
                ("BACKGROUND", (0, 1), (-1, -1), LIGHT_GREEN),
                ("GRID", (0, 0), (-1, -1), 0.45, colors.HexColor("#a5d6a7")),
                ("TOPPADDING", (0, 0), (-1, -1), 4),
                ("BOTTOMPADDING", (0, 0), (-1, -1), 4),
                ("LEFTPADDING", (0, 0), (-1, -1), 6),
            ]
        )
    )
    elements.append(bancos)

    elements.append(Spacer(1, 0.9 * cm))
    firma = _safe(asesor_nombre, "Equipo Comercial Orbes")
    firma_block = Table(
        [
            [
                Paragraph("Atentamente,", value),
                Paragraph("", value),
            ],
            [
                Paragraph("<br/><br/>____________________________", center),
                Paragraph("", value),
            ],
            [
                Paragraph(f"<b>{firma}</b><br/>Orbes Agrícola S.A.C. — Área Comercial", center),
                Paragraph("", value),
            ],
        ],
        colWidths=[8.5 * cm, 9 * cm],
    )
    firma_block.setStyle(
        TableStyle(
            [
                ("VALIGN", (0, 0), (-1, -1), "TOP"),
                ("LEFTPADDING", (0, 0), (-1, -1), 0),
                ("RIGHTPADDING", (0, 0), (-1, -1), 0),
            ]
        )
    )
    elements.append(firma_block)
    elements.append(Spacer(1, 0.55 * cm))
    elements.append(
        Paragraph(
            "Orbes Agrícola S.A.C. · Documento comercial oficial",
            ParagraphStyle("Foot", parent=center, textColor=GRAY, fontSize=7.5),
        )
    )

    doc.build(elements)
    return buffer.getvalue()
