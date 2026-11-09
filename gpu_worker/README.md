# MASTER CAD AI — modulo GPU NVIDIA (predisposto, non ancora attivo)

Questo modulo è **parte del repository** ma non viene caricato nel container Railway, per non richiedere CUDA e non interrompere il CAD 3D online.

## Stato reale

- **Online oggi:** CAD parametrico 3D, voce dal browser se supportata, OCR delle quote da immagini, STEP/STL e albero di costruzione per i solidi generati.
- **Pronto come infrastruttura:** connettore HTTPS Railway → worker NVIDIA, autenticazione Bearer, controlli sulla geometria proposta, caduta controllata alla modalità OCR se il worker è assente.
- **Non ancora operativo:** inferenza neurale Img2CAD/GenCAD su fotografie. Non sono inclusi pesi dei modelli o codice dei repository di ricerca. Non è dichiarata alcuna accuratezza industriale.

## Perché non installiamo Img2CAD su Railway oggi?

I checkpoint del repository Img2CAD per LlamaFT e TrAssembler sono **modelli esterni**, da scaricare e verificare separatamente. I pesi pubblicati si riferiscono in particolare a sedie, tavoli e mobili: non esiste una garanzia che ricostruiscano una staffa automobilistica. Il modello originale si aspetta un ambiente CUDA e una struttura dati/geometry tree diversi dal nostro schema parametrico.

GenCAD è un'altra pipeline di ricerca con checkpoint, CUDA e licenza da verificare: non viene incorporata automaticamente.

## Quando avremo la NVIDIA

1. Preparare una workstation con driver NVIDIA, CUDA/PyTorch compatibili e **checkpoint con termini di utilizzo verificati**.
2. Testare l'inferenza Image-to-CAD dalla sorgente originale, senza usare dati riservati.
3. Scrivere un piccolo **adapter** affidabile per convertire e verificare la rappresentazione CAD prodotta dal modello in uno schema compatibile con il nostro validatore. Il worker accetta solo un modulo affidabile specificato dal proprietario nella variabile `MASTER_CAD_IMAGE_MODEL_ADAPTER`, per esempio `my_trusted_adapter:infer`.
4. Avviare `gpu_worker/server.py` su un servizio con GPU. Il modulo richiede `Flask` e `torch` installato nell'ambiente GPU, e **non si dichiara pronto** finché CUDA e l'adapter non sono configurati.
5. Esporre il servizio mediante un **canale HTTPS autenticato**; non pubblicare direttamente una porta sul PC domestico. Configurare lo stesso token privato su entrambi i servizi.
6. Solo dopo un test positivo, configurare in Railway:
   - `MASTER_CAD_GPU_WORKER_URL=https://hostname-del-worker`
   - `MASTER_CAD_GPU_WORKER_TOKEN=token-segreto-lungo`
7. Il pannello MASTER CAD AI abiliterà il pulsante GPU. Ogni proposta richiederà conferma di quote, spessori, fori e materiali; nessuna geometria viene certificata automaticamente.

Il server GPU usa l'API:
- `GET /health`: indicatore minimale pubblico, senza dati hardware.
- `GET /capabilities`: autenticato, riporta CUDA/adattatore.
- `POST /infer`: autenticato, riceve `image_b64` e `category` e accetta dall'adapter **solo** una proposta `{"spec": {...}}` con le forme supportate. Non accetta script Python o modelli non strutturati.

**Limitazione da risolvere nella seconda iterazione neurale:** se Img2CAD genera un albero CAD più generale dei quattro tipi attuali, occorre sviluppare un convertitore geometrico più ampio, con validazione B-Rep e gestione verificabile delle quote. La sola presenza di CUDA non abilita questa funzionalità.

## Costi

Il codice open source non richiede licenze CAD commerciali. Railway può addebitare il server; un eventuale worker GPU cloud può avere tariffe a consumo. La futura workstation sarà un'alternativa al cloud GPU, ma per essere raggiungibile da Railway richiederà una connessione sicura e disponibile.
