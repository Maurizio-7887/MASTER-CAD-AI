"""Lettura «da officina» del progetto: il solido finito e l'elenco delle lavorazioni con le quote reali.

Lo usano la messa in tavola, il ciclo di lavoro, il preventivo, la verifica di fattibilità e il controllo qualità:
tutti partono dalle stesse misure, così tavola, ciclo e prezzo non si contraddicono mai.
"""
import math

import cadquery as cq

from .. import profili
from ..materiali import PASSO
from . import lavorazioni as L


def _passante(f):
    return f.get("prof") in (None, "", "passante")


def _faccia_area_perimetro(facce):
    area = sum(f.Area() for f in facce)
    perim = sum(w.Length() for f in facce for w in [f.outerWire()] + f.innerWires())
    return area, perim


def contorno_esterno(base):
    """Facce 2D (piano XY) della pianta del pezzo, per verifiche di bordo e contornatura."""
    ents = base.get("entita") if base.get("tipo") == "estrudi" else base.get("alto") if base.get("tipo") == "due_viste" else None
    if not ents:
        return []
    facce, _, _ = profili._facce(ents)
    return facce


def analizza(progetto):
    """Costruisce il pezzo e restituisce misure e lavorazioni pronte per tavola, ciclo e preventivo."""
    if not isinstance(progetto, dict) or not progetto.get("base"):
        raise ValueError("Manca il progetto: prima costruisci il pezzo nella pagina Disegno")
    obj, solido, storia = L.costruisci(progetto)
    lavs = progetto.get("lavorazioni") or []
    ok = [i for i, lav in enumerate(lavs) if isinstance(lav, dict) and not lav.get("sospesa")
          and i + 1 < len(storia) and storia[i + 1].get("ok")]
    # pezzo «pieno»: base + rialzi, per sapere da che quota parte ogni foro
    pieno_prog = {"base": progetto["base"], "lavorazioni": [lavs[i] for i in ok if lavs[i].get("tipo") == "rialzo"]}
    _, pieno, _ = L.costruisci(pieno_prog)
    zmin, zmax = L._quote_z(pieno)
    bb = solido.BoundingBox()
    out = {"solido": solido, "obj": obj, "storia": storia, "base": progetto["base"], "pieno": pieno,
           "ingombro": {"x": bb.xlen, "y": bb.ylen, "z": bb.zlen, "xmin": bb.xmin, "ymin": bb.ymin, "zmin": bb.zmin,
                        "xmax": bb.xmax, "ymax": bb.ymax, "zmax": bb.zmax},
           "volume": solido.Volume(), "volume_pieno": pieno.Volume(),
           "fori": [], "tasche": [], "rialzi": [], "spigoli": [], "guscio": None, "saltate": [],
           "quote_funzionali": [q for q in (progetto.get("quote_funzionali") or []) if isinstance(q, dict) and q.get("diametro")],
           "tolleranze_geometriche": progetto.get("tolleranze_geometriche") if isinstance(progetto.get("tolleranze_geometriche"), dict) else None}
    for i, lav in enumerate(lavs):
        if isinstance(lav, dict) and not lav.get("sospesa") and i + 1 < len(storia) and not storia[i + 1].get("ok"):
            out["saltate"].append({"indice": i, "tipo": lav.get("tipo"), "motivo": storia[i + 1].get("dettaglio")})
    rif = 0
    for i in ok:
        lav = lavs[i]
        tipo = lav.get("tipo")
        if tipo in ("foro", "serie_polare", "serie_rett"):
            fori = [lav] if tipo == "foro" else L._espandi_fori(lav)
            for f in fori:
                rif += 1
                x, y = float(f["x"]), float(f["y"])
                filetto = (f.get("filetto") or "").upper().replace(" ", "") or None
                d_punta = L.PREFORO[filetto] if filetto else float(f["d"])
                d_nom = float(filetto[1:]) if filetto else float(f["d"])
                sotto = bool(f.get("da_sotto"))
                ztop = L._cima_locale(pieno, x, y, zmin, zmax)
                zbot = L._cima_locale(pieno, x, y, zmin, zmax, True)
                spess = max(0.0, ztop - zbot)
                prof = spess if _passante(f) else min(float(f["prof"]), spess)
                out["fori"].append({
                    "rif": rif, "lavorazione": i, "serie": tipo if tipo != "foro" else None, "x": x, "y": y,
                    "d": d_nom, "d_punta": d_punta, "filetto": filetto, "passo": PASSO.get(filetto) if filetto else None,
                    "passante": _passante(f) or prof >= spess - 1e-6, "prof": prof, "spessore": spess,
                    "lamatura": f.get("lamatura"), "svasatura": f.get("svasatura"), "tolleranza": f.get("tolleranza"),
                    "da_sotto": sotto, "z_faccia": zbot if sotto else ztop, "funzione": lav.get("funzione"),
                    "in_opera": bool(lav.get("in_opera"))})
        elif tipo in ("tasca", "asola", "rialzo"):
            l2 = dict(lav, forma="asola") if tipo == "asola" else dict(lav)
            try:
                facce = L._profilo_lavorazione(l2)
            except ValueError:
                continue
            area, perim = _faccia_area_perimetro(facce)
            if tipo == "rialzo":
                h = float(lav["h"])
                out["rialzi"].append({"lavorazione": i, "area": area, "perimetro": perim, "h": h, "dati": lav})
                continue
            c = lav.get("centro") or [0, 0]
            ztop = L._cima_locale(pieno, float(c[0]), float(c[1]), zmin, zmax)
            zbot = L._cima_locale(pieno, float(c[0]), float(c[1]), zmin, zmax, True)
            prof = (ztop - zbot) if _passante(lav) else float(lav["prof"])
            if lav.get("forma") == "cerchio":
                larg = float(lav["d"])
            elif tipo == "asola":
                larg = float(lav["larghezza"])
            elif lav.get("forma") == "contorno":
                b = facce[0].BoundingBox() if facce else None
                larg = min(b.xlen, b.ylen) if b else 10
            else:
                larg = min(float(lav["l"]), float(lav["w"]))
            out["tasche"].append({"lavorazione": i, "tipo": tipo, "area": area, "perimetro": perim, "prof": prof,
                                  "passante": _passante(lav), "larghezza_min": larg,
                                  "raggio_angoli": float(lav.get("raggio_angoli") or 0), "spessore": ztop - zbot, "dati": lav})
        elif tipo in ("raccordo", "smusso"):
            try:
                wp = L._spigoli(cq.Workplane("XY").add(pieno), lav.get("spigoli", "verticali"))
                lung = sum(e.Length() for e in wp.vals())
            except Exception:
                lung = 0
            out["spigoli"].append({"lavorazione": i, "tipo": tipo, "valore": float(lav.get("r") or lav.get("d") or 0),
                                   "spigoli": lav.get("spigoli", "verticali"), "lunghezza": lung})
        elif tipo == "guscio":
            senza = dict(progetto, lavorazioni=[dict(x, sospesa=True) if x is lav else x for x in lavs])
            try:
                _, s2, _ = L.costruisci(senza)
                tolto = max(0.0, s2.Volume() - solido.Volume())
            except Exception:
                tolto = 0.0
            out["guscio"] = {"lavorazione": i, "spessore": float(lav["spessore"]), "aperta": lav.get("aperta", "sopra"), "volume": tolto}
    return out


