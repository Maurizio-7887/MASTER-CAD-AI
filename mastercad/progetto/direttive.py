"""Le indicazioni del tecnico, in italiano, trasformate in lavorazioni del progetto.

Esempio: «spessore 15, foro centrale Ø30 H7 con lamatura Ø40 profonda 5, 4 fori M8 passanti lamati su interasse 70,
tasca 40x20 profonda 6 in 30,50 raggio 4, asola 40x10 verticale in 130,50, rialzo Ø90 alto 5, raccordo R3 spigoli verticali,
smusso 1 bordi superiori, lunghezza totale 160».
Interprete a regole, deterministico: nessun codice generato. Quello che non capisce lo restituisce, non lo inventa.
I fori trovati nella foto (origine «foto») vengono corretti con le misure nominali date dal tecnico.
"""
import copy
import math
import re

from .. import profili
from .lavorazioni import LAMATURA, PASSAGGIO, PREFORO

NUM = r"(\d+(?:[.,]\d+)?)"
ORDINE = {"rialzo": 0, "tasca": 1, "asola": 2, "foro": 3, "serie_polare": 3, "serie_rett": 3, "raccordo": 5, "smusso": 6, "guscio": 7}


def _f(x):
    return float(str(x).replace(",", "."))


def _cerca(pattern, testo):
    m = re.search(pattern, testo)
    return m


def _ingombro(prog):
    """Ingombro esatto (xmin, ymin, xmax, ymax) del disegno di base: cerchi e archi con il loro raggio vero."""
    b = prog.get("base") or {}
    ents = b.get("entita") or b.get("alto")
    if not ents:
        return None
    xs, ys = [], []
    for e in ents:
        t = e.get("t")
        if t == "circle":
            xs += [e["c"][0] - e["r"], e["c"][0] + e["r"]]; ys += [e["c"][1] - e["r"], e["c"][1] + e["r"]]
        elif t == "arc":
            a0, a1 = e["a0"] % 360, e["a1"] % 360
            span = (a1 - a0) % 360 or 360
            angoli = [a0, a0 + span] + [q for q in (0, 90, 180, 270, 360, 450, 540, 630) if a0 < q < a0 + span]
            for a in angoli:
                xs.append(e["c"][0] + e["r"] * math.cos(math.radians(a))); ys.append(e["c"][1] + e["r"] * math.sin(math.radians(a)))
        elif t == "line":
            xs += [e["a"][0], e["b"][0]]; ys += [e["a"][1], e["b"][1]]
        elif t == "pline":
            xs += [p[0] for p in e["pts"]]; ys += [p[1] for p in e["pts"]]
    return (min(xs), min(ys), max(xs), max(ys)) if xs else None


def _centro(prog):
    e = _ingombro(prog)
    return [(e[0] + e[2]) / 2, (e[1] + e[3]) / 2] if e else [0.0, 0.0]


def _posizione(cl, prog):
    m = _cerca(r"\b(?:in|a|posizione|centro)\s*(?:x\s*=?\s*)?(-?" + NUM[1:-1] + r")\s*[,;/ ]\s*(?:y\s*=?\s*)?(-?" + NUM[1:-1] + r")\b", cl)
    if m:
        p = [_f(m.group(1)), _f(m.group(2))]
        if re.search(r"dal\s+centro|rispetto\s+al\s+centro", cl):     # quota presa dal centro del pezzo
            c = _centro(prog)
            p = [p[0] + c[0], p[1] + c[1]]
        return p
    return _centro(prog)


def _diametro(cl):
    m = _cerca(r"(?:ø|⌀|diametro|diam\.?|d\.|da)\s*" + NUM, cl) or _cerca(r"\b" + NUM + r"\s*mm\b", cl)
    return _f(m.group(1)) if m else None


def _profondita(cl):
    if re.search(r"passant", cl):
        return None
    m = _cerca(r"(?:profond[aoi]?|prof\.?|cieco|cieca)\s*(?:di\s*)?" + NUM, cl)
    return _f(m.group(1)) if m else None


