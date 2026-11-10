"""Componenti commerciali dell'assieme: geometria semplificata, tolleranze e scelta delle misure unificate.

Cuscinetti radiali (ISO 15, tolleranze anelli ISO 492 classe normale), viti a testa cilindrica ISO 4762, spine cilindriche ISO 8734.
"""
import math

import cadquery as cq

from ..tolleranze.funzioni import CUSCINETTI

# ISO 492 classe normale: scostamento del diametro medio (µm), superiore 0
ISO492_FORO = [(10, -8), (18, -8), (30, -10), (50, -12), (80, -15), (120, -20)]     # (d fino a, Δdmp inferiore)
ISO492_ESTERNO = [(18, -8), (30, -9), (50, -11), (80, -13), (120, -15), (150, -18)]
VITI_L = (8, 10, 12, 16, 20, 25, 30, 35, 40, 45, 50, 55, 60, 65, 70, 80, 90, 100, 110, 120)
SPINE_L = (6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 26, 28, 30, 32, 35, 40, 45, 50, 55, 60, 70, 80, 90, 100)
TESTA_4762 = {"M3": (5.5, 3), "M4": (7, 4), "M5": (8.5, 5), "M6": (10, 6), "M8": (13, 8), "M10": (16, 10), "M12": (18, 12), "M16": (24, 16), "M20": (30, 20)}


def iso492(diametro, esterno=False):
    tab = ISO492_ESTERNO if esterno else ISO492_FORO
    inf = next((v for lim, v in tab if diametro <= lim), tab[-1][1])
    return (0, inf)


def solido_cuscinetto(codice):
    d, D, B = CUSCINETTI[codice]
    esterno = cq.Workplane("XY").circle(D / 2).circle(D / 2 - (D - d) * 0.22).extrude(B)
    interno = cq.Workplane("XY").circle(d / 2 + (D - d) * 0.22).circle(d / 2).extrude(B)
    sfere = cq.Workplane("XY").circle(d / 2 + (D - d) * 0.4).circle(d / 2 + (D - d) * 0.3).extrude(B * 0.7).translate((0, 0, B * 0.15))
    try:
        return esterno.union(interno).union(sfere).edges("%CIRCLE").chamfer(min(0.5, B * 0.04)).val()
    except Exception:
        return esterno.union(interno).union(sfere).val()


def solido_vite(m, lunghezza):
    dk, k = TESTA_4762[m]
    d = float(m[1:])
    testa = cq.Workplane("XY").circle(dk / 2).extrude(k).faces(">Z").workplane().polygon(6, d * 0.58).cutBlind(-k * 0.6)
    gambo = cq.Workplane("XY").circle(d / 2).extrude(-lunghezza)
    return testa.union(gambo).val()        # z=0 sotto la testa, gambo verso -Z


def solido_spina(d, lunghezza):
    s = cq.Workplane("XY").circle(d / 2).extrude(lunghezza)
    try:
        s = s.edges("%CIRCLE").chamfer(min(0.5, d * 0.1))
    except Exception:
        pass
    return s.val()


def lunghezza_vite(m, presa, filetto_disponibile, materiale_filetto="acciaio"):
    """Lunghezza unificata: sotto la testa la presa, poi un avvitamento di 1–2 d (1,5 d ideale in acciaio, 2 d in alluminio)."""
    d = float(m[1:])
    ideale = d * (2.0 if materiale_filetto == "alluminio" else 1.5)
    minimo = d * (1.5 if materiale_filetto == "alluminio" else 1.0)
    massimo = filetto_disponibile - 1.0           # non toccare il fondo del foro
    candidati = [L for L in VITI_L if minimo <= L - presa <= max(minimo, massimo)]
    if not candidati:
        L = next((x for x in VITI_L if x - presa >= minimo), VITI_L[-1])
        return L, L - presa, False
    L = min(candidati, key=lambda x: abs(x - presa - ideale))
    return L, L - presa, True


def lunghezza_spina(d, presa_a, presa_b):
    """Spina: entra in ciascun pezzo almeno 1,5 d (o quanto permettono i fori)."""
    voluta = min(presa_a, 1.5 * d + 2) + min(presa_b, 1.5 * d + 2)
    L = max([x for x in SPINE_L if x <= voluta] or [SPINE_L[0]])
    return L
