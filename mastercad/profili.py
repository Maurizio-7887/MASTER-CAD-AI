"""Dal disegno 2D al solido 3D, come ESTRUDI e RIVOLUZIONE di AutoCAD.

Le entità arrivano dalla pagina Disegno (o dal reverse engineering da foto), in millimetri:
  {"t":"line","a":[x,y],"b":[x,y]}
  {"t":"arc","c":[x,y],"r":r,"a0":gradi,"a1":gradi}      (antiorario da a0 ad a1)
  {"t":"circle","c":[x,y],"r":r}
  {"t":"pline","pts":[[x,y],...],"closed":true|false}
Linee, archi e polilinee che si toccano agli estremi vengono concatenati in contorni chiusi.
Il contorno più esterno è il pezzo; i contorni dentro sono fori (come REGIONE + SOTTRAI in AutoCAD).
Nessun codice generato dall'AI: solo geometria validata.
"""
import math

import cadquery as cq

TOL = 0.01          # mm: due estremi più vicini di così sono lo stesso punto
LIMITE = 5000.0     # mm: coordinate ammesse ±5 m
MAX_ENTITA = 3000


def _num(v, nome):
    try:
        v = float(v)
    except (TypeError, ValueError):
        raise ValueError(nome + ": numero non valido") from None
    if not math.isfinite(v) or abs(v) > LIMITE:
        raise ValueError(nome + ": fuori dal campo di lavoro (±5000 mm)")
    return v


def _pt(p, nome):
    if not isinstance(p, (list, tuple)) or len(p) < 2:
        raise ValueError(nome + ": punto non valido")
    return (_num(p[0], nome), _num(p[1], nome))


def _vicini(p, q, tol=TOL):
    return abs(p[0] - q[0]) <= tol and abs(p[1] - q[1]) <= tol


def normalizza(entita):
    """Valida le entità e le riduce a segmenti (linea/arco) e cerchi."""
    if not isinstance(entita, list) or not entita:
        raise ValueError("Il disegno è vuoto: disegna un contorno chiuso")
    if len(entita) > MAX_ENTITA:
        raise ValueError("Troppe entità nel disegno (massimo %d)" % MAX_ENTITA)
    segmenti, cerchi = [], []
    for i, e in enumerate(entita):
        if not isinstance(e, dict):
            raise ValueError("Entità %d non valida" % (i + 1))
        t = e.get("t")
        if t == "line":
            a, b = _pt(e.get("a"), "linea"), _pt(e.get("b"), "linea")
            if not _vicini(a, b):
                segmenti.append({"t": "line", "a": a, "b": b})
        elif t == "pline":
            pts = [_pt(p, "polilinea") for p in (e.get("pts") or [])]
            if len(pts) < 2:
                continue
            if e.get("closed") and not _vicini(pts[0], pts[-1]):
                pts.append(pts[0])
            for a, b in zip(pts, pts[1:]):
                if not _vicini(a, b):
                    segmenti.append({"t": "line", "a": a, "b": b})
        elif t == "arc":
            c, r = _pt(e.get("c"), "arco"), _num(e.get("r"), "raggio arco")
            a0, a1 = _num(e.get("a0"), "angolo arco"), _num(e.get("a1"), "angolo arco")
            if r <= TOL:
                raise ValueError("Arco con raggio nullo")
            sweep = (a1 - a0) % 360 or 360
            if sweep >= 359.999:
                cerchi.append({"c": c, "r": r})
                continue
            p = lambda ang: (c[0] + r * math.cos(math.radians(ang)), c[1] + r * math.sin(math.radians(ang)))
            segmenti.append({"t": "arc", "a": p(a0), "m": p(a0 + sweep / 2), "b": p(a0 + sweep), "c": c, "r": r})
        elif t == "circle":
            c, r = _pt(e.get("c"), "cerchio"), _num(e.get("r"), "raggio cerchio")
            if r <= TOL:
                raise ValueError("Cerchio con raggio nullo")
            cerchi.append({"c": c, "r": r})
        elif t in ("dim", "text", "point", "xline"):
            continue                       # quote e testi non fanno parte del solido
        else:
            raise ValueError("Entità sconosciuta: %s" % t)
    return segmenti, cerchi