def _spec_foro(cl, d_default=None):
    """Diametro, filetto, lamatura, svasatura e profondità da una frase."""
    spec, note = {}, []
    m = _cerca(r"\bm\s?(\d{1,2}(?:[.,]5)?)\b", cl)
    vite = ("M" + m.group(1).replace(",", ".")) if m else None
    if vite and re.search(r"filett|maschi", cl) and vite in PREFORO:
        spec["filetto"] = vite
    elif vite and vite in PASSAGGIO:
        spec["d"] = PASSAGGIO[vite]
        note.append("passaggio vite %s Ø%g" % (vite, PASSAGGIO[vite]))
        if re.search(r"lamat", cl) and not re.search(r"lamatura\s*(?:ø|⌀|diametro|da)?\s*\d", cl):
            dl, pl = LAMATURA[vite]
            spec["lamatura"] = {"d": dl, "prof": pl}
            note.append("lamatura per testa cilindrica Ø%g×%g" % (dl, pl))
    if "d" not in spec and "filetto" not in spec:
        testa = re.split(r"lamatur|svasatur|interasse|primitiv|su\s+(?:un\s+)?(?:diametro|circonferenza)", cl)[0]
        d = _diametro(testa)
        if d is None:
            m2 = _cerca(r"fori?\s+(?:da\s+)?" + NUM, testa)
            d = _f(m2.group(1)) if m2 else d_default
        if d is not None:
            spec["d"] = d
    m = _cerca(r"lamatura\s*(?:ø|⌀|diametro|da)?\s*" + NUM + r"(?:\s*(?:x|×|profonda|prof\.?|per)\s*" + NUM + r")?", cl)
    if m:
        spec["lamatura"] = {"d": _f(m.group(1)), "prof": _f(m.group(2)) if m.group(2) else 5.0}
    if re.search(r"svasat", cl):
        m = _cerca(r"svasat\w*\s*(?:ø|⌀|diametro|da)?\s*" + NUM, cl)
        ma = _cerca(NUM + r"\s*°", cl)
        base_d = spec.get("d") or PREFORO.get(spec.get("filetto"), 6)
        spec["svasatura"] = {"d": _f(m.group(1)) if m else round(base_d * 2, 1), "angolo": _f(ma.group(1)) if ma else 90}
    p = _profondita(re.split(r"lamatur|svasatur", cl)[0])
    if p is not None:
        spec["prof"] = p
    if re.search(r"\bh7\b|\bh8\b|\bh6\b|tolleranz", cl):
        t = _cerca(r"\b(h\d)\b", cl)
        spec["tolleranza"] = t.group(1).upper() if t else "indicata"
    if re.search(r"da\s+sotto|dal\s+basso", cl):
        spec["da_sotto"] = True
    return spec, note


def _fori_foto(prog):
    return [l for l in prog["lavorazioni"] if l.get("tipo") == "foro" and l.get("origine") in ("foto", "disegno")]


def _scala(prog, k, capito):
    def sc(p):
        return [round(p[0] * k, 4), round(p[1] * k, 4)]
    b = prog["base"]
    for chiave in ("entita", "alto", "fronte", "lato"):
        for e in b.get(chiave) or []:
            for c in ("a", "b", "c"):
                if c in e:
                    e[c] = sc(e[c])
            if "r" in e:
                e["r"] = round(e["r"] * k, 4)
            if "pts" in e:
                e["pts"] = [sc(p) for p in e["pts"]]
    for l in prog["lavorazioni"]:
        if l.get("origine") in ("foto", "disegno"):
            l["x"], l["y"], l["d"] = round(l["x"] * k, 4), round(l["y"] * k, 4), round(l["d"] * k, 3)
    capito.append("Scala corretta ×%.4f per rispettare la misura data" % k)


