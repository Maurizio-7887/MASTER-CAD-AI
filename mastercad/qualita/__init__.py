"""Controllo qualità con la foto del pezzo prodotto, con verbale e storico dei controlli."""
import json
import threading

from flask import Blueprint, current_app, jsonify, render_template, request, session
from psycopg2.extras import Json, RealDictCursor

from ..postgres_store import connect
from ..progetto.analisi import analizza
from ..reverse.foto import ricostruisci
from .confronto import confronta

bp = Blueprint("qualita", __name__, template_folder="templates", static_folder="static", static_url_path="/qualita/static")
_LOCK = threading.Lock()


def init_db():
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""CREATE TABLE IF NOT EXISTS cad_controlli (
            id SERIAL PRIMARY KEY, nome TEXT NOT NULL, lotto TEXT, operatore TEXT, esito TEXT NOT NULL,
            dettaglio JSONB NOT NULL, creato TIMESTAMPTZ NOT NULL DEFAULT NOW())""")


@bp.get("/qualita")
def pagina():
    return render_template("qualita/qualita.html", csrf=session.get("csrf", ""))


def _num(v, nome, default):
    if v in (None, ""):
        return default
    try:
        v = float(str(v).replace(",", "."))
    except ValueError:
        raise ValueError("%s: scrivi un numero" % nome) from None
    if not 0.01 <= v <= 20:
        raise ValueError("%s fuori dai limiti" % nome)
    return v


@bp.post("/api/qualita/controlla")
def controlla():
    f = request.files.get("image")
    if f is None:
        return jsonify(error="Carica la foto del pezzo prodotto"), 400
    try:
        progetto = json.loads(request.form.get("progetto") or "null")
        foto = ricostruisci(f.read(15_000_001), vista="alto", riferimento=request.form.get("riferimento", "a4"),
                            misura_mm=request.form.get("misura"), misura_di=request.form.get("misura_di", "larghezza"))
        with _LOCK:
            an = analizza(progetto)
            if an["base"].get("tipo") == "rivoluzione":
                raise ValueError("Il controllo con foto dall'alto vale per pezzi piatti; per i torniti usa calibro e micrometro")
            r = confronta(an, foto["entita"], _num(request.form.get("tol_pos"), "Tolleranza di posizione", 0.5),
                          _num(request.form.get("tol_d"), "Tolleranza del diametro", 0.4), _num(request.form.get("tol_ing"), "Tolleranza d'ingombro", 0.8))
        nome = str(request.form.get("nome") or "Pezzo")[:120]
        lotto, operatore = str(request.form.get("lotto") or "")[:60], str(request.form.get("operatore") or "")[:60]
        with connect() as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO cad_controlli(nome, lotto, operatore, esito, dettaglio) VALUES (%s,%s,%s,%s,%s) RETURNING id, creato",
                        (nome, lotto, operatore, r["esito"], Json({"righe": r["righe"], "rotazione": r["rotazione"]})))
            cid, creato = cur.fetchone()
        return jsonify(dict(r, id=cid, data=creato.strftime("%d/%m/%Y %H:%M"), anteprima=foto.get("anteprima"), avvisi_foto=foto.get("avvisi", [])))
    except (ValueError, TypeError, KeyError) as exc:
        return jsonify(error=str(exc)[:400]), 400
    except Exception:
        current_app.logger.exception("Errore controllo qualità")
        return jsonify(error="Controllo non riuscito: rifai la foto (pezzo perpendicolare, su foglio A4, senza ombre)"), 500


@bp.get("/api/qualita/storico")
def storico():
    with connect() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT id, nome, lotto, operatore, esito, creato FROM cad_controlli ORDER BY creato DESC LIMIT 30")
        righe = cur.fetchall()
    return jsonify([dict(r, creato=r["creato"].strftime("%d/%m/%Y %H:%M")) for r in righe])
