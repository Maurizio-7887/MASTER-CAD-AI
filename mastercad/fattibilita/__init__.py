"""Verifica di fattibilità: le regole di officina controllate sul progetto."""
import threading

from flask import Blueprint, current_app, jsonify, render_template, request, session

from ..progetto.analisi import analizza
from .regole import verifica

bp = Blueprint("fattibilita", __name__, template_folder="templates", static_folder="static", static_url_path="/fattibilita/static")
_LOCK = threading.Lock()


@bp.get("/fattibilita")
def pagina():
    return render_template("fattibilita/fattibilita.html", csrf=session.get("csrf", ""))


@bp.post("/api/fattibilita")
def api():
    dati = request.get_json(silent=True)
    if not isinstance(dati, dict):
        return jsonify(error="JSON non valido"), 400
    try:
        with _LOCK:
            an = analizza(dati.get("progetto"))
            return jsonify(verifica(an))
    except (ValueError, TypeError, KeyError) as exc:
        return jsonify(error=str(exc)[:400]), 400
    except Exception:
        current_app.logger.exception("Errore fattibilità")
        return jsonify(error="Non sono riuscito a verificare il pezzo: ricostruiscilo nella pagina Disegno"), 500
