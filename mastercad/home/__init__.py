"""Home a tile in stile SAP Fiori: orienta il disegnatore fra tutte le funzioni, nell'ordine in cui si lavora."""
from flask import Blueprint, render_template, session

bp = Blueprint("home", __name__, template_folder="templates", static_folder="static", static_url_path="/home/static")

# (gruppo, descrizione, colore, [ (url, icona, titolo, sottotitolo, chiave_kpi, solo_docente) ])
GRUPPI = [
    ("1 · Crea il pezzo", "Da una foto, da un disegno, da un pezzo a norma o direttamente dai carichi.", "#0a6ed1", [
        ("/disegno#foto", "foto", "Dalla foto al 3D", "Fotografa il pezzo su un foglio A4: contorno e fori in millimetri", "foto", False),
        ("/disegno", "cad", "Disegno CAD", "Comandi come AutoCAD, indicazioni del tecnico, albero delle lavorazioni, costo dal vivo", "lavorazioni", False),
        ("/libreria", "libro", "Libreria a norma", "Flange EN 1092-1, piastre, staffe, boccole, alberi: pronti in un clic", "libreria", False),
        ("/generativo", "dna", "Dal carico alla forma", "Viti, carichi e massa massima: il programma scolpisce la forma e sceglie lo spessore", "generativo", False),
        ("/parla", "voce", "Progetta parlando", "Descrivi il pezzo a voce o per iscritto", None, False),
    ]),
    ("2 · Progetta con lo scopo", "Ogni quota ha il suo perché: componente, accoppiamento, norma, decisione.", "#7858ff", [
        ("/assiemi", "assieme", "Assiemi con lo scopo", "Si montano da soli; tolleranze geometriche dedotte, montaggio guidato sul telefono", "assiemi", False),
        ("/tolleranze", "calibro", "Accoppiamenti e tolleranze", "ISO 286, catene di tolleranza, cuscinetti, spine e boccole a catalogo", None, False),
        ("/fattibilita", "scudo", "Verifica fattibilità", "Pareti, fori al bordo, sedi, filetti, tolleranze costose, pezzo che non entra in macchina", "fattibilita", False),
        ("/versioni", "storia", "Versioni e decisioni", "Cosa è cambiato, chi l'ha deciso e con quale norma; torna a qualsiasi versione", None, False),
    ]),
    ("3 · Officina", "Dal modello 3D a quello che serve per produrre, con le tue macchine.", "#e76500", [
        ("/tavola", "tavola", "Disegno tecnico", "Tavola A3 con viste, sezione, tolleranze con i limiti, tabella fori, cartiglio (PDF, DXF)", "tavola", False),
        ("/ciclo", "ingranaggio", "Ciclo di lavoro e CNC", "Fasi sulle tue macchine o dal terzista, utensili, tempi, programma ISO, piano di controllo", "ciclo", False),
        ("/officina", "fabbrica", "La mia officina", "Macchine con corse e costo orario, terzisti, prezzi di materiali e trattamenti", None, False),
    ]),
    ("4 · Vendi e controlla", "Prezzo al cliente, controllo del pezzo prodotto, presentazione.", "#188918", [
        ("/preventivo", "euro", "Preventivo istantaneo", "Prezzo per quantità con le tariffe della tua officina e dei terzisti", "preventivo", False),
        ("/qualita", "qualita", "Controllo qualità foto", "Foto del pezzo prodotto confrontata con il progetto, con verbale", "qualita", False),
        ("/ar", "cubo", "Pezzo in realtà aumentata", "Inquadra il QR col telefono: il pezzo sul tavolo a grandezza reale", "ar", False),
    ]),
    ("5 · Aiuto", "Il manuale dentro il programma: in ogni pagina il «?» porta alla spiegazione giusta.", "#556b82", [
        ("/manuale", "aiuto", "Manuale d'uso", "Come si lavora, passo per passo, con esempi di indicazioni da scrivere", None, False),
    ]),
]


@bp.get("/")
def launchpad():
    allievo = session.get("allievo") if not session.get("ok") else None
    gruppi = []
    for nome, desc, colore, tile in GRUPPI:
        t = [x for x in tile if not (x[5] and allievo)]
        if t:
            gruppi.append((nome, desc, colore, t))
    return render_template("home/launchpad.html", csrf=session.get("csrf", ""), gruppi=gruppi, allievo=allievo)


@bp.get("/manuale")
def manuale():
    return render_template("home/manuale.html", csrf=session.get("csrf", ""))
