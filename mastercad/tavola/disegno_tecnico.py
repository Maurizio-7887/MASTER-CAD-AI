"""Messa in tavola automatica: dal solido al disegno tecnico per l'officina (foglio A3, metodo E europeo).

Viste ortogonali con linee nascoste (algoritmo HLR di OpenCascade), sezione A-A sui fori, assonometria,
quote d'ingombro, tabella fori con coordinate dall'origine, distinta viti, note e cartiglio.
Il disegno è descritto da poche primitive (polilinee, testi, poligoni pieni) e scritto in SVG, PDF e DXF:
i tre file sono identici.
"""
import datetime
import math

import cadquery as cq
from OCP.gp import gp_Ax2, gp_Dir, gp_Pnt
from OCP.HLRAlgo import HLRAlgo_Projector
from OCP.HLRBRep import HLRBRep_Algo, HLRBRep_HLRToShape

from ..materiali import materiale as dati_materiale
from ..progetto import lavorazioni as L
from ..progetto.analisi import _num, descrivi_foro, gruppi_fori
from ..tolleranze.iso286 import limiti as iso286_limiti

FOGLIO = (420.0, 297.0)                       # A3 orizzontale
SCALE = [(10, "10:1"), (5, "5:1"), (2, "2:1"), (1, "1:1"), (0.5, "1:2"), (0.2, "1:5"), (0.1, "1:10"), (0.05, "1:20"), (0.02, "1:50")]
VITI_L = (6, 8, 10, 12, 16, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 80, 90, 100, 110, 120, 130, 140, 150, 160, 180, 200)
SPAZIO = 22.0                                  # spazio fra le viste, per le quote


# ── proiezioni ──
def _proietta(forma, v, xd):
    algo = HLRBRep_Algo()
    algo.Add(forma.wrapped)
    algo.Projector(HLRAlgo_Projector(gp_Ax2(gp_Pnt(0, 0, 0), gp_Dir(*v), gp_Dir(*xd))))
    algo.Update()
    algo.Hide()
    h = HLRBRep_HLRToShape(algo)
    out = {"vis": [], "nasc": []}
    for chiave, fn in (("vis", h.VCompound), ("vis", h.OutLineVCompound), ("nasc", h.HCompound), ("nasc", h.OutLineHCompound)):
        c = fn()
        if not c.IsNull():
            out[chiave] += [_campiona(e) for e in cq.Shape.cast(c).Edges()]
    return out


def _campiona(e):
    if e.geomType() == "LINE":
        a, b = e.startPoint(), e.endPoint()
        return [(a.x, a.y), (b.x, b.y)]
    n = max(6, min(160, int(e.Length() / 0.4)))
    return [(p.x, p.y) for p in e.positions([i / n for i in range(n + 1)])]


def _estensione(polilinee):
    xs = [p[0] for pl in polilinee for p in pl]
    ys = [p[1] for pl in polilinee for p in pl]
    return (min(xs), min(ys), max(xs), max(ys)) if xs else (0, 0, 1, 1)


# ── tratteggio della sezione: linee a 45° tagliate sul contorno (regola pari/dispari) ──
def tratteggio(anelli, passo=2.5, angolo=45.0):
    c, s = math.cos(math.radians(-angolo)), math.sin(math.radians(-angolo))
    rot = [[(x * c - y * s, x * s + y * c) for x, y in a] for a in anelli]
    ys = [p[1] for a in rot for p in a]
    if not ys:
        return []
    linee = []
    y = math.floor(min(ys) / passo) * passo + passo / 2
    ci, si = math.cos(math.radians(angolo)), math.sin(math.radians(angolo))
    while y < max(ys):
        xs = []
        for a in rot:
            for (x1, y1), (x2, y2) in zip(a, a[1:] + a[:1]):
                if (y1 <= y < y2) or (y2 <= y < y1):
                    xs.append(x1 + (y - y1) * (x2 - x1) / (y2 - y1))
        xs.sort()
        for xa, xb in zip(xs[::2], xs[1::2]):
            linee.append([(xa * ci - y * si, xa * si + y * ci), (xb * ci - y * si, xb * si + y * ci)])
        y += passo
    return linee


