"""Utenti con nome e password personali (oltre alla password del servizio, che resta l'accesso dell'amministratore).

- password salvate solo come hash (werkzeug, scrypt/pbkdf2), mai in chiaro;
- password temporanea generata dal programma e mostrata una volta: al primo accesso l'utente la deve cambiare;
- ruoli: «admin» (gestisce utenti e segnalazioni) e «tecnico» (usa tutto il CAD e manda segnalazioni);
- utenti iniziali: inseriti alla partenza se non esistono (solo l'hash della password temporanea).
"""
import secrets
import string
import time
from zoneinfo import ZoneInfo

from flask import Blueprint, jsonify, redirect, render_template, request, session
from werkzeug.security import check_password_hash, generate_password_hash

from ..postgres_store import connect

bp = Blueprint("utenti", __name__, template_folder="templates", static_folder="static", static_url_path="/utenti/static")

RUOLI = ("admin", "tecnico")
# Luca: tecnico, primo accesso con password temporanea (qui solo l'hash pbkdf2 da 600.000 iterazioni), da cambiare subito
UTENTI_INIZIALI = [
    ("luca", "Luca", "tecnico",
     "pbkdf2:sha256:600000$zabVP2dmIDxMBzO4$cc8918b49af491c8e82743d1b075b3f420e44799952ac451f339a22f2260a57d"),
]
ALFABETO = "".join(c for c in string.ascii_letters + string.digits if c not in "Il1O0o")
TENTATIVI, FINESTRA = 8, 600          # tentativi sbagliati ammessi per indirizzo in 10 minuti
_errori = {}


def password_temporanea():
    """Tre gruppi da cinque caratteri (≈ 84 bit), senza lettere che si confondono (I l 1 O 0 o)."""
    while True:
        pw = "-".join("".join(secrets.choice(ALFABETO) for _ in range(5)) for _ in range(3))
        if any(c.isdigit() for c in pw) and pw.lower() != pw and pw.upper() != pw:
            return pw


def valida_password(p):
    if len(p) < 10:
        raise ValueError("La password deve avere almeno 10 caratteri")
    if p.lower() == p or p.upper() == p or not any(c.isdigit() for c in p):
        raise ValueError("Usa maiuscole, minuscole e almeno un numero")
    if len(p) > 200:
        raise ValueError("Password troppo lunga")


