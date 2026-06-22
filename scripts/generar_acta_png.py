"""Genera acta de conformidad Orbes Agrícola como PNG (A4)."""

from pathlib import Path

from PIL import Image, ImageDraw, ImageFont

ROOT = Path(__file__).resolve().parent.parent
ACTA = ROOT / "docs" / "acta"
OUT = ACTA / "acta_conformidad_entrega_orbes.png"

W, H = 1654, 2339  # A4 ~200 DPI
MARGIN_X = 120
MARGIN_Y = 100
BOTTOM_MARGIN = 80
CONTENT_W = W - 2 * MARGIN_X
HEADER_H = 210
GREEN = (26, 95, 42)


def _font(size, bold=False):
    names = (
        ["timesbd.ttf", "Times New Roman Bold.ttf"]
        if bold
        else ["times.ttf", "Times New Roman.ttf"]
    )
    for name in names:
        path = Path("C:/Windows/Fonts") / name
        if path.exists():
            return ImageFont.truetype(str(path), size)
    return ImageFont.load_default()


def _wrap(draw, text, font, max_width):
    words = text.split()
    lines, current = [], ""
    for word in words:
        test = f"{current} {word}".strip()
        if draw.textlength(test, font=font) <= max_width:
            current = test
        else:
            if current:
                lines.append(current)
            current = word
    if current:
        lines.append(current)
    return lines


def _paragraph_height(draw, text, font, max_width, line_gap=8):
    lines = _wrap(draw, text, font, max_width)
    return len(lines) * (font.size + line_gap) + 12


def _draw_paragraph(draw, y, text, font, max_width, line_gap=8):
    for line in _wrap(draw, text, font, max_width):
        draw.text((MARGIN_X, y), line, fill="black", font=font)
        y += font.size + line_gap
    return y + 12


def _paste_signature(img, path, box, scale_min=0.5, max_h=120):
    if not path.exists():
        return
    src = Image.open(path).convert("RGBA")
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    target_w = max(int(bw * scale_min), 140)
    target_h = min(max(bh - 10, 80), max_h)
    ratio = min(target_w / src.width, target_h / src.height)
    new_size = (max(1, int(src.width * ratio)), max(1, int(src.height * ratio)))
    src = src.resize(new_size, Image.Resampling.LANCZOS)
    ox = x0 + (bw - src.width) // 2
    oy = max(y0, y1 - src.height - 10)
    img.paste(src, (ox, oy), src)


def _paste_fit(img, path, box):
    if not path.exists():
        return
    src = Image.open(path).convert("RGBA")
    x0, y0, x1, y1 = box
    bw, bh = x1 - x0, y1 - y0
    src.thumbnail((bw, bh), Image.Resampling.LANCZOS)
    ox = x0 + (bw - src.width) // 2
    oy = y0 + (bh - src.height) // 2
    img.paste(src, (ox, oy), src)


PARAGRAPHS = [
    (
        "Yo, MAGALY PAREJA GUERRERO, en mi calidad de Gerencia de Recursos Humanos "
        "de la empresa ORBES AGRÍCOLA S.A.C., con R.U.C. N.° 20421367605, ubicada en "
        "la ciudad de Lima, mediante el presente documento dejo constancia y doy conformidad "
        "a la culminación satisfactoria del proyecto «Arquitectura de inteligencia artificial "
        "distribuida para el análisis comercial y gestión automatizada de leads en Orbes "
        "Agrícola S.A.C. — 2025-2026», desarrollado en nuestra institución por los señores "
        "JUZCAMAYTA SÁNCHEZ, ANGEL SMITH, identificado con DNI N.° 77347183, y ACCOSTUPA TTITO, "
        "DIEGO REMIGIO, identificado con DNI N.° 75068757, respectivamente, estudiantes de la "
        "Carrera Profesional de Ingeniería de Sistemas."
    ),
    (
        "El proyecto fue ejecutado en el periodo comprendido entre noviembre de 2025 y "
        "junio de 2026, cumpliendo con las actividades, objetivos y requerimientos establecidos, "
        "demostrando responsabilidad, compromiso, profesionalismo y capacidad técnica durante "
        "todo el desarrollo del sistema CRM con arquitectura distribuida, agentes de análisis "
        "de leads (scoring, CAC, adquisición, probabilidad de compra y retención), worker Celery "
        "y microservicio de agentes de inteligencia artificial."
    ),
    (
        "Asimismo, manifiesto que los participantes realizaron sus labores de manera satisfactoria, "
        "contribuyendo al fortalecimiento y mejora de los procesos comerciales y de seguimiento "
        "de clientes dentro de la organización."
    ),
    (
        "Por tal motivo, expreso mi conformidad con la finalización del proyecto y extiendo el "
        "presente documento para los fines que los interesados consideren convenientes."
    ),
]

COL_W = 400
COL_GAP = 120
SIG_BOX_H = 130
REP_W = 520
REP_STAMP_H = 220
REP_GAP = 72


