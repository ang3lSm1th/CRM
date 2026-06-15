from flask import Blueprint, render_template, request, redirect, url_for, flash
from models.bien_servicio import BienServicio
from utils.security import login_required

bienes_bp = Blueprint("bienes_servicios", __name__)

@bienes_bp.before_request
@login_required
def _bienes_before_request():
    return None

@bienes_bp.route("/bienes-servicios", methods=["GET"])
def list_bienes():
    bienes = BienServicio.get_all() or []
    return render_template("leads/bienes_servicios.html", bienes=bienes)

@bienes_bp.route("/bienes-servicios/create", methods=["POST"])
def create_bien():
    nombre = (request.form.get("nombre") or "").strip()
    if not nombre:
        flash("Nombre es requerido", "danger")
        return redirect(url_for("bienes_servicios.list_bienes"))
    try:
        BienServicio.create(nombre)
        flash("Bien/Servicio creado", "success")
    except Exception as e:
        flash("Error al crear: " + str(e), "danger")
    return redirect(url_for("bienes_servicios.list_bienes"))

@bienes_bp.route("/bienes-servicios/edit/<int:bien_id>", methods=["POST"])
def edit_bien(bien_id):
    nombre = (request.form.get("nombre") or "").strip()
    if not nombre:
        flash("Nombre es requerido", "danger")
        return redirect(url_for("bienes_servicios.list_bienes"))
    try:
        BienServicio.update(bien_id, nombre)
        flash("Bien/Servicio actualizado", "success")
    except Exception as e:
        flash("Error al actualizar: " + str(e), "danger")
    return redirect(url_for("bienes_servicios.list_bienes"))

@bienes_bp.route("/bienes-servicios/delete/<int:bien_id>", methods=["POST"])
def delete_bien(bien_id):
    try:
        BienServicio.delete(bien_id)
        flash("Bien/Servicio eliminado", "success")
    except Exception as e:
        flash("Error al eliminar: " + str(e), "danger")
    return redirect(url_for("bienes_servicios.list_bienes"))