def gruppi_fori(fori):
    """Fori uguali raggruppati per la tabella e la distinta: «4× Ø9 passante, lamatura Ø15×8,6»."""
    gruppi = {}
    for f in fori:
        chiave = (f["filetto"], round(f["d"], 3), round(f["prof"], 2), f["passante"], f["da_sotto"], f["tolleranza"],
                  tuple(sorted((f["lamatura"] or {}).items())), tuple(sorted((f["svasatura"] or {}).items())))
        gruppi.setdefault(chiave, []).append(f)
    return list(gruppi.values())


def descrivi_foro(f, limiti=False):
    from ..tolleranze.iso286 import limiti as lim286

    def tol(d, sig):
        if not sig:
            return ""
        if not limiti:
            return " " + sig
        try:
            x = lim286(d, sig)
            return " %s (%s/%s)" % (sig, _dev(x["sup_um"]), _dev(x["inf_um"]))
        except ValueError:
            return " " + sig
    t = f["filetto"] + (" passante" if f["passante"] else " prof. %s" % _num(f["prof"])) if f["filetto"] else \
        "Ø" + _num(f["d"]) + tol(f["d"], f["tolleranza"]) + (" passante" if f["passante"] else " prof. %s" % _num(f["prof"]))
    if f["lamatura"]:
        lt = f["lamatura"].get("tolleranza")
        t += ", %s Ø%s%s×%s" % ("sede" if lt else "lamatura", _num(f["lamatura"]["d"]), tol(f["lamatura"]["d"], lt), _num(f["lamatura"]["prof"]))
    fz = f.get("funzione") or {}
    if fz.get("componente") and fz.get("tipo") in ("sede_cuscinetto", "sede_boccola", "foro_spina"):
        t += " — " + {"sede_cuscinetto": "cuscinetto ", "sede_boccola": "", "foro_spina": ""}[fz["tipo"]] + str(fz["componente"])
    if f["svasatura"]:
        t += ", svasatura Ø%s a %s°" % (_num(f["svasatura"]["d"]), _num(f["svasatura"].get("angolo", 90)))
    if f.get("in_opera"):
        t += " — preforo Ø%s, alesare in opera" % _num(f["d"] - 0.2)
    if f["da_sotto"]:
        t += " (dal lato opposto)"
    return t