class Tavola:
    def __init__(self):
        self.prim = []

    def pl(self, pts, ly="vis"):
        if len(pts) >= 2:
            self.prim.append({"k": "pl", "pts": [(round(x, 3), round(y, 3)) for x, y in pts], "ly": ly})

    def tx(self, p, t, h=3.5, al="start", rot=0.0, ly="testo"):
        self.prim.append({"k": "tx", "p": (round(p[0], 3), round(p[1], 3)), "t": str(t), "h": h, "al": al, "rot": rot, "ly": ly})

    def pg(self, pts, ly="quota"):
        self.prim.append({"k": "pg", "pts": [(round(x, 3), round(y, 3)) for x, y in pts], "ly": ly})

    def rett(self, x0, y0, x1, y1, ly="cornice"):
        self.pl([(x0, y0), (x1, y0), (x1, y1), (x0, y1), (x0, y0)], ly)

    def freccia(self, punta, ang):
        a = math.radians(ang)
        l, w = 3.0, 0.9
        b = (punta[0] - l * math.cos(a), punta[1] - l * math.sin(a))
        self.pg([punta, (b[0] - w * math.sin(a), b[1] + w * math.cos(a)), (b[0] + w * math.sin(a), b[1] - w * math.cos(a))])

    def quota(self, a, b, offset, testo, h=3.5):
        """Quota lineare fra i punti a e b (in tavola), linea di misura spostata di «offset» a sinistra di a→b."""
        dx, dy = b[0] - a[0], b[1] - a[1]
        lung = math.hypot(dx, dy) or 1
        ux, uy = dx / lung, dy / lung
        nx, ny = -uy, ux
        A, B = (a[0] + nx * offset, a[1] + ny * offset), (b[0] + nx * offset, b[1] + ny * offset)
        sgn = 1 if offset >= 0 else -1
        self.pl([(a[0] + nx * sgn * 1.0, a[1] + ny * sgn * 1.0), (A[0] + nx * sgn * 2, A[1] + ny * sgn * 2)], "quota")
        self.pl([(b[0] + nx * sgn * 1.0, b[1] + ny * sgn * 1.0), (B[0] + nx * sgn * 2, B[1] + ny * sgn * 2)], "quota")
        self.pl([A, B], "quota")
        ang = math.degrees(math.atan2(dy, dx))
        self.freccia(A, ang + 180)
        self.freccia(B, ang)
        rot = ang if -90 < ang <= 90 else ang + 180
        m = ((A[0] + B[0]) / 2 + nx * sgn * 1.2, (A[1] + B[1]) / 2 + ny * sgn * 1.2)
        if sgn < 0:     # testo sempre sopra la linea di misura
            m = ((A[0] + B[0]) / 2 - nx * (h + 1.2), (A[1] + B[1]) / 2 - ny * (h + 1.2)) if ny > 0 or (ny == 0 and nx < 0) else m
        self.tx(m, testo, h, "middle", rot, "quota")


def _viti(an):
    """Distinta viti ISO 4762 per i fori lamati di passaggio."""
    inv = {v: k for k, v in L.PASSAGGIO.items()}
    righe = {}
    for f in an["fori"]:
        if f["filetto"] or not f["lamatura"] or not f["passante"] or f["lamatura"].get("tolleranza") or (f.get("funzione") or {}).get("tipo") == "sede_cuscinetto":
            continue
        m = inv.get(round(f["d"], 1)) or inv.get(f["d"])
        if not m:
            continue
        d = float(m[1:])
        presa = max(1.0, f["spessore"] - float(f["lamatura"]["prof"]))
        lung = next((x for x in VITI_L if x >= presa + 1.5 * d), VITI_L[-1])
        chiave = "ISO 4762 %s×%d" % (m, lung)
        righe[chiave] = righe.get(chiave, 0) + 1
    return [{"descrizione": k, "quantita": q} for k, q in righe.items()]


def _tondo(base):
    """Pezzo tondo (flangia, disco): pianta fatta solo di cerchi, il più grande è il contorno."""
    ents = base.get("entita") if base.get("tipo") == "estrudi" else None
    return bool(ents) and all(e.get("t") == "circle" for e in ents)


