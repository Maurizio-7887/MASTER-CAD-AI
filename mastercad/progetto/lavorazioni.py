"""Progetto parametrico: forma di base + albero delle lavorazioni, ricostruito da capo a ogni modifica.

progetto = {
  "base": {"tipo": "estrudi", "entita": [...], "altezza": 15}
        | {"tipo": "rivoluzione", "entita": [...], "asse": [[0,0],[1,0]], "angolo": 360}
        | {"tipo": "due_viste", "alto": [...entità piano XY...], "fronte": [...entità piano XZ, y del disegno = Z...],
           "lato": [...opzionale, piano YZ...]},
  "lavorazioni": [ {"tipo": "foro", ...}, {"tipo": "serie_polare", ...}, ... ]
}
Tipi di lavorazione (quote in mm, faccia superiore = la più alta in Z, salvo «da_sotto»):
  foro          x, y, d, prof (assente = passante), lamatura {d, prof}, svasatura {d, angolo}, filetto "M8", da_sotto
  serie_polare  centro [x,y], diametro (interasse), n, angolo0, foro {...}
  serie_rett    origine [x,y], nx, ny, passo_x, passo_y, foro {...}
  tasca         forma "rett"|"cerchio"|"contorno", centro [x,y], l, w | d | entita, prof, raggio_angoli, angolo
  asola         centro, lunghezza, larghezza, angolo, prof (assente = passante)
  rialzo        come tasca ma aggiunge materiale: h
  raccordo      r, spigoli "verticali"|"superiori"|"inferiori"|"tutti"
  smusso        d, spigoli come sopra
  guscio        spessore, aperta "sopra"|"sotto"|"nessuna"
Ogni lavorazione che non si può eseguire viene saltata con il motivo, senza buttare via tutto il progetto.
"""
import math

import cadquery as cq

from .. import profili

# preforo per filettatura metrica grossa (UNI ISO 261 / tabelle di officina)
PREFORO = {"M2": 1.6, "M2.5": 2.05, "M3": 2.5, "M4": 3.3, "M5": 4.2, "M6": 5.0, "M8": 6.8, "M10": 8.5, "M12": 10.2,
           "M14": 12.0, "M16": 14.0, "M18": 15.5, "M20": 17.5, "M22": 19.5, "M24": 21.0}
# fori di passaggio medi (UNI EN 20273) e lamature per viti a testa cilindrica (ISO 4762)
PASSAGGIO = {"M3": 3.4, "M4": 4.5, "M5": 5.5, "M6": 6.6, "M8": 9.0, "M10": 11.0, "M12": 13.5, "M16": 17.5, "M20": 22.0, "M24": 26.0}
LAMATURA = {"M3": (6.5, 3.3), "M4": (8.0, 4.4), "M5": (10.0, 5.4), "M6": (11.0, 6.4), "M8": (15.0, 8.6), "M10": (18.0, 10.6),
            "M12": (20.0, 12.6), "M16": (26.0, 16.6), "M20": (33.0, 20.6), "M24": (40.0, 24.8)}
MAX_LAVORAZIONI = 200


def _n(v, nome, minimo=None, massimo=5000):
    try:
        v = float(v)
    except (TypeError, ValueError):
        raise ValueError(nome + ": numero mancante o non valido") from None
    if not math.isfinite(v) or abs(v) > massimo:
        raise ValueError(nome + ": valore fuori campo")
    if minimo is not None and v < minimo:
        raise ValueError(nome + ": deve essere almeno %g" % minimo)
    return v


def _p(v, nome):
    if not isinstance(v, (list, tuple)) or len(v) < 2:
        raise ValueError(nome + ": punto x,y mancante")
    return _n(v[0], nome), _n(v[1], nome)


# ── forma di base ──
def _estrudi_piano(entita, altezza, piano):
    """Estrude un profilo disegnato in XY dentro il piano voluto: 'XY' (vista dall'alto, lungo Z),
    'XZ' (vista di fronte: y del disegno = Z, estrusione lungo Y), 'YZ' (vista di lato: x del disegno = Y, lungo X)."""
    facce, _, _ = profili._facce(entita)
    solido = None
    for f in facce:
        s = cq.Solid.extrudeLinear(f, cq.Vector(0, 0, altezza))
        solido = s if solido is None else solido.fuse(s)
    if piano == "XZ":       # (x, y, z) → (x, z, y): ruota di +90° attorno a X e porta lo spessore lungo +Y
        solido = solido.rotate(cq.Vector(0, 0, 0), cq.Vector(1, 0, 0), 90).translate(cq.Vector(0, altezza, 0))
    elif piano == "YZ":     # (x, y, z) → (z, x, y)
        solido = solido.rotate(cq.Vector(0, 0, 0), cq.Vector(1, 0, 0), 90).rotate(cq.Vector(0, 0, 0), cq.Vector(0, 0, 1), 90)
    return solido


