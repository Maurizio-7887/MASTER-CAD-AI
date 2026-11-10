"""Assiemi con lo scopo: proposte di montaggio dai fori funzionali, verifiche al micron, collisioni, distinta, 3D e AR."""
import secrets
import threading

from flask import Blueprint, abort, current_app, jsonify, render_template, request, session, url_for
from psycopg2.extras import Json, RealDictCursor

from ..postgres_store import connect
from . import montaggio as M

bp = Blueprint("assiemi", __name__, template_folder="templates", static_folder="static", static_url_path="/assiemi/static")
_LOCK = threading.Lock()
MAX_COMPONENTI = 20


def init_db():
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""CREATE TABLE IF NOT EXISTS cad_assiemi (uid TEXT PRIMARY KEY, nome TEXT NOT NULL, dati JSONB NOT NULL,
                       aggiornato TIMESTAMPTZ NOT NULL DEFAULT NOW())""")


def _assieme(d):
    a = d.get("assieme")
    if not isinstance(a, dict):
        raise ValueError("Assieme non valido")
    comps = a.get("componenti") or []
    if not comps:
        raise ValueError("Aggiungi almeno due pezzi all'assieme")
    if len(comps) > MAX_COMPONENTI:
        raise ValueError("Massimo %d pezzi per assieme" % MAX_COMPONENTI)
    for c in comps:
        if c.get("tipo") != "pezzo" or not isinstance(c.get("progetto"), dict) or not c["progetto"].get("base"):
            raise ValueError("Componente «%s» senza progetto" % c.get("nome"))
        c.setdefault("id", secrets.token_hex(4))
        c.setdefault("pos", [0, 0, 0])
    return a


@bp.get("/assiemi")
def pagina():
    return render_template("assiemi/assiemi.html", csrf=session.get("csrf", ""))


@bp.post("/api/assiemi/proponi")
def proponi():
    try:
        a = _assieme(request.get_json(silent=True) or {})
        with _LOCK:
            return jsonify(proposte=M.proponi(a))
    except (ValueError, TypeError, KeyError) as exc:
        return jsonify(error=str(exc)[:400]), 400
    except Exception:
        current_app.logger.exception("Errore proposte assieme")
        return jsonify(error="Non sono riuscito a leggere i pezzi: ricostruiscili nel CAD"), 500


@bp.post("/api/assiemi/monta")
def monta():
    from ..ar import GIORNI, qr_svg
    try:
        d = request.get_json(silent=True) or {}
        a = _assieme(d)
        with _LOCK:
            r = M.monta(a, d.get("montaggi") or [])
            glb = M.esporta_glb(r["solidi"])
            glb_esp = M.esporta_glb(r["solidi"], esploso=True)
        nome = str(a.get("nome") or "Assieme")[:120]
        tok, tok_e = secrets.token_hex(16), secrets.token_hex(16)
        with connect() as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO cad_condivisioni(token, nome, glb) VALUES (%s,%s,%s),(%s,%s,%s)", (tok, nome, glb, tok_e, nome + " (esploso)", glb_esp))
        link = request.host_url.rstrip("/") + url_for("ar.vista", token=tok)
        comps = [{k: v for k, v in c.items()} for c in r["componenti"]]
        return jsonify(verifiche=r["verifiche"], distinta=r["distinta"], componenti=comps,
                       commerciali=[{"id": c["id"], "tipo": c["tipo"], "nome": c["nome"]} for c in r["commerciali"]],
                       glb=url_for("ar.modello", token=tok), glb_esploso=url_for("ar.modello", token=tok_e), link_ar=link, qr=qr_svg(link), giorni=GIORNI)
    except (ValueError, TypeError, KeyError) as exc:
        return jsonify(error=str(exc)[:400]), 400
    except Exception:
        current_app.logger.exception("Errore montaggio")
        return jsonify(error="Montaggio non riuscito: controlla i pezzi e le proposte scelte"), 500


@bp.get("/api/assiemi")
def elenco():
    with connect() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT uid, nome, jsonb_array_length(dati->'componenti') AS pezzi, to_char(aggiornato,'DD/MM/YYYY HH24:MI') AS aggiornato FROM cad_assiemi ORDER BY aggiornato DESC LIMIT 50")
        return jsonify(cur.fetchall())


@bp.get("/api/assiemi/<uid>")
def leggi(uid):
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT dati FROM cad_assiemi WHERE uid=%s", (uid[:40],))
        r = cur.fetchone()
    if not r:
        abort(404)
    return jsonify(r[0])


@bp.post("/api/assiemi")
def salva():
    d = request.get_json(silent=True) or {}
    a = d.get("assieme")
    if not isinstance(a, dict) or not a.get("uid"):
        return jsonify(error="Assieme non valido"), 400
    if len(a.get("componenti") or []) > MAX_COMPONENTI:
        return jsonify(error="Troppi pezzi"), 400
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""INSERT INTO cad_assiemi(uid, nome, dati) VALUES (%s,%s,%s)
                       ON CONFLICT (uid) DO UPDATE SET nome=EXCLUDED.nome, dati=EXCLUDED.dati, aggiornato=NOW()""",
                    (str(a["uid"])[:40], str(a.get("nome") or "Assieme")[:120], Json(a)))
    return jsonify(ok=True)
