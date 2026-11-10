# MASTER CAD AI — Industrial Design Studio

Prototipo **CAD 3D online** utilizzabile da browser, senza licenze CAD a pagamento. Il modello viene elaborato sul server mediante CadQuery/OpenCascade; puoi descrivere forme e quote in italiano, usare il microfono quando il browser supporta la trascrizione, ruotare il modello ed esportare STEP/STL.

## Novità: Disegno come AutoCAD e reverse engineering da foto

Pagina **/disegno** (pulsante «📐 Disegno come AutoCAD» in alto):
- **Riga di comando come AutoCAD**, con nomi italiani, inglesi e alias: LINEA (L), PLINEA (PL), CERCHIO (C), ARCO (A), RETTANGOLO (REC), POLIGONO (POL), SPOSTA (M), COPIA (CO), RUOTA (RO), SPECCHIO (MI), SCALA (SC), OFFSET (O), RACCORDO (F), CIMA (CHA), TAGLIA (TR), ESTENDI (EX), ESPLODI (X), CANCELLA (E), ANNULLA (U), RIPRISTINA, ZOOM (Z), DIST (DI), ID, LISTA (LI), QUOTA (DLI), TESTO, ORTO (F8), SNAP (F9), OSNAP (F3), DXFIN/DXFOUT, ESTRUDI (EXT), RIVOLUZIONE (REV), AIUTO (F1).
- Coordinate: `100,50` assolute · `@30,0` relative · `@50<45` polari · un numero = distanza diretta verso il cursore. INVIO/SPAZIO ripete l'ultimo comando, ESC annulla, tasto destro = INVIO.
- Snap ad oggetto: estremo, medio, centro, quadrante, intersezione. Selezione a finestra (sinistra→destra) e intersecante (destra→sinistra).
- **DXF**: apre i DXF di AutoCAD (LINE, CIRCLE, ARC, LWPOLYLINE, POLYLINE) e salva in DXF R12.
- **3D**: ESTRUDI trasforma i contorni chiusi in solido (i contorni interni diventano fori); RIVOLUZIONE fa ruotare la mezza sezione (pezzi torniti). STEP/STL salvati in PostgreSQL.

**Reverse engineering da foto** (pannello a destra della tavola):
- Vista **dall'alto** (piastre, flange, staffe, sagome) → contorno esterno + fori (riconosciuti come cerchi) → ESTRUDI.
- Vista **di lato** (perni, alberi, boccole) → mezza sezione → RIVOLUZIONE.
- Scala: **foglio A4** sotto il pezzo (corregge anche la prospettiva) oppure **una misura vera** del pezzo.
- Elaborazione con OpenCV sul server, nessun servizio a pagamento. Una foto non mostra spessore, parti nascoste, gole interne o filetti: il disegno è una bozza da controllare (DIST, LISTA) e correggere con i comandi.

Codice: `mastercad/disegno/` (blueprint, pagina e motore comandi JS), `mastercad/reverse/` (blueprint e analisi della foto), `mastercad/profili.py` (dal 2D al solido CadQuery). Test: `tests/test_disegno_reverse.py`, `node tests/js/comandi.test.js`.

## Novità: assiemi con lo scopo

`/assiemi` (`mastercad/assiemi/`): i pezzi si montano da soli in base allo scopo dei loro fori. Il programma prova 4 rotazioni e il ribaltamento per allineare **fori spina** uguali (o passaggi vite sopra filetti), appoggia il pezzo sopra l'altro, mette **spine ISO 8734** e **viti ISO 4762** della lunghezza giusta (presa, avvitamento 1,5 d in acciaio / 2 d in alluminio, fondo del filetto) e, per ogni **sede cuscinetto**, il cuscinetto ISO 15 e un **albero generato** con il tratto k5 sotto l'anello interno e lo spallamento. Verifiche: giochi e interferenze degli anelli (tolleranze ISO 492 classe normale + ISO 286), presa delle spine, gioco dell'albero nel passaggio, collisioni fra tutti i componenti. Distinta base su più livelli (CSV), vista montata ed esplosa, AR con QR. L'albero generato si apre nel CAD: in tavola compare «Ø20 k5 (+0,011/+0,002)», nel ciclo la rettifica (o il terzista rettifiche), nel controllo l'anello P/NP. Test: `tests/test_assiemi.py`.

