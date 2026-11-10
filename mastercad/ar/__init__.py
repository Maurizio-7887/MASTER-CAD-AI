"""Il pezzo in realtà aumentata: modello GLB a grandezza reale, da aprire sul telefono inquadrando un QR.

Il link di condivisione è un token casuale di 32 caratteri, valido 7 giorni, che apre SOLO la vista 3D di quel pezzo
(senza login, perché il visore AR di Android scarica il modello da fuori della sessione).
"""
import io
import json
import secrets
import struct
import tempfile
import threading
from pathlib import Path

from flask import Blueprint, Response, abort, current_app, jsonify, render_template, request, session, url_for

from ..postgres_store import connect
from ..progetto import lavorazioni as L

bp = Blueprint("ar", __name__, template_folder="templates", static_folder="static", static_url_path="/ar/static")
_LOCK = threading.Lock()
GIORNI = 7


def init_db():
    with connect() as conn, conn.cursor() as cur:
        cur.execute("""CREATE TABLE IF NOT EXISTS cad_condivisioni (
            token TEXT PRIMARY KEY, nome TEXT NOT NULL, glb BYTEA NOT NULL, creato TIMESTAMPTZ NOT NULL DEFAULT NOW())""")
        cur.execute("DELETE FROM cad_condivisioni WHERE creato < NOW() - INTERVAL '%s days'" % GIORNI)


def glb_in_metri(dati):
    """CadQuery esporta in millimetri: il glTF vuole metri. Metto una scala 0,001 sul nodo radice."""
    if dati[:4] != b"glTF":
        raise ValueError("GLB non valido")
    lung_json = struct.unpack("<I", dati[12:16])[0]
    js = json.loads(dati[20:20 + lung_json])
    resto = dati[20 + lung_json:]
    radici = js["scenes"][js.get("scene", 0)]["nodes"]
    for n in radici:
        js["nodes"][n]["scale"] = [0.001, 0.001, 0.001]
    nuovo = json.dumps(js, separators=(",", ":")).encode()
    nuovo += b" " * ((4 - len(nuovo) % 4) % 4)
    corpo = struct.pack("<I", len(nuovo)) + b"JSON" + nuovo + resto
    return b"glTF" + struct.pack("<II", 2, 12 + len(corpo)) + corpo


def esporta_glb(solido, colore=(0.72, 0.76, 0.80)):
    import cadquery as cq
    a = cq.Assembly()
    a.add(solido, name="pezzo", color=cq.Color(*colore))
    with tempfile.TemporaryDirectory(prefix="cad-ar-") as tmp:
        p = Path(tmp) / "pezzo.glb"
        a.export(str(p))
        return glb_in_metri(p.read_bytes())


def qr_svg(testo):
    import qrcode
    import qrcode.image.svg
    img = qrcode.make(testo, image_factory=qrcode.image.svg.SvgPathImage, box_size=10, border=2)
    buf = io.BytesIO()
    img.save(buf)
    return buf.getvalue().decode("utf-8")


def _token_ok(token):
    return len(token) == 32 and all(c in "0123456789abcdef" for c in token)


@bp.get("/ar")
def pagina():
    return render_template("ar/ar.html", csrf=session.get("csrf", ""))


@bp.post("/api/ar")
def crea():
    dati = request.get_json(silent=True)
    if not isinstance(dati, dict):
        return jsonify(error="JSON non valido"), 400
    try:
        with _LOCK:
            _, solido, storia = L.costruisci(dati.get("progetto"))
            glb = esporta_glb(solido)
        token = secrets.token_hex(16)
        nome = str(dati.get("nome") or "Pezzo")[:120]
        with connect() as conn, conn.cursor() as cur:
            cur.execute("INSERT INTO cad_condivisioni(token, nome, glb) VALUES (%s,%s,%s)", (token, nome, glb))
        link = request.host_url.rstrip("/") + url_for("ar.vista", token=token)
        b = solido.BoundingBox()
        return jsonify(token=token, link=link, glb=url_for("ar.modello", token=token), qr=qr_svg(link), giorni=GIORNI,
                       misure="%.0f × %.0f × %.0f mm" % (b.xlen, b.ylen, b.zlen))
    except (ValueError, TypeError, KeyError) as exc:
        return jsonify(error=str(exc)[:400]), 400
    except Exception:
        current_app.logger.exception("Errore AR")
        return jsonify(error="Non sono riuscito a preparare il modello 3D: ricostruisci il pezzo nella pagina Disegno"), 500


def _leggi(token):
    if not _token_ok(token):
        abort(404)
    with connect() as conn, conn.cursor() as cur:
        cur.execute("SELECT nome, glb FROM cad_condivisioni WHERE token=%s AND creato > NOW() - INTERVAL '%s days'" % ("%s", GIORNI), (token,))
        riga = cur.fetchone()
    if not riga:
        abort(404)
    return riga[0], bytes(riga[1])


@bp.get("/ar/v/<token>")
def vista(token):
    nome, _ = _leggi(token)
    return render_template("ar/vista.html", nome=nome, glb=url_for("ar.modello", token=token))


@bp.get("/ar/v/<token>/pezzo.glb")
def modello(token):
    _, glb = _leggi(token)
    return Response(glb, mimetype="model/gltf-binary", headers={"Access-Control-Allow-Origin": "*"})
