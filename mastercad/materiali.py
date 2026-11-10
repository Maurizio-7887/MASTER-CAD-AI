"""Materiali di officina: densità, prezzo indicativo al kg e parametri di taglio di partenza.

Valori medi di riferimento (cataloghi utensili e listini 2026): sono un punto di partenza per il ciclo
e il preventivo, non sostituiscono i dati del fornitore. Si aggiornano qui, in un posto solo.
vc_* in m/min (punta HSS, fresa in metallo duro, maschio, tornio), fz in mm/dente, taglio in mm²/min (sega a nastro).
"""

MATERIALI = {
    "S235": {"nome": "Acciaio S235JR (Fe360)", "densita": 7.85, "euro_kg": 1.40, "vc_punta": 25, "vc_fresa": 180, "vc_maschio": 10, "vc_tornio": 200, "fz": 0.06, "taglio": 2500},
    "C45": {"nome": "Acciaio C45", "densita": 7.85, "euro_kg": 1.80, "vc_punta": 20, "vc_fresa": 150, "vc_maschio": 8, "vc_tornio": 180, "fz": 0.05, "taglio": 2000},
    "42CrMo4": {"nome": "Acciaio 42CrMo4 bonificato", "densita": 7.85, "euro_kg": 2.90, "vc_punta": 15, "vc_fresa": 110, "vc_maschio": 6, "vc_tornio": 140, "fz": 0.05, "taglio": 1400},
    "AISI304": {"nome": "Inox AISI 304", "densita": 7.90, "euro_kg": 4.80, "vc_punta": 10, "vc_fresa": 90, "vc_maschio": 4, "vc_tornio": 120, "fz": 0.04, "taglio": 1000},
    "AL6082": {"nome": "Alluminio EN AW-6082 T6", "densita": 2.70, "euro_kg": 4.60, "vc_punta": 60, "vc_fresa": 400, "vc_maschio": 20, "vc_tornio": 500, "fz": 0.08, "taglio": 8000},
    "OTTONE": {"nome": "Ottone CW614N", "densita": 8.50, "euro_kg": 8.00, "vc_punta": 50, "vc_fresa": 250, "vc_maschio": 15, "vc_tornio": 300, "fz": 0.08, "taglio": 6000},
    "GHISA": {"nome": "Ghisa EN-GJL-250", "densita": 7.20, "euro_kg": 2.10, "vc_punta": 20, "vc_fresa": 140, "vc_maschio": 8, "vc_tornio": 160, "fz": 0.08, "taglio": 2000},
    "POM": {"nome": "Tecnopolimero POM-C", "densita": 1.41, "euro_kg": 7.50, "vc_punta": 50, "vc_fresa": 300, "vc_maschio": 20, "vc_tornio": 300, "fz": 0.10, "taglio": 9000},
}

# trattamenti superficiali, €/kg indicativi (conto terzi, lotto medio)
TRATTAMENTI = {
    "nessuno": {"nome": "Nessuno", "euro_kg": 0.0},
    "zincatura": {"nome": "Zincatura elettrolitica", "euro_kg": 1.10},
    "brunitura": {"nome": "Brunitura", "euro_kg": 1.60},
    "verniciatura": {"nome": "Verniciatura a polvere", "euro_kg": 2.60},
    "anodizzazione": {"nome": "Anodizzazione (solo alluminio)", "euro_kg": 6.00},
}

# passo della filettatura metrica grossa
PASSO = {"M2": 0.4, "M2.5": 0.45, "M3": 0.5, "M4": 0.7, "M5": 0.8, "M6": 1.0, "M8": 1.25, "M10": 1.5, "M12": 1.75,
         "M14": 2.0, "M16": 2.0, "M18": 2.5, "M20": 2.5, "M22": 2.5, "M24": 3.0}


def materiale(codice):
    m = MATERIALI.get(str(codice or "S235").upper().replace(" ", ""))
    if m is None:
        raise ValueError("Materiale sconosciuto: scegli fra " + ", ".join(MATERIALI))
    return m


def elenco():
    return [{"codice": k, "nome": v["nome"], "euro_kg": v["euro_kg"], "densita": v["densita"]} for k, v in MATERIALI.items()]
