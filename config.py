import os

class Config:
    SECRET_KEY = os.getenv("SECRET_KEY", "cambia_esta_clave")
    MYSQL_HOST = os.getenv("MYSQL_HOST", "auth-db1896.hstgr.io")
    MYSQL_USER = os.getenv("MYSQL_USER", "u349183440_orbesagricola")
    MYSQL_PASSWORD = os.getenv("MYSQL_PASSWORD", "Orbesagricola25")
    MYSQL_DB = os.getenv("MYSQL_DB", "u349183440_crm_orbes")
    MYSQL_CURSORCLASS = "DictCursor"
