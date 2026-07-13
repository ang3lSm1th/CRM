import re
import difflib
import unicodedata

_DIRECT_TOKEN_FIXES = {
    "cuants": "cuantos",
    "cuantoss": "cuantos",
    "cuantasz": "cuantas",
    "leds": "leads",
    "leadz": "leads",
    "leed": "lead",
    "leeds": "leads",
    "leasd": "leads",
    "ventaas": "ventas",
    "ventaz": "ventas",
    "vemtas": "ventas",
    "benatas": "ventas",
    "enro": "enero",
    "enroo": "enero",
    "febreo": "febrero",
    "marso": "marzo",
    "abirl": "abril",
    "mzo": "marzo",
    "setiembre": "septiembre",
    "octube": "octubre",
    "novimbre": "noviembre",
    "dicimbre": "diciembre",
    "cotisados": "cotizados",
    "cotisado": "cotizado",
    "cotizadps": "cotizados",
    "pipline": "pipeline",
    "pipelin": "pipeline",
    "embdoo": "embudo",
    "embudoo": "embudo",
    "rporte": "reporte",
    "reportee": "reporte",
    "reportez": "reportes",
    "retencionn": "retencion",
    "abandno": "abandono",
    "inactvidad": "inactividad",
    "campanaas": "campanas",
    "campanasz": "campanas",
    "markting": "marketing",
    "mkt": "marketing",
}

_DOMAIN_VOCAB = {
    "cuantos",
    "cuantas",
    "lead",
    "leads",
    "ventas",
    "venta",
    "pipeline",
    "embudo",
    "cotizado",
    "cotizados",
    "seguimiento",
    "cerrado",
    "cerrados",
    "reportes",
    "reporte",
    "resumen",
    "informe",
    "tendencia",
    "conversion",
    "funnel",
    "producto",
    "productos",
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
    "mes",
    "meses",
    "ultimo",
    "ultimos",
    "dias",
    "hoy",
    "marketing",
    "campanas",
    "campana",
    "ferias",
    "inventario",
    "stock",
    "retencion",
    "abandono",
    "inactividad",
    "riesgo",
    "compra",
    "maquinaria",
    "tractor",
    "tractores",
    "crm",
    "general",
    "sistema",
    "top",
}


def _strip_accents(text):
    if not text:
        return ""
    return "".join(
        ch
        for ch in unicodedata.normalize("NFKD", text)
        if not unicodedata.combining(ch)
    )


def normalize_user_text(text):
    """Normaliza texto de usuario para tolerar acentos, typos y ruido tipico."""
    if text is None:
        return ""

    raw = str(text).strip().lower()
    raw = _strip_accents(raw)
    raw = re.sub(r"[^a-z0-9#\s]", " ", raw)
    raw = re.sub(r"\s+", " ", raw).strip()
    if not raw:
        return ""

    tokens = []
    for tok in raw.split(" "):
        if not tok:
            continue
        if tok in _DIRECT_TOKEN_FIXES:
            tokens.append(_DIRECT_TOKEN_FIXES[tok])
            continue
        if tok.isdigit() or len(tok) <= 2:
            tokens.append(tok)
            continue

        close = difflib.get_close_matches(tok, _DOMAIN_VOCAB, n=1, cutoff=0.84)
        tokens.append(close[0] if close else tok)

    return " ".join(tokens)
