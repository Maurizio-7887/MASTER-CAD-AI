"""Reverse engineering da foto: contorno del pezzo → disegno 2D in mm, da correggere e portare in 3D."""
from flask import Blueprint, jsonify, request

from .foto import ricostruisci

bp = Blueprint("reverse", __name__, template_folder="templates", static_folder="static", static_url_path="/reverse/static")


@bp.post("/api/reverse/foto")
def da_foto():
    f = request.files.get("image")
    if f is None:
        return jsonify(error="Carica una foto del pezzo"), 400
    try:
        r = ricostruisci(f.read(15_000_001), vista=request.form.get("vista", "alto"),
                         riferimento=request.form.get("riferimento", "misura"),
                         misura_mm=request.form.get("misura"), misura_di=request.form.get("misura_di", "larghezza"))
        return jsonify(r)
    except ValueError as exc:
        return jsonify(error=str(exc)[:400]), 400
