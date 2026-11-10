"""La mia officina: macchine (con corse e costo orario), terzisti, prezzi dei materiali e dei trattamenti, costi di banco.

Ciclo di lavoro, preventivo e verifica di fattibilità usano questi dati, non medie generiche: se il pezzo non entra
nella fresatrice, il ciclo lo manda al terzista che fa quella lavorazione, con la sua tariffa.
"""
import copy

from flask import Blueprint, jsonify, render_template, request, session
from psycopg2.extras import Json

from ..materiali import MATERIALI, TRATTAMENTI
from ..postgres_store import connect

bp = Blueprint("officina", __name__, template_folder="templates", static_folder="static", static_url_path="/officina/static")

TIPI_MACCHINA = {"fresa": "Centro di lavoro / fresatrice CNC", "tornio": "Tornio CNC", "rettifica": "Rettifica cilindrica",
                 "rettifica_piana": "Rettifica tangenziale", "sega": "Sega a nastro", "laser": "Taglio laser", "elettroerosione": "Elettroerosione a filo"}
LAVORAZIONI_TERZI = {"fresatura": "Fresatura CNC", "tornitura": "Tornitura CNC", "rettifica": "Rettifica", "trattamento_termico": "Trattamenti termici",
                     "trattamento_superficiale": "Trattamenti superficiali", "laser": "Taglio laser", "elettroerosione": "Elettroerosione"}

PREDEFINITA = {
    "nome": "La mia officina",
    "macchine": [
        {"nome": "Centro di lavoro 3 assi", "tipo": "fresa", "x": 800, "y": 500, "z": 500, "costo_ora": 55, "attiva": True},
        {"nome": "Tornio CNC", "tipo": "tornio", "diametro": 300, "lunghezza": 600, "costo_ora": 45, "attiva": True},
        {"nome": "Sega a nastro", "tipo": "sega", "diametro": 250, "costo_ora": 30, "attiva": True},
    ],
    "terzisti": [
        {"nome": "Terzista rettifiche", "lavorazioni": ["rettifica"], "costo_ora": 65, "giorni": 5},
        {"nome": "Terzista fresature grandi", "lavorazioni": ["fresatura", "tornitura"], "costo_ora": 70, "giorni": 10},
        {"nome": "Terzista trattamenti", "lavorazioni": ["trattamento_termico", "trattamento_superficiale"], "costo_ora": 0, "giorni": 7},
    ],
    "materiali": {k: {"euro_kg": v["euro_kg"]} for k, v in MATERIALI.items()},
    "trattamenti": {k: {"euro_kg": v["euro_kg"]} for k, v in TRATTAMENTI.items()},
    "costi": {"banco": 32, "attrezzaggio": 45, "margine": 25, "scarto": 3},
}


def init_db():
    with connect() as conn, conn.cursor() as cur:
        cur.execute("CREATE TABLE IF NOT EXISTS cad_officina (id INT PRIMARY KEY, dati JSONB NOT NULL, aggiornato TIMESTAMPTZ NOT NULL DEFAULT NOW())")


def leggi():
    try:
        with connect() as conn, conn.cursor() as cur:
            cur.execute("SELECT dati FROM cad_officina WHERE id=1")
            r = cur.fetchone()
    except Exception:
        r = None
    o = copy.deepcopy(PREDEFINITA)
    if r and isinstance(r[0], dict):
        for k in ("nome", "macchine", "terzisti", "costi"):
            if k in r[0]:
                o[k] = r[0][k]
        for k in ("materiali", "trattamenti"):
            o[k].update(r[0].get(k) or {})
    return o


def _num(v, nome, minimo=0, massimo=1e6):
    try:
        v = float(v)
    except (TypeError, ValueError):
        raise ValueError("%s: scrivi un numero" % nome) from None
    if not minimo <= v <= massimo:
        raise ValueError("%s fuori dai limiti" % nome)
    return v