def applica(testo, progetto):
    prog = copy.deepcopy(progetto) if isinstance(progetto, dict) else {}
    prog.setdefault("lavorazioni", [])
    if not prog.get("base"):
        raise ValueError("Prima serve la forma di base: una foto o un disegno da estrudere")
    t = (testo or "").lower().replace("ø", " ø ").replace("⌀", " ø ")
    if len(t) > 4000:
        raise ValueError("Indicazioni troppo lunghe")
    frasi = [x.strip() for x in re.split(r"[;\n]|,(?!-?\d)|\.(?=\s|$)", t) if x.strip()]
    capito, non_capito, nuove = [], [], []
    ultimo_gruppo = []        # fori dell'ultima frase: «lamatura …» da sola si applica a quelli
    for cl in frasi:
        fatto = False
        # misure d'ingombro: correggono la scala della foto
        m = _cerca(r"\b(lunghezza|larghezza)\s*(?:totale|massima|esterna)?\s*(?:di\s*)?" + NUM, cl)
        if m and not re.search(r"tasca|asola|rialzo|scanalat", cl):
            e = _ingombro(prog)
            if e:
                attuale = (e[2] - e[0]) if m.group(1) == "lunghezza" else (e[3] - e[1])
                if attuale > 0 and abs(_f(m.group(2)) / attuale - 1) > 1e-4:
                    _scala(prog, _f(m.group(2)) / attuale, capito)
                else:
                    capito.append("%s già %g mm" % (m.group(1).capitalize(), _f(m.group(2))))
                fatto = True
        m = _cerca(r"diametro\s+(?:esterno|esterna|max|massimo|del pezzo)\s*(?:di\s*)?(?:ø\s*)?" + NUM, cl)
        if m:
            e = _ingombro(prog)
            if e and (e[2] - e[0]) > 0:
                k = _f(m.group(1)) / (e[2] - e[0])
                if abs(k - 1) > 1e-4:
                    _scala(prog, k, capito)
                capito.append("Diametro esterno %g mm" % _f(m.group(1)))
            fatto = True
        m = None if fatto else _cerca(r"\b(spessore|altezza)\s*(?:del pezzo|totale|piastra)?\s*(?:di\s*)?" + NUM, cl)
        if m and not re.search(r"guscio|parete|rialzo|tasca|lamatura", cl):
            if prog["base"].get("tipo") == "estrudi":
                prog["base"]["altezza"] = _f(m.group(2))
                capito.append("Spessore del pezzo %g mm" % _f(m.group(2)))
            else:
                capito.append("Spessore %g: con la base %s si ricava dalle viste" % (_f(m.group(2)), prog["base"].get("tipo")))
            fatto = True
        if re.search(r"\bguscio|svuot", cl):
            m = _cerca(r"(?:spessore|parete|pareti)\s*(?:di\s*)?" + NUM, cl) or _cerca(NUM, cl)
            if m:
                aperta = "sotto" if re.search(r"aperto\s+sotto|dal\s+basso", cl) else "nessuna" if re.search(r"chius", cl) else "sopra"
                nuove.append({"tipo": "guscio", "spessore": _f(m.group(1)), "aperta": aperta}); capito.append("Guscio spessore %g, aperto %s" % (_f(m.group(1)), aperta)); fatto = True
        elif re.search(r"\braccord", cl):
            m = _cerca(r"\br\s?" + NUM, cl) or _cerca(r"raggio\s*" + NUM, cl) or _cerca(r"raccord\w*\s*(?:di|da)?\s*" + NUM, cl)
            if m:
                dove = "superiori" if re.search(r"superior|sopra", cl) else "inferiori" if re.search(r"inferior|sotto", cl) else "tutti" if re.search(r"tutt", cl) else "verticali"
                nuove.append({"tipo": "raccordo", "r": _f(m.group(1)), "spigoli": dove}); capito.append("Raccordo R%g sugli spigoli %s" % (_f(m.group(1)), dove)); fatto = True
        elif re.search(r"\bsmuss", cl) and not re.search(r"\bfor", cl):
            m = _cerca(r"smuss\w*\s*(?:di|da)?\s*" + NUM, cl) or _cerca(NUM, cl)
            if m:
                dove = "verticali" if re.search(r"vertical", cl) else "inferiori" if re.search(r"inferior|sotto", cl) else "tutti" if re.search(r"tutt", cl) else "superiori"
                nuove.append({"tipo": "smusso", "d": _f(m.group(1)), "spigoli": dove}); capito.append("Smusso %g×45° sugli spigoli %s" % (_f(m.group(1)), dove)); fatto = True
        elif re.search(r"\btasca|\bcava\b|\bscasso", cl):
            prof = _profondita(cl)
            pos = _posizione(cl, prog)
            m = _cerca(NUM + r"\s*[x×]\s*" + NUM, cl)
            ra = _cerca(r"(?:raggio|r)\s?" + NUM, cl)
            if m:
                l = {"tipo": "tasca", "forma": "rett", "centro": pos, "l": _f(m.group(1)), "w": _f(m.group(2)), "prof": prof}
                if ra: l["raggio_angoli"] = _f(ra.group(1))
                nuove.append(l); capito.append("Tasca %gx%g %s in %g,%g" % (l["l"], l["w"], "passante" if prof is None else "profonda %g" % prof, pos[0], pos[1])); fatto = True
            else:
                d = _diametro(cl)
                if d:
                    nuove.append({"tipo": "tasca", "forma": "cerchio", "centro": pos, "d": d, "prof": prof}); capito.append("Tasca tonda Ø%g" % d); fatto = True
        elif re.search(r"\basol|\bscanalat", cl):
            m = _cerca(NUM + r"\s*[x×]\s*" + NUM, cl)
            if m:
                ang = 90 if re.search(r"vertical", cl) else 0
                ma = _cerca(r"a\s*" + NUM + r"\s*°", cl)
                if ma: ang = _f(ma.group(1))
                L, W = sorted([_f(m.group(1)), _f(m.group(2))], reverse=True)
                pos = _posizione(cl, prog)
                nuove.append({"tipo": "asola", "centro": pos, "lunghezza": L, "larghezza": W, "angolo": ang, "prof": _profondita(cl)})
                capito.append("Asola %gx%g a %g° in %g,%g" % (L, W, ang, pos[0], pos[1])); fatto = True
        elif re.search(r"\brialz|\bborchi|\bmozzo|\bspallament", cl):
            mh = _cerca(r"(?:alt[oa]|altezza|h)\s*" + NUM, cl)
            pos = _posizione(cl, prog)
            m = _cerca(NUM + r"\s*[x×]\s*" + NUM, cl)
            if mh and m:
                nuove.append({"tipo": "rialzo", "forma": "rett", "centro": pos, "l": _f(m.group(1)), "w": _f(m.group(2)), "h": _f(mh.group(1))}); capito.append("Rialzo %gx%g alto %g" % (_f(m.group(1)), _f(m.group(2)), _f(mh.group(1)))); fatto = True
            elif mh and _diametro(cl.replace(mh.group(0), "")):
                d = _diametro(cl.replace(mh.group(0), ""))
                nuove.append({"tipo": "rialzo", "forma": "cerchio", "centro": pos, "d": d, "h": _f(mh.group(1))}); capito.append("Rialzo tondo Ø%g alto %g" % (d, _f(mh.group(1)))); fatto = True
        elif re.search(r"\bfor[oi]\b|\bfilett|\bmaschi", cl) or (re.search(r"lamatur|svasat", cl) and ultimo_gruppo):
            spec, note = _spec_foro(cl)
            solo_finitura = not re.search(r"\bfor[oi]\b|\bfilett|\bmaschi", cl)
            if solo_finitura:
                for l in ultimo_gruppo:
                    tgt = l.get("foro") if l.get("tipo") != "foro" else l
                    for k in ("lamatura", "svasatura"):
                        if k in spec: tgt[k] = spec[k]
                capito.append("Finitura applicata ai fori precedenti: " + ", ".join(k for k in ("lamatura", "svasatura") if k in spec)); fatto = True
            elif re.search(r"centrale|al centro|\bmozzo\b", cl):
                c = _posizione(cl, prog) if re.search(r"\bin\s*-?\d", cl) else _centro(prog)
                fotof = _fori_foto(prog)
                vicino = min(fotof, key=lambda l: math.hypot(l["x"] - c[0], l["y"] - c[1]), default=None)
                if vicino and math.hypot(vicino["x"] - c[0], vicino["y"] - c[1]) < max(5, vicino["d"]):
                    misurato = vicino["d"]; vicino.update(spec); vicino["origine"] = "foto+tecnico"; ultimo_gruppo = [vicino]
                    vicino["x"], vicino["y"] = c[0], c[1]       # «centrale» vuol dire in asse, non dove l'ha visto la foto
                    capito.append("Foro centrale: Ø%s nominale (dalla foto %.2f)%s" % (spec.get("d", spec.get("filetto")), misurato, " " + ", ".join(note) if note else ""))
                else:
                    l = dict(spec, tipo="foro", x=c[0], y=c[1]); nuove.append(l); ultimo_gruppo = [l]
                    capito.append("Foro centrale aggiunto Ø%s in %g,%g" % (spec.get("d", spec.get("filetto")), c[0], c[1]))
                fatto = True
            else:
                mn = _cerca(r"(\d+)\s+fori", cl)
                n = int(mn.group(1)) if mn else None
                mi = _cerca(r"(?:interasse|primitivo|su\s+(?:un\s+)?(?:diametro|circonferenza)(?:\s+di)?)\s*(?:ø|di)?\s*" + NUM, cl)
                mr = _cerca(r"(\d+)\s*[x×]\s*(\d+)\s+fori|(?:passo|interassi?)\s*" + NUM + r"\s*[x×]\s*" + NUM, cl)
                fotof = [l for l in _fori_foto(prog) if not re.search(r"centrale", str(l.get("nota", "")))]
                c0 = _centro(prog)
                # escludi dai fori della foto quello al centro (se c'è): è il foro centrale
                fotof = [l for l in fotof if math.hypot(l["x"] - c0[0], l["y"] - c0[1]) > max(3, l["d"])]
                if mi and n:
                    cen = _centro(prog)
                    a0 = 0.0
                    if fotof and len(fotof) == n:      # la foto dà l'orientamento della corona di fori
                        a0 = math.degrees(math.atan2(fotof[0]["y"] - cen[1], fotof[0]["x"] - cen[0]))
                        a0 = round(a0 / 15) * 15 if abs(a0 - round(a0 / 15) * 15) < 4 else a0   # la foto è storta di qualche grado
                        for l in fotof: prog["lavorazioni"].remove(l)
                        capito.append("I %d fori rilevati sostituiti dalla serie esatta" % n)
                    s = {"tipo": "serie_polare", "centro": cen, "diametro": _f(mi.group(1)), "n": n, "angolo0": round(a0, 3), "foro": spec}
                    nuove.append(s); ultimo_gruppo = [s]
                    capito.append("Serie polare: %d fori %s su interasse Ø%g" % (n, spec.get("filetto") or "Ø%g" % spec.get("d", 0), _f(mi.group(1)))); fatto = True
                elif mr and (mr.group(1) or mr.group(3)):
                    m2 = _cerca(r"(\d+)\s*[x×]\s*(\d+)\s+fori", cl); mp = _cerca(r"(?:passo|interassi?)\s*" + NUM + r"\s*[x×]\s*" + NUM, cl)
                    nx, ny = (int(m2.group(1)), int(m2.group(2))) if m2 else (2, 2)
                    px, py = (_f(mp.group(1)), _f(mp.group(2))) if mp else (0, 0)
                    cen = _centro(prog)
                    s = {"tipo": "serie_rett", "origine": [cen[0] - px * (nx - 1) / 2, cen[1] - py * (ny - 1) / 2], "nx": nx, "ny": ny, "passo_x": px, "passo_y": py, "foro": spec}
                    nuove.append(s); ultimo_gruppo = [s]; capito.append("Serie rettangolare %dx%d fori, passo %gx%g, centrata" % (nx, ny, px, py)); fatto = True
                elif fotof and (n is None or n == len(fotof)) and spec:
                    for l in fotof:
                        l.update(spec); l["origine"] = "foto+tecnico"
                    ultimo_gruppo = fotof
                    capito.append("%d fori rilevati portati a %s%s" % (len(fotof), spec.get("filetto") or "Ø%g" % spec.get("d", 0), (" (" + ", ".join(note) + ")") if note else "")); fatto = True
                elif spec and re.search(r"\bin\s*-?\d", cl):
                    pos = _posizione(cl, prog); l = dict(spec, tipo="foro", x=pos[0], y=pos[1]); nuove.append(l); ultimo_gruppo = [l]
                    capito.append("Foro %s in %g,%g" % (spec.get("filetto") or "Ø%g" % spec.get("d", 0), pos[0], pos[1])); fatto = True
                elif n and fotof and n != len(fotof):
                    non_capito.append("«%s»: la foto ha %d fori, non %d. Indica l'interasse (es. «su interasse 70») per crearli esatti" % (cl, len(fotof), n)); fatto = True
        if not fatto and not re.fullmatch(r"(e|con|poi)?", cl):
            non_capito.append(cl)
    prog["lavorazioni"].extend(nuove)
    prog["lavorazioni"].sort(key=lambda l: ORDINE.get(l.get("tipo"), 4))
    return {"progetto": prog, "capito": capito, "non_capito": non_capito}


