"""Correzione automatica di una consegna: il pezzo dell'allievo confrontato con la soluzione del docente.

Il voto (0–10) viene da quattro misure semplici e spiegate all'allievo:
  40% sovrapposizione dei volumi (quanto i due pezzi coincidono, dopo averli centrati),
  25% fori giusti (posizione entro 1 mm, diametro entro 0,2 mm),
  15% ingombri (lunghezza, larghezza, altezza),
  20% lavorazioni presenti (tasche, asole, rialzi, raccordi, smussi, guscio).
Il docente può sempre cambiare il voto e scrivere un commento.
"""
import math

import cadquery as cq

from ..progetto.analisi import _num, analizza, descrivi_foro


def valuta(riferimento, consegna):
    ar = analizza(riferimento)
    try:
        ac = analizza(consegna)
    except ValueError as exc:
        return {"voto": 0.0, "punteggi": {"volume": 0, "fori": 0, "ingombro": 0}, "messaggi": ["Il pezzo non si costruisce: %s" % exc]}
    ir, ic = ar["ingombro"], ac["ingombro"]
    cr = cq.Vector((ir["xmin"] + ir["xmax"]) / 2, (ir["ymin"] + ir["ymax"]) / 2, ir["zmin"])
    cc = cq.Vector((ic["xmin"] + ic["xmax"]) / 2, (ic["ymin"] + ic["ymax"]) / 2, ic["zmin"])
    spost = cr - cc
    sc = ac["solido"].translate(spost)
    try:
        inter = ar["solido"].intersect(sc).Volume()
    except Exception:
        inter = 0.0
    vr, vc = ar["volume"], ac["volume"]
    iou = inter / max(vr + vc - inter, 1e-9)
    messaggi = []
    for asse, nome in (("x", "Lunghezza (X)"), ("y", "Larghezza (Y)"), ("z", "Altezza (Z)")):
        d = ic[asse] - ir[asse]
        if abs(d) > 0.2:
            messaggi.append("%s: %s mm invece di %s mm (%s%s)." % (nome, _num(ic[asse]), _num(ir[asse]), "+" if d > 0 else "", _num(d)))
    tot = ir["x"] + ir["y"] + ir["z"]
    errore_ing = sum(abs(ic[a] - ir[a]) for a in "xyz") / max(tot, 1e-9)
    p_ing = max(0.0, 1 - errore_ing * 10)
    # fori: posizione dopo lo stesso spostamento, diametro
    fr = ar["fori"]
    fc = [dict(f, x=f["x"] + spost.x, y=f["y"] + spost.y) for f in ac["fori"]]
    usati, giusti = set(), 0
    for f in fr:
        cand = [(math.hypot(f["x"] - g["x"], f["y"] - g["y"]), j) for j, g in enumerate(fc) if j not in usati]
        if not cand or min(cand)[0] > 1.0:
            messaggi.append("Manca il foro %s in (%s; %s)." % (descrivi_foro(f), _num(f["x"]), _num(f["y"])))
            continue
        dist, j = min(cand)
        usati.add(j)
        g = fc[j]
        if abs(g["d"] - f["d"]) > 0.2 or (g["filetto"] or "") != (f["filetto"] or ""):
            messaggi.append("Foro in (%s; %s): hai fatto %s, serviva %s." % (_num(f["x"]), _num(f["y"]), descrivi_foro(g), descrivi_foro(f)))
            continue
        if bool(g["lamatura"]) != bool(f["lamatura"]):
            messaggi.append("Foro in (%s; %s): %s la lamatura." % (_num(f["x"]), _num(f["y"]), "manca" if f["lamatura"] else "non serviva"))
            continue
        giusti += 1
    extra = len(fc) - len(usati)
    if extra:
        messaggi.append("Ci sono %d fori in più rispetto al disegno." % extra)
    p_fori = 1.0 if not fr and not fc else giusti / max(len(fr) + extra, 1)
    if abs(vc - vr) / max(vr, 1e-9) > 0.02:
        messaggi.append("Il volume è %s del %s%%: %s" % ("maggiore" if vc > vr else "minore", _num(abs(vc - vr) / vr * 100),
                        "manca qualche tasca, asola o svuotatura?" if vc > vr else "hai tolto troppo materiale?"))
    # lavorazioni presenti: tasche, asole, rialzi, raccordi, smussi, guscio
    def conta(an):
        c = {}
        for t in an["tasche"]:
            c[t["tipo"]] = c.get(t["tipo"], 0) + 1
        for r in an["rialzi"]:
            c["rialzo"] = c.get("rialzo", 0) + 1
        for sp in an["spigoli"]:
            c[sp["tipo"]] = c.get(sp["tipo"], 0) + 1
        if an["guscio"]:
            c["guscio"] = 1
        return c
    NOMI = {"tasca": "tasche", "asola": "asole", "rialzo": "rialzi", "raccordo": "raccordi", "smusso": "smussi", "guscio": "guscio"}
    cr_, cc_ = conta(ar), conta(ac)
    attese = sum(cr_.values())
    giuste_l = sum(min(cr_.get(k, 0), cc_.get(k, 0)) for k in cr_)
    for k in sorted(set(cr_) | set(cc_)):
        if cr_.get(k, 0) != cc_.get(k, 0):
            messaggi.append("%s: ne hai fatte %d, ne servivano %d." % (NOMI.get(k, k).capitalize(), cc_.get(k, 0), cr_.get(k, 0)))
    extra_l = max(0, sum(cc_.values()) - giuste_l)
    p_lav = 1.0 if not attese and not extra_l else giuste_l / max(attese + extra_l, 1)
    p_vol = max(0.0, 1 - (1 - iou) * 5)          # il 2% di volume in meno costa già un punto su dieci
    voto = round((0.4 * p_vol + 0.25 * p_fori + 0.15 * p_ing + 0.2 * p_lav) * 10 * 2) / 2
    if not messaggi:
        messaggi.append("Pezzo identico alla soluzione: ottimo lavoro!")
    return {"voto": voto, "punteggi": {"volume": round(iou * 100, 1), "fori": round(p_fori * 100, 1), "ingombro": round(p_ing * 100, 1),
                                       "lavorazioni": round(p_lav * 100, 1)},
            "messaggi": messaggi, "fori_giusti": giusti, "fori_attesi": len(fr)}
