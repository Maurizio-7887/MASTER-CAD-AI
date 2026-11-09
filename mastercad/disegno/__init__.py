"""Disegno: la tavola 2D con i comandi di AutoCAD e il passaggio al 3D (ESTRUDI, RIVOLUZIONE)."""
import json
import tempfile
import threading
import uuid
from pathlib import Path

from flask import Blueprint, current_app, jsonify, render_template, request, session

from ..postgres_store import save_model
from .. import profili

bp = Blueprint("disegno", __name__, template_folder="templates", static_folder="static", static_url_path="/disegno/static")
_LOCK = threading.Lock()


def mesh_fine(solido, max_triangoli=24000):
    """Mesh più fitta di quella di base: cerchi e raccordi tondi nella vista 3D."""
    import math
    box = solido.BoundingBox()
    tol = max(0.05, min(0.3, max(box.xlen, box.ylen, box.zlen) / 600))
    vertici, facce = solido.tessellate(tol, 0.2)
    salto = max(1, math.ceil(len(facce) / max_triangoli))
    tri = [[[round(vertici[j].x, 3), round(vertici[j].y, 3), round(vertici[j].z, 3)] for j in f] for f in facce[::salto]]
    return {"triangles": tri, "bounds": {"x": round(box.xlen, 2), "y": round(box.ylen, 2), "z": round(box.zlen, 2)},
            "volume_mm3": round(solido.Volume(), 3)}


@bp.get("/disegno")
def pagina():
    return render_template("disegno/disegno.html", csrf=session.get("csrf", ""))


def salva_solido(obj, solido, spec, storia, nome):
    """Esporta STEP/STL, salva in PostgreSQL e restituisce mesh e link di download."""
    import cadquery as cq
    token = uuid.uuid4().hex
    with tempfile.TemporaryDirectory(prefix="cad-disegno-") as tmp:
        step, stl = Path(tmp) / "model.step", Path(tmp) / "model.stl"
        cq.exporters.export(obj, str(step))
        cq.exporters.export(obj, str(stl), tolerance=.05, angularTolerance=.15)
        save_model(token, nome, spec, storia, step.read_bytes(), stl.read_bytes())
    return {"id": token, "mesh": mesh_fine(solido), "history": storia,
            "exports": {"step": "/api/export/" + token + "?format=step", "stl": "/api/export/" + token + "?format=stl"}}


@bp.post("/api/disegno/solido")
def solido():
    dati = request.get_json(silent=True)
    if not isinstance(dati, dict):
        return jsonify(error="JSON non valido"), 400
    op, entita = dati.get("op"), dati.get("entita")
    try:
        with _LOCK:
            if op == "estrudi":
                obj, sol, info = profili.estrudi(entita, dati.get("altezza"))
                storia = [{"op": "Profilo 2D", "dettaglio": "%d contorni, %d fori" % (info["regioni"], info["fori"])},
                          {"op": "ESTRUDI", "dettaglio": "altezza %g mm" % info["altezza"]}]
            elif op == "rivoluzione":
                asse = dati.get("asse") or [[0, 0], [1, 0]]
                obj, sol, info = profili.rivoluzione(entita, asse[0], asse[1], dati.get("angolo", 360))
                storia = [{"op": "Mezza sezione 2D", "dettaglio": "%d contorni" % info["regioni"]},
                          {"op": "RIVOLUZIONE", "dettaglio": "%g° attorno all'asse" % info["angolo"]}]
            else:
                return jsonify(error="Operazione 3D: estrudi o rivoluzione"), 400
            spec = {"kind": "disegno", "op": op, "info": info, "entita": entita}
            out = salva_solido(obj, sol, spec, storia, str(dati.get("nome") or "Disegno " + op)[:180])
        avviso = None
        if info.get("aperti"):
            avviso = "Alcune linee non chiudono un contorno e sono state ignorate (%d estremi aperti)." % info["aperti"]
        return jsonify(dict(out, info=info, avviso=avviso,
                            warning="Bozza CAD: verificare quote, tolleranze, materiale e carichi prima di produrre."))
    except (ValueError, TypeError, KeyError) as exc:
        return jsonify(error=str(exc)[:400]), 400
    except Exception:
        current_app.logger.exception("Errore solido dal disegno")
        return jsonify(error="Il motore 3D non è riuscito a costruire il solido: controlla che i contorni non si intersechino"), 500