def init_db():
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""CREATE TABLE IF NOT EXISTS cad_utenti (username TEXT PRIMARY KEY, nome TEXT NOT NULL, ruolo TEXT NOT NULL,
                       hash TEXT NOT NULL, deve_cambiare BOOLEAN NOT NULL DEFAULT TRUE, attivo BOOLEAN NOT NULL DEFAULT TRUE,
                       creato TIMESTAMPTZ NOT NULL DEFAULT NOW(), ultimo_accesso TIMESTAMPTZ)""")
        for u, nome, ruolo, h in UTENTI_INIZIALI:
            cur.execute("INSERT INTO cad_utenti(username, nome, ruolo, hash, deve_cambiare) VALUES (%s,%s,%s,%s,TRUE) ON CONFLICT (username) DO NOTHING",
                        (u, nome, ruolo, h))


def bloccato(ip):
    ora = time.time()
    lista = [t for t in _errori.get(ip, []) if ora - t < FINESTRA]
    _errori[ip] = lista
    return len(lista) >= TENTATIVI


def errore(ip):
    _errori.setdefault(ip, []).append(time.time())


def verifica(username, password):
    """L'utente se nome e password sono giusti e l'utente è attivo, altrimenti None."""
    username = (username or "").strip().lower()[:40]
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT username, nome, ruolo, hash, deve_cambiare, attivo FROM cad_utenti WHERE username=%s", (username,))
        r = cur.fetchone()
        if not r or not r[5] or not check_password_hash(r[3], password or ""):
            return None
        cur.execute("UPDATE cad_utenti SET ultimo_accesso=NOW() WHERE username=%s", (username,))
    return {"username": r[0], "nome": r[1], "ruolo": r[2], "deve_cambiare": r[4]}


def utente():
    return session.get("utente") or {}


def admin():
    return session.get("ok") and utente().get("ruolo") == "admin"


@bp.route("/cambia-password", methods=["GET", "POST"])
def cambia_password():
    u = utente()
    if not session.get("ok") or not u.get("username") or u.get("username") == "admin":
        return redirect("/")
    if request.method == "GET":
        return render_template("utenti/cambia.html", u=u, csrf=session.get("csrf", ""), errore=None)
    attuale, nuova, ripeti = (request.form.get(k, "") for k in ("attuale", "nuova", "ripeti"))
    err = None
    try:
        if not verifica(u["username"], attuale):
            raise ValueError("La password attuale non è giusta")
        if nuova != ripeti:
            raise ValueError("Le due password nuove non coincidono")
        if nuova == attuale:
            raise ValueError("La nuova password deve essere diversa")
        valida_password(nuova)
    except ValueError as e:
        err = str(e)
    if err:
        return render_template("utenti/cambia.html", u=u, csrf=session.get("csrf", ""), errore=err), 400
    with connect() as conn, conn.cursor() as cur:
        cur.execute("UPDATE cad_utenti SET hash=%s, deve_cambiare=FALSE WHERE username=%s", (generate_password_hash(nuova), u["username"]))
    session["utente"] = dict(u, deve_cambiare=False)
    return redirect("/?benvenuto=1")


@bp.get("/utenti")
def pagina():
    if not admin():
        return redirect("/")
    return render_template("utenti/utenti.html", csrf=session.get("csrf", ""))


@bp.get("/api/utenti")
def elenco():
    if not admin():
        return jsonify(error="Riservato all'amministratore"), 403
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT username, nome, ruolo, deve_cambiare, attivo, creato, ultimo_accesso FROM cad_utenti ORDER BY creato")
        righe = cur.fetchall()
    return jsonify([{"username": r[0], "nome": r[1], "ruolo": r[2], "deve_cambiare": r[3], "attivo": r[4],
                     "creato": r[5].astimezone(ZoneInfo("Europe/Rome")).strftime("%Y-%m-%d %H:%M") if r[5] else None,
                     "ultimo_accesso": r[6].astimezone(ZoneInfo("Europe/Rome")).strftime("%Y-%m-%d %H:%M") if r[6] else None} for r in righe])


@bp.post("/api/utenti")
def crea():
    if not admin():
        return jsonify(error="Riservato all'amministratore"), 403
    d = request.get_json(silent=True) or {}
    username = str(d.get("username") or "").strip().lower()
    nome = str(d.get("nome") or "").strip()[:60]
    ruolo = d.get("ruolo") if d.get("ruolo") in RUOLI else "tecnico"
    if not (3 <= len(username) <= 30) or any(c not in string.ascii_lowercase + string.digits + "._-" for c in username) or username == "admin":
        return jsonify(error="Nome utente: 3–30 caratteri fra lettere minuscole, numeri, punto, trattino"), 400
    if not nome:
        return jsonify(error="Scrivi il nome da mostrare"), 400
    pw = password_temporanea()
    with connect() as conn, conn.cursor() as cur:
        cur.execute("INSERT INTO cad_utenti(username, nome, ruolo, hash) VALUES (%s,%s,%s,%s) ON CONFLICT DO NOTHING RETURNING username",
                    (username, nome, ruolo, generate_password_hash(pw)))
        if not cur.fetchone():
            return jsonify(error="Esiste già un utente «%s»" % username), 400
    return jsonify(username=username, password=pw, nota="Password temporanea: mostrata solo ora. Al primo accesso l'utente la cambia.")


@bp.post("/api/utenti/<username>")
def modifica(username):
    if not admin():
        return jsonify(error="Riservato all'amministratore"), 403
    d = request.get_json(silent=True) or {}
    with connect() as conn, conn.cursor() as cur:
        if d.get("azione") == "reimposta":
            pw = password_temporanea()
            cur.execute("UPDATE cad_utenti SET hash=%s, deve_cambiare=TRUE, attivo=TRUE WHERE username=%s RETURNING username", (generate_password_hash(pw), username))
            if not cur.fetchone():
                return jsonify(error="Utente non trovato"), 404
            return jsonify(username=username, password=pw, nota="Nuova password temporanea: mostrata solo ora.")
        if d.get("azione") in ("disattiva", "attiva"):
            cur.execute("UPDATE cad_utenti SET attivo=%s WHERE username=%s RETURNING username", (d["azione"] == "attiva", username))
            if not cur.fetchone():
                return jsonify(error="Utente non trovato"), 404
            return jsonify(ok=True)
        if d.get("ruolo") in RUOLI:
            cur.execute("UPDATE cad_utenti SET ruolo=%s WHERE username=%s", (d["ruolo"], username))
            return jsonify(ok=True)
    return jsonify(error="Azione non valida"), 400
