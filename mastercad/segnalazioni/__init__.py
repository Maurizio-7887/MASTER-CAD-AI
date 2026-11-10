"""Segnalazioni: chi usa il programma (Luca in officina) dice cosa manca, cosa non va, cosa non si capisce.

Da ogni pagina il bottone «💡 Suggerisci» apre un modulo: tipo, testo, pagina in cui si trovava, a scelta il pezzo aperto
(per riprodurre il caso) e una foto o schermata. L'amministratore le vede tutte, cambia lo stato e risponde; chi le ha
scritte vede le sue con la risposta. «Scarica per lo sviluppo» dà un JSON da passare a chi sviluppa.
"""
import json
from zoneinfo import ZoneInfo

from flask import Blueprint, Response, jsonify, redirect, render_template, request, session
from psycopg2.extras import Json

from ..postgres_store import connect

bp = Blueprint("segnalazioni", __name__, template_folder="templates", static_folder="static", static_url_path="/segnalazioni/static")

TIPI = {"idea": "Idea / funzione che manca", "errore": "Qualcosa non funziona", "calcolo": "Calcolo o norma da correggere", "domanda": "Non si capisce come fare"}
STATI = ("nuova", "in lavorazione", "fatta", "scartata")
MAX_IMG = 3_000_000


def init_db():
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""CREATE TABLE IF NOT EXISTS cad_segnalazioni (id SERIAL PRIMARY KEY, utente TEXT NOT NULL, nome TEXT NOT NULL,
                       tipo TEXT NOT NULL, pagina TEXT, testo TEXT NOT NULL, progetto JSONB, immagine BYTEA, immagine_tipo TEXT,
                       stato TEXT NOT NULL DEFAULT 'nuova', risposta TEXT, creato TIMESTAMPTZ NOT NULL DEFAULT NOW(),
                       aggiornato TIMESTAMPTZ NOT NULL DEFAULT NOW())""")


def _io():
    u = session.get("utente") or {}
    return u.get("username") or "admin", u.get("nome") or "Amministratore", u.get("ruolo") == "admin"


def _ora(t):
    return t.astimezone(ZoneInfo("Europe/Rome")).strftime("%Y-%m-%d %H:%M")


def _riga(r, completo=False):
    d = {"id": r[0], "utente": r[1], "nome": r[2], "tipo": r[3], "tipo_testo": TIPI.get(r[3], r[3]), "pagina": r[4], "testo": r[5],
         "ha_progetto": r[6] is not None, "ha_immagine": r[7], "stato": r[8], "risposta": r[9],
         "creato": _ora(r[10]), "aggiornato": _ora(r[11])}
    if completo:
        d["progetto"] = r[6]
    return d


COLONNE = "id, utente, nome, tipo, pagina, testo, progetto, immagine IS NOT NULL, stato, risposta, creato, aggiornato"


@bp.get("/segnalazioni")
def pagina():
    if not session.get("ok"):
        return redirect("/login")
    _, nome, adm = _io()
    return render_template("segnalazioni/segnalazioni.html", csrf=session.get("csrf", ""), admin=adm, tipi=TIPI, stati=STATI)


@bp.post("/api/segnalazioni")
def crea():
    if not session.get("ok"):
        return jsonify(error="Accesso richiesto"), 401
    f = request.form
    tipo = f.get("tipo") if f.get("tipo") in TIPI else "idea"
    testo = (f.get("testo") or "").strip()
    if len(testo) < 5:
        return jsonify(error="Scrivi almeno una frase"), 400
    progetto = None
    if f.get("progetto"):
        try:
            progetto = json.loads(f["progetto"])
            if not isinstance(progetto, dict) or len(f["progetto"]) > 1_500_000:
                progetto = None
        except ValueError:
            progetto = None
    img, img_tipo = None, None
    fi = request.files.get("immagine")
    if fi and fi.filename:
        img = fi.read(MAX_IMG + 1)
        if len(img) > MAX_IMG:
            return jsonify(error="Immagine troppo grande (max 3 MB)"), 400
        if img[:8] == b"\x89PNG\r\n\x1a\n":
            img_tipo = "image/png"
        elif img[:3] == b"\xff\xd8\xff":
            img_tipo = "image/jpeg"
        else:
            return jsonify(error="Immagine: solo PNG o JPEG"), 400
    u, nome, _ = _io()
    with connect() as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO cad_segnalazioni(utente, nome, tipo, pagina, testo, progetto, immagine, immagine_tipo) VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id",
                    (u, nome, tipo, (f.get("pagina") or "")[:200], testo[:5000], Json(progetto) if progetto else None, img, img_tipo))
        n = cur.fetchone()[0]
    return jsonify(ok=True, id=n, messaggio="Grazie! Segnalazione n. %d registrata." % n)


@bp.get("/api/segnalazioni")
def elenco():
    if not session.get("ok"):
        return jsonify(error="Accesso richiesto"), 401
    u, _, adm = _io()
    with connect() as conn, conn.cursor() as cur:
        if adm:
            cur.execute("SELECT %s FROM cad_segnalazioni ORDER BY id DESC LIMIT 500" % COLONNE)
        else:
            cur.execute("SELECT %s FROM cad_segnalazioni WHERE utente=%%s ORDER BY id DESC LIMIT 500" % COLONNE, (u,))
        righe = cur.fetchall()
    return jsonify([_riga(r) for r in righe])


def _mia_o_admin(cur, n):
    u, _, adm = _io()
    cur.execute("SELECT %s FROM cad_segnalazioni WHERE id=%%s" % COLONNE, (n,))
    r = cur.fetchone()
    if not r or (not adm and r[1] != u):
        return None
    return r


@bp.get("/api/segnalazioni/<int:n>")
def dettaglio(n):
    with connect() as conn, conn.cursor() as cur:
        r = _mia_o_admin(cur, n)
    if not r:
        return jsonify(error="Segnalazione non trovata"), 404
    return jsonify(_riga(r, completo=True))


@bp.get("/api/segnalazioni/<int:n>/immagine")
def immagine(n):
    with connect() as conn, conn.cursor() as cur:
        if not _mia_o_admin(cur, n):
            return jsonify(error="Segnalazione non trovata"), 404
        cur.execute("SELECT immagine, immagine_tipo FROM cad_segnalazioni WHERE id=%s", (n,))
        img, tipo = cur.fetchone()
    if not img:
        return jsonify(error="Nessuna immagine"), 404
    return Response(bytes(img), mimetype=tipo)


@bp.post("/api/segnalazioni/<int:n>")
def aggiorna(n):
    _, _, adm = _io()
    if not adm:
        return jsonify(error="Riservato all'amministratore"), 403
    d = request.get_json(silent=True) or {}
    stato = d.get("stato") if d.get("stato") in STATI else None
    risposta = str(d.get("risposta") or "").strip()[:3000]
    with connect() as conn, conn.cursor() as cur:
        cur.execute("UPDATE cad_segnalazioni SET stato=COALESCE(%s, stato), risposta=%s, aggiornato=NOW() WHERE id=%s RETURNING id",
                    (stato, risposta or None, n))
        if not cur.fetchone():
            return jsonify(error="Segnalazione non trovata"), 404
    return jsonify(ok=True)


@bp.get("/api/segnalazioni/esporta")
def esporta():
    _, _, adm = _io()
    if not adm:
        return jsonify(error="Riservato all'amministratore"), 403
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT %s FROM cad_segnalazioni WHERE stato IN ('nuova','in lavorazione') ORDER BY id" % COLONNE)
        righe = [_riga(r, completo=True) for r in cur.fetchall()]
    corpo = json.dumps({"programma": "MASTER CAD AI", "segnalazioni_aperte": righe}, ensure_ascii=False, indent=1)
    return Response(corpo, mimetype="application/json", headers={"Content-Disposition": "attachment; filename=segnalazioni-aperte.json"})