def da_foto(entita, altezza=10):
    """Risultato del reverse engineering → progetto: contorno come base, cerchi interni come fori modificabili."""
    regs, _ = profili.regioni(entita)
    if not regs:
        raise ValueError("Nessun contorno nella foto")
    esterno_area = max(r["esterno"]["area"] for r in regs)
    base_ent, fori = [], []
    for e in entita:
        if e.get("t") == "circle":
            area = math.pi * e["r"] ** 2
            if area < esterno_area * 0.95:
                fori.append({"tipo": "foro", "x": e["c"][0], "y": e["c"][1], "d": round(2 * e["r"], 2), "origine": "foto"})
                continue
        base_ent.append(e)
    return {"base": {"tipo": "estrudi", "entita": base_ent, "altezza": altezza}, "lavorazioni": fori}


def _posizioni_fori(lavs):
    """Centri di tutti i fori dell'albero (anche quelli delle serie)."""
    from .lavorazioni import _espandi_fori
    pos = []
    for l in lavs:
        try:
            if l.get("tipo") == "foro":
                pos.append((float(l["x"]), float(l["y"])))
            elif l.get("tipo") in ("serie_polare", "serie_rett"):
                pos += [(f["x"], f["y"]) for f in _espandi_fori(l)]
        except (KeyError, TypeError, ValueError):
            pass
    return pos