def base(spec):
    if not isinstance(spec, dict):
        raise ValueError("Manca la forma di base del progetto")
    tipo = spec.get("tipo")
    if tipo == "estrudi":
        _, s, info = profili.estrudi(spec.get("entita"), spec.get("altezza"))
        return s, "Base: profilo estruso di %g mm (%d contorni, %d fori)" % (info["altezza"], info["regioni"], info["fori"])
    if tipo == "rivoluzione":
        asse = spec.get("asse") or [[0, 0], [1, 0]]
        _, s, info = profili.rivoluzione(spec.get("entita"), asse[0], asse[1], spec.get("angolo", 360))
        return s, "Base: rivoluzione di %g°" % info["angolo"]
    if tipo == "due_viste":
        alto, fronte = spec.get("alto"), spec.get("fronte")
        if not alto or not fronte:
            raise ValueError("Per due viste servono il profilo dall'alto e quello di fronte")
        ba, bf = profili.estensione_entita(alto), profili.estensione_entita(fronte)
        larghezza_y = ba[3] - ba[1] + 2
        altezza_z = bf[3] - bf[1] + 2
        s_alto = _estrudi_piano(alto, altezza_z, "XY").translate(cq.Vector(0, 0, bf[1] - 1))
        s_fronte = _estrudi_piano(fronte, larghezza_y, "XZ").translate(cq.Vector(0, ba[1] - 1, 0))
        s = s_alto.intersect(s_fronte)
        desc = "Base: intersezione vista dall'alto × vista di fronte"
        if spec.get("lato"):
            bl = profili.estensione_entita(spec["lato"])
            s_lato = _estrudi_piano(spec["lato"], ba[2] - ba[0] + 2, "YZ").translate(cq.Vector(ba[0] - 1, 0, 0))
            s = s.intersect(s_lato)
            desc += " × vista di lato"
        if s.Volume() <= 1e-6:
            raise ValueError("Le viste non si sovrappongono: controlla che abbiano la stessa origine e la stessa scala")
        return s, desc
    raise ValueError("Forma di base: estrudi, rivoluzione o due_viste")


# ── utensili ──
def _cilindro(x, y, z0, z1, d):
    return cq.Solid.makeCylinder(d / 2, z1 - z0, cq.Vector(x, y, z0))


def _cono(x, y, z_alto, d_alto, d_basso, alt):
    return cq.Solid.makeCone(d_basso / 2, d_alto / 2, alt, cq.Vector(x, y, z_alto - alt))


def _quote_z(solido):
    b = solido.BoundingBox()
    return b.zmin, b.zmax


def _cima_locale(solido, x, y, zmin, zmax, sotto=False):
    """Quota della superficie del pezzo sopra (o sotto) il punto x,y: i fori su un rialzo partono dal rialzo."""
    try:
        ago = cq.Solid.makeBox(0.02, 0.02, zmax - zmin + 2, cq.Vector(x - 0.01, y - 0.01, zmin - 1))
        pezzo = solido.intersect(ago)
        if pezzo.Volume() > 1e-9:
            b = pezzo.BoundingBox()
            return b.zmin if sotto else b.zmax
    except Exception:
        pass
    return zmin if sotto else zmax


