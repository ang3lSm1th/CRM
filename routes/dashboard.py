from flask import Blueprint, session, redirect, url_for, flash
from utils.security import login_required, ROLE_ADMIN, ROLE_GERENTE, ROLE_RRHH, ROLE_ASESOR

dashboard_bp = Blueprint("dashboard", __name__)

@dashboard_bp.route("/dashboard")
@login_required
def dashboard_router():
    rol = session.get("id_rol")

    if rol in (ROLE_ADMIN, ROLE_GERENTE, ROLE_RRHH):
        return redirect(url_for("leads.list_leads"))     # → /leads/list
    elif rol == ROLE_ASESOR:
        return redirect(url_for("leads.list_unstarted")) # → /leads/sin-iniciar

    flash("Rol no reconocido", "warning")
    return redirect(url_for("auth.login"))