def _num(v):
    v = float(v)
    if abs(v) < 0.005:
        v = 0.0
    return ("%.2f" % v).rstrip("0").rstrip(".").replace(".", ",")


def grezzo(an):
    """Grezzo di partenza: barra tonda per i pezzi torniti, piatto/blocco con sovrametallo per gli altri."""
    i = an["ingombro"]
    if an["base"].get("tipo") == "rivoluzione":
        dmax = max(i["y"], i["z"])
        diam = next((d for d in (10, 12, 14, 16, 18, 20, 22, 25, 28, 30, 32, 35, 40, 45, 50, 55, 60, 65, 70, 75, 80, 90, 100,
                                  110, 120, 130, 140, 150, 160, 180, 200, 220, 250, 280, 300) if d >= dmax + 2), math.ceil(dmax + 5))
        lung = i["x"] + 5
        return {"forma": "barra tonda", "descrizione": "Barra tonda Ø%d × %s mm" % (diam, _num(lung)),
                "volume": math.pi * diam ** 2 / 4 * lung, "sezione": math.pi * diam ** 2 / 4, "x": lung, "y": diam, "z": diam}
    x, y = i["x"] + 6, i["y"] + 6
    spessori = (3, 4, 5, 6, 8, 10, 12, 15, 20, 25, 30, 35, 40, 45, 50, 60, 70, 80, 90, 100, 120, 150, 200)
    z = next((s for s in spessori if s >= i["z"] + 1.5), math.ceil(i["z"] + 5))
    return {"forma": "piatto" if z <= 30 else "blocco", "descrizione": "%s %s × %s × %d mm (sovrametallo 3 mm per lato)" % (
        "Piatto" if z <= 30 else "Blocco", _num(x), _num(y), z), "volume": x * y * z, "sezione": min(x, y) * z, "x": x, "y": y, "z": z}


def _dev(um):
    if abs(um) < 1e-9:
        return "0"
    return ("+" if um > 0 else "-") + ("%.3f" % (abs(um) / 1000)).rstrip("0").rstrip(".").replace(".", ",")
