"""Lo scopo di ogni quota: la funzione dice perché un foro esiste e da lì nascono misura, tolleranza, ciclo e controllo.

Esempi: «sede cuscinetto 6204» → foro Ø47 H7 profondo 14 + passaggio albero; «foro spina Ø8» → Ø8 H7;
«boccola 20×26» → sede Ø26 H7; «vite M8» → passaggio Ø9 con lamatura ISO 4762.
Se cambia il componente (6204 → 6205) si rigenera la lavorazione e il programma dice cosa cambia nel pezzo.
"""
import copy

from ..progetto.lavorazioni import LAMATURA, PASSAGGIO
from . import iso286

# cuscinetti radiali rigidi a sfere: d, D, B (ISO 15, serie 60, 62, 63)
CUSCINETTI = {
    "6000": (10, 26, 8), "6001": (12, 28, 8), "6002": (15, 32, 9), "6003": (17, 35, 10), "6004": (20, 42, 12), "6005": (25, 47, 12),
    "6006": (30, 55, 13), "6007": (35, 62, 14), "6008": (40, 68, 15), "6009": (45, 75, 16), "6010": (50, 80, 16),
    "6200": (10, 30, 9), "6201": (12, 32, 10), "6202": (15, 35, 11), "6203": (17, 40, 12), "6204": (20, 47, 14), "6205": (25, 52, 15),
    "6206": (30, 62, 16), "6207": (35, 72, 17), "6208": (40, 80, 18), "6209": (45, 85, 19), "6210": (50, 90, 20),
    "6300": (10, 35, 11), "6301": (12, 37, 12), "6302": (15, 42, 13), "6303": (17, 47, 14), "6304": (20, 52, 15), "6305": (25, 62, 17),
    "6306": (30, 72, 19), "6307": (35, 80, 21), "6308": (40, 90, 23),
}
SPINE = (2, 2.5, 3, 4, 5, 6, 8, 10, 12, 16, 20)          # spine cilindriche ISO 8734 / ISO 2338
BOCCOLE = {(8, 10): 8, (10, 12): 10, (12, 14): 12, (15, 17): 15, (16, 18): 15, (20, 23): 20, (25, 28): 20, (30, 34): 30}   # boccole DU d×D: lunghezza tipica

TIPI = {
    "sede_cuscinetto": "Sede cuscinetto",
    "foro_spina": "Foro per spina di riferimento",
    "sede_boccola": "Sede boccola",
    "passaggio_vite": "Passaggio vite",
    "filetto": "Foro filettato",
    "libera": "Quota libera (tolleranza generale)",
}


def cuscinetto(codice):
    c = CUSCINETTI.get(str(codice).strip())
    if not c:
        raise ValueError("Cuscinetto %s non in catalogo (serie 60xx, 62xx, 63xx fino a d=50)" % codice)
    return {"codice": str(codice), "d": c[0], "D": c[1], "B": c[2]}


def applica_funzione(lav, funzione):
    """Rigenera il foro (singolo o serie) a partire dalla sua funzione; restituisce la lavorazione nuova."""
    tipo = funzione.get("tipo")
    if tipo not in TIPI:
        raise ValueError("Funzione sconosciuta: %s" % tipo)
    nuova = copy.deepcopy(lav)
    f = nuova if nuova.get("tipo") == "foro" else nuova.setdefault("foro", {})
    for k in ("d", "filetto", "lamatura", "svasatura", "tolleranza", "prof"):
        if k in f and tipo != "libera":
            f.pop(k)
    fz = {"tipo": tipo}
    if tipo == "sede_cuscinetto":
        c = cuscinetto(funzione.get("componente"))
        sigla = funzione.get("sigla") or "H7"
        if funzione.get("chiusa"):          # sede cieca (fine albero): solo l'alloggiamento
            f.update(d=float(c["D"]), prof=float(c["B"]), tolleranza=sigla)
        else:                               # sede passante con spallamento: passaggio albero + alloggiamento come «lamatura»
            f.update(d=float(c["d"]) + 2.0, lamatura={"d": float(c["D"]), "prof": float(c["B"]), "tolleranza": sigla})
        fz.update(componente=c["codice"], sigla=sigla, perche="Cuscinetto %s (d%g × D%g × B%g): alloggiamento fisso, anello esterno %s" % (
            c["codice"], c["d"], c["D"], c["B"], "accoppiamento incerto" if sigla in ("K7", "M7", "N7") else "montato a mano"),
            norma="ISO 15 (dimensioni), ISO 286 (tolleranza %s)" % sigla)
    elif tipo == "foro_spina":
        d = float(funzione.get("diametro") or funzione.get("componente") or 8)
        if d not in SPINE:
            raise ValueError("Spina Ø%g non unificata: scegli fra %s" % (d, ", ".join("%g" % s for s in SPINE)))
        sigla = funzione.get("sigla") or "H7"
        f.update(d=d, tolleranza=sigla)
        if funzione.get("profondita"):
            f["prof"] = float(funzione["profondita"])
        fz.update(componente="Spina Ø%g" % d, sigla=sigla, perche="Spina cilindrica di riferimento Ø%g m6 in foro %s: posiziona i pezzi tra loro" % (d, sigla),
                  norma="ISO 8734 / ISO 2338, ISO 286")
    elif tipo == "sede_boccola":
        dd = str(funzione.get("componente") or "20x23").lower().replace("×", "x").split("x")
        d_i, D = float(dd[0]), float(dd[1])
        f.update(d=D, tolleranza=funzione.get("sigla") or "H7")
        lung = BOCCOLE.get((int(d_i), int(D)))
        if lung:
            f["prof"] = float(lung)
        fz.update(componente="Boccola %g×%g" % (d_i, D), sigla=f["tolleranza"], perche="Boccola autolubrificante %g×%g piantata nella sede %s" % (d_i, D, f["tolleranza"]),
                  norma="ISO 3547 (boccole avvolte), ISO 286")
    elif tipo == "passaggio_vite":
        vite = str(funzione.get("componente") or "M8").upper()
        if vite not in PASSAGGIO:
            raise ValueError("Vite %s non in tabella" % vite)
        f["d"] = PASSAGGIO[vite]
        if funzione.get("lamatura", True) and vite in LAMATURA:
            dl, pl = LAMATURA[vite]
            f["lamatura"] = {"d": dl, "prof": pl}
        fz.update(componente=vite, perche="Passaggio per vite %s a testa cilindrica" % vite, norma="UNI EN 20273 (fori medi), ISO 4762 (lamatura)")
    elif tipo == "filetto":
        fil = str(funzione.get("componente") or "M8").upper()
        f["filetto"] = fil
        if funzione.get("profondita"):
            f["prof"] = float(funzione["profondita"])
        fz.update(componente=fil, perche="Foro filettato %s per vite di fissaggio" % fil, norma="ISO 261 / ISO 965 (6H)")
    else:
        fz.update(perche=funzione.get("perche") or "Quota libera: tolleranze generali ISO 2768-m", norma="ISO 2768-1")
    if funzione.get("perche") and tipo != "libera":
        fz["perche"] = str(funzione["perche"])[:200]
    nuova["funzione"] = fz
    return nuova