def utensile_foro(f, zmin, zmax, solido=None):
    """Solido da sottrarre per un foro (con lamatura, svasatura o preforo di filettatura)."""
    x, y = _n(f.get("x"), "foro x"), _n(f.get("y"), "foro y")
    if solido is not None:      # profondità e lamature contate dalla faccia che il foro incontra davvero
        if f.get("da_sotto"):
            zmin = _cima_locale(solido, x, y, zmin, zmax, True)
        else:
            zmax = _cima_locale(solido, x, y, zmin, zmax)
    filetto = (f.get("filetto") or "").upper().replace(" ", "") or None
    if filetto:
        if filetto not in PREFORO:
            raise ValueError("Filetto %s non in tabella (M2–M24)" % filetto)
        d = PREFORO[filetto]
    else:
        d = _n(f.get("d"), "diametro foro", 0.3)
    sotto = bool(f.get("da_sotto"))
    alt_tot = zmax - zmin
    prof = f.get("prof")
    prof = alt_tot + 2 if prof in (None, "", "passante") else _n(prof, "profondità foro", 0.05)
    if sotto:
        t = _cilindro(x, y, zmin - 1, zmin + prof, d)
    else:
        t = _cilindro(x, y, zmax - prof, zmax + 1, d)
    if not sotto and prof < alt_tot + 1:     # foro cieco: punta a 118° come in officina
        punta = (d / 2) / math.tan(math.radians(59))
        t = t.fuse(cq.Solid.makeCone(d / 2, 0.001, punta, cq.Vector(x, y, zmax - prof), cq.Vector(0, 0, -1)))
    lam = f.get("lamatura")
    if lam:
        dl, pl = _n(lam.get("d"), "diametro lamatura", d + 0.1), _n(lam.get("prof"), "profondità lamatura", 0.05)
        t = t.fuse(_cilindro(x, y, zmin - 1, zmin + pl, dl) if sotto else _cilindro(x, y, zmax - pl, zmax + 1, dl))
    sv = f.get("svasatura")
    if sv and not sotto:
        ds = _n(sv.get("d"), "diametro svasatura", d + 0.1)
        ang = _n(sv.get("angolo", 90), "angolo svasatura", 30, 179)
        alt = (ds - d) / 2 / math.tan(math.radians(ang / 2))
        t = t.fuse(_cono(x, y, zmax + 0.001, ds, d, alt)).fuse(_cilindro(x, y, zmax, zmax + 1, ds))
    return t, d, filetto


def _espandi_fori(lav):
    """serie_polare / serie_rett → lista di fori singoli."""
    tipo = lav["tipo"]
    modello = dict(lav.get("foro") or {})
    if tipo == "serie_polare":
        cx, cy = _p(lav.get("centro", [0, 0]), "centro serie")
        r = _n(lav.get("diametro"), "interasse (diametro primitivo)", 0.1) / 2
        n = int(_n(lav.get("n"), "numero di fori", 1, 360))
        a0 = _n(lav.get("angolo0", 0), "angolo iniziale")
        return [dict(modello, x=cx + r * math.cos(math.radians(a0 + 360 * i / n)), y=cy + r * math.sin(math.radians(a0 + 360 * i / n))) for i in range(n)]
    ox, oy = _p(lav.get("origine", [0, 0]), "origine serie")
    nx, ny = int(_n(lav.get("nx", 1), "colonne", 1, 100)), int(_n(lav.get("ny", 1), "righe", 1, 100))
    px, py = _n(lav.get("passo_x", 0), "passo x"), _n(lav.get("passo_y", 0), "passo y")
    return [dict(modello, x=ox + i * px, y=oy + j * py) for j in range(ny) for i in range(nx)]


def _profilo_lavorazione(lav):
    """Faccia 2D (in XY) di tasche, rialzi e asole."""
    forma = lav.get("forma", "rett")
    ang = _n(lav.get("angolo", 0), "angolo")
    if forma == "contorno":
        facce, _, _ = profili._facce(lav.get("entita"))
        return facce
    cx, cy = _p(lav.get("centro", [0, 0]), "centro")
    if forma == "cerchio":
        r = _n(lav.get("d"), "diametro", 0.1) / 2
        return [cq.Face.makeFromWires(cq.Wire.makeCircle(r, cq.Vector(cx, cy, 0), cq.Vector(0, 0, 1)))]
    if forma == "asola":
        L, W = _n(lav.get("lunghezza"), "lunghezza asola", 0.2), _n(lav.get("larghezza"), "larghezza asola", 0.1)
        if W >= L:
            raise ValueError("L'asola deve essere più lunga che larga")
        a, r, c, s_ = (L - W) / 2, W / 2, math.cos(math.radians(ang)), math.sin(math.radians(ang))
        R = lambda x, y: [cx + x * c - y * s_, cy + x * s_ + y * c]
        ents = [{"t": "line", "a": R(-a, -r), "b": R(a, -r)}, {"t": "arc", "c": R(a, 0), "r": r, "a0": ang - 90, "a1": ang + 90},
                {"t": "line", "a": R(a, r), "b": R(-a, r)}, {"t": "arc", "c": R(-a, 0), "r": r, "a0": ang + 90, "a1": ang + 270}]
        facce, _, _ = profili._facce(ents)
        return facce
    L, W = _n(lav.get("l"), "lunghezza", 0.1), _n(lav.get("w"), "larghezza", 0.1)
    w = cq.Workplane("XY").center(cx, cy).transformed(rotate=(0, 0, ang)).rect(L, W)
    facce = _faccia_da_wp(w)
    ra = float(lav.get("raggio_angoli") or 0)
    if ra > 0:
        if ra * 2 >= min(L, W):
            raise ValueError("Raggio degli angoli troppo grande per la tasca")
        lav["_raggio"] = ra
    return facce