## Novità: il CAD che conosce lo scopo del pezzo e la tua officina

Pensato per il metalmeccanico (costruttori di macchine automatiche). L'idea: **ogni quota ha il suo perché** e il programma segue il filo requisito → geometria → tolleranza → processo → controllo, sulle macchine e con le tariffe della tua officina. L'AI propone, il motore geometrico e normativo verifica: niente risposte inventate.

- **Home a colori per area** (crea · scopo · officina · vendi e controlla · aiuto) e **manuale integrato**: il «?» in ogni pagina porta alla sezione giusta (`/manuale`).
- **Lo scopo delle quote** (`mastercad/tolleranze/`): sede cuscinetto (serie 60/62/63, ISO 15), foro spina (ISO 8734), sede boccola, passaggio vite, filetto. Tolleranze ISO 286 con i limiti (`iso286.py`: IT5–IT11, fori H/G/F/JS/K/M/N/P, alberi d–p), accoppiamenti, catene di tolleranza (caso peggiore e RSS). Il pulsante «Scopo» sull'albero mostra **l'impatto** prima di confermare (misure, nuovi problemi, volume). Indicazioni: «sede cuscinetto 6204 in 80,50», «foro spina Ø8 in 40,20», «boccola 20x23 in 30,60». I limiti arrivano in tavola, nel ciclo (barenatura sede, alesatura) e nel piano di controllo (tamponi P/NP).
- **La mia officina** (`mastercad/officina/`): macchine con corse e costo orario, terzisti con lavorazioni, tariffe e giorni, prezzi di materiali e trattamenti. Il ciclo sceglie la macchina in cui il pezzo entra o il terzista; preventivo e fattibilità usano questi dati.
- **Costo e fattibilità dal vivo** nel CAD, a ogni lavorazione, con la variazione rispetto alla modifica precedente.
- **Versioni e registro delle decisioni** (`mastercad/versioni/`): differenze per lavorazione (identificativi stabili), chi ha deciso cosa e con quale norma o calcolo, ripristino di qualsiasi versione.
- **Dal carico alla forma** (`mastercad/generativo/`): ottimizzazione topologica 2D SIMP (stato piano di tensione, filtro di densità, continuazione della penalizzazione) da viti, carichi, zone vietate e massa massima; contorno vero con fori esatti, verifica von Mises e spessore commerciale per il coefficiente di sicurezza voluto. Calcolo 2D lineare: per pezzi critici serve il FEM 3D.
- **Disegno tecnico**: per le piastre la frontale diventa la sezione A-A (scala più grande), tabella fori con limiti di tolleranza e componente.

Test: `tests/test_scopo_officina.py`.

## Novità: home a tile e strumenti d'officina

La home (`/`) è un **launchpad a tile in stile SAP Fiori**, ordinato come si lavora: 1 · Crea il pezzo → 2 · Prepara l'officina → 3 · Vendi e controlla → 4 · Formazione. Ogni tile dice in una riga cosa fa e mostra l'ultimo risultato (lavorazioni, minuti macchina, prezzo, esito del controllo). In alto il percorso in 5 passi e il «pezzo aperto», lo stesso per tutte le pagine. La vecchia pagina vocale è su `/parla`.

