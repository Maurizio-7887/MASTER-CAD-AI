"""Versioni del progetto e registro delle decisioni: chi ha deciso cosa, quando e in base a quale norma o calcolo.

Ogni lavorazione ha un identificativo stabile: il confronto fra due versioni dice esattamente cosa è stato aggiunto,
tolto o cambiato (non «righe diverse», ma «sede cuscinetto 6204 → 6205»). Si può tornare a qualsiasi versione.
"""
from flask import Blueprint, abort, jsonify, render_template, request, session
from psycopg2.extras import Json, RealDictCursor

from ..postgres_store import connect

bp = Blueprint("versioni", __name__, template_folder="templates", static_folder="static", static_url_path="/versioni/static")
CAMPI_IGNORATI = {"registro", "nome", "uid"}


def init_db():
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""CREATE TABLE IF NOT EXISTS cad_versioni (
            id SERIAL PRIMARY KEY, uid TEXT NOT NULL, numero INT NOT NULL, nome TEXT NOT NULL, messaggio TEXT NOT NULL,
            autore TEXT NOT NULL, progetto JSONB NOT NULL, differenze JSONB NOT NULL, decisioni JSONB NOT NULL,
            creato TIMESTAMPTZ NOT NULL DEFAULT NOW(), UNIQUE(uid, numero))""")


def _descrivi(l):
    t = l.get("tipo", "?")
    fz = l.get("funzione") or {}
    if fz.get("componente"):
        return "%s %s" % ({"sede_cuscinetto": "Sede cuscinetto", "foro_spina": "Foro spina", "sede_boccola": "Sede boccola",
                           "passaggio_vite": "Passaggio vite", "filetto": "Filetto"}.get(fz.get("tipo"), t), fz["componente"])
    if t == "foro":
        return "Foro %s in (%g; %g)" % (l.get("filetto") or "Ø%g" % float(l.get("d") or 0), float(l.get("x", 0)), float(l.get("y", 0)))
    if t in ("serie_polare", "serie_rett"):
        return "Serie di fori %s" % ((l.get("foro") or {}).get("filetto") or "Ø%g" % float((l.get("foro") or {}).get("d") or 0))
    return t.capitalize()


def differenze(a, b):
    """Cosa cambia da a a b: base, lavorazioni aggiunte, tolte, modificate (per identificativo)."""
    out = []
    if not a:
        return ["Prima versione"]
    ba, bb = a.get("base") or {}, b.get("base") or {}
    if ba.get("tipo") != bb.get("tipo"):
        out.append("Forma di base: %s → %s" % (ba.get("tipo"), bb.get("tipo")))
    elif ba != bb:
        if ba.get("altezza") != bb.get("altezza"):
            out.append("Spessore %s → %s mm" % (ba.get("altezza"), bb.get("altezza")))
        if {k: v for k, v in ba.items() if k != "altezza"} != {k: v for k, v in bb.items() if k != "altezza"}:
            out.append("Contorno di base modificato")
    la = {l.get("id") or "#%d" % i: l for i, l in enumerate(a.get("lavorazioni") or [])}
    lb = {l.get("id") or "#%d" % i: l for i, l in enumerate(b.get("lavorazioni") or [])}
    for k, l in lb.items():
        if k not in la:
            out.append("+ " + _descrivi(l))
        elif {x: y for x, y in l.items() if x not in CAMPI_IGNORATI} != {x: y for x, y in la[k].items() if x not in CAMPI_IGNORATI}:
            prima, dopo = _descrivi(la[k]), _descrivi(l)
            campi = sorted(x for x in set(l) | set(la[k]) if x not in CAMPI_IGNORATI and l.get(x) != la[k].get(x))
            out.append("~ %s%s (%s)" % (prima, " → " + dopo if dopo != prima else "", ", ".join(campi)))
    for k, l in la.items():
        if k not in lb:
            out.append("− " + _descrivi(l))
    return out or ["Nessuna modifica alla geometria"]


@bp.get("/versioni")
def pagina():
    return render_template("versioni/versioni.html", csrf=session.get("csrf", ""))


@bp.get("/api/versioni")
def elenco():
    uid = str(request.args.get("uid") or "")[:40]
    with connect() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""SELECT id, numero, nome, messaggio, autore, differenze, decisioni, to_char(creato,'DD/MM/YYYY HH24:MI') AS creato
                       FROM cad_versioni WHERE uid=%s ORDER BY numero DESC""", (uid,))
        return jsonify(cur.fetchall())


@bp.get("/api/versioni/progetti")
def progetti():
    with connect() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("""SELECT DISTINCT ON (uid) uid, nome, numero, autore, to_char(creato,'DD/MM/YYYY HH24:MI') AS creato
                       FROM cad_versioni ORDER BY uid, numero DESC""")
        righe = sorted(cur.fetchall(), key=lambda r: r["creato"], reverse=True)
    return jsonify(righe[:100])


@bp.get("/api/versioni/<int:vid>")
def leggi(vid):
    with connect() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT id, uid, numero, nome, progetto FROM cad_versioni WHERE id=%s", (vid,))
        r = cur.fetchone()
    if not r:
        abort(404)
    return jsonify(r)


@bp.post("/api/versioni")
def salva():
    d = request.get_json(silent=True)
    if not isinstance(d, dict) or not isinstance(d.get("progetto"), dict) or not d["progetto"].get("base"):
        return jsonify(error="Prima costruisci il pezzo"), 400
    p = d["progetto"]
    uid = str(p.get("uid") or "")[:40]
    if len(uid) < 6:
        return jsonify(error="Progetto senza identificativo: ricostruiscilo nel CAD"), 400
    messaggio = " ".join(str(d.get("messaggio") or "").split())[:300]
    if not messaggio:
        return jsonify(error="Scrivi in una riga cosa è cambiato (es. «sede 6204 → 6205 per carico maggiore»)"), 400
    autore = " ".join(str(d.get("autore") or "").split())[:60] or ("Allievo " + session["allievo"]["nome"] if session.get("allievo") else "Ufficio tecnico")
    with connect() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute("SELECT numero, progetto, decisioni FROM cad_versioni WHERE uid=%s ORDER BY numero DESC LIMIT 1", (uid,))
        prec = cur.fetchone()
        reg = [x for x in (p.get("registro") or []) if isinstance(x, dict)][-500:]
        gia = len(prec["progetto"].get("registro") or []) if prec else 0
        nuove = reg[gia:]
        diff = differenze(prec["progetto"] if prec else None, p)
        numero = (prec["numero"] + 1) if prec else 1
        cur.execute("""INSERT INTO cad_versioni(uid, numero, nome, messaggio, autore, progetto, differenze, decisioni)
                       VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
                    (uid, numero, str(p.get("nome") or "Pezzo")[:120], messaggio, autore, Json(p), Json(diff), Json(nuove)))
        vid = cur.fetchone()["id"]
    return jsonify(id=vid, numero=numero, differenze=diff, decisioni=nuove)
