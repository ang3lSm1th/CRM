from flask import Blueprint, render_template, session, redirect, url_for, flash
from utils.security import role_required, login_required, ROLE_ADMIN, ROLE_GERENTE, ROLE_RRHH, ROLE_ASESOR

dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route("/dashboard")
@login_required
def dashboard_router():
    rol = session.get("id_rol")
    if rol == ROLE_ADMIN:
        return redirect(url_for("dashboard.admin_dashboard"))
    elif rol == ROLE_GERENTE:
        return redirect(url_for("dashboard.gerente_dashboard"))
    elif rol == ROLE_RRHH:
        return redirect(url_for("dashboard.rrhh_dashboard"))
    elif rol == ROLE_ASESOR:
        return redirect(url_for("dashboard.asesor_dashboard"))
    flash("Rol no reconocido", "warning")
    return redirect(url_for("auth.login"))

@dashboard_bp.route("/dashboard/admin")
@role_required(ROLE_ADMIN)
def admin_dashboard():
    return render_template("dashboards/admin.html")

@dashboard_bp.route("/dashboard/gerente")
@role_required(ROLE_GERENTE)
def gerente_dashboard():
    return render_template("dashboards/gerente.html")

@dashboard_bp.route("/dashboard/rrhh")
@role_required(ROLE_RRHH)
def rrhh_dashboard():
    return render_template("dashboards/rrhh.html")

@dashboard_bp.route("/dashboard/asesor")
@role_required(ROLE_ASESOR)
def asesor_dashboard():
    return render_template("dashboards/asesor.html")