| Tile | Cosa fa | Codice |
|---|---|---|
| Libreria a norma | Flange EN 1092-1 PN16 (DN15–200), piastra forata, staffa a L, boccola, albero a gradini: progetto pronto e modificabile | `mastercad/libreria/` |
| Verifica fattibilità | Regole di officina: parete foro-bordo e foro-foro, lamature più profonde dello spessore, fori lunghi, filetti troppo corti/lunghi, angoli vivi delle tasche, fondi sottili, gusci sottili. Anche come avviso automatico nel CAD | `mastercad/fattibilita/` |
| Disegno tecnico | Tavola A3 metodo E: frontale, pianta, sezione A-A (o vista laterale) con linee nascoste (HLR OpenCascade), assonometria, quote d'ingombro, tabella fori con coordinate, viteria ISO 4762, note, cartiglio. PDF, DXF a layer, SVG | `mastercad/tavola/` |
| Ciclo di lavoro e CNC | Fasi (taglio, lato A, lato B, sbavatura, controllo), utensili, giri e avanzamenti dal materiale, tempi; programma ISO Fanuc/Haas (spianatura, contornatura, tasche, asole, rialzi, cicli fissi G81/G83/G84/G82/G85 con G98, interpolazione elicoidale dei fori oltre Ø25, barenatura), solo ASCII | `mastercad/ciclo/` |
| Preventivo istantaneo | Grezzo × €/kg + minuti × €/ora + attrezzaggio sul lotto + trattamento + scarto + margine, a scaglioni di quantità, stampabile | `mastercad/preventivo/` |
| Controllo qualità foto | Foto del pezzo prodotto su A4 → allineamento automatico (4 rotazioni + Kabsch robusto) → verbale OK/KO per ingombri e fori, sovrapposizione grafica, storico in PostgreSQL | `mastercad/qualita/` |
| Pezzo in AR | GLB in metri + `<model-viewer>` (incluso nel repo, Apache-2.0) + QR: il telefono apre il pezzo a grandezza reale (link pubblico a token, 7 giorni) | `mastercad/ar/` |
| Pannello docente / I miei esercizi | Corsi con codice, esercizi con foto e indicazioni, accesso allievi con PIN, diario delle azioni (comandi, foto, indicazioni, costruzioni), tempo lavorato, consegne con voto automatico (volumi, fori, ingombri, lavorazioni) e correzione del docente | `mastercad/corso/` |

Materiali e parametri di taglio sono in un solo posto (`mastercad/materiali.py`); tavola, ciclo, preventivo, fattibilità e controllo leggono le stesse misure (`mastercad/progetto/analisi.py`), così non si contraddicono. Test: `tests/test_officina.py`.

## Novità: progetto complesso con le indicazioni del tecnico

Dalla foto (o dal disegno) al **pezzo completo**, come in un CAD parametrico:

