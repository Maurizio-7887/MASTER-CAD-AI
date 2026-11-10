"""Ciclo di lavoro e programma CNC dal progetto."""
import threading

from flask import Blueprint, Response, current_app, jsonify, render_template, request, session

from ..materiali import elenco as elenco_materiali
from ..progetto.analisi import analizza
from . import motore

bp = Blueprint("ciclo", __name__, template_folder="templates", static_folder="static", static_url_path="/ciclo/static")
_LOCK = threading.Lock()


@bp.get("/ciclo")
def pagina():
    return render_template("ciclo/ciclo.html", csrf=session.get("csrf", ""), materiali=elenco_materiali())


def _calcola(dati):
    with _LOCK:
        an = analizza(dati.get("progetto"))
        c = motore.calcola(an, dati.get("materiale") or "S235")
        prog = motore.programma(an, c, dati.get("nome") or "PEZZO")
    return an, c, prog


@bp.post("/api/ciclo")
def api_ciclo():
    dati = request.get_json(silent=True)
    if not isinstance(dati, dict):
        return jsonify(error="JSON non valido"), 400
    try:
        an, c, prog = _calcola(dati)
        return jsonify(ciclo=c, fori=motore.tabella_fori(an), gcode=prog, saltate=an["saltate"],
                       avviso="Ciclo e programma di partenza: simulare il percorso e verificare utensili e parametri sulla macchina prima di lavorare.")
    except (ValueError, TypeError, KeyError) as exc:
        return jsonify(error=str(exc)[:400]), 400
    except Exception:
        current_app.logger.exception("Errore ciclo")
        return jsonify(error="Non sono riuscito a calcolare il ciclo: ricostruisci il pezzo nella pagina Disegno"), 500


@bp.post("/api/ciclo/gcode")
def api_gcode():
    dati = request.get_json(silent=True)
    if not isinstance(dati, dict):
        return jsonify(error="JSON non valido"), 400
    try:
        _, _, prog = _calcola(dati)
    except (ValueError, TypeError, KeyError) as exc:
        return jsonify(error=str(exc)[:400]), 400
    if not prog:
        return jsonify(error="Pezzo tornito: il programma di tornitura si prepara con il CAM del tornio"), 400
    nome = "".join(c for c in str(dati.get("nome") or "pezzo") if c.isalnum() or c in "-_")[:40] or "pezzo"
    return Response(prog, mimetype="text/plain", headers={"Content-Disposition": "attachment; filename=O1001_%s.nc" % nome})
