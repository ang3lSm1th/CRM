# al inicio del archivo de routes donde está lead_bp
from flask import jsonify
from models.ubigeo import get_departamentos, get_provincias_by_departamento, get_distritos_by_provincia

@lead_bp.route('/api/departamentos', methods=['GET'])
def api_list_departamentos():
    deps = get_departamentos()
    return jsonify([{"id": d["id"], "nombre": d["nombre"]} for d in deps]), 200

@lead_bp.route('/api/provincias/<int:departamento_id>', methods=['GET'])
def api_provincias_by_dep(departamento_id):
    provs = get_provincias_by_departamento(departamento_id)
    return jsonify([{"id": p["id"], "nombre": p["nombre"]} for p in provs]), 200

@lead_bp.route('/api/distritos/<int:provincia_id>', methods=['GET'])
def api_distritos_by_prov(provincia_id):
    dists = get_distritos_by_provincia(provincia_id)
    return jsonify([{"id": d["id"], "nombre": d["nombre"]} for d in dists]), 200