def _faccia_da_wp(w):
    fili = w.ctx.pendingWires if w.ctx.pendingWires else []
    if not fili:
        fili = [x for x in w.vals() if isinstance(x, cq.Wire)]
    return [cq.Face.makeFromWires(f) for f in fili]


def _spigoli(wp, dove):
    sel = {"verticali": "|Z", "superiori": ">Z", "inferiori": "<Z"}.get(dove or "verticali")
    if dove == "tutti":
        return wp.edges()
    if dove in ("superiori", "inferiori"):
        return wp.faces(sel).edges()
    return wp.edges(sel)


def esegui(solido, lav):
    """Applica una lavorazione; restituisce (nuovo solido, descrizione)."""
    tipo = lav.get("tipo")
    zmin, zmax = _quote_z(solido)
    if tipo in ("foro", "serie_polare", "serie_rett"):
        fori = [lav] if tipo == "foro" else _espandi_fori(lav)
        if len(fori) > 400:
            raise ValueError("Troppi fori in una serie (massimo 400)")
        desc = None
        for f in fori:
            t, d, fil = utensile_foro(f, zmin, zmax, solido)
            solido = solido.cut(t)
            desc = ("filettato %s (preforo Ø%g)" % (fil, d)) if fil else ("Ø%g" % d)
            extra = []
            if f.get("lamatura"): extra.append("lamatura Ø%g×%g" % (float(f["lamatura"]["d"]), float(f["lamatura"]["prof"])))
            if f.get("svasatura"): extra.append("svasatura Ø%g a %g°" % (float(f["svasatura"]["d"]), float(f["svasatura"].get("angolo", 90))))
            prof = "passante" if f.get("prof") in (None, "", "passante") else "profondo %g" % float(f["prof"])
            desc += " " + prof + (", " + ", ".join(extra) if extra else "")
        if tipo == "foro":
            return solido, "Foro %s in %g, %g" % (desc, float(lav["x"]), float(lav["y"]))
        if tipo == "serie_polare":
            return solido, "Serie polare: %d fori %s su interasse Ø%g" % (len(fori), desc, float(lav["diametro"]))
        return solido, "Serie rettangolare: %d fori %s" % (len(fori), desc)
    if tipo in ("tasca", "asola", "rialzo"):
        if tipo == "asola":
            lav = dict(lav, forma="asola")
        facce = _profilo_lavorazione(lav)
        out = None
        for f in facce:
            if tipo == "rialzo":
                h = _n(lav.get("h"), "altezza rialzo", 0.01)
                s = cq.Solid.extrudeLinear(f, cq.Vector(0, 0, h)).translate(cq.Vector(0, 0, zmax))
            else:
                prof = lav.get("prof")
                ztop = zmax
                if prof not in (None, "", "passante") and lav.get("forma") != "contorno":
                    c = _p(lav.get("centro", [0, 0]), "centro")
                    ztop = _cima_locale(solido, c[0], c[1], zmin, zmax)     # la tasca parte dalla faccia che incontra
                prof = (zmax - zmin) + 2 if prof in (None, "", "passante") else _n(prof, "profondità", 0.01)
                s = cq.Solid.extrudeLinear(f, cq.Vector(0, 0, prof + 1 + (zmax - ztop))).translate(cq.Vector(0, 0, ztop - prof))
            if lav.get("_raggio"):
                try:
                    s = cq.Workplane("XY").add(s).edges("|Z").fillet(lav["_raggio"]).val()
                except Exception:
                    pass
            out = s if out is None else out.fuse(s)
        solido = solido.fuse(out) if tipo == "rialzo" else solido.cut(out)
        nomi = {"tasca": "Tasca", "asola": "Asola", "rialzo": "Rialzo"}
        misura = ("h %g" % float(lav["h"])) if tipo == "rialzo" else ("profonda %s" % ("passante" if lav.get("prof") in (None, "", "passante") else "%g" % float(lav["prof"])))
        return solido, "%s %s, %s" % (nomi[tipo], lav.get("forma", "rett") if tipo != "asola" else "%gx%g" % (float(lav["lunghezza"]), float(lav["larghezza"])), misura)
    if tipo in ("raccordo", "smusso"):
        v = _n(lav.get("r" if tipo == "raccordo" else "d"), "raggio" if tipo == "raccordo" else "smusso", 0.01)
        wp = _spigoli(cq.Workplane("XY").add(solido), lav.get("spigoli", "verticali"))
        if not wp.size():
            raise ValueError("Nessuno spigolo «%s» su questo pezzo" % lav.get("spigoli"))
        nome = "Raccordo R" if tipo == "raccordo" else "Smusso"
        try:
            nuovo = (wp.fillet(v) if tipo == "raccordo" else wp.chamfer(v)).val()
            return nuovo, "%s %g sugli spigoli %s" % (nome, v, lav.get("spigoli", "verticali"))
        except Exception:
            pass
        # tutti insieme non riesce (spigolo troppo corto, parete sottile): uno alla volta, saltando quelli impossibili
        centri = [e.Center() for e in wp.vals()]
        fatti = 0
        for c in centri:
            try:
                w = cq.Workplane("XY").add(solido).edges(cq.selectors.NearestToPointSelector((c.x, c.y, c.z)))
                prova = (w.fillet(v) if tipo == "raccordo" else w.chamfer(v)).val()
                if prova.isValid():
                    solido, fatti = prova, fatti + 1
            except Exception:
                continue
        if not fatti:
            raise ValueError("%s %g troppo grande per questi spigoli: prova un valore più piccolo" % (nome, v))
        return solido, "%s %g su %d spigoli %s su %d (gli altri non lo permettono)" % (nome, v, fatti, lav.get("spigoli", "verticali"), len(centri))
    if tipo == "guscio":
        sp = _n(lav.get("spessore"), "spessore del guscio", 0.1)
        aperta = lav.get("aperta", "sopra")
        wp = cq.Workplane("XY").add(solido)
        try:
            if aperta == "nessuna":
                nuovo = wp.shell(-sp).val()
            else:
                nuovo = wp.faces(">Z" if aperta == "sopra" else "<Z").shell(-sp).val()
        except Exception:
            raise ValueError("Guscio di %g mm non riuscito: spessore troppo grande per la forma" % sp) from None
        return nuovo, "Guscio spessore %g, aperto %s" % (sp, aperta)
    raise ValueError("Lavorazione sconosciuta: %s" % tipo)