def genera(an, info):
    """an: progetto analizzato; info: nome, disegnatore, materiale, trattamento, numero, revisione."""
    sol = an["solido"]
    ing = an["ingombro"]
    W, D, H = ing["x"], ing["y"], ing["z"]
    m = dati_materiale(info.get("materiale") or "S235")
    t = Tavola()
    FW, FH = FOGLIO
    # cornice, zona di archiviazione a sinistra, centratura
    t.rett(20, 10, FW - 10, FH - 10)
    for x in (FW / 2,):
        t.pl([(x, FH - 10), (x, FH - 5)], "sottile")
        t.pl([(x, 10), (x, 5)], "sottile")
    t.pl([(20, FH / 2), (15, FH / 2)], "sottile")
    t.pl([(FW - 10, FH / 2), (FW - 5, FH / 2)], "sottile")

    # ── impaginazione: piastre (sottili, con fori) → frontale in sezione + pianta, più grandi; altrimenti 3 viste ──
    cavita = an["fori"] or an["tasche"] or an["guscio"]
    piatto = bool(cavita) and H <= 0.35 * min(W, D)
    area_w, area_h = 262.0, 205.0
    if piatto:
        s_max = min((area_w - 2 * SPAZIO) / max(W, 1), (area_h - 2.5 * SPAZIO) / max(H + D, 1))
    else:
        s_max = min((area_w - 2.5 * SPAZIO) / max(W + D, 1), (area_h - 2.5 * SPAZIO) / max(H + D, 1))
    scala, scala_txt = next(((v, n) for v, n in SCALE if v <= s_max), SCALE[-1])
    s = scala
    if piatto:
        xL = 24 + SPAZIO + (area_w - 2 * SPAZIO - W * s) / 2
    else:
        xL = 24 + SPAZIO + (area_w - 2 * SPAZIO - (W + D) * s - SPAZIO) / 2
    yF = FH - 14 - SPAZIO * 0.5 - H * s
    yT = yF - SPAZIO - D * s
    xS = xL + W * s + SPAZIO

    def mappa(x0, y0, u0, v0):
        return lambda pts: [(x0 + (u - u0) * s, y0 + (v - v0) * s) for u, v in pts]

    def facce_tagliate(tenuto, asse, quota, proietta2d, mappa_):
        for f in tenuto.Faces():
            try:
                c = f.Center()
                nrm = f.normalAt(c)
            except Exception:
                continue
            if abs(getattr(c, asse) - quota) < 1e-4 and getattr(nrm, asse) < -0.99:
                anelli = []
                for w in [f.outerWire()] + f.innerWires():
                    pts = []
                    for e in w.Edges():
                        pts += [proietta2d(p) for p in ([e.startPoint(), e.endPoint()] if e.geomType() == "LINE" else e.positions([i / 24 for i in range(25)]))]
                    anelli.append(mappa_(pts))
                for ln in tratteggio(anelli):
                    t.pl(ln, "sez")

    def marca_sezione(p1, p2, ang_freccia):
        """Traccia del piano di sezione con le frecce nel verso di osservazione e le lettere A."""
        t.pl([p1, p2], "asse")
        a = math.radians(ang_freccia)
        for p in (p1, p2):
            q = (p[0] + 6 * math.cos(a), p[1] + 6 * math.sin(a))
            t.pl([p, q], "vis")
            t.freccia((q[0] + math.cos(a), q[1] + math.sin(a)), ang_freccia)
            t.tx((p[0] - 2.5, p[1] - 4.5), "A", 4, "end")

    mf = mappa(xL, yF, ing["xmin"], ing["zmin"])
    ma = mappa(xL, yT, ing["xmin"], ing["ymin"])
    ms = mappa(xS, yF, -ing["ymax"], ing["zmin"])
    xc = yc = None
    if piatto:
        # frontale in sezione A-A sul piano che passa per i fori più vicini al centro
        cy = (ing["ymin"] + ing["ymax"]) / 2
        yc = min([f["y"] for f in an["fori"]] or [cy], key=lambda y: abs(y - cy))
        yc = min(max(yc, ing["ymin"] + 0.01), ing["ymax"] - 0.01)
        tenuto = sol.intersect(cq.Solid.makeBox(W + 2, ing["ymax"] - yc + 1, H + 2, cq.Vector(ing["xmin"] - 1, yc, ing["zmin"] - 1)))
        fr = _proietta(tenuto, (0, -1, 0), (1, 0, 0))
        facce_tagliate(tenuto, "y", yc, lambda p: (p.x, p.z), mf)
        for pl in fr["vis"]:
            t.pl(mf(pl), "vis")
        t.tx((xL + W * s / 2, yF + H * s + 6), "SEZIONE A-A", 3.5, "middle")
    else:
        fr = _proietta(sol, (0, -1, 0), (1, 0, 0))
        for pl in fr["nasc"]:
            t.pl(mf(pl), "nasc")
        for pl in fr["vis"]:
            t.pl(mf(pl), "vis")
    # vista dall'alto (sotto la frontale): u = X, v = Y
    al = _proietta(sol, (0, 0, 1), (1, 0, 0))
    for pl in al["nasc"]:
        t.pl(ma(pl), "nasc")
    for pl in al["vis"]:
        t.pl(ma(pl), "vis")
    if piatto:
        ya = yT + (yc - ing["ymin"]) * s
        marca_sezione((xL - 8, ya), (xL + W * s + 8, ya), 90)
    elif cavita:
        # vista da sinistra in sezione A-A sul piano che passa per i fori più vicini al centro
        cx = (ing["xmin"] + ing["xmax"]) / 2
        xc = min([f["x"] for f in an["fori"]] or [cx], key=lambda x: abs(x - cx))
        xc = min(max(xc, ing["xmin"] + 0.01), ing["xmax"] - 0.01)
        tenuto = sol.intersect(cq.Solid.makeBox(ing["xmax"] - xc + 1, D + 2, H + 2, cq.Vector(xc, ing["ymin"] - 1, ing["zmin"] - 1)))
        se = _proietta(tenuto, (-1, 0, 0), (0, -1, 0))
        facce_tagliate(tenuto, "x", xc, lambda p: (-p.y, p.z), ms)
        for pl in se["vis"]:
            t.pl(ms(pl), "vis")
        t.tx((xS + D * s / 2, yF + H * s + 6), "SEZIONE A-A", 3.5, "middle")
        xa = xL + (xc - ing["xmin"]) * s
        marca_sezione((xa, yT - 8), (xa, yT + D * s + 8), 0)
    else:
        la = _proietta(sol, (-1, 0, 0), (0, -1, 0))
        for pl in la["nasc"]:
            t.pl(ms(pl), "nasc")
        for pl in la["vis"]:
            t.pl(ms(pl), "vis")

    # assi di simmetria dei pezzi tondi e dei fori
    tondo = _tondo(an["base"])
    assi_front = set()
    for f in an["fori"]:
        x, y = xL + (f["x"] - ing["xmin"]) * s, yT + (f["y"] - ing["ymin"]) * s
        r = f["d"] / 2 * s + 1.5
        t.pl([(x - r, y), (x + r, y)], "asse")
        t.pl([(x, y - r), (x, y + r)], "asse")
        if len(an["fori"]) <= 40:
            t.tx((x + r * 0.7, y + r * 0.7), "%d" % f["rif"], 2.5, "start", 0, "sottile")
        assi_front.add(round(x, 2))
    for xf in sorted(assi_front):           # assi dei fori anche nella vista frontale
        t.pl([(xf, yF - 1.5), (xf, yF + H * s + 1.5)], "asse")
    # cerchi primitivi delle serie polari
    polari = {}
    for f in an["fori"]:
        if f["serie"] == "serie_polare":
            polari.setdefault(f["lavorazione"], []).append(f)
    for g in polari.values():
        if len(g) >= 2:
            cx = sum(f["x"] for f in g) / len(g)
            cy = sum(f["y"] for f in g) / len(g)
            rr = [math.hypot(f["x"] - cx, f["y"] - cy) for f in g]
            if rr[0] > 1 and max(rr) - min(rr) < 0.01:
                R = rr[0] * s
                X, Y = xL + (cx - ing["xmin"]) * s, yT + (cy - ing["ymin"]) * s
                t.pl([(X + R * math.cos(a / 60 * math.pi), Y + R * math.sin(a / 60 * math.pi)) for a in range(121)], "asse")
                t.tx((X + R * 0.72 + 1, Y - R * 0.72 - 3.5), "Ø" + _num(2 * rr[0]), 3, "start", 0, "quota")
    if tondo:
        X, Y = xL + W * s / 2, yT + D * s / 2
        t.pl([(X - W * s / 2 - 3, Y), (X + W * s / 2 + 3, Y)], "asse")
        t.pl([(X, Y - D * s / 2 - 3), (X, Y + D * s / 2 + 3)], "asse")

    # ── quote d'ingombro ──
    t.quota((xL, yT), (xL + W * s, yT), -15, ("Ø" if tondo else "") + _num(W))
    if not tondo:
        t.quota((xL, yT + D * s), (xL, yT), -15, _num(D))
    t.quota((xL, yF), (xL, yF + H * s), 9, _num(H))
    if an["rialzi"]:
        zb = L.base(an["base"])[0].BoundingBox()
        hb = zb.zmax - ing["zmin"]
        if 0.05 < hb < H - 0.05:
            t.quota((xL, yF), (xL, yF + hb * s), 18, _num(hb))
    # origine delle coordinate dei fori
    if an["fori"]:
        X0, Y0 = xL + (0 - ing["xmin"]) * s, yT + (0 - ing["ymin"]) * s
        if xL - 15 <= X0 <= xL + W * s + 15 and yT - 15 <= Y0 <= yT + D * s + 15:
            t.pg([(X0 - 1.5, Y0), (X0, Y0 + 1.5), (X0 + 1.5, Y0), (X0, Y0 - 1.5)], "quota")
            t.tx((X0 - 2, Y0 - 4.5), "0,0", 2.5, "end", 0, "quota")

    # ── assonometria ──
    iso = _proietta(sol, (1 / math.sqrt(3), -1 / math.sqrt(3), 1 / math.sqrt(3)), (1 / math.sqrt(2), 1 / math.sqrt(2), 0))
    ex = _estensione(iso["vis"])
    box = (300.0, FH - 82.0, FW - 14.0, FH - 14.0)
    si = min((box[2] - box[0]) / max(ex[2] - ex[0], 1), (box[3] - box[1] - 6) / max(ex[3] - ex[1], 1))
    for pl in iso["vis"]:
        t.pl([(box[0] + (u - ex[0]) * si + ((box[2] - box[0]) - (ex[2] - ex[0]) * si) / 2,
               box[1] + (v - ex[1]) * si) for u, v in pl], "sottile_vis")
    t.tx(((box[0] + box[2]) / 2, box[3] - 1), "ASSONOMETRIA (fuori scala)", 2.5, "middle", 0, "sottile")

    # ── tabella fori ──
    y = FH - 92
    if an["fori"]:
        t.tx((300, y), "TABELLA FORI (quote dallo zero 0,0)", 3, "start", 0, "testo")
        y -= 3
        righe = [(str(f["rif"]), _num(f["x"]), _num(f["y"]), descrivi_foro(f, True)) for f in an["fori"]]
        if len(righe) > 22:
            righe = [("%d–%d" % (g[0]["rif"], g[-1]["rif"]) if len(g) > 1 else str(g[0]["rif"]), "", "", "%d× %s" % (len(g), descrivi_foro(g[0])))
                     for g in gruppi_fori(an["fori"])]
        col = (300, 309, 324, 339)
        t.pl([(300, y), (FW - 12, y)], "sottile")
        for c_, h_ in zip(col, ("N.", "X", "Y", "Descrizione")):
            t.tx((c_ + 0.8, y - 3.6), h_, 2.5, "start", 0, "testo")
        y -= 5
        t.pl([(300, y), (FW - 12, y)], "sottile")
        for r in righe[:24]:
            desc = r[3]
            taglio = max(desc.rfind(", ", 0, 37), desc.rfind(" — ", 0, 37))
            parti = [desc] if len(desc) <= 36 else ([desc[:taglio + 1], desc[taglio + 1:].lstrip(" —,")] if taglio > 0 else [desc[:36], desc[36:]])
            for k, p in enumerate(parti):
                if k == 0:
                    for c_, v in zip(col[:3], r[:3]):
                        t.tx((c_ + 0.8, y - 3.4), v, 2.3, "start", 0, "testo")
                t.tx((col[3] + 0.8, y - 3.4), p.strip(), 2.3, "start", 0, "testo")
                y -= 4.2
            t.pl([(300, y), (FW - 12, y)], "sottile")
        for c_ in col + (FW - 12,):
            t.pl([(c_, FH - 95), (c_, y)], "sottile")
        y -= 6
    viti = _viti(an)
    if viti and y > 80:
        t.tx((300, y), "VITERIA CONSIGLIATA", 3, "start", 0, "testo")
        for v in viti:
            y -= 4.5
            t.tx((302, y), "%d× %s (lunghezza da verificare sul pezzo accoppiato)" % (v["quantita"], v["descrizione"]), 2.3, "start", 0, "testo")
        y -= 6

    # ── note ──
    note = ["Quote in mm. Tolleranze generali ISO 2768-mK.", "Rugosità generale Ra 3,2 µm.", "Spigoli vivi: smussare 0,2×45° se non indicato."]
    for sp in an["spigoli"]:
        note.append("%s %s×45° sugli spigoli %s." % ("Smussi" if sp["tipo"] == "smusso" else "Raccordi R", _num(sp["valore"]), sp["spigoli"])
                    if sp["tipo"] == "smusso" else "Raccordi R%s sugli spigoli %s." % (_num(sp["valore"]), sp["spigoli"]))
    for k, tc in enumerate(an["tasche"], 1):
        d = tc["dati"]
        c = d.get("centro") or [0, 0]
        if tc["tipo"] == "asola":
            note.append("Asola %s×%s %s, centro (%s; %s), a %s°." % (_num(d["lunghezza"]), _num(d["larghezza"]),
                        "passante" if tc["passante"] else "prof. " + _num(tc["prof"]), _num(c[0]), _num(c[1]), _num(d.get("angolo") or 0)))
        else:
            misura = "Ø" + _num(d["d"]) if d.get("forma") == "cerchio" else "%s×%s" % (_num(d.get("l", 0)), _num(d.get("w", 0)))
            note.append("Tasca %s %s, centro (%s; %s)%s." % (misura, "passante" if tc["passante"] else "prof. " + _num(tc["prof"]),
                        _num(c[0]), _num(c[1]), ", angoli R" + _num(tc["raggio_angoli"]) if tc["raggio_angoli"] else ""))
    for r in an["rialzi"]:
        d = r["dati"]
        c = d.get("centro") or [0, 0]
        misura = "Ø" + _num(d["d"]) if d.get("forma") == "cerchio" else "%s×%s" % (_num(d.get("l", 0)), _num(d.get("w", 0)))
        note.append("Rialzo %s alto %s, centro (%s; %s)." % (misura, _num(r["h"]), _num(c[0]), _num(c[1])))
    for q in an.get("quote_funzionali") or []:
        if q.get("sigla"):
            try:
                lim = iso286_limiti(q["diametro"], q["sigla"])
                note.append("%s tra %s e %s mm: %s." % (lim["testo"], _num(q["da"]), _num(q["a"]), q.get("perche", "")))
            except ValueError:
                pass
        else:
            note.append("Ø%s tra %s e %s mm: %s." % (_num(q["diametro"]), _num(q["da"]), _num(q["a"]), q.get("perche", "")))
    if an["guscio"]:
        note.append("Svuotato con pareti di %s mm (aperto %s)." % (_num(an["guscio"]["spessore"]), an["guscio"]["aperta"]))
    if any(f["tolleranza"] for f in an["fori"]):
        note.append("Fori con tolleranza: controllo con tampone passa/non passa.")
    yn = 66
    t.tx((26, yn + 1), "NOTE", 3, "start", 0, "testo")
    import textwrap
    for i, n in enumerate(note[:12]):
        for k, riga in enumerate(textwrap.wrap("%d. %s" % (i + 1, n), 92)):
            if yn < 16:
                break
            yn -= 4.0 if k else 4.6
            t.tx((26 + (4 if k else 0), yn), riga, 2.6, "start", 0, "testo")

    # ── cartiglio ──
    x0, y0, x1, y1 = 230.0, 10.0, FW - 10, 62.0
    t.rett(x0, y0, x1, y1)
    massa = an["volume"] / 1e6 * m["densita"]
    oggi = datetime.date.today()
    campi = [
        ((x0, y1 - 14, x1, y1), "Denominazione", info.get("nome") or "Pezzo", 5),
        ((x0, y1 - 24, x0 + 90, y1 - 14), "Materiale", m["nome"], 3),
        ((x0 + 90, y1 - 24, x1, y1 - 14), "Trattamento", info.get("trattamento_nome") or "—", 3),
        ((x0, y1 - 34, x0 + 45, y1 - 24), "Scala", scala_txt, 3.5),
        ((x0 + 45, y1 - 34, x0 + 90, y1 - 24), "Formato", "A3", 3.5),
        ((x0 + 90, y1 - 34, x0 + 135, y1 - 24), "Massa", "%s kg" % _num(massa), 3.5),
        ((x0 + 135, y1 - 34, x1, y1 - 24), "Foglio", "1 / 1", 3.5),
        ((x0, y1 - 44, x0 + 60, y1 - 34), "Disegnato", info.get("disegnatore") or "—", 3),
        ((x0 + 60, y1 - 44, x0 + 120, y1 - 34), "Controllato", info.get("controllato") or "", 3),
        ((x0 + 120, y1 - 44, x1, y1 - 34), "Data", oggi.strftime("%d/%m/%Y"), 3),
        ((x0, y0, x0 + 120, y1 - 44), "N. disegno", info.get("numero") or "MCAD-%s" % oggi.strftime("%y%m%d"), 4),
        ((x0 + 120, y0, x0 + 150, y1 - 44), "Rev.", info.get("revisione") or "0", 3.5),
        ((x0 + 150, y0, x1, y1 - 44), "Proiezione", "metodo E", 3),
    ]
    for (a, b, c, d), et, val, h in campi:
        t.rett(a, b, c, d)
        t.tx((a + 1.2, d - 2.6), et, 1.9, "start", 0, "sottile")
        t.tx((a + 2, b + 1.8), val[:60] if h <= 3.5 else val[:40], h, "start", 0, "testo")
    t.tx((x0, y1 + 2), "MASTER CAD AI · disegno generato dal modello 3D — verificare prima della produzione", 2.2, "start", 0, "sottile")
    return {"primitive": t.prim, "scala": scala_txt, "massa_kg": round(massa, 3), "viti": viti, "note": note,
            "tabella_fori": [{"rif": f["rif"], "x": round(f["x"], 3), "y": round(f["y"], 3), "descrizione": descrivi_foro(f, True)} for f in an["fori"]],
            "sezione": xc is not None or yc is not None}


