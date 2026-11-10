"""Home a tile in stile SAP Fiori: orienta il disegnatore fra tutte le funzioni, nell'ordine in cui si lavora."""
from flask import Blueprint, render_template, session

bp = Blueprint("home", __name__, template_folder="templates", static_folder="static", static_url_path="/home/static")

# (gruppo, [ (url, icona, titolo, sottotitolo, chiave_kpi, solo_docente) ])
GRUPPI = [
    ("1 · Crea il pezzo", "Parti da una foto, da un disegno o da un pezzo a norma.", [
        ("/disegno#foto", "foto", "Dalla foto al 3D", "Fotografa il pezzo su un foglio A4: contorno e fori in millimetri", "foto", False),
        ("/disegno", "cad", "Disegno CAD", "Comandi come AutoCAD, indicazioni del tecnico, albero delle lavorazioni", "lavorazioni", False),
        ("/libreria", "libro", "Libreria a norma", "Flange EN 1092-1, piastre, staffe, boccole, alberi: pronti in un clic", "libreria", False),
        ("/parla", "voce", "Progetta parlando", "Descrivi il pezzo a voce o per iscritto", None, False),
    ]),
    ("2 · Prepara l'officina", "Dal modello 3D a quello che serve per produrre.", [
        ("/fattibilita", "scudo", "Verifica fattibilità", "Il tecnico esperto controlla pareti, fori, tasche e filetti", "fattibilita", False),
        ("/tavola", "tavola", "Disegno tecnico", "Tavola A3 con viste, sezione, quote, tabella fori e cartiglio (PDF, DXF)", "tavola", False),
        ("/ciclo", "ingranaggio", "Ciclo di lavoro e CNC", "Fasi, utensili, tempi e programma ISO per il centro di lavoro", "ciclo", False),
    ]),
    ("3 · Vendi e controlla", "Prezzo al cliente, controllo del pezzo prodotto, presentazione.", [
        ("/preventivo", "euro", "Preventivo istantaneo", "Materiale, tempi e costi: prezzo per 1, 10, 50, 100 pezzi", "preventivo", False),
        ("/qualita", "qualita", "Controllo qualità foto", "Foto del pezzo prodotto confrontata con il progetto, con verbale", "qualita", False),
        ("/ar", "cubo", "Pezzo in realtà aumentata", "Inquadra il QR col telefono: il pezzo sul tavolo a grandezza reale", "ar", False),
    ]),
    ("4 · Formazione", "Esercizi «dalla foto al pezzo» corretti in automatico.", [
        ("/corso/docente", "docente", "Pannello docente", "Corsi, esercizi, chi ha lavorato, quanto tempo, voti da confermare", "docente", True),
        ("/corso/allievo", "allievo", "I miei esercizi", "Consegne del docente, foto, indicazioni e voto", "esercizi", False),
    ]),
]


@bp.get("/")
def launchpad():
    allievo = session.get("allievo") if not session.get("ok") else None
    gruppi = []
    for nome, desc, tile in GRUPPI:
        t = [x for x in tile if not (x[5] and allievo) and not (x[2] == "I miei esercizi" and not allievo)]
        if t:
            gruppi.append((nome, desc, t))
    return render_template("home/launchpad.html", csrf=session.get("csrf", ""), gruppi=gruppi, allievo=allievo)