- **Albero delle lavorazioni**: forma di base + fori (Ø o filettati M2–M24, passanti o ciechi con punta a 118°, lamati per viti ISO 4762, svasati), serie polari e rettangolari di fori, tasche (anche con angoli raggiati), asole, rialzi/borchie/mozzi, raccordi e smussi degli spigoli, guscio. Ogni lavorazione si può sospendere o togliere: il pezzo si ricostruisce da capo. Quelle impossibili (fuori dal pezzo, raggio troppo grande) vengono **saltate con il motivo**, senza perdere il resto. Fori e tasche partono dalla faccia che incontrano davvero (es. sopra un rialzo).
- **Indicazioni del tecnico in italiano**, anche di massima: «diametro esterno 100; spessore 15; foro centrale Ø30 H7 con lamatura Ø40 profonda 5; 4 fori M8 lamati su interasse 70; foro M6 filettato profondo 12 in 0,40; tasca 40x20 profonda 6 in 30,50 raggio 4; asola 30x8 verticale in -40,0; rialzo Ø60 alto 5; raccordo R1 spigoli superiori; smusso 0.5 bordi inferiori; guscio spessore 3 aperto sotto». Le misure nominali **correggono quelle della foto** (scala, foro centrale portato in asse, corona di fori sostituita dalla serie esatta con l'orientamento della foto). Interprete a regole, deterministico: quello che non capisce lo dice, non lo inventa. Coordinate come nella tavola (comando ID), oppure «… dal centro».
- **Due viste**: foto (o disegno) dall'alto + foto di fronte → intersezione delle due estrusioni, per staffe a L, pezzi a gradini, spallamenti.
- **Comandi 3D dalla riga di comando**: FORO/HOLE (anche serie Polare/Rettangolare), TASCA/POCKET, ASOLA/SLOT, RIALZO/BOSS, RACCORDASPIGOLI/FILLETEDGE, SMUSSASPIGOLI/CHAMFEREDGE, GUSCIO/SHELL; in 2D SERIEPOLARE/ARRAYPOLAR e SERIERETT/ARRAYRECT.

Codice: `mastercad/progetto/` (`lavorazioni.py` motore dell'albero, `direttive.py` interprete delle indicazioni, blueprint e pannello). Test: `tests/test_progetto.py`.

## Funzioni disponibili (MVP)
- Piastra, blocco, cilindro e staffa a L parametrici, con controlli dimensionali
- Fori su piastre e blocchi, quote in mm, modifiche da testo o campi
- Visualizzatore 3D interattivo, download di geometrie STEP e STL
- Voce dal browser (Web Speech API): su alcuni browser può usare servizi esterni, **non è trascrizione locale o offline**
- Nessun codice arbitrario generato dall'AI: interprete linguistico deterministico. Non promette un CAD generativo universale.
- Disegni quotati: OCR online che estrae misure candidate; l'utente deve confermarle prima del CAD. Le foto senza quote non vengono ricostruite automaticamente.

## Deploy Railway
1. Railway → New Project → Deploy from GitHub Repo → `Maurizio-7887/MASTER-CAD-AI`.
2. Il progetto include `Dockerfile` e `railway.json`, per il motore CAD su Linux.
3. Aggiungere PostgreSQL al progetto Railway e configurare sul servizio applicativo `DATABASE_URL` usando la reference Railway `${{Postgres.DATABASE_URL}}`. Il nome del servizio PostgreSQL potrebbe essere diverso da `Postgres` e in tal caso va usato quello reale. In **Variables**, configurare inoltre:
   - `MASTER_CAD_PASSWORD` — password privata lunga per il login.
   - `FLASK_SECRET_KEY` — valore casuale diverso, almeno 32 caratteri, per firmare la sessione.
4. Railway → Networking → Generate Domain; apri il sito HTTPS, inserisci la password e prova il primo progetto.
5. Health check: `/health`.

**Persistenza PostgreSQL obbligatoria:** il codice legge `DATABASE_URL` da Railway, crea automaticamente la tabella `cad_projects` e salva nel database progetti, parametri, cronologia e file STEP/STL. Nessun utilizzo o fallback SQLite. Se la variabile manca o non contiene un URL PostgreSQL, l'app non parte, anziché perdere i dati.

## Costi e limiti
Software CAD open source, ma **Railway può avere costi di hosting**. Il browser può usare un servizio remoto di trascrizione. Non servono abbonamenti CAD.
I file CAD non certificano resistenza, sicurezza, materiali o tolleranze. Componenti automobilistici richiedono verifica tecnica prima della produzione, soprattutto se strutturali o relativi alla sicurezza.


## Modalità Disegno/Fotografia → quote (MVP OCR, 9 novembre 2026)

Nel pannello **3 · Foto e disegno quotato**:
1. Carica una tavola PNG/JPEG/WEBP da massimo 4 MB;
2. Premi **Leggi le quote dalla foto**: il servizio usa **Tesseract OCR locale sul server** (senza API a pagamento), legge etichette come lunghezza, larghezza, spessore, altezza e diametro, o annotazioni tipo `120 x 80 x 5`;
3. Le misure vengono mostrate come **candidate non verificate**; indica esplicitamente la forma (piastra, blocco, staffa L, cilindro);
4. **Prepara descrizione dalle quote da verificare**, correggi o completa ogni misura e premi **Comprendi istruzione → Costruisci 3D**; infine scarica STEP/STL.

Per una fotografia senza misure il programma **non inventa la scala**, né ricostruisce automaticamente le superfici nascoste. OCR non è Image-to-CAD neurale: l'integrazione di Img2CAD è oggetto di una fase sperimentale separata.

### Valutazione ZIP open source per Image-to-CAD

| Progetto | Fonte/licenza riscontrata nello ZIP | Impiego |
| --- | --- | --- |
| ai-cad | MIT | Riferimento per pianificazione/validazione di operazioni parametriche |
| Img2CAD (qq456cvb) | MIT per codice; base model e checkpoint da valutare separatamente | Pipeline neurale sperimentale GPU, non attiva in Railway; pretrained focalizzati su categorie come mobili |
| GenCAD (ferdous-alam) | **Nessun file di licenza trovato nello ZIP** | Solo studio tecnico, niente incorporazione del codice |
| CADAM (Adam-CAD) | GPLv3 | Studio dell'esperienza utente e controlli parametrici; non incorporato |
| FreeCAD | Licenze upstream da rispettare | Possibile integrazione kernel/workbench in futuro |

**Non sono stati copiati sorgenti di questi ZIP nel progetto attuale**: la funzione OCR è una piccola implementazione originale che utilizza Tesseract. Il software CAD open source non richiede licenze a pagamento, ma Railway può addebitare hosting/risorse. Per un'inferenza neurale con Img2CAD servirebbe un ambiente CUDA, checkpoint compatibili, gestione delle licenze e test su parti meccaniche industriali. È improprio dichiarare automaticamente producibili pezzi ottenuti da un'immagine: occorre confermare quote, tolleranze, materiali e carichi.

## Architettura ibrida attivabile in futuro — GPU temporaneamente bypassata

L'app ospita ora un **selettore di backend** con modalità CPU su Railway e connettore **opzionale** verso un worker NVIDIA esterno. Senza le variabili GPU, la modalità CPU resta operativa; il sito espone chiaramente `GPU non collegata` e il pulsante GPU è disabilitato. Non installiamo PyTorch/CUDA nel Dockerfile Railway, preservando requisiti e tempi di avvio.

Con un worker GPU autenticato e installato:
- `MASTER_CAD_GPU_WORKER_URL=https://dominio-pubblico-https-del-worker`
- `MASTER_CAD_GPU_WORKER_TOKEN=token-lungo-e-privato`

Il worker, il suo protocollo e i requisiti dei checkpoint sono documentati in [gpu_worker/README.md](gpu_worker/README.md). **Non attivare le variabili fino a quando non esistono un worker funzionante, un adapter testato e i checkpoint.** Il semplice acquisto della scheda NVIDIA non basta a completare l'inferenza Img2CAD.

Il generatore produce ora anche un **albero delle operazioni parametriche effettivamente eseguite**: schizzo, estrusione, raccordo e fori. Tale albero non è una ricostruzione neurale della storia originaria del pezzo fotografato.

### Modelli sperimentali e licenze

Img2CAD è un progetto accademico con licenza MIT per il codice: i checkpoint pubblici di LlamaFT/TrAssembler sono principalmente su classi di mobili. Non vengono copiati pesi o modelli nel repository; occorre verificare termini, hardware e precisione sulle geometrie industriali prima dell'adozione. GenCAD e CADAM rimangono riferimenti di ricerca, non componenti incorporati nell'app.

### Limiti per produzione automobilistica

La geometria CAD prodotta è una **bozza da verificare**. Nessun componente è certificato per auto, sicurezza o uso strutturale. Per la fabbricazione occorrono quote rilevate fisicamente, controlli di tolleranza, materiale, carichi e verifica tecnica competente.

## Configurazione database PostgreSQL (obbligatoria)

Su Railway, nel servizio MASTER-CAD-AI, configurare `DATABASE_URL` come **reference** al database PostgreSQL del progetto, ad esempio `${{Postgres.DATABASE_URL}}`. Non incollare una password reale nel repository. È necessario utilizzare il nome effettivo del servizio PostgreSQL indicato in Railway. L'app usa `psycopg2` e crea `cad_projects` alla partenza. L'endpoint di elenco `/api/projects` e il download `/api/export/<id>?format=step|stl` leggono dal database e non da cartelle locali. Nessuna dipendenza SQLite.

## Esempio industriale avanzato — flangia forata

Dal pannello **Esempi da dire al microfono**, scegliere **Flangia industriale** oppure pronunciare: 

> Crea una flangia diametro esterno 100 mm spessore 12 mm foro centrale 30 mm interasse fori 70 mm quattro fori fissaggio 8 mm.

Il motore genera un unico solido B-Rep con schizzo circolare, estrusione, foro centrale passante e quattro fori su circonferenza di passo. Le dimensioni sono parametriche e il risultato è esportabile in STEP/STL, salvato in PostgreSQL. Modelli e quote sono dimostrativi, da verificare prima di qualsiasi fabbricazione. Non è una flangia certificata o pronta per un impianto/veicolo.