def _inverti(s):
    return dict(s, a=s["b"], b=s["a"])


def concatena(segmenti):
    """Unisce i segmenti in contorni chiusi. Restituisce (contorni, estremi aperti)."""
    liberi = list(segmenti)
    contorni, aperti = [], []
    while liberi:
        catena = [liberi.pop(0)]
        progresso = True
        while progresso and not _vicini(catena[0]["a"], catena[-1]["b"]):
            progresso = False
            for k, s in enumerate(liberi):
                if _vicini(s["a"], catena[-1]["b"]):
                    catena.append(liberi.pop(k)); progresso = True; break
                if _vicini(s["b"], catena[-1]["b"]):
                    catena.append(_inverti(liberi.pop(k))); progresso = True; break
                if _vicini(s["b"], catena[0]["a"]):
                    catena.insert(0, liberi.pop(k)); progresso = True; break
                if _vicini(s["a"], catena[0]["a"]):
                    catena.insert(0, _inverti(liberi.pop(k))); progresso = True; break
        if _vicini(catena[0]["a"], catena[-1]["b"]) and (len(catena) > 2 or any(s["t"] == "arc" for s in catena)):
            contorni.append(catena)
        else:
            aperti.append(catena[-1]["b"])
    return contorni, aperti


def _poligono(catena):
    """Punti del contorno (archi campionati) per area e contenimento."""
    pts = []
    for s in catena:
        if s["t"] == "line":
            pts.append(s["a"])
        else:
            c, r = s["c"], s["r"]
            ang = lambda p: math.atan2(p[1] - c[1], p[0] - c[0])
            a0, am, a1 = ang(s["a"]), ang(s["m"]), ang(s["b"])
            ccw = ((am - a0) % (2 * math.pi)) <= ((a1 - a0) % (2 * math.pi))
            sweep = (a1 - a0) % (2 * math.pi) if ccw else -((a0 - a1) % (2 * math.pi))
            for k in range(12):
                t = a0 + sweep * k / 12
                pts.append((c[0] + r * math.cos(t), c[1] + r * math.sin(t)))
    return pts


def _poligono_cerchio(c, r):
    return [(c[0] + r * math.cos(2 * math.pi * k / 48), c[1] + r * math.sin(2 * math.pi * k / 48)) for k in range(48)]


def area(pts):
    return abs(sum(p[0] * q[1] - q[0] * p[1] for p, q in zip(pts, pts[1:] + pts[:1]))) / 2


def dentro(p, pts):
    x, y, ins = p[0], p[1], False
    for (x1, y1), (x2, y2) in zip(pts, pts[1:] + pts[:1]):
        if (y1 > y) != (y2 > y) and x < (x2 - x1) * (y - y1) / (y2 - y1) + x1:
            ins = not ins
    return ins


def _filo(catena):
    edges = []
    for s in catena:
        a, b = cq.Vector(s["a"][0], s["a"][1], 0), cq.Vector(s["b"][0], s["b"][1], 0)
        if s["t"] == "line":
            edges.append(cq.Edge.makeLine(a, b))
        else:
            edges.append(cq.Edge.makeThreePointArc(a, cq.Vector(s["m"][0], s["m"][1], 0), b))
    return cq.Wire.assembleEdges(edges)


def _filo_cerchio(c, r):
    return cq.Wire.makeCircle(r, cq.Vector(c[0], c[1], 0), cq.Vector(0, 0, 1))