# ── scrittori ──
STILI = {"vis": (0.5, None), "sottile_vis": (0.3, None), "nasc": (0.25, (3, 1.5)), "asse": (0.18, (9, 1.5, 1.5, 1.5)),
         "quota": (0.18, None), "sez": (0.18, None), "cornice": (0.5, None), "sottile": (0.18, None), "testo": (0.25, None)}


def _esc(t):
    return t.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def svg(tav):
    W, H = FOGLIO
    out = ['<svg xmlns="http://www.w3.org/2000/svg" width="%gmm" height="%gmm" viewBox="0 0 %g %g" font-family="Arial, Helvetica, sans-serif">' % (W, H, W, H),
           '<rect width="%g" height="%g" fill="#fff"/>' % (W, H)]
    for p in tav["primitive"]:
        if p["k"] == "pl":
            lw, dash = STILI.get(p["ly"], (0.25, None))
            pts = " ".join("%g,%g" % (x, H - y) for x, y in p["pts"])
            out.append('<polyline points="%s" fill="none" stroke="#000" stroke-width="%g"%s stroke-linecap="round" stroke-linejoin="round"/>' % (
                pts, lw, ' stroke-dasharray="%s"' % " ".join("%g" % d for d in dash) if dash else ""))
        elif p["k"] == "pg":
            out.append('<polygon points="%s" fill="#000"/>' % " ".join("%g,%g" % (x, H - y) for x, y in p["pts"]))
        else:
            x, y = p["p"]
            out.append('<text x="%g" y="%g" font-size="%g" text-anchor="%s"%s>%s</text>' % (
                x, H - y, p["h"], p["al"], ' transform="rotate(%g %g %g)"' % (-p["rot"], x, H - y) if p["rot"] else "", _esc(p["t"])))
    out.append("</svg>")
    return "\n".join(out)