def limiti_foro(f):
    """Limiti ISO 286 del foro e della sua sede/lamatura di precisione: lista (diametro, limiti)."""
    out = []
    for d, sig in ((f.get("d"), f.get("tolleranza")), ((f.get("lamatura") or {}).get("d"), (f.get("lamatura") or {}).get("tolleranza"))):
        if d and sig:
            try:
                out.append(iso286.limiti(d, sig))
            except (ValueError, KeyError):
                pass
    return out


def impatto(prima, dopo):
    """Cosa cambia nel pezzo cambiando un requisito: misure dei fori, fattibilità, peso e costo."""
    from ..fattibilita.regole import verifica
    from ..progetto.analisi import analizza
    a, b = analizza(prima), analizza(dopo)
    righe = []
    fa = {(round(f["x"], 3), round(f["y"], 3)): f for f in a["fori"]}
    for f in b["fori"]:
        g = fa.get((round(f["x"], 3), round(f["y"], 3)))
        if g is None:
            righe.append("Nuovo foro in (%g; %g): Ø%g" % (f["x"], f["y"], f["d"]))
            continue
        for k, nome in (("d", "diametro"), ("prof", "profondità")):
            if abs((g[k] or 0) - (f[k] or 0)) > 1e-6:
                righe.append("Foro %d: %s %g → %g mm" % (f["rif"], nome, g[k], f[k]))
        la, lb = g["lamatura"] or {}, f["lamatura"] or {}
        for k, nome in (("d", "Ø sede/lamatura"), ("prof", "profondità sede/lamatura")):
            if abs(float(la.get(k) or 0) - float(lb.get(k) or 0)) > 1e-6:
                righe.append("Foro %d: %s %g → %g mm" % (f["rif"], nome, float(la.get(k) or 0), float(lb.get(k) or 0)))
        if (la.get("tolleranza") or "") != (lb.get("tolleranza") or ""):
            righe.append("Foro %d: tolleranza sede %s → %s" % (f["rif"], la.get("tolleranza") or "generale", lb.get("tolleranza") or "generale"))
        if (g["tolleranza"] or "") != (f["tolleranza"] or ""):
            righe.append("Foro %d: tolleranza %s → %s" % (f["rif"], g["tolleranza"] or "generale", f["tolleranza"] or "generale"))
    import re
    va, vb = verifica(a), verifica(b)
    # stesso problema con numeri diversi (es. sede 14 → 15 mm) = stesso problema: si confronta il tipo, non le cifre
    chiave = lambda x: (re.sub(r"\(.*", "", x["dove"]).strip(), re.sub(r"[\d.,]+", "#", x["testo"]))
    ka, kb = {chiave(y) for y in va["avvisi"]}, {chiave(y) for y in vb["avvisi"]}
    nuovi = [x for x in vb["avvisi"] if x["livello"] != "consiglio" and chiave(x) not in ka]
    risolti = [x for x in va["avvisi"] if x["livello"] != "consiglio" and chiave(x) not in kb]
    restano = [x for x in vb["avvisi"] if x["livello"] == "errore" and chiave(x) in ka]
    dv = b["volume"] - a["volume"]
    if abs(dv) > 1:
        righe.append("Volume %s di %s cm³" % ("+" if dv > 0 else "−", ("%.1f" % (abs(dv) / 1000)).replace(".", ",")))
    return {"modifiche": righe, "problemi_nuovi": nuovi, "problemi_risolti": risolti, "problemi_restano": restano}
