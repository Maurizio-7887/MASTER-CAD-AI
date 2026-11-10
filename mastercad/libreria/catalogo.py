"""Libreria di pezzi a norma e pezzi tipo: scegli, scrivi le misure, il progetto è pronto e modificabile.

Le tabelle riportano valori indicativi tratti dalle norme citate: verificarli sulla norma in vigore prima della produzione.
"""

from ..progetto.lavorazioni import LAMATURA, PASSAGGIO, _espandi_fori

# EN 1092-1 tipo 01 (flangia piana da saldare), PN16: DN → D esterno, K interasse fori, n fori, Ø foro, vite, spessore b, Ø interno B1
EN1092_PN16 = {
    15: (95, 65, 4, 14, "M12", 14, 22.0), 20: (105, 75, 4, 14, "M12", 16, 27.5), 25: (115, 85, 4, 14, "M12", 16, 34.5),
    32: (140, 100, 4, 18, "M16", 18, 43.5), 40: (150, 110, 4, 18, "M16", 18, 49.5), 50: (165, 125, 4, 18, "M16", 20, 61.5),
    65: (185, 145, 8, 18, "M16", 20, 77.5), 80: (200, 160, 8, 18, "M16", 20, 90.5), 100: (220, 180, 8, 18, "M16", 22, 116.0),
    125: (250, 210, 8, 18, "M16", 22, 141.5), 150: (285, 240, 8, 22, "M20", 24, 170.5), 200: (340, 295, 12, 22, "M20", 24, 221.5),
}


def _f(v, nome, minimo=0.1, massimo=3000):
    try:
        v = float(v)
    except (TypeError, ValueError):
        raise ValueError("%s: scrivi un numero" % nome) from None
    if not minimo <= v <= massimo:
        raise ValueError("%s fuori dai limiti (%g–%g mm)" % (nome, minimo, massimo))
    return v


def _rett(x0, y0, x1, y1):
    return {"t": "pline", "pts": [[x0, y0], [x1, y0], [x1, y1], [x0, y1]], "closed": True}


def _foro(spec):
    """«M8» → foro di passaggio; «M8F» o «M8 filettato» → filettato; numero → Ø."""
    t = str(spec or "").upper().replace(" ", "").replace(",", ".")
    if t.startswith("M"):
        fil = t.replace("FILETTATO", "F").rstrip("F")
        if t.endswith("F") or "FILETT" in t:
            return {"filetto": fil}
        if fil not in PASSAGGIO:
            raise ValueError("Vite %s non in tabella" % fil)
        return {"d": PASSAGGIO[fil], "_vite": fil}
    return {"d": _f(t, "Diametro dei fori", 0.5, 200)}


CATALOGO = [
    {"codice": "flangia_en1092", "nome": "Flangia EN 1092-1 PN16", "norma": "EN 1092-1 tipo 01 (valori indicativi)",
     "descrizione": "Flangia piana da saldare: diametro, interasse e fori dalla tabella della norma.",
     "campi": [{"nome": "dn", "etichetta": "DN", "tipo": "scelta", "valori": list(EN1092_PN16), "predefinito": 50},
               {"nome": "cieca", "etichetta": "Flangia cieca (senza foro centrale)", "tipo": "si_no", "predefinito": False}]},
    {"codice": "piastra_base", "nome": "Piastra di base forata", "norma": "Fori di passaggio UNI EN 20273, lamature ISO 4762",
     "descrizione": "Piastra rettangolare con 4 fori agli angoli, angoli raggiati, lamature opzionali.",
     "campi": [{"nome": "l", "etichetta": "Lunghezza (mm)", "predefinito": 160}, {"nome": "w", "etichetta": "Larghezza (mm)", "predefinito": 100},
               {"nome": "s", "etichetta": "Spessore (mm)", "predefinito": 15}, {"nome": "foro", "etichetta": "Fori (es. M10, M10F filettati, 9)", "tipo": "testo", "predefinito": "M10"},
               {"nome": "e", "etichetta": "Distanza fori dal bordo (mm)", "predefinito": 15}, {"nome": "r", "etichetta": "Raggio angoli (mm)", "predefinito": 5},
               {"nome": "lamati", "etichetta": "Fori lamati per viti a testa cilindrica", "tipo": "si_no", "predefinito": True}]},
    {"codice": "staffa_l", "nome": "Staffa a L", "norma": "—",
     "descrizione": "Angolare con base forata: due viste (dall'alto e di fronte), fori sulla base.",
     "campi": [{"nome": "base", "etichetta": "Lato base (mm)", "predefinito": 80}, {"nome": "altezza", "etichetta": "Altezza ala (mm)", "predefinito": 60},
               {"nome": "larghezza", "etichetta": "Larghezza (mm)", "predefinito": 50}, {"nome": "s", "etichetta": "Spessore (mm)", "predefinito": 8},
               {"nome": "foro", "etichetta": "Fori sulla base (es. M8, 9)", "tipo": "testo", "predefinito": "M8"},
               {"nome": "r", "etichetta": "Raccordo spigoli (mm, 0 = vivi)", "predefinito": 3}]},
    {"codice": "boccola", "nome": "Boccola", "norma": "Smussi d'imbocco 0,5–1 mm",
     "descrizione": "Boccola cilindrica tornita con smussi alle estremità.",
     "campi": [{"nome": "de", "etichetta": "Ø esterno (mm)", "predefinito": 30}, {"nome": "di", "etichetta": "Ø interno (mm)", "predefinito": 20},
               {"nome": "l", "etichetta": "Lunghezza (mm)", "predefinito": 25}, {"nome": "smusso", "etichetta": "Smusso (mm)", "predefinito": 0.5}]},
    {"codice": "albero", "nome": "Albero a gradini", "norma": "Smussi 45° alle estremità",
     "descrizione": "Perno o albero tornito: scrivi i tratti come Ø×lunghezza, separati da punto e virgola.",
     "campi": [{"nome": "tratti", "etichetta": "Tratti Ø×L (es. 20×30; 30×50; 20×25)", "tipo": "testo", "predefinito": "20x30; 30x50; 25x20"},
               {"nome": "smusso", "etichetta": "Smusso (mm)", "predefinito": 1}]},
]


