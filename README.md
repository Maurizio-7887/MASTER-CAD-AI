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