def valida(d):
    if not isinstance(d, dict):
        raise ValueError("Dati non validi")
    o = {"nome": str(d.get("nome") or "La mia officina")[:80], "macchine": [], "terzisti": [], "materiali": {}, "trattamenti": {}, "costi": {}}
    for m in (d.get("macchine") or [])[:40]:
        tipo = m.get("tipo")
        if tipo not in TIPI_MACCHINA:
            raise ValueError("Tipo di macchina sconosciuto: %s" % tipo)
        x = {"nome": str(m.get("nome") or TIPI_MACCHINA[tipo])[:60], "tipo": tipo, "costo_ora": _num(m.get("costo_ora"), "Costo orario", 1, 1000),
             "attiva": bool(m.get("attiva", True))}
        for k in ("x", "y", "z", "diametro", "lunghezza"):
            if m.get(k) not in (None, ""):
                x[k] = _num(m[k], "Corsa " + k, 1, 20000)
        o["macchine"].append(x)
    for t in (d.get("terzisti") or [])[:40]:
        lav = [x for x in (t.get("lavorazioni") or []) if x in LAVORAZIONI_TERZI]
        o["terzisti"].append({"nome": str(t.get("nome") or "Terzista")[:60], "lavorazioni": lav, "costo_ora": _num(t.get("costo_ora") or 0, "Tariffa terzista", 0, 1000),
                              "giorni": int(_num(t.get("giorni") or 0, "Giorni", 0, 365))})
    for k, v in (d.get("materiali") or {}).items():
        if k in MATERIALI:
            o["materiali"][k] = {"euro_kg": _num(v.get("euro_kg"), "Prezzo " + k, 0.01, 500)}
    for k, v in (d.get("trattamenti") or {}).items():
        if k in TRATTAMENTI:
            o["trattamenti"][k] = {"euro_kg": _num(v.get("euro_kg"), "Prezzo " + k, 0, 500)}
    c = d.get("costi") or {}
    o["costi"] = {"banco": _num(c.get("banco", 32), "Costo banco", 1, 1000), "attrezzaggio": _num(c.get("attrezzaggio", 45), "Costo attrezzaggio", 1, 1000),
                  "margine": _num(c.get("margine", 25), "Margine", 0, 300), "scarto": _num(c.get("scarto", 3), "Scarto", 0, 50)}
    return o


def scegli_macchina(off, tipo, ingombro):
    """Prima macchina attiva del tipo in cui il pezzo entra; altrimenti il terzista; altrimenti None.
    ingombro: (x, y, z) per frese, (diametro, lunghezza) per torni."""
    lav_terzi = {"fresa": "fresatura", "tornio": "tornitura", "rettifica": "rettifica", "rettifica_piana": "rettifica", "laser": "laser",
                 "elettroerosione": "elettroerosione"}.get(tipo)
    motivo = None
    for m in off["macchine"]:
        if m["tipo"] != tipo or not m.get("attiva", True):
            continue
        if tipo in ("fresa", "rettifica_piana", "laser"):
            dims = sorted(ingombro[:2], reverse=True)
            corse = sorted([m.get("x", 1e9), m.get("y", 1e9)], reverse=True)
            if dims[0] <= corse[0] and dims[1] <= corse[1] and ingombro[2] <= m.get("z", 1e9):
                return {"nome": m["nome"], "costo_ora": m["costo_ora"], "interna": True}
            motivo = "il pezzo (%g × %g × %g) non entra in «%s»" % (round(ingombro[0]), round(ingombro[1]), round(ingombro[2]), m["nome"])
        elif tipo in ("tornio", "rettifica"):
            if ingombro[0] <= m.get("diametro", 1e9) and ingombro[1] <= m.get("lunghezza", 1e9):
                return {"nome": m["nome"], "costo_ora": m["costo_ora"], "interna": True}
            motivo = "il pezzo (Ø%g × %g) non entra in «%s»" % (round(ingombro[0]), round(ingombro[1]), m["nome"])
        else:
            return {"nome": m["nome"], "costo_ora": m["costo_ora"], "interna": True}
    for t in off["terzisti"]:
        if lav_terzi in t["lavorazioni"]:
            return {"nome": "Terzista: " + t["nome"], "costo_ora": t["costo_ora"] or 60, "interna": False, "giorni": t["giorni"],
                    "motivo": motivo or "nessuna macchina interna per questa lavorazione"}
    return {"nome": "Da assegnare (nessuna macchina né terzista)", "costo_ora": 60, "interna": False, "motivo": motivo or "manca la macchina"}


@bp.get("/officina")
def pagina():
    return render_template("officina/officina.html", csrf=session.get("csrf", ""), tipi=TIPI_MACCHINA, lavorazioni=LAVORAZIONI_TERZI,
                           materiali={k: v["nome"] for k, v in MATERIALI.items()}, trattamenti={k: v["nome"] for k, v in TRATTAMENTI.items()})


@bp.get("/api/officina")
def api_leggi():
    return jsonify(leggi())


@bp.post("/api/officina")
def api_salva():
    if session.get("allievo") and not session.get("ok"):
        return jsonify(error="Riservato"), 403
    try:
        o = valida(request.get_json(silent=True))
    except ValueError as exc:
        return jsonify(error=str(exc)), 400
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""INSERT INTO cad_officina(id, dati) VALUES (1, %s)
                       ON CONFLICT (id) DO UPDATE SET dati=EXCLUDED.dati, aggiornato=NOW()""", (Json(o),))
    return jsonify(ok=True, officina=o)
