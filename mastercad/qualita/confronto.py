"""Controllo qualità con la foto: il pezzo prodotto confrontato con il progetto.

La foto (dall'alto, su foglio A4) dà il contorno e i fori passanti in millimetri; il programma la allinea al disegno
(prova le 4 rotazioni a 90° e poi corregge rotazione e spostamento sui fori) e confronta quota per quota.
Serve a scovare gli errori grossi (foro dimenticato, spostato, diametro sbagliato): non sostituisce calibro e CMM.
"""
import math

import numpy as np

from .. import profili
from ..progetto.analisi import _num


def _misurato(entita):
    cerchi = [e for e in entita if e.get("t") == "circle"]
    altri = [e for e in entita if e.get("t") != "circle"]
    if altri:
        est = profili.estensione_entita(altri)
        fori = cerchi
    else:      # pezzo tondo: il cerchio più grande è il contorno
        grande = max(cerchi, key=lambda e: e["r"])
        est = (grande["c"][0] - grande["r"], grande["c"][1] - grande["r"], grande["c"][0] + grande["r"], grande["c"][1] + grande["r"])
        fori = [c for c in cerchi if c is not grande]
    return est, [(c["c"][0], c["c"][1], 2 * c["r"]) for c in fori]


def _abbina(nom, mis):
    """Abbinamento goloso per distanza crescente: ogni foro misurato va a un solo foro nominale."""
    coppie, usati_n, usati_m = [], set(), set()
    cand = sorted(((math.hypot(a[0] - b[0], a[1] - b[1]), i, j) for i, a in enumerate(nom) for j, b in enumerate(mis)))
    for d, i, j in cand:
        if i in usati_n or j in usati_m:
            continue
        coppie.append((i, j, d))
        usati_n.add(i)
        usati_m.add(j)
    return coppie


def _trasforma(pts, ang, centro_da, centro_a):
    c, s = math.cos(ang), math.sin(ang)
    return [(centro_a[0] + (x - centro_da[0]) * c - (y - centro_da[1]) * s,
             centro_a[1] + (x - centro_da[0]) * s + (y - centro_da[1]) * c) + tuple(r) for x, y, *r in pts]