def _signature_block_height():
    student_h = SIG_BOX_H + 28 + 3 * 34
    rep_h = REP_GAP + REP_STAMP_H + 10 + 12 + 4 * 30
    return student_h + rep_h


def main():
    img = Image.new("RGB", (W, H), "white")
    draw = ImageDraw.Draw(img)

    f_body = _font(28)
    f_bold = _font(28, bold=True)
    f_title = _font(36, bold=True)
    f_small = _font(24)
    f_sig = _font(22)

    # Encabezado fijo arriba
    header_top = MARGIN_Y
    _paste_fit(
        img,
        ACTA / "logo_orbes.png",
        (MARGIN_X, header_top, MARGIN_X + 520, header_top + 200),
    )
    meta_x = W - MARGIN_X - 420
    draw.text((meta_x, header_top + 10), "ORBES AGRÍCOLA S.A.C.", fill="black", font=f_bold)
    draw.text((meta_x, header_top + 52), "R.U.C. N.° 20421367605", fill="black", font=f_small)
    draw.text((meta_x, header_top + 86), "Maquinarias y Riego Tecnificado", fill="black", font=f_small)
    draw.text((meta_x, header_top + 120), "Lima — Perú", fill="black", font=f_small)
    draw.line(
        [(MARGIN_X, header_top + HEADER_H), (W - MARGIN_X, header_top + HEADER_H)],
        fill=GREEN,
        width=3,
    )

    y = header_top + HEADER_H + 40
    title = "ACTA DE CONFORMIDAD DE ENTREGA"
    tw = draw.textlength(title, font=f_title)
    draw.text(((W - tw) / 2, y), title, fill="black", font=f_title)
    y += f_title.size + 34

    for p in PARAGRAPHS:
        y = _draw_paragraph(draw, y, p, f_body, CONTENT_W)

    fecha = "Lima, 3 de julio de 2026."
    draw.text((MARGIN_X, y), fecha, fill="black", font=f_body)
    y += f_body.size + 36

    # Centrar bloque de firmas en el espacio restante de la hoja
    remaining = H - BOTTOM_MARGIN - y
    sig_block_h = _signature_block_height()
    y += max(48, (remaining - sig_block_h) // 2)

    block_w = COL_W * 2 + COL_GAP
    left_x = (W - block_w) // 2
    right_x = left_x + COL_W + COL_GAP
    sig_y = y + SIG_BOX_H

    draw.line([(left_x, sig_y), (left_x + COL_W, sig_y)], fill="black", width=2)
    draw.line([(right_x, sig_y), (right_x + COL_W, sig_y)], fill="black", width=2)

    _paste_signature(
        img,
        ACTA / "firma_angel.png",
        (left_x, sig_y - SIG_BOX_H, left_x + COL_W, sig_y - 8),
        scale_min=0.8,
        max_h=100,
    )
    _paste_signature(
        img,
        ACTA / "firma_diego_sig.png",
        (right_x, sig_y - SIG_BOX_H, right_x + COL_W, sig_y - 8),
        scale_min=0.85,
        max_h=100,
    )

    labels_left = [
        "Estudiante:",
        "Juzcamayta Sánchez, Angel Smith",
        "DNI: 77347183",
    ]
    labels_right = [
        "Estudiante:",
        "Accostupa Ttito, Diego Remigio",
        "DNI: 75068757",
    ]
    ly = sig_y + 28
    for line in labels_left:
        tw = draw.textlength(line, font=f_sig)
        draw.text((left_x + (COL_W - tw) / 2, ly), line, fill="black", font=f_sig)
        ly += 34
    ly = sig_y + 28
    for line in labels_right:
        tw = draw.textlength(line, font=f_sig)
        draw.text((right_x + (COL_W - tw) / 2, ly), line, fill="black", font=f_sig)
        ly += 34

    rep_x = (W - REP_W) // 2
    rep_y = sig_y + 28 + 3 * 34 + REP_GAP
    _paste_fit(
        img,
        ACTA / "sello_rrhh.png",
        (rep_x, rep_y, rep_x + REP_W, rep_y + REP_STAMP_H),
    )
    rep_y += REP_STAMP_H + 10
    rep_lines = [
        "Magaly Pareja Guerrero",
        "Gerencia de Recursos Humanos",
        "Orbes Agrícola S.A.C. — R.U.C. 20421367605",
        "Firma y sello del Representante Legal",
    ]
    draw.line([(rep_x, rep_y), (rep_x + REP_W, rep_y)], fill="black", width=2)
    rep_y += 12
    for line in rep_lines:
        tw = draw.textlength(line, font=f_sig)
        draw.text((rep_x + (REP_W - tw) / 2, rep_y), line, fill="black", font=f_sig)
        rep_y += 30

    img.save(OUT, "PNG", optimize=True)
    print(f"Generado: {OUT}")


if __name__ == "__main__":
    main()
