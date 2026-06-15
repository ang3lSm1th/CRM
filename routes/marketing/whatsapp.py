import os
from datetime import datetime

from werkzeug.utils import secure_filename

from routes.marketing.shared import (
    ROLE_ADMIN,
    ROLE_GERENTE,
    ROLE_MARKETING,
    flash,
    jsonify,
    login_required,
    marketing_bp,
    os as _shared_os,
    redirect,
    render_template,
    request,
    role_required,
    url_for,
)


@marketing_bp.route("/upload-image", methods=["POST"])
@login_required
@role_required(ROLE_ADMIN, ROLE_GERENTE, ROLE_MARKETING)
def marketing_upload_image():
    file = request.files.get("file")
    if not file:
        return jsonify({"error": "Archivo no recibido"}), 400

    filename = secure_filename(file.filename or "")
    if not filename:
        return jsonify({"error": "Nombre de archivo invalido"}), 400
    ext = os.path.splitext(filename)[1].lower()
    if ext not in (".jpg", ".jpeg", ".png", ".gif", ".webp"):
        return jsonify({"error": "Formato no permitido"}), 400

    subdir = datetime.utcnow().strftime("%Y%m%d")
    upload_dir = os.path.join("static", "uploads", "marketing", subdir)
    os.makedirs(upload_dir, exist_ok=True)

    ts = datetime.utcnow().strftime("%H%M%S%f")
    save_name = f"mk_{ts}{ext}"
    save_path = os.path.join(upload_dir, save_name)
    file.save(save_path)

    url = f"/static/uploads/marketing/{subdir}/{save_name}"
    return jsonify({"url": url}), 200


def _normalize_phone(phone, default_cc):
    p = "".join(ch for ch in str(phone or "") if ch.isdigit())
    if not p:
        return ""
    if p.startswith("00"):
        p = p[2:]
    if p.startswith("0"):
        p = p[1:]
    if default_cc and not p.startswith(default_cc) and len(p) <= 11:
        p = f"{default_cc}{p}"
    return p



def _get_env_path():
    return os.path.abspath(os.path.join(os.path.dirname(__file__), "..", ".env"))


def _update_dotenv(vars_map):
    env_path = _get_env_path()
    existing_lines = []
    try:
        if os.path.exists(env_path):
            with open(env_path, "r", encoding="utf-8") as file_obj:
                existing_lines = file_obj.read().splitlines()
    except Exception:
        existing_lines = []

    keys = {key.strip() for key in vars_map.keys() if key}
    new_lines = []
    for line in existing_lines:
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            new_lines.append(line)
            continue
        key = stripped.split("=", 1)[0].strip()
        if key in keys:
            continue
        new_lines.append(line)

    for key, value in vars_map.items():
        value = "" if value is None else str(value)
        if any(ch in value for ch in [" ", '"', "\t"]):
            escaped_v = value.replace('"', '\\"')
            line = f'{key}="{escaped_v}"'
        else:
            line = f"{key}={value}"
        new_lines.append(line)

    with open(env_path, "w", encoding="utf-8") as file_obj:
        file_obj.write("\n".join(new_lines) + "\n")


@marketing_bp.route("/api-config", methods=["GET", "POST"])
@login_required
@role_required(ROLE_ADMIN)
def marketing_api_config():
    brand = (request.cookies.get("brand") or "orbes").strip().lower()
    brand_prefix = brand.upper()

    if request.method == "POST":
        meta_token = request.form.get("meta_token", "").strip()
        meta_api_version = request.form.get("meta_api_version", "").strip() or "v20.0"
        fb_page_id = request.form.get("fb_page_id", "").strip()
        ig_account_id = request.form.get("ig_account_id", "").strip()

        _update_dotenv(
            {
                f"{brand_prefix}_META_ACCESS_TOKEN": meta_token,
                f"{brand_prefix}_META_API_VERSION": meta_api_version,
                f"{brand_prefix}_FB_PAGE_ID": fb_page_id,
                f"{brand_prefix}_IG_ACCOUNT_ID": ig_account_id,
            }
        )
        os.environ[f"{brand_prefix}_META_ACCESS_TOKEN"] = meta_token
        os.environ[f"{brand_prefix}_META_API_VERSION"] = meta_api_version
        os.environ[f"{brand_prefix}_FB_PAGE_ID"] = fb_page_id
        os.environ[f"{brand_prefix}_IG_ACCOUNT_ID"] = ig_account_id

        flash(f"Configuración de {brand.capitalize()} guardada correctamente.", "success")
        return redirect(url_for("marketing.marketing_api_config"))

    ctx = {
        "brand": brand,
        "meta_token": os.getenv(f"{brand_prefix}_META_ACCESS_TOKEN", "").strip(),
        "meta_api_version": os.getenv(f"{brand_prefix}_META_API_VERSION", "v20.0").strip() or "v20.0",
        "fb_page_id": os.getenv(f"{brand_prefix}_FB_PAGE_ID", "").strip(),
        "ig_account_id": os.getenv(f"{brand_prefix}_IG_ACCOUNT_ID", "").strip(),
    }
    return render_template("reportes/marketing_api_config.html", **ctx)


@marketing_bp.route("/wa/templates", methods=["GET"])
@login_required
@role_required(ROLE_ADMIN, ROLE_GERENTE, ROLE_MARKETING)
def marketing_list_wa_templates():
    """Devuelve una lista de plantillas de WhatsApp disponible para el módulo de clientes."""
    return jsonify({"ok": True, "templates": []}), 200


