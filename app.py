from flask import Flask, redirect, url_for, session
from config import Config
from extensions import mysql, bcrypt
from routes.auth_login import auth_bp
from routes.dashboard import dashboard_bp
from routes.lead import lead_bp
from routes.auth_register import register_bp  # 👈 solo importamos register_bp

def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    mysql.init_app(app)
    bcrypt.init_app(app)

    # Registramos blueprints
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(register_bp, url_prefix="/auth")  # 👈 separado pero mismo prefijo
    app.register_blueprint(dashboard_bp, url_prefix="")
    app.register_blueprint(lead_bp, url_prefix="/leads")

    @app.route("/")
    def index():
        if session.get("user_id"):
            return redirect(url_for("dashboard.dashboard_router"))
        return redirect(url_for("auth.login"))

    # Endpoints listos
    return app

# 👇 instancia a nivel de módulo para Gunicorn
app = create_app()

# Config extra (cookies/seguridad) sobre la instancia
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,   # evita acceso JS
    SESSION_COOKIE_SECURE=True,     # solo sobre HTTPS (Render sirve sobre HTTPS)
    SESSION_COOKIE_SAMESITE="Lax",  # mitiga CSRF básicos
    PERMANENT_SESSION_LIFETIME=1800 # 30 min inactividad
)

# Solo para correr LOCALMENTE (no en Render)
if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