def _sposta(entita, dx, dy):
    out = []
    for e in entita:
        e = copy.deepcopy(e)
        for c in ("a", "b", "c"):
            if c in e:
                e[c] = [e[c][0] + dx, e[c][1] + dy]
        if "pts" in e:
            e["pts"] = [[p[0] + dx, p[1] + dy] for p in e["pts"]]
        out.append(e)
    return out


def da_disegno(entita, come, progetto=None, altezza=10, asse=None, angolo=360):
    """Il disegno della tavola diventa la forma di base del progetto, senza perdere le lavorazioni già decise.
    come: "estrudi" | "rivoluzione" | "alto" | "fronte". Con estrudi/alto i cerchi interni diventano fori
    dell'albero (modificabili dalle indicazioni del tecnico); quelli già presenti nell'albero non vengono doppiati."""
    prog = copy.deepcopy(progetto) if isinstance(progetto, dict) else {}
    lavs = [l for l in (prog.get("lavorazioni") or []) if l.get("origine") not in ("foto", "disegno")]
    entita = [e for e in (entita or []) if e.get("t") in ("line", "arc", "circle", "pline")]
    if not entita:
        raise ValueError("Il disegno è vuoto")
    if come == "rivoluzione":
        prog["base"] = {"tipo": "rivoluzione", "entita": entita, "asse": asse or [[0, 0], [1, 0]], "angolo": angolo}
        prog["lavorazioni"] = lavs
        return prog
    if come == "fronte":
        b = prog.get("base") or {}
        if b.get("tipo") == "due_viste" or (b.get("tipo") == "estrudi" and b.get("entita")):
            alto = b.get("alto") or b.get("entita")
            ea, ef = profili.estensione_entita(alto), profili.estensione_entita(entita)
            entita = _sposta(entita, ea[0] - ef[0], -ef[1])      # stessa X della vista dall'alto, base a quota 0
            prog["base"] = {"tipo": "due_viste", "alto": alto, "fronte": entita}
        else:
            prog["base"] = {"tipo": "due_viste", "alto": None, "fronte": _sposta(entita, 0, -profili.estensione_entita(entita)[1])}
        prog["lavorazioni"] = lavs + [l for l in (progetto or {}).get("lavorazioni", []) if l.get("origine") in ("foto", "disegno")]
        return prog
    auto = da_foto(entita, altezza)
    gia = _posizioni_fori(lavs)
    nuovi = []
    for f in auto["lavorazioni"]:
        if any(math.hypot(f["x"] - x, f["y"] - y) < max(0.5, f["d"] / 2) for x, y in gia):
            continue      # quel foro è già nell'albero con le misure del tecnico
        f["origine"] = "disegno"
        nuovi.append(f)
    b = prog.get("base") or {}
    if come == "alto":
        fronte = b.get("fronte") if b.get("tipo") == "due_viste" else None
        prog["base"] = {"tipo": "due_viste", "alto": auto["base"]["entita"], "fronte": fronte}
    else:
        prog["base"] = {"tipo": "estrudi", "entita": auto["base"]["entita"], "altezza": altezza}
    prog["lavorazioni"] = nuovi + lavs
    prog["lavorazioni"].sort(key=lambda l: ORDINE.get(l.get("tipo"), 4))
    return prog
