# MASTER CAD AI — Industrial Design Studio

Prototipo **CAD 3D online** utilizzabile da browser, senza licenze CAD a pagamento. Il modello viene elaborato sul server mediante CadQuery/OpenCascade; puoi descrivere forme e quote in italiano, usare il microfono quando il browser supporta la trascrizione, ruotare il modello ed esportare STEP/STL.

## Funzioni disponibili (MVP)
- Piastra, blocco, cilindro e staffa a L parametrici, con controlli dimensionali
- Fori su piastre e blocchi, quote in mm, modifiche da testo o campi
- Visualizzatore 3D interattivo, download di geometrie STEP e STL
- Voce dal browser (Web Speech API): su alcuni browser può usare servizi esterni, **non è trascrizione locale o offline**
- Nessun codice arbitrario generato dall'AI: interprete linguistico deterministico. Non promette un CAD generativo universale.
- Fotografie: solo riferimento visivo. **Non è ancora implementata la conversione foto → CAD.**

## Deploy Railway
1. Railway → New Project → Deploy from GitHub Repo → `Maurizio-7887/MASTER-CAD-AI`.
2. Il progetto include `Dockerfile` e `railway.json`, per il motore CAD su Linux.
3. In **Variables**, creare due variabili **separate**:
   - `MASTER_CAD_PASSWORD` — password privata lunga per il login.
   - `FLASK_SECRET_KEY` — valore casuale diverso, almeno 32 caratteri, per firmare la sessione.
4. Railway → Networking → Generate Domain; apri il sito HTTPS, inserisci la password e prova il primo progetto.
5. Health check: `/health`.

**Attenzione:** i file STEP/STL sono temporanei (filesystem Railway effimero): scaricali subito. Lo storage persistente sarà un'evoluzione. Non serve PostgreSQL per questa demo iniziale.

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