def genera(codice, p):
    p = p or {}
    voce = next((c for c in CATALOGO if c["codice"] == codice), None)
    if voce is None:
        raise ValueError("Pezzo non in libreria")
    val = {c["nome"]: p.get(c["nome"], c["predefinito"]) for c in voce["campi"]}
    if codice == "flangia_en1092":
        dn = int(_f(val["dn"], "DN", 10, 2000))
        if dn not in EN1092_PN16:
            raise ValueError("DN non in tabella")
        D, K, n, dfo, vite, b, B1 = EN1092_PN16[dn]
        lav = [{"tipo": "serie_polare", "centro": [0, 0], "diametro": K, "n": n, "angolo0": 180 / n, "foro": {"d": dfo}}]
        if not val["cieca"] in (True, "true", "1", 1, "si"):
            lav.insert(0, {"tipo": "foro", "x": 0, "y": 0, "d": B1})
        lav.append({"tipo": "smusso", "d": 1, "spigoli": "superiori"})
        nome = "Flangia %sDN%d PN16" % ("cieca " if val["cieca"] in (True, "true", "1", 1, "si") else "", dn)
        prog = {"base": {"tipo": "estrudi", "entita": [{"t": "circle", "c": [0, 0], "r": D / 2}], "altezza": b}, "lavorazioni": lav}
        note = ["Viti %d× %s (EN 1092-1)" % (n, vite)]
    elif codice == "piastra_base":
        L_, W, s = _f(val["l"], "Lunghezza", 5), _f(val["w"], "Larghezza", 5), _f(val["s"], "Spessore", 1, 500)
        e, r = _f(val["e"], "Distanza dal bordo", 1), _f(val["r"], "Raggio", 0, 500)
        foro = _foro(val["foro"])
        if val["lamati"] in (True, "true", "1", 1, "si") and foro.get("_vite") in LAMATURA:
            dl, pl = LAMATURA[foro["_vite"]]
            if pl < s - 1:
                foro["lamatura"] = {"d": dl, "prof": pl}
        foro.pop("_vite", None)
        lav = [{"tipo": "serie_rett", "origine": [e, e], "nx": 2, "ny": 2, "passo_x": L_ - 2 * e, "passo_y": W - 2 * e, "foro": foro}]
        if r > 0:
            lav.append({"tipo": "raccordo", "r": r, "spigoli": "verticali"})
        lav.append({"tipo": "smusso", "d": 0.5, "spigoli": "superiori"})
        prog = {"base": {"tipo": "estrudi", "entita": [_rett(0, 0, L_, W)], "altezza": s}, "lavorazioni": lav}
        nome, note = "Piastra %g×%g×%g" % (L_, W, s), []
    elif codice == "staffa_l":
        B, H, W, s = _f(val["base"], "Lato base", 5), _f(val["altezza"], "Altezza", 5), _f(val["larghezza"], "Larghezza", 5), _f(val["s"], "Spessore", 1, 100)
        if s >= min(B, H):
            raise ValueError("Lo spessore deve essere minore dei lati")
        foro = _foro(val["foro"])
        foro.pop("_vite", None)
        xf = s + (B - s) / 2
        lav = [{"tipo": "serie_rett", "origine": [xf, W / 4], "nx": 1, "ny": 2, "passo_x": 0, "passo_y": W / 2, "foro": foro}]
        r = _f(val["r"], "Raccordo", 0, 100)
        if r > 0:
            lav.append({"tipo": "raccordo", "r": r, "spigoli": "verticali"})
        prog = {"base": {"tipo": "due_viste", "alto": [_rett(0, 0, B, W)],
                         "fronte": [{"t": "pline", "pts": [[0, 0], [B, 0], [B, s], [s, s], [s, H], [0, H]], "closed": True}]}, "lavorazioni": lav}
        nome, note = "Staffa a L %g×%g×%g" % (B, H, W), ["I fori sull'ala verticale si aggiungono in tavola (foratura orizzontale)."]
    elif codice == "boccola":
        de, di, L_, sm = _f(val["de"], "Ø esterno"), _f(val["di"], "Ø interno", 0.5), _f(val["l"], "Lunghezza"), _f(val["smusso"], "Smusso", 0, 20)
        if di >= de:
            raise ValueError("Il Ø interno deve essere minore dell'esterno")
        prof = [{"t": "pline", "pts": [[0, di / 2], [L_, di / 2], [L_, de / 2], [0, de / 2]], "closed": True}]
        lav = [{"tipo": "smusso", "d": sm, "spigoli": "tutti"}] if sm > 0 else []
        prog = {"base": {"tipo": "rivoluzione", "entita": prof, "asse": [[0, 0], [1, 0]], "angolo": 360}, "lavorazioni": lav}
        nome, note = "Boccola Ø%g/Ø%g×%g" % (de, di, L_), []
    elif codice == "albero":
        tratti = []
        for pezzo in str(val["tratti"]).replace(",", ".").replace("×", "x").replace("X", "x").split(";"):
            if pezzo.strip():
                a, _, b = pezzo.partition("x")
                tratti.append((_f(a, "Diametro del tratto", 1, 1000), _f(b, "Lunghezza del tratto", 0.5, 5000)))
        if not tratti or len(tratti) > 12:
            raise ValueError("Scrivi da 1 a 12 tratti, es. 20×30; 30×50")
        pts, x = [[0, 0]], 0.0
        for d, l in tratti:
            pts += [[x, d / 2], [x + l, d / 2]]
            x += l
        pts.append([x, 0])
        sm = _f(val["smusso"], "Smusso", 0, 20)
        prog = {"base": {"tipo": "rivoluzione", "entita": [{"t": "pline", "pts": pts, "closed": True}], "asse": [[0, 0], [1, 0]], "angolo": 360},
                "lavorazioni": [{"tipo": "smusso", "d": sm, "spigoli": "tutti"}] if sm > 0 else []}
        nome, note = "Albero %s" % " / ".join("Ø%g×%g" % t for t in tratti), []
    prog["nome"] = nome
    return {"progetto": prog, "nome": nome, "note": note, "tavola": entita_tavola(prog)}


def entita_tavola(prog):
    """Entità 2D da mettere sulla tavola di disegno: contorno di base + cerchi dei fori."""
    b = prog["base"]
    ents = [dict(e) for e in (b.get("entita") if b["tipo"] != "due_viste" else b.get("alto")) or []]
    if b["tipo"] != "rivoluzione":
        for lav in prog["lavorazioni"]:
            if lav["tipo"] in ("foro", "serie_polare", "serie_rett"):
                for f in ([lav] if lav["tipo"] == "foro" else _espandi_fori(lav)):
                    d = f.get("d") or float(str(f.get("filetto", "M6"))[1:])
                    ents.append({"t": "circle", "c": [round(f["x"], 4), round(f["y"], 4)], "r": d / 2})
    return ents


def catalogo():
    return [{k: v for k, v in c.items()} for c in CATALOGO]


def _verifica_tabella():
    for dn, (D, K, n, d, vite, b, B1) in EN1092_PN16.items():
        assert D > K + d and K - d > B1, dn
    return True


assert _verifica_tabella()
