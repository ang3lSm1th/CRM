"""Resolución de códigos ubigeo (departamento/provincia/distrito) a nombres."""

from __future__ import annotations

from typing import Any

from MySQLdb.cursors import DictCursor

from extensions import mysql

DEPARTAMENTOS = {
    "1": "Amazonas",
    "2": "Ancash",
    "3": "Apurímac",
    "4": "Arequipa",
    "5": "Ayacucho",
    "6": "Cajamarca",
    "7": "Callao",
    "8": "Cusco",
    "9": "Huancavelica",
    "10": "Huánuco",
    "11": "Ica",
    "12": "Junín",
    "13": "La Libertad",
    "14": "Lambayeque",
    "15": "Lima",
    "16": "Loreto",
    "17": "Madre de Dios",
    "18": "Moquegua",
    "19": "Pasco",
    "20": "Piura",
    "21": "Puno",
    "22": "San Martín",
    "23": "Tacna",
    "24": "Tumbes",
    "25": "Ucayali",
}

_LOOKUPS = {
    "departamento": ("departamentos", "idDepartamento", "departamento"),
    "provincia": ("provincia", "idProvincia", "provincia"),
    "distrito": ("distrito", "idDistrito", "distrito"),
}


def resolve_ubigeo_name(level: str, raw_value: Any) -> str:
    value = str(raw_value or "").strip()
    if not value:
        return ""

    # Ya es nombre (no solo dígitos)
    if not value.isdigit():
        return value

    if level == "departamento":
        mapped = DEPARTAMENTOS.get(value) or DEPARTAMENTOS.get(value.lstrip("0") or value)
        if mapped:
            # Intentar BD igual por si el id difiere; preferir BD si responde
            db_name = _lookup_db(level, value)
            return db_name or mapped

    db_name = _lookup_db(level, value)
    return db_name or value


def _lookup_db(level: str, value: str) -> str:
    if level not in _LOOKUPS:
        return ""
    table_name, id_col, name_col = _LOOKUPS[level]
    cur = None
    try:
        cur = mysql.connection.cursor(DictCursor)
        cur.execute(
            f"SELECT {name_col} AS nombre FROM {table_name} WHERE {id_col} = %s LIMIT 1",
            (value,),
        )
        row = cur.fetchone() or {}
        return str(row.get("nombre") or "").strip()
    except Exception:
        return ""
    finally:
        if cur is not None:
            try:
                cur.close()
            except Exception:
                pass


def enrich_lead_ubicacion(lead: dict[str, Any] | None) -> dict[str, Any]:
    """Devuelve copia del lead con departamento/provincia/distrito en nombres."""
    row = dict(lead or {})
    dep = resolve_ubigeo_name("departamento", row.get("departamento"))
    prov = resolve_ubigeo_name("provincia", row.get("provincia"))
    dist = resolve_ubigeo_name("distrito", row.get("distrito"))
    row["departamento"] = dep
    row["provincia"] = prov
    row["distrito"] = dist
    row["departamento_id"] = lead.get("departamento") if lead else None
    row["provincia_id"] = lead.get("provincia") if lead else None
    row["distrito_id"] = lead.get("distrito") if lead else None

    # Evitar que la dirección sea solo un código ubigeo o duplique el depto
    direccion = str(row.get("direccion") or "").strip()
    if direccion.isdigit() or direccion.upper() in {dep.upper(), prov.upper(), dist.upper()}:
        row["direccion"] = ""
    return row


def _title_place(name: str) -> str:
    name = (name or "").strip()
    if not name:
        return ""
    # Mantener acrónimos cortos
    if name.isupper() and len(name) <= 4:
        return name
    return name.title() if name.isupper() or name.islower() else name


def format_ubicacion(
    lead: dict[str, Any] | None,
    *,
    include_direccion: bool = True,
) -> str:
    row = enrich_lead_ubicacion(lead)
    parts: list[str] = []
    if include_direccion:
        dir_txt = _title_place(str(row.get("direccion") or ""))
        if dir_txt:
            parts.append(dir_txt)
    dist = _title_place(str(row.get("distrito") or ""))
    prov = _title_place(str(row.get("provincia") or ""))
    dep = _title_place(str(row.get("departamento") or ""))
    geo_parts = [dist, prov, dep]
    for idx, val in enumerate(geo_parts):
        if not val:
            continue
        if parts and parts[-1].casefold() == val.casefold():
            continue
        # Si distrito y departamento son el mismo nombre, omitir el departamento
        if idx == 2 and dist and dep.casefold() == dist.casefold():
            continue
        parts.append(val)
    return ", ".join(parts) if parts else "—"
