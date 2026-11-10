"""Accoppiamenti e tolleranze ISO 286, catene di tolleranza, cataloghi di cuscinetti, spine e boccole."""
from flask import Blueprint, jsonify, render_template, request, session

from . import funzioni, iso286

bp = Blueprint("tolleranze", __name__, template_folder="templates", static_folder="static", static_url_path="/tolleranze/static")

ACCOPPIAMENTI_TIPICI = [
    ("H7", "g6", "Perni e alberi che ruotano o scorrono con precisione (leve, rulli folli)"),
    ("H7", "f7", "Scorrimento libero, lubrificato (guide, pistoni)"),
    ("H7", "h6", "Centraggio con gioco minimo, montaggio a mano"),
    ("H7", "k6", "Centraggio preciso, montaggio con mazzuolo (anello interno cuscinetto)"),
    ("H7", "m6", "Spine di riferimento, ruote calettate con linguetta"),
    ("H7", "n6", "Bloccaggio leggero alla pressa"),
    ("H7", "p6", "Bloccaggio alla pressa (boccole, perni fissi)"),
]


@bp.get("/tolleranze")
def pagina():
    return render_template("tolleranze/tolleranze.html", csrf=session.get("csrf", ""), tipici=ACCOPPIAMENTI_TIPICI,
                           cuscinetti=[dict(codice=k, d=v[0], D=v[1], B=v[2]) for k, v in funzioni.CUSCINETTI.items()], spine=funzioni.SPINE)


def _json():
    d = request.get_json(silent=True)
    if not isinstance(d, dict):
        raise ValueError("JSON non valido")
    return d


@bp.post("/api/tolleranze/accoppiamento")
def accoppiamento():
    try:
        d = _json()
        return jsonify(iso286.accoppiamento(float(str(d.get("diametro")).replace(",", ".")), str(d.get("foro") or "H7").strip(), str(d.get("albero") or "g6").strip()))
    except (ValueError, TypeError) as exc:
        return jsonify(error=str(exc)), 400


@bp.post("/api/tolleranze/catena")
def catena():
    try:
        d = _json()
        anelli = []
        for a in d.get("anelli") or []:
            anelli.append({"nome": str(a.get("nome") or "")[:40], "nominale": float(a["nominale"]), "sup": float(a.get("sup") or 0),
                           "inf": float(a.get("inf") or 0), "verso": 1 if float(a.get("verso") or 1) >= 0 else -1})
        return jsonify(iso286.catena(anelli))
    except (ValueError, TypeError, KeyError) as exc:
        return jsonify(error=str(exc)), 400
