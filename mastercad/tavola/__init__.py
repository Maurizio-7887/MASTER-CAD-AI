"""Messa in tavola: il disegno tecnico per l'officina generato dal modello 3D (PDF, DXF, SVG)."""
import threading

from flask import Blueprint, Response, current_app, jsonify, render_template, request, session

from ..materiali import TRATTAMENTI, elenco as elenco_materiali
from ..progetto.analisi import analizza
from . import disegno_tecnico as DT

bp = Blueprint("tavola", __name__, template_folder="templates", static_folder="static", static_url_path="/tavola/static")
_LOCK = threading.Lock()


@bp.get("/tavola")
def pagina():
    return render_template("tavola/tavola.html", csrf=session.get("csrf", ""), materiali=elenco_materiali(),
                           trattamenti=[{"codice": k, "nome": v["nome"]} for k, v in TRATTAMENTI.items()])


def _genera(dati):
    info = dict(dati.get("cartiglio") or {})
    info["materiale"] = dati.get("materiale") or info.get("materiale") or "S235"
    tr = TRATTAMENTI.get(dati.get("trattamento") or "nessuno") or TRATTAMENTI["nessuno"]
    info["trattamento_nome"] = tr["nome"] if tr["euro_kg"] else "—"
    for k in ("nome", "disegnatore", "controllato", "numero", "revisione"):
        if k in info:
            info[k] = str(info[k])[:60]
    with _LOCK:
        an = analizza(dati.get("progetto"))
        return an, DT.genera(an, info)


@bp.post("/api/tavola")
def api():
    dati = request.get_json(silent=True)
    if not isinstance(dati, dict):
        return jsonify(error="JSON non valido"), 400
    try:
        an, tav = _genera(dati)
        return jsonify(svg=DT.svg(tav), scala=tav["scala"], massa_kg=tav["massa_kg"], viti=tav["viti"], note=tav["note"],
                       tabella_fori=tav["tabella_fori"], sezione=tav["sezione"], saltate=an["saltate"])
    except (ValueError, TypeError, KeyError) as exc:
        return jsonify(error=str(exc)[:400]), 400
    except Exception:
        current_app.logger.exception("Errore messa in tavola")
        return jsonify(error="Non sono riuscito a fare la tavola: ricostruisci il pezzo nella pagina Disegno"), 500


@bp.post("/api/tavola/<fmt>")
def scarica(fmt):
    if fmt not in ("pdf", "dxf", "svg"):
        return jsonify(error="Formato: pdf, dxf o svg"), 400
    dati = request.get_json(silent=True)
    if not isinstance(dati, dict):
        return jsonify(error="JSON non valido"), 400
    try:
        _, tav = _genera(dati)
    except (ValueError, TypeError, KeyError) as exc:
        return jsonify(error=str(exc)[:400]), 400
    nome = "".join(c for c in str((dati.get("cartiglio") or {}).get("nome") or "tavola") if c.isalnum() or c in "-_ ")[:40].strip().replace(" ", "_") or "tavola"
    if fmt == "pdf":
        corpo, tipo = DT.pdf(tav), "application/pdf"
    elif fmt == "dxf":
        corpo, tipo = DT.dxf(tav), "application/dxf"
    else:
        corpo, tipo = DT.svg(tav).encode("utf-8"), "image/svg+xml"
    return Response(corpo, mimetype=tipo, headers={"Content-Disposition": "attachment; filename=%s.%s" % (nome, fmt)})
