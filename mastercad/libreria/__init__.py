"""Libreria di pezzi a norma: flange EN 1092-1, piastre, staffe, boccole, alberi."""
from flask import Blueprint, jsonify, render_template, request, session

from . import catalogo as C

bp = Blueprint("libreria", __name__, template_folder="templates", static_folder="static", static_url_path="/libreria/static")


@bp.get("/libreria")
def pagina():
    return render_template("libreria/libreria.html", csrf=session.get("csrf", ""), catalogo=C.catalogo())


@bp.post("/api/libreria/genera")
def genera():
    dati = request.get_json(silent=True)
    if not isinstance(dati, dict):
        return jsonify(error="JSON non valido"), 400
    try:
        return jsonify(C.genera(str(dati.get("codice") or ""), dati.get("parametri") or {}))
    except (ValueError, TypeError, KeyError) as exc:
        return jsonify(error=str(exc)[:400]), 400
