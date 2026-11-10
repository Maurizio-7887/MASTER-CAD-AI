"""Tolleranze ISO 286-1/-2 per fori e alberi fino a 500 mm, accoppiamenti e catene di tolleranza.

Tabelle delle tolleranze fondamentali IT5–IT11 e degli scostamenti fondamentali più usati nella costruzione
di macchine (fori H, G, F, JS, K, M, N, P; alberi d, e, f, g, h, js, k, m, n, p). Valori in micrometri.
Sono le tabelle della norma per i campi dimensionali principali: per i casi limite fa fede la norma in vigore.
"""
import math
import re

CAMPI = [3, 6, 10, 18, 30, 50, 80, 120, 180, 250, 315, 400, 500]       # limite superiore di ogni campo (mm)
IT = {
    5: [4, 5, 6, 8, 9, 11, 13, 15, 18, 20, 23, 25, 27],
    6: [6, 8, 9, 11, 13, 16, 19, 22, 25, 29, 32, 36, 40],
    7: [10, 12, 15, 18, 21, 25, 30, 35, 40, 46, 52, 57, 63],
    8: [14, 18, 22, 27, 33, 39, 46, 54, 63, 72, 81, 89, 97],
    9: [25, 30, 36, 43, 52, 62, 74, 87, 100, 115, 130, 140, 155],
    10: [40, 48, 58, 70, 84, 100, 120, 140, 160, 185, 210, 230, 250],
    11: [60, 75, 90, 110, 130, 160, 190, 220, 250, 290, 320, 360, 400],
}
# alberi: scostamento superiore es (a–h) o inferiore ei (k–p)
ALBERO_ES = {
    "d": [-20, -30, -40, -50, -65, -80, -100, -120, -145, -170, -190, -210, -230],
    "e": [-14, -20, -25, -32, -40, -50, -60, -72, -85, -100, -110, -125, -135],
    "f": [-6, -10, -13, -16, -20, -25, -30, -36, -43, -50, -56, -62, -68],
    "g": [-2, -4, -5, -6, -7, -9, -10, -12, -14, -15, -17, -18, -20],
    "h": [0] * 13,
}
ALBERO_EI = {
    "k": [0, 1, 1, 1, 2, 2, 2, 3, 3, 4, 4, 4, 5],
    "m": [2, 4, 6, 7, 8, 9, 11, 13, 15, 17, 20, 21, 23],
    "n": [4, 8, 10, 12, 15, 17, 20, 23, 27, 31, 34, 37, 40],
    "p": [6, 12, 15, 18, 22, 26, 32, 37, 43, 50, 56, 62, 68],
}
# fori: H, G, F da EI; K7, M7, N7, P7 da tabella (ES) — i più usati nelle sedi di cuscinetti, spine e boccole
FORO_EI = {"H": [0] * 13, "G": [2, 4, 5, 6, 7, 9, 10, 12, 14, 15, 17, 18, 20], "F": [6, 10, 13, 16, 20, 25, 30, 36, 43, 50, 56, 62, 68]}
FORO_ES_7 = {
    "K": [0, 3, 5, 6, 6, 7, 9, 10, 12, 13, 16, 17, 18],
    "M": [-2, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0],
    "N": [-4, -4, -4, -5, -7, -8, -9, -10, -12, -14, -14, -16, -17],
    "P": [-6, -8, -9, -11, -14, -17, -21, -24, -28, -33, -36, -41, -45],
}


def _campo(d):
    d = float(d)
    if not 0 < d <= 500:
        raise ValueError("Tolleranze ISO 286 qui disponibili fino a Ø500")
    return next(i for i, lim in enumerate(CAMPI) if d <= lim)


