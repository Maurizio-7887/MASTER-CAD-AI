"""Assiemi con lo scopo: proposte di montaggio dai fori funzionali, verifiche al micron, collisioni, distinta, 3D e AR,
tolleranze geometriche dedotte e montaggio guidato sul telefono (pagina pubblica col link segreto, conferme del montatore)."""
import datetime
import secrets
import threading

from flask import Blueprint, abort, current_app, jsonify, render_template, request, session, url_for
from psycopg2.extras import Json, RealDictCursor

from ..officina import leggi as leggi_officina
from ..postgres_store import connect
from . import montaggio as M

bp = Blueprint("assiemi", __name__, template_folder="templates", static_folder="static", static_url_path="/assiemi/static")
_LOCK = threading.Lock()
MAX_COMPONENTI = 20


def init_db():
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""CREATE TABLE IF NOT EXISTS cad_assiemi (uid TEXT PRIMARY KEY, nome TEXT NOT NULL, dati JSONB NOT NULL,
                       aggiornato TIMESTAMPTZ NOT NULL DEFAULT NOW())""")
        cur.execute("""CREATE TABLE IF NOT EXISTS cad_montaggi (token TEXT PRIMARY KEY, nome TEXT NOT NULL, dati JSONB NOT NULL,
                       conferme JSONB NOT NULL DEFAULT '[]'::jsonb, creato TIMESTAMPTZ NOT NULL DEFAULT NOW())""")


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
        nome = str(a.get("nome") or "Assieme")[:120]
        with _LOCK:
            r = M.monta(a, d.get("montaggi") or [], officina=leggi_officina())
            modelli = [(nome, M.esporta_glb(r["solidi"])), (nome + " (esploso)", M.esporta_glb(r["solidi"], esploso=True))]
            # un modello per passo: i pezzi già montati e, in arancio, quelli che si aggiungono in quel passo
            ist, visibili, passo_glb = r["istruzioni"], set(), []
            for p in ist["passi"]:
                nuovi = {x for x in p["nuovi"] if x in r["solidi"]}
                if p is ist["passi"][-1]:
                    nuovi |= set(r["solidi"]) - visibili
                if nuovi or not passo_glb:
                    visibili |= nuovi
                    modelli.append(("%s · passo %d" % (nome, p["n"]), M.esporta_glb({k: v for k, v in r["solidi"].items() if k in visibili}, evidenzia=nuovi)))
                passo_glb.append(len(modelli) - 1)
        toks = [secrets.token_hex(16) for _ in modelli]
        tok_m = secrets.token_hex(16)
        for p, i in zip(ist["passi"], passo_glb):
            p["glb"] = url_for("ar.modello", token=toks[i])
        with connect() as conn, conn.cursor() as cur:
            cur.executemany("INSERT INTO cad_condivisioni(token, nome, glb) VALUES (%s,%s,%s)", [(t, n, g) for t, (n, g) in zip(toks, modelli)])
            cur.execute("INSERT INTO cad_montaggi(token, nome, dati) VALUES (%s,%s,%s)", (tok_m, nome, Json({"istruzioni": ist, "uid": a.get("uid")})))
        link = request.host_url.rstrip("/") + url_for("ar.vista", token=toks[0])
        link_m = request.host_url.rstrip("/") + url_for("assiemi.guida", token=tok_m)
        comps = [{k: v for k, v in c.items()} for c in r["componenti"]]
        return jsonify(verifiche=r["verifiche"], distinta=r["distinta"], componenti=comps, istruzioni=ist,
                       commerciali=[{"id": c["id"], "tipo": c["tipo"], "nome": c["nome"]} for c in r["commerciali"]],
                       glb=url_for("ar.modello", token=toks[0]), glb_esploso=url_for("ar.modello", token=toks[1]), link_ar=link, qr=qr_svg(link), giorni=GIORNI,
                       montaggio={"token": tok_m, "link": link_m, "qr": qr_svg(link_m)})
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


# ── montaggio guidato: pagina per il telefono del montatore (link segreto, senza login, come la vista AR) ──
def _montaggio(token):
    if len(token) != 32 or any(c not in "0123456789abcdef" for c in token):
        abort(404)
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT nome, dati, conferme FROM cad_montaggi WHERE token=%s", (token,))
        r = cur.fetchone()
    if not r:
        abort(404)
    return r


@bp.get("/assiemi/m/<token>")
def guida(token):
    nome, _, _ = _montaggio(token)
    return render_template("assiemi/guida.html", nome=nome, token=token)


@bp.get("/assiemi/m/<token>/dati")
def guida_dati(token):
    nome, dati, conferme = _montaggio(token)
    return jsonify(nome=nome, istruzioni=dati.get("istruzioni"), conferme=conferme)


@bp.post("/assiemi/m/<token>/conferma")
def guida_conferma(token):
    nome, dati, conferme = _montaggio(token)
    d = request.get_json(silent=True) or {}
    try:
        n = int(d.get("passo"))
    except (TypeError, ValueError):
        return jsonify(error="Passo non valido"), 400
    passi = (dati.get("istruzioni") or {}).get("passi") or []
    if not 1 <= n <= len(passi):
        return jsonify(error="Passo non valido"), 400
    operatore = str(d.get("operatore") or "").strip()[:60]
    if not operatore:
        return jsonify(error="Scrivi il tuo nome"), 400
    if len(conferme) >= 500:
        return jsonify(error="Troppe conferme su questo montaggio"), 400
    c = {"passo": n, "operatore": operatore, "esito": "problema" if d.get("esito") == "problema" else "ok",
         "nota": str(d.get("nota") or "").strip()[:300], "quando": datetime.datetime.now().isoformat(timespec="seconds")}
    with connect() as conn, conn.cursor() as cur:
        cur.execute("UPDATE cad_montaggi SET conferme = conferme || %s::jsonb WHERE token=%s RETURNING conferme", (Json([c]), token))
        conferme = cur.fetchone()[0]
    return jsonify(ok=True, conferme=conferme)


@bp.get("/api/assiemi/montaggio/<token>")
def avanzamento(token):
    nome, dati, conferme = _montaggio(token)
    return jsonify(nome=nome, passi=len(((dati.get("istruzioni") or {}).get("passi") or [])), conferme=conferme)
