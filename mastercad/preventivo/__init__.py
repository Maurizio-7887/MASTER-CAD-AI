"""Preventivo istantaneo: dal pezzo a materiale, tempi, costi e prezzo per quantità.

Stessi numeri del ciclo di lavoro: il prezzo nasce da grezzo × €/kg, minuti macchina × €/ora,
attrezzaggio spalmato sul lotto, trattamento, scarto e margine. Tutto modificabile dalla pagina.
"""
import threading

from flask import Blueprint, current_app, jsonify, render_template, request, session

from ..ciclo import motore
from ..materiali import TRATTAMENTI, elenco as elenco_materiali, materiale as dati_materiale
from ..officina import leggi as leggi_officina
from ..progetto.analisi import analizza

bp = Blueprint("preventivo", __name__, template_folder="templates", static_folder="static", static_url_path="/preventivo/static")
_LOCK = threading.Lock()

DEFAULT = {"costo_attrezzaggio": 45.0, "margine": 25.0, "scarto": 3.0, "quantita": [1, 10, 50, 100]}


def _f(v, nome, minimo=0.0, massimo=1e6):
    try:
        v = float(v)
    except (TypeError, ValueError):
        raise ValueError("%s non valido" % nome) from None
    if not minimo <= v <= massimo:
        raise ValueError("%s fuori dai limiti" % nome)
    return v


def calcola(an, ciclo, parametri):
    p = dict(DEFAULT, **{k: v for k, v in (parametri or {}).items() if v not in (None, "")})
    m = dati_materiale(ciclo["codice_materiale"])
    tratt = TRATTAMENTI.get(p.get("trattamento") or "nessuno")
    if tratt is None:
        raise ValueError("Trattamento sconosciuto")
    if p.get("trattamento") == "anodizzazione" and ciclo["codice_materiale"] != "AL6082":
        raise ValueError("L'anodizzazione si fa solo sull'alluminio")
    euro_kg = _f(p.get("euro_kg") or m["euro_kg"], "Prezzo del materiale", 0.01, 500)
    costo_att = _f(p["costo_attrezzaggio"], "Costo attrezzaggio", 1, 1000)
    margine = _f(p["margine"], "Margine", 0, 300) / 100
    scarto = _f(p["scarto"], "Scarto", 0, 50) / 100
    qta = sorted({int(_f(q, "Quantità", 1, 1_000_000)) for q in (p["quantita"] or [1])})[:8]
    kg_grezzo = ciclo["grezzo"]["volume"] / 1e6 * m["densita"]
    kg_finito = an["volume"] / 1e6 * m["densita"]
    mat = kg_grezzo * euro_kg
    t_mac, t_banco, t_att = ciclo["tempi"]["macchina_min"], ciclo["tempi"]["banco_min"], ciclo["tempi"]["attrezzaggio_min"]
    # ogni fase con la tariffa della sua macchina (o del terzista) presa dall'officina
    lav = sum(sum(o["tempo"] for o in f["operazioni"]) / 60 * float(f.get("costo_ora") or 50) for f in ciclo["fasi"])
    tr = kg_finito * float(p.get("euro_kg_trattamento") if p.get("euro_kg_trattamento") is not None else tratt["euro_kg"])
    righe = []
    for q in qta:
        # lotti grandi: il tempo macchina cala (programma rodato, carico/scarico ottimizzato), fino al −20%
        fattore = 1.0 if q < 10 else 0.92 if q < 50 else 0.85 if q < 200 else 0.80     # solo sul tempo, non sul materiale
        att = t_att / 60 * costo_att / q
        costo = (mat + lav * fattore + tr) * (1 + scarto) + att
        prezzo = costo * (1 + margine)
        righe.append({"quantita": q, "materiale": round(mat, 2), "lavorazione": round(lav * fattore, 2), "trattamento": round(tr, 2),
                      "attrezzaggio": round(att, 2), "costo": round(costo, 2), "prezzo": round(prezzo, 2), "totale": round(prezzo * q, 2)})
    return {"materiale": m["nome"], "euro_kg": euro_kg, "grezzo": ciclo["grezzo"]["descrizione"],
            "kg_grezzo": round(kg_grezzo, 3), "kg_finito": round(kg_finito, 3), "trattamento": tratt["nome"],
            "tempi": ciclo["tempi"], "margine": margine * 100, "scarto": scarto * 100, "terzisti": ciclo.get("terzisti", []),
            "righe": righe,
            "voci_ciclo": [{"fase": f["n"], "nome": f["nome"], "macchina": f["macchina"], "costo_ora": f.get("costo_ora"),
                            "minuti": round(sum(o["tempo"] for o in f["operazioni"]), 2),
                            "euro": round(sum(o["tempo"] for o in f["operazioni"]) / 60 * float(f.get("costo_ora") or 50), 2)} for f in ciclo["fasi"]]}


@bp.get("/preventivo")
def pagina():
    return render_template("preventivo/preventivo.html", csrf=session.get("csrf", ""), materiali=elenco_materiali(),
                           trattamenti=[{"codice": k, "nome": v["nome"]} for k, v in TRATTAMENTI.items()], default=DEFAULT)


@bp.post("/api/preventivo")
def api():
    dati = request.get_json(silent=True)
    if not isinstance(dati, dict):
        return jsonify(error="JSON non valido"), 400
    try:
        with _LOCK:
            an = analizza(dati.get("progetto"))
            off = leggi_officina()
            c = motore.calcola(an, dati.get("materiale") or "S235", off)
        par = {k: v for k, v in (dati.get("parametri") or {}).items() if v not in (None, "")}
        mat = (dati.get("materiale") or "S235").upper()
        par.setdefault("euro_kg", off["materiali"].get(mat, {}).get("euro_kg"))
        par.setdefault("costo_attrezzaggio", off["costi"]["attrezzaggio"])
        for k in ("margine", "scarto"):
            par.setdefault(k, off["costi"][k])
        if par.get("trattamento") and par["trattamento"] in off["trattamenti"]:
            par["euro_kg_trattamento"] = off["trattamenti"][par["trattamento"]]["euro_kg"]
        return jsonify(preventivo=calcola(an, c, par), saltate=an["saltate"],
                       avviso="Preventivo indicativo: prezzi dei materiali e costi orari sono valori medi, aggiornali con i tuoi.")
    except (ValueError, TypeError, KeyError) as exc:
        return jsonify(error=str(exc)[:400]), 400
    except Exception:
        current_app.logger.exception("Errore preventivo")
        return jsonify(error="Non sono riuscito a calcolare il preventivo: ricostruisci il pezzo nella pagina Disegno"), 500
