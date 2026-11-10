"""Dal carico alla forma: ottimizzazione topologica 2D e dimensionamento dello spessore da carichi e vincoli."""
import threading

from flask import Blueprint, current_app, jsonify, render_template, request, session

from ..materiali import elenco as elenco_materiali
from .topologia import ottimizza

bp = Blueprint("generativo", __name__, template_folder="templates", static_folder="static", static_url_path="/generativo/static")
_LOCK = threading.Lock()


@bp.get("/generativo")
def pagina():
    return render_template("generativo/generativo.html", csrf=session.get("csrf", ""), materiali=elenco_materiali())


@bp.post("/api/generativo")
def api():
    d = request.get_json(silent=True)
    if not isinstance(d, dict):
        return jsonify(error="JSON non valido"), 400
    try:
        if len(d.get("viti") or []) > 20 or len(d.get("carichi") or []) > 10 or len(d.get("zone_vietate") or []) > 20:
            raise ValueError("Troppi vincoli (massimo 20 viti, 10 carichi, 20 zone)")
        with _LOCK:
            return jsonify(ottimizza(d))
    except (ValueError, TypeError, KeyError) as exc:
        return jsonify(error=str(exc)[:400]), 400
    except Exception:
        current_app.logger.exception("Errore generativo")
        return jsonify(error="Calcolo non riuscito: controlla che carichi e viti siano dentro la sagoma"), 500