def pdf(tav):
    import io
    from reportlab.lib.units import mm
    from reportlab.pdfgen import canvas
    buf = io.BytesIO()
    c = canvas.Canvas(buf, pagesize=(FOGLIO[0] * mm, FOGLIO[1] * mm))
    c.setTitle("MASTER CAD AI - disegno tecnico")
    c.scale(mm, mm)
    c.setLineCap(1)
    c.setLineJoin(1)
    for p in tav["primitive"]:
        if p["k"] == "pl":
            lw, dash = STILI.get(p["ly"], (0.25, None))
            c.setLineWidth(lw)
            c.setDash(list(dash) if dash else [])
            path = c.beginPath()
            path.moveTo(*p["pts"][0])
            for q in p["pts"][1:]:
                path.lineTo(*q)
            c.drawPath(path, stroke=1, fill=0)
        elif p["k"] == "pg":
            c.setDash([])
            path = c.beginPath()
            path.moveTo(*p["pts"][0])
            for q in p["pts"][1:]:
                path.lineTo(*q)
            path.close()
            c.drawPath(path, stroke=0, fill=1)
        else:
            c.saveState()
            c.translate(*p["p"])
            if p["rot"]:
                c.rotate(p["rot"])
            c.setFont("Helvetica", p["h"] * 1.0)
            fn = {"start": c.drawString, "middle": c.drawCentredString, "end": c.drawRightString}[p["al"]]
            fn(0, 0, p["t"])
            c.restoreState()
    c.showPage()
    c.save()
    return buf.getvalue()


