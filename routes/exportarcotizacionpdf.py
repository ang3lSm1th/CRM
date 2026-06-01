from reportlab.lib import colors
from reportlab.lib.pagesizes import A4
from reportlab.platypus import SimpleDocTemplate, Table, TableStyle, Paragraph, Spacer, HRFlowable
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle
from reportlab.lib.units import cm

def generar_cotizacion():
    doc = SimpleDocTemplate("Cotizacion_ORTEGA.pdf", pagesize=A4, rightMargin=30, leftMargin=30, topMargin=30, bottomMargin=18)
    elements = []
    styles = getSampleStyleSheet()

    # Estilos personalizados
    estilo_negrita = ParagraphStyle('Negrita', parent=styles['Normal'], fontSize=10, fontName='Helvetica-Bold')
    estilo_titulo = ParagraphStyle('Titulo', parent=styles['Normal'], fontSize=12, fontName='Helvetica-Bold')

    # --- ENCABEZADO ---
    elements.append(Paragraph("ORBES AGRICOLA", estilo_titulo))
    elements.append(Paragraph("Comprometido con la prosperidad del agro peruano", styles['Normal']))
    elements.append(Spacer(1, 10))
    
    header_data = [
        [Paragraph(f"<b>COTIZACIÓN N° 2603330044</b>", styles['Normal']), ""],
        ["LIMA, 23 de Marzo del 2026", ""],
        ["Señores:", ""],
        ["ORTEGA DE LA CRUZ, ALBERTO FLORENCIO 20988989", ""],
        ["CALLE S/N MAZAMARI - SATIPO JUNIN", ""]
    ]
    t_header = Table(header_data, colWidths=[10*cm, 5*cm])
    elements.append(t_header)
    elements.append(Spacer(1, 15))

    # --- TABLA DE PRODUCTOS ---
    data_productos = [
        ["It", "Código", "Descripción", "U.M.", "Cant.", "Precio", "Total"]
    ]
    
    # Datos extraídos del documento original
    items = [
        ["001", "2.2560.006.0", "COJINETE RODILLO - DEUTZ FAHR", "UND", "1.00", "239.36", "239.36"],
        ["002", "2.1580.301.9", "SUPLEMENTO DE AJUSTE 76X89X0,2", "UND", "2.00", "27.93", "55.85"],
        ["003", "2.1580.302.9", "SUPLEMENTO DE AJUSTE 76X89X0,5", "UND", "2.00", "51.86", "103.72"],
        ["012", "2.1580.109.0", "SUPLEMENTO DE AJUSTE 36X43X0.15", "UND", "2.00", "598.40", "1,196.79"],
        ["022", "0.445.4620.3/50", "PAR CONICO Z=10/Z=38-DEUTZ FAHR", "UND", "1.00", "7,779.16", "7,779.16"],
        ["023", "42718402175", "SERVICIO DE MANTENIMIENTO", "UND", "1.00", "4,000.00", "4,000.00"],
    ]
    # (He resumido algunos para el ejemplo, puedes agregar los 23 items aquí)
    data_productos.extend(items)

    t_prod = Table(data_productos, repeatRows=1, colWidths=[0.8*cm, 3*cm, 7.5*cm, 1.2*cm, 1.5*cm, 2*cm, 2.5*cm])
    t_prod.setStyle(TableStyle([
        ('BACKGROUND', (0, 0), (-1, 0), colors.lightgrey),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey),
        ('FONTSIZE', (0, 0), (-1, -1), 8),
        ('ALIGN', (4, 0), (-1, -1), 'RIGHT'),
    ]))
    elements.append(t_prod)

    # --- TOTAL ---
    elements.append(Spacer(1, 10))
    elements.append(Paragraph("<b>TOTAL: S/. 16,145.34</b>", ParagraphStyle('Total', parent=styles['Normal'], alignment=2)))
    elements.append(Paragraph("PRECIO EN SOLES INCLUYE IGV", styles['Normal']))

    # --- TÉRMINOS Y BANCOS ---
    elements.append(Spacer(1, 20))
    elements.append(HRFlowable(width="100%", thickness=1, color=colors.black))
    elements.append(Paragraph("TÉRMINOS GENERALES", estilo_negrita))
    terminos = [
        "1. Los plazos de entrega consideran stock actual sujeto a variación.",
        "2. Revisar conformidad; no hay cambios ni devoluciones tras la aceptación.",
        "3. Pedidos hasta 12:30 p.m. se despachan el mismo día."
    ]
    for t in terminos:
        elements.append(Paragraph(t, ParagraphStyle('Small', fontSize=8)))

    elements.append(Spacer(1, 10))
    elements.append(Paragraph("CUENTAS BANCARIAS (ORBES AGRICOLA SAC)", estilo_negrita))
    
    bancos_data = [
        ["BANCO", "CUENTA SOLES", "CCI SOLES"],
        ["BCP", "191-1052045-0-16", "002-191-001052045016-53"],
        ["BBVA", "0011-0109-0100034231", "011-109-000100034231-69"]
    ]
    t_bancos = Table(bancos_data, colWidths=[3*cm, 6*cm, 8*cm])
    t_bancos.setStyle(TableStyle([
        ('FONTSIZE', (0, 0), (-1, -1), 7),
        ('GRID', (0, 0), (-1, -1), 0.5, colors.grey)
    ]))
    elements.append(t_bancos)

    # Firma
    elements.append(Spacer(1, 30))
    elements.append(Paragraph("Atentamente,<br/>LEONARDO VILLAVERDE L.<br/>POSTVENTA", styles['Normal']))

    doc.build(elements)
    print("PDF Generado exitosamente.")

generar_cotizacion()