def costruisci(progetto):
    if not isinstance(progetto, dict):
        raise ValueError("Progetto non valido")
    solido, desc = base(progetto.get("base"))
    storia = [{"op": "BASE", "dettaglio": desc, "ok": True}]
    lavs = progetto.get("lavorazioni") or []
    if not isinstance(lavs, list) or len(lavs) > MAX_LAVORAZIONI:
        raise ValueError("Lavorazioni non valide (massimo %d)" % MAX_LAVORAZIONI)
    for i, lav in enumerate(lavs):
        if not isinstance(lav, dict):
            storia.append({"op": "?", "dettaglio": "lavorazione %d non valida" % (i + 1), "ok": False})
            continue
        if lav.get("sospesa"):
            storia.append({"op": lav.get("tipo", "?").upper(), "dettaglio": "sospesa", "ok": True, "sospesa": True})
            continue
        try:
            prima = solido.Volume()
            nuovo, d = esegui(solido, dict(lav))
            if nuovo is None or nuovo.Volume() <= 1e-6:
                raise ValueError("la lavorazione toglierebbe tutto il pezzo")
            if abs(nuovo.Volume() - prima) < 1e-6 and lav.get("tipo") not in ("raccordo", "smusso"):
                raise ValueError("non tocca il pezzo: controlla la posizione (fuori dal contorno?)")
            solido = nuovo
            storia.append({"op": lav["tipo"].upper(), "dettaglio": d, "ok": True})
        except (ValueError, TypeError, KeyError) as exc:
            storia.append({"op": str(lav.get("tipo", "?")).upper(), "dettaglio": "SALTATA: " + str(exc), "ok": False})
        except Exception:
            storia.append({"op": str(lav.get("tipo", "?")).upper(), "dettaglio": "SALTATA: il motore geometrico non è riuscito (controlla posizione e misure)", "ok": False})
    if not solido.isValid():
        try:
            solido = solido.fix()
        except Exception:
            pass
    return cq.Workplane("XY").add(solido), solido, storia