def dxf(tav):
    """DXF R12 a layer separati (VISIBILI, NASCOSTE, ASSI, QUOTE, SEZIONE, TESTI, CORNICE), unità mm."""
    strati = {"vis": ("VISIBILI", 7, "CONTINUOUS"), "sottile_vis": ("ASSONOMETRIA", 8, "CONTINUOUS"), "nasc": ("NASCOSTE", 4, "HIDDEN"),
              "asse": ("ASSI", 1, "CENTER"), "quota": ("QUOTE", 3, "CONTINUOUS"), "sez": ("SEZIONE", 6, "CONTINUOUS"),
              "cornice": ("CORNICE", 7, "CONTINUOUS"), "sottile": ("CORNICE", 7, "CONTINUOUS"), "testo": ("TESTI", 7, "CONTINUOUS")}
    n = lambda v: ("%.4f" % v).rstrip("0").rstrip(".")
    o = ["0", "SECTION", "2", "HEADER", "9", "$INSUNITS", "70", "4", "9", "$LTSCALE", "40", "1", "0", "ENDSEC",
         "0", "SECTION", "2", "TABLES", "0", "TABLE", "2", "LTYPE", "70", "3",
         "0", "LTYPE", "2", "CONTINUOUS", "70", "0", "3", "Continua", "72", "65", "73", "0", "40", "0",
         "0", "LTYPE", "2", "HIDDEN", "70", "0", "3", "Nascosta", "72", "65", "73", "2", "40", "4.5", "49", "3", "49", "-1.5",
         "0", "LTYPE", "2", "CENTER", "70", "0", "3", "Asse", "72", "65", "73", "4", "40", "13.5", "49", "9", "49", "-1.5", "49", "1.5", "49", "-1.5",
         "0", "ENDTAB", "0", "TABLE", "2", "LAYER", "70", str(len(set(strati.values())))]
    for nome, col, lt in sorted(set(strati.values())):
        o += ["0", "LAYER", "2", nome, "70", "0", "62", str(col), "6", lt]
    o += ["0", "ENDTAB", "0", "ENDSEC", "0", "SECTION", "2", "ENTITIES"]
    for p in tav["primitive"]:
        lay = strati.get(p["ly"], ("0", 7, "CONTINUOUS"))[0]
        if p["k"] == "pl":
            if len(p["pts"]) == 2:
                (a, b) = p["pts"]
                o += ["0", "LINE", "8", lay, "10", n(a[0]), "20", n(a[1]), "30", "0", "11", n(b[0]), "21", n(b[1]), "31", "0"]
            else:
                o += ["0", "POLYLINE", "8", lay, "66", "1", "10", "0", "20", "0", "30", "0", "70", "0"]
                for x, y in p["pts"]:
                    o += ["0", "VERTEX", "8", lay, "10", n(x), "20", n(y), "30", "0"]
                o += ["0", "SEQEND", "8", lay]
        elif p["k"] == "pg":
            a, b, c = p["pts"][:3]
            o += ["0", "SOLID", "8", lay, "10", n(a[0]), "20", n(a[1]), "30", "0", "11", n(b[0]), "21", n(b[1]), "31", "0",
                  "12", n(c[0]), "22", n(c[1]), "32", "0", "13", n(c[0]), "23", n(c[1]), "33", "0"]
        else:
            x, y = p["p"]
            al = {"start": "0", "middle": "1", "end": "2"}[p["al"]]
            testo = p["t"].replace("Ø", "%%c").replace("°", "%%d")
            o += ["0", "TEXT", "8", lay, "10", n(x), "20", n(y), "30", "0", "40", n(p["h"] * 0.72), "1", testo, "50", n(p["rot"]), "72", al,
                  "11", n(x), "21", n(y), "31", "0"]
    o += ["0", "ENDSEC", "0", "EOF"]
    return ("\r\n".join(o) + "\r\n").encode("cp1252", "replace")
