"""Progetto parametrico: forma di base (disegno o foto) + albero delle lavorazioni + indicazioni del tecnico."""
import threading

from flask import Blueprint, current_app, jsonify, request

from . import direttive, lavorazioni

bp = Blueprint("progetto", __name__, template_folder="templates", static_folder="static", static_url_path="/progetto/static")
_LOCK = threading.Lock()


def _json():
    dati = request.get_json(silent=True)
    if not isinstance(dati, dict):
        raise ValueError("JSON non valido")
    return dati


@bp.post("/api/progetto/da-foto")
def da_foto():
    """Contorno della foto → base estrusa; i cerchi interni diventano fori modificabili nell'albero."""
    try:
        dati = _json()
        return jsonify(progetto=direttive.da_foto(dati.get("entita") or [], float(dati.get("altezza") or 10)))
    except (ValueError, TypeError) as exc:
        return jsonify(error=str(exc)[:400]), 400


@bp.post("/api/progetto/da-disegno")
def da_disegno():
    """Il disegno della tavola diventa la base (estruso, tornito, vista dall'alto o di fronte) senza perdere l'albero."""
    try:
        dati = _json()
        come = dati.get("come")
        if come not in ("estrudi", "rivoluzione", "alto", "fronte"):
            raise ValueError("Base: estrudi, rivoluzione, alto o fronte")
        prog = direttive.da_disegno(dati.get("entita"), come, dati.get("progetto"), float(dati.get("altezza") or 10),
                                    dati.get("asse"), float(dati.get("angolo") or 360))
        return jsonify(progetto=prog)
    except (ValueError, TypeError) as exc:
        return jsonify(error=str(exc)[:400]), 400


@bp.post("/api/progetto/direttive")
def applica_direttive():
    try:
        dati = _json()
        return jsonify(direttive.applica(str(dati.get("testo") or ""), dati.get("progetto") or {}))
    except (ValueError, TypeError) as exc:
        return jsonify(error=str(exc)[:400]), 400


@bp.post("/api/progetto/costruisci")
def costruisci():
    from ..disegno import salva_solido
    try:
        dati = _json()
        progetto = dati.get("progetto")
        with _LOCK:
            obj, sol, storia = lavorazioni.costruisci(progetto)
            nome = str(dati.get("nome") or "Progetto")[:180]
            out = salva_solido(obj, sol, {"kind": "progetto", "progetto": progetto}, storia, nome)
        saltate = [s for s in storia if not s.get("ok")]
        return jsonify(dict(out, saltate=len(saltate),
                            warning="Bozza CAD: verificare quote, tolleranze, materiale e carichi prima di produrre."))
    except (ValueError, TypeError, KeyError) as exc:
        return jsonify(error=str(exc)[:400]), 400
    except Exception:
        current_app.logger.exception("Errore costruzione progetto")
        return jsonify(error="Il motore 3D non è riuscito a costruire la forma di base: controlla i contorni"), 500


@bp.post("/api/progetto/funzione")
def funzione():
    """Assegna o cambia lo scopo di un foro (cuscinetto, spina, boccola, vite…) e dice cosa cambia nel pezzo."""
    import copy
    from ..tolleranze.funzioni import applica_funzione, impatto
    try:
        dati = _json()
        prog = dati.get("progetto") or {}
        i = int(dati.get("indice"))
        lavs = prog.get("lavorazioni") or []
        if not 0 <= i < len(lavs) or lavs[i].get("tipo") not in ("foro", "serie_polare", "serie_rett"):
            raise ValueError("Lo scopo si assegna ai fori (singoli o in serie)")
        nuovo = copy.deepcopy(prog)
        nuovo["lavorazioni"][i] = applica_funzione(lavs[i], dati.get("funzione") or {})
        with _LOCK:
            imp = impatto(prog, nuovo)
        return jsonify(progetto=nuovo, impatto=imp, funzione=nuovo["lavorazioni"][i]["funzione"])
    except (ValueError, TypeError, KeyError) as exc:
        return jsonify(error=str(exc)[:400]), 400