def regioni(entita):
    """Come il comando REGIONE: contorni esterni con i loro fori, già pronti per il 3D."""
    segmenti, cerchi = normalizza(entita)
    contorni, aperti = concatena(segmenti)
    loops = [{"filo": lambda cat=c: _filo(cat), "pts": _poligono(c)} for c in contorni]
    loops += [{"filo": lambda c=c["c"], r=c["r"]: _filo_cerchio(c, r), "pts": _poligono_cerchio(c["c"], c["r"])} for c in cerchi]
    if not loops:
        msg = "Nessun contorno chiuso: il profilo deve chiudersi"
        if aperti:
            p = aperti[0]
            msg += " (c'è un estremo aperto vicino a %.2f,%.2f — usa lo snap ESTREMO o il comando RACCORDO con raggio 0)" % p
        raise ValueError(msg)
    for l in loops:
        l["area"] = area(l["pts"])
    loops.sort(key=lambda l: -l["area"])
    # livello di annidamento: esterno (pari) / foro (dispari)
    for i, l in enumerate(loops):
        l["livello"] = sum(1 for m in loops[:i] if dentro(l["pts"][0], m["pts"]))
    risultato = []
    for i, l in enumerate(loops):
        if l["livello"] % 2:
            continue
        fori = [m for m in loops[i + 1:] if m["livello"] == l["livello"] + 1 and dentro(m["pts"][0], l["pts"])]
        risultato.append({"esterno": l, "fori": fori})
    return risultato, aperti


def estensione_entita(entita):
    """Ingombro (xmin, ymin, xmax, ymax) dei contorni chiusi."""
    regs, _ = regioni(entita)
    xs = [p[0] for r in regs for p in r["esterno"]["pts"]]
    ys = [p[1] for r in regs for p in r["esterno"]["pts"]]
    return min(xs), min(ys), max(xs), max(ys)


def _facce(entita):
    regs, aperti = regioni(entita)
    facce = []
    for r in regs:
        facce.append(cq.Face.makeFromWires(r["esterno"]["filo"](), [f["filo"]() for f in r["fori"]]))
    return facce, regs, aperti


def estrudi(entita, altezza):
    altezza = _num(altezza, "altezza di estrusione")
    if altezza <= 0:
        raise ValueError("Altezza di estrusione: deve essere maggiore di 0")
    facce, regs, aperti = _facce(entita)
    solido = None
    for f in facce:
        s = cq.Solid.extrudeLinear(f, cq.Vector(0, 0, altezza))
        solido = s if solido is None else solido.fuse(s)
    return _finale(solido, {"op": "estrudi", "altezza": altezza, "regioni": len(regs),
                            "fori": sum(len(r["fori"]) for r in regs), "aperti": len(aperti)})


def rivoluzione(entita, asse_a, asse_b, angolo=360):
    a, b = _pt(asse_a, "asse"), _pt(asse_b, "asse")
    if _vicini(a, b, 0.001):
        raise ValueError("L'asse di rivoluzione deve avere due punti diversi")
    angolo = _num(angolo, "angolo")
    if not 0 < angolo <= 360:
        raise ValueError("Angolo di rivoluzione tra 0 e 360 gradi")
    facce, regs, aperti = _facce(entita)
    dx, dy = b[0] - a[0], b[1] - a[1]
    lati = set()
    for r in regs:
        for p in r["esterno"]["pts"]:
            d = dx * (p[1] - a[1]) - dy * (p[0] - a[0])
            if abs(d) > TOL * math.hypot(dx, dy):
                lati.add(d > 0)
    if len(lati) > 1:
        raise ValueError("Il profilo attraversa l'asse di rivoluzione: disegna solo metà sezione, da un lato dell'asse")
    solido = None
    for f in facce:
        s = cq.Solid.revolve(f, angolo, cq.Vector(a[0], a[1], 0), cq.Vector(b[0], b[1], 0))
        solido = s if solido is None else solido.fuse(s)
    return _finale(solido, {"op": "rivoluzione", "angolo": angolo, "asse": [a, b], "regioni": len(regs),
                            "fori": sum(len(r["fori"]) for r in regs), "aperti": len(aperti)})


def _finale(solido, info):
    if solido is None or solido.Volume() <= 1e-6:
        raise ValueError("Il solido è vuoto: controlla che il profilo sia chiuso e non si intersechi")
    return cq.Workplane("XY").add(solido), solido, info