def scostamenti(d, sigla):
    """(scostamento superiore, inferiore) in µm. Maiuscola = foro, minuscola = albero. Es. «H7», «g6», «js6», «K7»."""
    m = re.fullmatch(r"\s*([A-Za-z]{1,2})\s*(\d{1,2})\s*", str(sigla or ""))
    if not m:
        raise ValueError("Sigla di tolleranza non valida: %s (es. H7, g6, k5)" % sigla)
    lett, grado = m.group(1), int(m.group(2))
    if grado not in IT:
        raise ValueError("Grado IT%d non in tabella (IT5–IT11)" % grado)
    i = _campo(d)
    it = IT[grado][i]
    if lett in ("js", "JS"):
        return (it / 2, -it / 2)
    if lett.islower():
        if lett in ALBERO_ES:
            es = ALBERO_ES[lett][i]
            return (es, es - it)
        if lett in ALBERO_EI:
            ei = ALBERO_EI[lett][i] if not (lett == "k" and grado > 7) else 0
            return (ei + it, ei)
    else:
        if lett in FORO_EI:
            ei = FORO_EI[lett][i]
            return (ei + it, ei)
        if lett in FORO_ES_7:
            if grado != 7:
                raise ValueError("%s disponibile in grado 7 (es. %s7)" % (lett, lett))
            es = FORO_ES_7[lett][i]
            return (es, es - it)
    raise ValueError("Posizione «%s» non in tabella" % lett)


def limiti(d, sigla):
    sup, inf = scostamenti(d, sigla)
    d = float(d)
    return {"sigla": sigla, "nominale": d, "sup_um": sup, "inf_um": inf, "max": round(d + sup / 1000, 4), "min": round(d + inf / 1000, 4),
            "it_um": sup - inf, "foro": sigla[0].isupper(), "testo": "Ø%s %s (%s/%s)" % (_mm(d), sigla, _dev(sup), _dev(inf))}


def accoppiamento(d, foro, albero):
    f, a = limiti(d, foro), limiti(d, albero)
    if not f["foro"] or a["foro"]:
        raise ValueError("Scrivi prima la tolleranza del foro (maiuscola, es. H7) e poi quella dell'albero (minuscola, es. g6)")
    gmax = round((f["max"] - a["min"]) * 1000, 1)      # µm, positivo = gioco
    gmin = round((f["min"] - a["max"]) * 1000, 1)
    tipo = "con gioco" if gmin >= 0 else "con interferenza" if gmax <= 0 else "incerto"
    uso = {"con gioco": "parti che scorrono o ruotano (montaggio a mano)", "incerto": "centraggi precisi, montaggio con mazzuolo o leggera pressa",
           "con interferenza": "parti bloccate: montaggio alla pressa o a caldo"}[tipo]
    return {"foro": f, "albero": a, "gioco_max_um": gmax, "gioco_min_um": gmin, "tipo": tipo, "uso": uso,
            "sigla": "Ø%s %s/%s" % (_mm(d), foro, albero), "norma": "ISO 286-1/-2"}


def catena(anelli, sicurezza_rss=True):
    """Catena di tolleranza 1D. anelli: [{nome, nominale, sup, inf, verso: +1/-1}] in mm.
    Restituisce la quota di chiusura nel caso peggiore (aritmetico) e statistico (RSS, distribuzioni normali centrate)."""
    if not anelli or len(anelli) > 40:
        raise ValueError("Da 1 a 40 quote nella catena")
    nom = sum(a["verso"] * float(a["nominale"]) for a in anelli)
    vmax = sum(float(a["nominale"]) + (float(a["sup"]) if a["verso"] > 0 else float(a["inf"])) for a in anelli if a["verso"] > 0) - \
        sum(float(a["nominale"]) + float(a["inf"]) for a in anelli if a["verso"] < 0)
    vmin = sum(float(a["nominale"]) + float(a["inf"]) for a in anelli if a["verso"] > 0) - \
        sum(float(a["nominale"]) + float(a["sup"]) for a in anelli if a["verso"] < 0)
    centro = sum(a["verso"] * (float(a["nominale"]) + (float(a["sup"]) + float(a["inf"])) / 2) for a in anelli)
    semi = math.sqrt(sum(((float(a["sup"]) - float(a["inf"])) / 2) ** 2 for a in anelli))
    return {"nominale": round(nom, 4), "max_peggiore": round(vmax, 4), "min_peggiore": round(vmin, 4),
            "max_rss": round(centro + semi, 4), "min_rss": round(centro - semi, 4), "norma": "caso peggiore e RSS (ISO 286 per i singoli campi)"}


def _mm(v):
    v = float(v)
    return ("%.3f" % v).rstrip("0").rstrip(".").replace(".", ",")


def _dev(um):
    if abs(um) < 1e-9:
        return "0"
    return ("+" if um > 0 else "−") + ("%.3f" % (abs(um) / 1000)).rstrip("0").rstrip(".").replace(".", ",")
