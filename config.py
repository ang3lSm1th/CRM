import os
from dotenv import load_dotenv

# Carga variables desde .env si existe
load_dotenv()


class Config:
    SECRET_KEY = (
        os.getenv("SECRET_KEY") or os.getenv("FLASK_SECRET_KEY") or "cambia_esta_clave"
    )
    MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
    MYSQL_USER = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DB = os.getenv("MYSQL_DB", "u349183440_crm_orbes")
    MYSQL_PORT = int(os.getenv("MYSQL_PORT", "3307"))
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
