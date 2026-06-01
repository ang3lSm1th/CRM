import os
from urllib.parse import urlparse
from dotenv import load_dotenv

# Carga variables desde .env si existe
load_dotenv()


def _first_non_empty(*values):
    for value in values:
        if value is not None and str(value).strip() != "":
            return value
    return None


def _parse_mysql_url(url):
    if not url:
        return {}
    try:
        parsed = urlparse(url)
    except Exception:
        return {}
    if parsed.scheme not in {"mysql", "mysql2", "mariadb"}:
        return {}
    db_name = parsed.path.lstrip("/") if parsed.path else None
    return {
        "host": parsed.hostname,
        "port": parsed.port,
        "user": parsed.username,
        "password": parsed.password,
        "database": db_name,
    }


_MYSQL_URL_DATA = _parse_mysql_url(
    _first_non_empty(
        os.getenv("DATABASE_URL"),
        os.getenv("MYSQL_URL"),
        os.getenv("MYSQL_URI"),
    )
)


class Config:
    SECRET_KEY = (
        os.getenv("SECRET_KEY") or os.getenv("FLASK_SECRET_KEY") or "cambia_esta_clave"
    )
    MYSQL_HOST = _first_non_empty(
        os.getenv("MYSQL_HOST"),
        os.getenv("DB_HOST"),
        os.getenv("DATABASE_HOST"),
        _MYSQL_URL_DATA.get("host"),
        "127.0.0.1",
    )
    MYSQL_USER = _first_non_empty(
        os.getenv("MYSQL_USER"),
        os.getenv("DB_USER"),
        os.getenv("DATABASE_USER"),
        _MYSQL_URL_DATA.get("user"),
        "root",
    )
    MYSQL_PASSWORD = _first_non_empty(
        os.getenv("MYSQL_PASSWORD"),
        os.getenv("DB_PASSWORD"),
        os.getenv("DATABASE_PASSWORD"),
        _MYSQL_URL_DATA.get("password"),
        "",
    )
    MYSQL_DB = _first_non_empty(
        os.getenv("MYSQL_DB"),
        os.getenv("DB_NAME"),
        os.getenv("DATABASE_NAME"),
        _MYSQL_URL_DATA.get("database"),
        "u349183440_crm_orbes",
    )
    MYSQL_PORT = int(
        _first_non_empty(
            os.getenv("MYSQL_PORT"),
            os.getenv("DB_PORT"),
            os.getenv("DATABASE_PORT"),
            _MYSQL_URL_DATA.get("port"),
            "3307",
        )
    )
    MYSQL_CURSORCLASS = "DictCursor"
    ORBES_NEGOCIO_ID = int(os.getenv("ORBES_NEGOCIO_ID", "1"))
    TRACTOR_DB_HOST = os.getenv("TRACTOR_DB_HOST", MYSQL_HOST)
    TRACTOR_DB_USER = os.getenv("TRACTOR_DB_USER", MYSQL_USER)
    TRACTOR_DB_PASSWORD = os.getenv("TRACTOR_DB_PASSWORD", MYSQL_PASSWORD)
    TRACTOR_DB_NAME = os.getenv("TRACTOR_DB_NAME", "clinica_tractores_db")
    TRACTOR_DB_PORT = int(os.getenv("TRACTOR_DB_PORT", str(MYSQL_PORT)))
    TRACTOR_DB_CONNECT_TIMEOUT = int(os.getenv("TRACTOR_DB_CONNECT_TIMEOUT", "8"))
    ALLOW_PUBLIC_REGISTRATION = os.getenv("ALLOW_PUBLIC_REGISTRATION", "0") == "1"
    USE_HTTPS = os.getenv("USE_HTTPS", "0") == "1"
    OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
    AGENT_MODEL = os.getenv("AGENT_MODEL", "gpt-3.5-turbo")
    AGENT_MEMORY_SIZE = int(os.getenv("AGENT_MEMORY_SIZE", "10"))
    TRUST_PROXY = os.getenv("TRUST_PROXY", "1") == "1"
    PROXY_FIX_X_FOR = int(os.getenv("PROXY_FIX_X_FOR", "1"))
    PROXY_FIX_X_PROTO = int(os.getenv("PROXY_FIX_X_PROTO", "1"))
    PROXY_FIX_X_HOST = int(os.getenv("PROXY_FIX_X_HOST", "1"))
