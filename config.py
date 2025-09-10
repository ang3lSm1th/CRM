import os

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "cambia_esta_clave")
    MYSQL_HOST = os.getenv("MYSQL_HOST", "127.0.0.1")
    MYSQL_USER = os.getenv("MYSQL_USER", "root")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "")
    MYSQL_DB = os.getenv("MYSQL_DB", "crm_orbes")
    MYSQL_CURSORCLASS = "DictCursor"
