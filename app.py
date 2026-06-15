from dotenv import load_dotenv
from werkzeug.middleware.proxy_fix import ProxyFix

load_dotenv()
from flask import Flask, jsonify, redirect, url_for, session
from core.config import Config
from core.extensions import mysql, bcrypt, socketio
from routes.auth.login import auth_bp
from routes.crm.dashboard import dashboard_bp
from routes.crm.lead import lead_bp
from routes.auth.register import register_bp
from routes.auth.usuarios import usuarios_bp
from routes.crm.reporte_rapido import reporte_rapido_bp
from routes.crm.bienes_servicios import bienes_bp
from routes.crm.reportes import reportes_bp
from routes.marketing import marketing_bp
from routes.agents.chat import chat_bp
from routes.agents.lead_workflow import lead_workflow_bp
from flask import request


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    app.logger.info(
        "DB runtime config host=%s port=%s db=%s user=%s",
        app.config.get("MYSQL_HOST"),
        app.config.get("MYSQL_PORT"),
        app.config.get("MYSQL_DB"),
        app.config.get("MYSQL_USER"),
    )
    if str(app.config.get("MYSQL_HOST", "")).strip() in {"", "127.0.0.1", "localhost"}:
        app.logger.error(
            "MYSQL_HOST no esta configurado para entorno Docker/VPS; revisa variables de entorno del servicio backend"
        )

    if app.config.get("TRUST_PROXY"):
        app.wsgi_app = ProxyFix(
            app.wsgi_app,
            x_for=app.config.get("PROXY_FIX_X_FOR", 1),
            x_proto=app.config.get("PROXY_FIX_X_PROTO", 1),
            x_host=app.config.get("PROXY_FIX_X_HOST", 1),
        )

    mysql.init_app(app)
    bcrypt.init_app(app)
    # Socket.IO: monitor workflow leads (workflow_event)
    socketio.init_app(app)

    # Filtro personalizado para formatear números con comas decimales
    @app.template_filter("number_format")
    def number_format_filter(value):
        if value is None:
            return "0.00"
        try:
            # Convertir a float si es necesario
            num = float(value)
            # Formatear con comas y 2 decimales
            return "{:,.2f}".format(num)
        except (ValueError, TypeError):
            return str(value)

    # Registramos blueprints
    app.register_blueprint(auth_bp, url_prefix="/auth")
    app.register_blueprint(
        register_bp, url_prefix="/auth"
    )  # 👈 separado pero mismo prefijo
    app.register_blueprint(usuarios_bp, url_prefix="/usuarios")  # <-- registrar aquí
    app.register_blueprint(dashboard_bp, url_prefix="")
    app.register_blueprint(bienes_bp, url_prefix="/leads")
    app.register_blueprint(lead_bp, url_prefix="/leads")
    app.register_blueprint(reporte_rapido_bp, url_prefix="/leads")
    app.register_blueprint(reportes_bp, url_prefix="/reportes")
    app.register_blueprint(marketing_bp, url_prefix="/marketing")
    app.register_blueprint(chat_bp, url_prefix="/chat")
    app.register_blueprint(lead_workflow_bp)

    @app.before_request
    def require_login():
        allowed_endpoints = {
            "auth.login",
            "auth.logout",
            "healthz",
            "static",
            "lead_workflow.workflow_webhook",
        }
        if app.config.get("ALLOW_PUBLIC_REGISTRATION"):
            allowed_endpoints.add("register.register")

        endpoint = request.endpoint or ""
        if endpoint == "register.register" and not app.config.get(
            "ALLOW_PUBLIC_REGISTRATION"
        ):
            # El registro público está deshabilitado, pero los usuarios autenticados
            # deben poder ver la página de registro interna.
            if session.get("user_id"):
                return None
            return redirect(url_for("auth.login"))
        if endpoint in allowed_endpoints or endpoint.startswith("static"):
            return None
        if session.get("user_id"):
            return None
        return redirect(url_for("auth.login"))

    @app.before_request
    def restrict_marketing_role_scope():
        """El rol marketing solo puede operar dentro del módulo marketing."""
        rol = str(session.get("id_rol") or "").strip().lower()
        if rol != "marketing":
            return None

        endpoint = request.endpoint or ""
        allowed_endpoints = {
            "auth.login",
            "auth.logout",
            "dashboard.dashboard_router",
            "reportes.analisis_clientes",
            "static",
        }

        if endpoint.startswith("marketing.") or endpoint in allowed_endpoints:
            return None

        return redirect(url_for("reportes.analisis_clientes"))

    @app.after_request
    def set_security_headers(response):
        response.headers.setdefault("X-Content-Type-Options", "nosniff")
        response.headers.setdefault("X-Frame-Options", "SAMEORIGIN")
        response.headers.setdefault(
            "Referrer-Policy", "strict-origin-when-cross-origin"
        )
        return response

    @app.route("/")
    def index():
        if session.get("user_id"):
            return redirect(url_for("dashboard.dashboard_router"))
        return redirect(url_for("auth.login"))

    @app.route("/healthz")
    def healthz():
        return jsonify({"status": "ok"}), 200

    # Endpoints listos
    return app


# 👇 instancia a nivel de módulo para Gunicorn
app = create_app()

from core.celery_app import init_celery

init_celery(app)

# Config extra (cookies/seguridad) sobre la instancia
app.config.update(
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SECURE=bool(app.config.get("USE_HTTPS")),
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=7200,
)


# Solo para correr LOCALMENTE (no en Render)
if __name__ == "__main__":
    socketio.run(app, host="127.0.0.1", port=8000, debug=True)