def confronta(an, entita_foto, tol_pos=0.5, tol_d=0.4, tol_ingombro=0.8):
    ing = an["ingombro"]
    est, fori_m = _misurato(entita_foto)
    nom = [(f["x"], f["y"], f["d_punta"] if f["filetto"] else f["d"], f) for f in an["fori"] if f["passante"] and not f["svasatura"]]
    cn = ((ing["xmin"] + ing["xmax"]) / 2, (ing["ymin"] + ing["ymax"]) / 2)
    cm = ((est[0] + est[2]) / 2, (est[1] + est[3]) / 2)
    migliore = None
    for k in range(4):
        ang = k * math.pi / 2
        mis = _trasforma(fori_m, ang, cm, cn)
        coppie = _abbina(nom, mis)
        costo = sum(min(d, 20) for _, _, d in coppie) + 20 * (abs(len(nom) - len(mis)))
        w, h = (est[2] - est[0], est[3] - est[1]) if k % 2 == 0 else (est[3] - est[1], est[2] - est[0])
        costo += abs(w - ing["x"]) + abs(h - ing["y"])
        if migliore is None or costo < migliore[0]:
            migliore = (costo, ang, mis, (w, h))
    _, ang, mis, (w, h) = migliore
    coppie = _abbina(nom, mis)
    def kabsch(coppie_buone, punti):
        A = np.array([nom[i][:2] for i, _ in coppie_buone])
        B = np.array([punti[j][:2] for _, j in coppie_buone])
        ca, cb = A.mean(0), B.mean(0)
        U, _, Vt = np.linalg.svd((B - cb).T @ (A - ca))
        R = (U @ Vt).T
        if np.linalg.det(R) < 0:
            Vt[-1] *= -1
            R = (U @ Vt).T
        return [tuple((R @ (np.array(p[:2]) - cb) + ca).tolist()) + tuple(p[2:]) for p in punti]

    # rifinitura: rotazione e spostamento che sovrappongono meglio i fori (Kabsch 2D), poi di nuovo
    # senza i fori fuori posto, così un foro sbagliato non «trascina» gli altri
    base = mis
    buone = [(i, j) for i, j, d in coppie if d < 5]
    if len(buone) >= 2:
        mis = kabsch(buone, base)
        coppie = _abbina(nom, mis)
        affidabili = [(i, j) for i, j, d in coppie if d <= tol_pos]
        if 2 <= len(affidabili) < len(buone):
            mis = kabsch(affidabili, base)
            coppie = _abbina(nom, mis)
    righe = []

    def riga(voce, nominale, misurato, scost, tol, esito, nota=""):
        righe.append({"voce": voce, "nominale": nominale, "misurato": misurato, "scostamento": scost, "tolleranza": tol, "esito": esito, "nota": nota})

    for nome, vn, vm in (("Ingombro X", ing["x"], w), ("Ingombro Y", ing["y"], h)):
        dv = vm - vn
        riga(nome, _num(vn), _num(vm), ("+" if dv >= 0 else "") + _num(dv), "±" + _num(tol_ingombro), "OK" if abs(dv) <= tol_ingombro else "KO")
    abbinati = {i: (j, d) for i, j, d in coppie if d <= max(3.0, 6 * tol_pos)}
    for i, (x, y, d, f) in enumerate(nom):
        voce = "Foro %d (Ø%s%s)" % (f["rif"], _num(d), " preforo " + f["filetto"] if f["filetto"] else "")
        if i not in abbinati:
            riga(voce, "X%s Y%s Ø%s" % (_num(x), _num(y), _num(d)), "—", "—", "", "KO", "Foro mancante o non visibile nella foto")
            continue
        j, dist = abbinati[i]
        xm, ym, dm = mis[j]
        dd = dm - d
        ok = dist <= tol_pos and abs(dd) <= tol_d
        riga(voce, "X%s Y%s Ø%s" % (_num(x), _num(y), _num(d)), "X%s Y%s Ø%s" % (_num(xm), _num(ym), _num(dm)),
             "pos %s · Ø %s%s" % (_num(dist), "+" if dd >= 0 else "", _num(dd)), "pos %s · Ø ±%s" % (_num(tol_pos), _num(tol_d)),
             "OK" if ok else "KO", "" if ok else ("Spostato" if dist > tol_pos else "") + (" Diametro" if abs(dd) > tol_d else ""))
    usati = {j for j, _ in abbinati.values()}
    for j, (xm, ym, dm) in enumerate(mis):
        if j not in usati:
            riga("Foro non a disegno", "—", "X%s Y%s Ø%s" % (_num(xm), _num(ym), _num(dm)), "—", "", "KO", "Foro in più (o ombra/riflesso nella foto)")
    esito = "CONFORME" if all(r["esito"] == "OK" for r in righe) else "NON CONFORME"
    return {"esito": esito, "righe": righe, "rotazione": round(math.degrees(ang)) % 360,
            "sovrapposizione": _svg(an, mis, nom, abbinati),
            "limiti": "Controllo con foto: precisione ±0,5–1 mm. Si vedono solo contorno e fori passanti; filetti, lamature e quote in altezza vanno controllati con gli strumenti."}


def _svg(an, mis, nom, abbinati):
    ing = an["ingombro"]
    m = 12
    x0, y0, W, H = ing["xmin"] - m, ing["ymin"] - m, ing["x"] + 2 * m, ing["y"] + 2 * m
    k = max(W, H) / 400
    out = ['<svg xmlns="http://www.w3.org/2000/svg" viewBox="%g %g %g %g" width="100%%">' % (x0, -(y0 + H), W, H),
           '<rect x="%g" y="%g" width="%g" height="%g" fill="#fff"/>' % (x0, -(y0 + H), W, H),
           '<rect x="%g" y="%g" width="%g" height="%g" fill="none" stroke="#1b8a4a" stroke-width="%g"/>' % (ing["xmin"], -ing["ymax"], ing["x"], ing["y"], 1.5 * k)]
    for i, (x, y, d, f) in enumerate(nom):
        out.append('<circle cx="%g" cy="%g" r="%g" fill="none" stroke="#1b8a4a" stroke-width="%g"/>' % (x, -y, d / 2, 1.5 * k))
        out.append('<text x="%g" y="%g" font-size="%g" fill="#1b8a4a">%d</text>' % (x + d / 2 + 1, -y - d / 2, 9 * k, f["rif"]))
    for j, (x, y, d) in enumerate(mis):
        out.append('<circle cx="%g" cy="%g" r="%g" fill="none" stroke="#d0342c" stroke-width="%g" stroke-dasharray="%g %g"/>' % (x, -y, d / 2, 1.5 * k, 4 * k, 2 * k))
    out.append("</svg>")
    return "".join(out)
