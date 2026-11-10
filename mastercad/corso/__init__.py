"""Modalità corso: esercizi «dalla foto al pezzo», accesso allievi, diario delle azioni, correzione automatica
e pannello docente (chi ha lavorato, quanto tempo, cosa ha fatto, voti da confermare o correggere)."""
import datetime
import secrets
import threading

from flask import Blueprint, Response, abort, current_app, jsonify, redirect, render_template, request, session
from psycopg2.extras import Json, RealDictCursor
from werkzeug.security import check_password_hash, generate_password_hash

from ..postgres_store import connect
from ..progetto import lavorazioni as L
from .valuta import valuta

bp = Blueprint("corso", __name__, template_folder="templates", static_folder="static", static_url_path="/corso/static")
_LOCK = threading.Lock()
PAUSA_MAX = 300          # secondi: oltre questa pausa fra due azioni il tempo non conta come lavoro
FOTO_MAX = 8_000_000


def init_db():
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""CREATE TABLE IF NOT EXISTS cad_corsi (
            id SERIAL PRIMARY KEY, nome TEXT NOT NULL, codice TEXT UNIQUE NOT NULL, attivo BOOLEAN NOT NULL DEFAULT TRUE,
            creato TIMESTAMPTZ NOT NULL DEFAULT NOW())""")
        cur.execute("""CREATE TABLE IF NOT EXISTS cad_esercizi (
            id SERIAL PRIMARY KEY, corso_id INT NOT NULL REFERENCES cad_corsi(id) ON DELETE CASCADE, titolo TEXT NOT NULL,
            consegna TEXT NOT NULL DEFAULT '', indicazioni TEXT NOT NULL DEFAULT '', foto BYTEA, foto_tipo TEXT,
            riferimento JSONB, materiale TEXT, attivo BOOLEAN NOT NULL DEFAULT TRUE, creato TIMESTAMPTZ NOT NULL DEFAULT NOW())""")
        cur.execute("""CREATE TABLE IF NOT EXISTS cad_allievi (
            id SERIAL PRIMARY KEY, corso_id INT NOT NULL REFERENCES cad_corsi(id) ON DELETE CASCADE, nome TEXT NOT NULL,
            pin TEXT NOT NULL, ultimo_progetto JSONB, ultimo_accesso TIMESTAMPTZ, creato TIMESTAMPTZ NOT NULL DEFAULT NOW())""")
        cur.execute("CREATE UNIQUE INDEX IF NOT EXISTS cad_allievi_nome_idx ON cad_allievi(corso_id, lower(nome))")
        cur.execute("""CREATE TABLE IF NOT EXISTS cad_azioni (
            id BIGSERIAL PRIMARY KEY, allievo_id INT NOT NULL REFERENCES cad_allievi(id) ON DELETE CASCADE, esercizio_id INT,
            tipo TEXT NOT NULL, dettaglio TEXT NOT NULL DEFAULT '', ts TIMESTAMPTZ NOT NULL DEFAULT NOW())""")
        cur.execute("CREATE INDEX IF NOT EXISTS cad_azioni_allievo_idx ON cad_azioni(allievo_id, ts)")
        cur.execute("""CREATE TABLE IF NOT EXISTS cad_consegne (
            id SERIAL PRIMARY KEY, allievo_id INT NOT NULL REFERENCES cad_allievi(id) ON DELETE CASCADE,
            esercizio_id INT NOT NULL REFERENCES cad_esercizi(id) ON DELETE CASCADE, progetto JSONB NOT NULL, esito JSONB NOT NULL,
            voto_auto NUMERIC(4,1) NOT NULL, voto_docente NUMERIC(4,1), commento TEXT NOT NULL DEFAULT '',
            creato TIMESTAMPTZ NOT NULL DEFAULT NOW(), corretto TIMESTAMPTZ)""")


def _q(sql, args=(), uno=False, scrivi=False):
    with connect() as conn, conn.cursor(cursor_factory=RealDictCursor) as cur:
        cur.execute(sql, args)
        if scrivi and cur.description is None:
            return None
        return cur.fetchone() if uno else cur.fetchall()


def _json():
    d = request.get_json(silent=True)
    if not isinstance(d, dict):
        raise ValueError("JSON non valido")
    return d


def _docente():
    if not session.get("ok"):
        abort(403)


def _allievo():
    a = session.get("allievo")
    if not a:
        abort(403)
    return a


def tempo_lavorato(tempi):
    """Somma delle pause fra azioni consecutive, contando solo quelle sotto i 5 minuti (+30 s per l'ultima azione)."""
    if not tempi:
        return 0
    tot = 0.0
    for a, b in zip(tempi, tempi[1:]):
        d = (b - a).total_seconds()
        tot += d if d <= PAUSA_MAX else 30
    return int(tot + 30)


def _durata(sec):
    if sec < 60:
        return "%d s" % sec if sec else "—"
    h, m = divmod(int(sec) // 60, 60)
    return ("%d h %02d min" % (h, m)) if h else ("%d min" % m)


# ── accesso allievi ──
@bp.route("/corso/entra", methods=["GET", "POST"])
def entra():
    if request.method == "GET":
        return render_template("corso/entra.html", errore=None, csrf_entra=_csrf_entra())
    if not secrets.compare_digest(request.form.get("csrf", ""), session.get("csrf_entra", "-")):
        return render_template("corso/entra.html", errore="Pagina scaduta: riprova", csrf_entra=_csrf_entra()), 400
    codice = request.form.get("codice", "").strip().upper()
    nome = " ".join(request.form.get("nome", "").split())[:80]
    pin = request.form.get("pin", "").strip()
    errore = None
    if len(nome) < 3 or not pin.isdigit() or not 4 <= len(pin) <= 8:
        errore = "Scrivi nome e cognome e un PIN di 4–8 cifre"
    corso = None if errore else _q("SELECT id, nome FROM cad_corsi WHERE codice=%s AND attivo", (codice,), uno=True)
    if not errore and not corso:
        errore = "Codice del corso non trovato: chiedilo al docente"
    if not errore:
        a = _q("SELECT id, nome, pin FROM cad_allievi WHERE corso_id=%s AND lower(nome)=lower(%s)", (corso["id"], nome), uno=True)
        if a is None:
            a = _q("INSERT INTO cad_allievi(corso_id, nome, pin) VALUES (%s,%s,%s) RETURNING id, nome",
                   (corso["id"], nome, generate_password_hash(pin)), uno=True)
        elif not check_password_hash(a["pin"], pin):
            session["tentativi"] = session.get("tentativi", 0) + 1
            errore = "PIN sbagliato. Se l'hai dimenticato, il docente può azzerarlo."
        if not errore:
            session.clear()
            session.permanent = True
            session["allievo"] = {"id": a["id"], "nome": a["nome"], "corso_id": corso["id"], "corso": corso["nome"]}
            session["csrf"] = secrets.token_urlsafe(32)
            _q("UPDATE cad_allievi SET ultimo_accesso=NOW() WHERE id=%s", (a["id"],), scrivi=True)
            _q("INSERT INTO cad_azioni(allievo_id, tipo, dettaglio) VALUES (%s,'accesso','Entrato nel corso')", (a["id"],), scrivi=True)
            return redirect("/")
    return render_template("corso/entra.html", errore=errore, csrf_entra=_csrf_entra()), 400


def _csrf_entra():
    session["csrf_entra"] = session.get("csrf_entra") or secrets.token_urlsafe(24)
    return session["csrf_entra"]


# ── pagine allievo ──
@bp.get("/corso/allievo")
def allievo_home():
    a = _allievo()
    return render_template("corso/allievo.html", csrf=session.get("csrf", ""), allievo=a)


@bp.get("/api/corso/allievo/esercizi")
def allievo_esercizi():
    a = _allievo()
    righe = _q("""SELECT e.id, e.titolo, e.consegna, e.indicazioni, e.materiale, (e.foto IS NOT NULL) AS ha_foto,
                  c.voto_auto, c.voto_docente, c.commento, c.creato AS consegnato, c.esito
                  FROM cad_esercizi e
                  LEFT JOIN LATERAL (SELECT * FROM cad_consegne x WHERE x.esercizio_id=e.id AND x.allievo_id=%s ORDER BY creato DESC LIMIT 1) c ON TRUE
                  WHERE e.corso_id=%s AND e.attivo ORDER BY e.id""", (a["id"], a["corso_id"]))
    for r in righe:
        r["consegnato"] = r["consegnato"].strftime("%d/%m %H:%M") if r["consegnato"] else None
        for k in ("voto_auto", "voto_docente"):
            r[k] = float(r[k]) if r[k] is not None else None
    return jsonify(allievo=a, esercizi=righe)


@bp.get("/corso/esercizio/<int:eid>/foto")
def foto_esercizio(eid):
    a, docente = session.get("allievo"), session.get("ok")
    if not a and not docente:
        abort(403)
    r = _q("SELECT corso_id, foto, foto_tipo FROM cad_esercizi WHERE id=%s", (eid,), uno=True)
    if not r or not r["foto"] or (a and r["corso_id"] != a["corso_id"]):
        abort(404)
    return Response(bytes(r["foto"]), mimetype=r["foto_tipo"] or "image/jpeg")


@bp.post("/api/corso/allievo/azioni")
def allievo_azioni():
    a = _allievo()
    try:
        d = _json()
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    azioni = d.get("azioni") or []
    if not isinstance(azioni, list):
        return jsonify(error="azioni non valide"), 400
    eid = d.get("esercizio_id")
    eid = int(eid) if str(eid or "").isdigit() else None
    adesso = datetime.datetime.now(datetime.timezone.utc)
    with connect() as conn, conn.cursor() as cur:
        for az in azioni[:200]:
            if not isinstance(az, dict):
                continue
            ts = adesso
            try:        # orario del browser, accettato solo se plausibile (±10 minuti)
                t = datetime.datetime.fromtimestamp(float(az.get("t")) / 1000, datetime.timezone.utc)
                if abs((t - adesso).total_seconds()) < 600:
                    ts = t
            except (TypeError, ValueError, OverflowError):
                pass
            cur.execute("INSERT INTO cad_azioni(allievo_id, esercizio_id, tipo, dettaglio, ts) VALUES (%s,%s,%s,%s,%s)",
                        (a["id"], eid, str(az.get("tipo") or "?")[:30], str(az.get("dettaglio") or "")[:300], ts))
        prog = d.get("progetto")
        if isinstance(prog, dict) and prog.get("base"):
            cur.execute("UPDATE cad_allievi SET ultimo_progetto=%s, ultimo_accesso=NOW() WHERE id=%s", (Json(prog), a["id"]))
        else:
            cur.execute("UPDATE cad_allievi SET ultimo_accesso=NOW() WHERE id=%s", (a["id"],))
    return jsonify(ok=True)


@bp.post("/api/corso/allievo/consegna")
def allievo_consegna():
    a = _allievo()
    try:
        d = _json()
        eid = int(d.get("esercizio_id"))
        prog = d.get("progetto")
        if not isinstance(prog, dict) or not prog.get("base"):
            raise ValueError("Prima costruisci il pezzo nella pagina Disegno")
        es = _q("SELECT id, riferimento FROM cad_esercizi WHERE id=%s AND corso_id=%s AND attivo", (eid, a["corso_id"]), uno=True)
        if not es:
            raise ValueError("Esercizio non trovato")
        with _LOCK:
            if es["riferimento"]:
                esito = valuta(es["riferimento"], prog)
            else:
                L.costruisci(prog)
                esito = {"voto": None, "punteggi": {}, "messaggi": ["Consegna ricevuta: la correggerà il docente."]}
        voto = esito["voto"] if esito["voto"] is not None else 0
        r = _q("""INSERT INTO cad_consegne(allievo_id, esercizio_id, progetto, esito, voto_auto) VALUES (%s,%s,%s,%s,%s)
                  RETURNING id, creato""", (a["id"], eid, Json(prog), Json(esito), voto), uno=True)
        _q("INSERT INTO cad_azioni(allievo_id, esercizio_id, tipo, dettaglio) VALUES (%s,%s,'consegna',%s)",
           (a["id"], eid, "Consegnato: voto automatico %s" % (esito["voto"] if esito["voto"] is not None else "—")), scrivi=True)
        return jsonify(id=r["id"], esito=esito)
    except (ValueError, TypeError, KeyError) as exc:
        return jsonify(error=str(exc)[:400]), 400
    except Exception:
        current_app.logger.exception("Errore consegna")
        return jsonify(error="Consegna non riuscita: ricostruisci il pezzo e riprova"), 500


# ── pannello docente ──
@bp.get("/corso/docente")
def docente():
    _docente()
    return render_template("corso/docente.html", csrf=session.get("csrf", ""))


@bp.get("/api/corso/docente/corsi")
def corsi():
    _docente()
    righe = _q("""SELECT c.id, c.nome, c.codice, c.attivo, to_char(c.creato,'DD/MM/YYYY') AS creato,
                  (SELECT count(*) FROM cad_allievi a WHERE a.corso_id=c.id) AS allievi,
                  (SELECT count(*) FROM cad_esercizi e WHERE e.corso_id=c.id AND e.attivo) AS esercizi,
                  (SELECT count(*) FROM cad_consegne k JOIN cad_allievi a ON a.id=k.allievo_id WHERE a.corso_id=c.id AND k.voto_docente IS NULL) AS da_correggere
                  FROM cad_corsi c ORDER BY c.creato DESC""")
    return jsonify(righe)


@bp.post("/api/corso/docente/corsi")
def nuovo_corso():
    _docente()
    try:
        nome = " ".join(str(_json().get("nome") or "").split())[:100]
        if len(nome) < 3:
            raise ValueError("Scrivi il nome del corso")
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    alfabeto = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
    for _ in range(10):
        codice = "CAD-" + "".join(secrets.choice(alfabeto) for _ in range(4))
        if not _q("SELECT 1 FROM cad_corsi WHERE codice=%s", (codice,), uno=True):
            break
    r = _q("INSERT INTO cad_corsi(nome, codice) VALUES (%s,%s) RETURNING id, codice", (nome, codice), uno=True)
    return jsonify(r)


@bp.post("/api/corso/docente/esercizi")
def nuovo_esercizio():
    _docente()
    try:
        cid = int(request.form.get("corso_id") or 0)
        titolo = " ".join((request.form.get("titolo") or "").split())[:150]
        if not titolo:
            raise ValueError("Scrivi il titolo dell'esercizio")
        if not _q("SELECT 1 FROM cad_corsi WHERE id=%s", (cid,), uno=True):
            raise ValueError("Corso non trovato")
        import json
        rif = json.loads(request.form.get("riferimento") or "null")
        if rif is not None:
            if not isinstance(rif, dict) or not rif.get("base"):
                raise ValueError("Soluzione non valida")
            with _LOCK:
                L.costruisci(rif)
        f = request.files.get("foto")
        foto, tipo = (None, None)
        if f is not None and f.filename:
            foto = f.read(FOTO_MAX + 1)
            if len(foto) > FOTO_MAX:
                raise ValueError("Foto troppo grande (massimo 8 MB)")
            tipo = f.mimetype if f.mimetype in ("image/jpeg", "image/png", "image/webp") else "image/jpeg"
        r = _q("""INSERT INTO cad_esercizi(corso_id, titolo, consegna, indicazioni, foto, foto_tipo, riferimento, materiale)
                  VALUES (%s,%s,%s,%s,%s,%s,%s,%s) RETURNING id""",
               (cid, titolo, (request.form.get("consegna") or "")[:4000], (request.form.get("indicazioni") or "")[:4000],
                foto, tipo, Json(rif) if rif else None, (request.form.get("materiale") or "")[:20]), uno=True)
        return jsonify(r)
    except (ValueError, TypeError) as exc:
        return jsonify(error=str(exc)[:400]), 400


@bp.get("/api/corso/docente/corso/<int:cid>")
def dettaglio_corso(cid):
    _docente()
    corso = _q("SELECT id, nome, codice, attivo FROM cad_corsi WHERE id=%s", (cid,), uno=True)
    if not corso:
        abort(404)
    esercizi = _q("""SELECT id, titolo, consegna, indicazioni, materiale, attivo, (foto IS NOT NULL) AS ha_foto, (riferimento IS NOT NULL) AS ha_soluzione,
                     (SELECT count(*) FROM cad_consegne k WHERE k.esercizio_id=e.id) AS consegne
                     FROM cad_esercizi e WHERE corso_id=%s ORDER BY id""", (cid,))
    allievi = _q("""SELECT a.id, a.nome, a.ultimo_accesso, (a.ultimo_progetto IS NOT NULL) AS ha_lavoro,
                    (SELECT count(*) FROM cad_azioni z WHERE z.allievo_id=a.id) AS azioni,
                    (SELECT count(*) FROM cad_consegne k WHERE k.allievo_id=a.id) AS consegne,
                    (SELECT round(avg(coalesce(k.voto_docente, k.voto_auto)),1) FROM cad_consegne k WHERE k.allievo_id=a.id) AS media
                    FROM cad_allievi a WHERE a.corso_id=%s ORDER BY lower(a.nome)""", (cid,))
    tempi = _q("""SELECT allievo_id, ts FROM cad_azioni WHERE allievo_id IN (SELECT id FROM cad_allievi WHERE corso_id=%s) ORDER BY allievo_id, ts""", (cid,))
    per = {}
    for t in tempi:
        per.setdefault(t["allievo_id"], []).append(t["ts"])
    for a in allievi:
        sec = tempo_lavorato(per.get(a["id"], []))
        a["tempo"] = _durata(sec)
        a["tempo_sec"] = sec
        a["ultimo_accesso"] = a["ultimo_accesso"].strftime("%d/%m %H:%M") if a["ultimo_accesso"] else "mai"
        a["media"] = float(a["media"]) if a["media"] is not None else None
    return jsonify(corso=corso, esercizi=esercizi, allievi=allievi)


@bp.get("/api/corso/docente/allievo/<int:aid>")
def dettaglio_allievo(aid):
    _docente()
    a = _q("SELECT id, nome, corso_id, ultimo_progetto FROM cad_allievi WHERE id=%s", (aid,), uno=True)
    if not a:
        abort(404)
    azioni = _q("""SELECT z.tipo, z.dettaglio, z.ts, e.titolo FROM cad_azioni z LEFT JOIN cad_esercizi e ON e.id=z.esercizio_id
                   WHERE z.allievo_id=%s ORDER BY z.ts DESC LIMIT 400""", (aid,))
    consegne = _q("""SELECT k.id, k.esercizio_id, e.titolo, k.voto_auto, k.voto_docente, k.commento, k.esito, k.creato, k.progetto
                     FROM cad_consegne k JOIN cad_esercizi e ON e.id=k.esercizio_id WHERE k.allievo_id=%s ORDER BY k.creato DESC""", (aid,))
    tutti = [z["ts"] for z in reversed(azioni)]
    for z in azioni:
        z["ts"] = z["ts"].strftime("%d/%m %H:%M:%S")
    for k in consegne:
        k["creato"] = k["creato"].strftime("%d/%m %H:%M")
        k["voto_auto"] = float(k["voto_auto"])
        k["voto_docente"] = float(k["voto_docente"]) if k["voto_docente"] is not None else None
    return jsonify(allievo={"id": a["id"], "nome": a["nome"], "tempo": _durata(tempo_lavorato(tutti))},
                   ultimo_progetto=a["ultimo_progetto"], azioni=azioni, consegne=consegne)


@bp.post("/api/corso/docente/consegna/<int:kid>")
def correggi(kid):
    _docente()
    try:
        d = _json()
        voto = d.get("voto")
        voto = None if voto in (None, "") else float(str(voto).replace(",", "."))
        if voto is not None and not 0 <= voto <= 10:
            raise ValueError("Il voto va da 0 a 10")
    except (ValueError, TypeError) as exc:
        return jsonify(error=str(exc)), 400
    _q("UPDATE cad_consegne SET voto_docente=%s, commento=%s, corretto=NOW() WHERE id=%s",
       (voto, str(d.get("commento") or "")[:2000], kid), scrivi=True)
    return jsonify(ok=True)


@bp.post("/api/corso/docente/allievo/<int:aid>/pin")
def azzera_pin(aid):
    _docente()
    pin = "".join(secrets.choice("0123456789") for _ in range(4))
    _q("UPDATE cad_allievi SET pin=%s WHERE id=%s", (generate_password_hash(pin), aid), scrivi=True)
    return jsonify(pin=pin)


@bp.post("/api/corso/docente/esercizio/<int:eid>/attivo")
def attiva(eid):
    _docente()
    _q("UPDATE cad_esercizi SET attivo = NOT attivo WHERE id=%s", (eid,), scrivi=True)
    return jsonify(ok=True)
