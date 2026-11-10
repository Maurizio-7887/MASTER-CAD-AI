"""Verifica di fattibilità: le regole del tecnico esperto controllate sul progetto prima che arrivi in officina.

Regole fisse e spiegate (niente scatola nera): ogni avviso dice dove, perché e come rimediare.
Livelli: «errore» (non si può fare o si rompe), «attenzione» (si fa ma costa o rischia), «consiglio».
"""
import math

import cadquery as cq

from ..progetto.analisi import _num, contorno_esterno, descrivi_foro

MIN_PARETE_METALLO = 1.5


def _dist_bordo(facce, x, y):
    """Distanza del punto dal contorno esterno della pianta (None se il pezzo non ha una pianta piana)."""
    if not facce:
        return None
    v = cq.Vertex.makeVertex(x, y, 0)
    return min(v.distance(f.outerWire()) for f in facce)


def verifica(an, officina=None):
    avvisi = []

    def add(livello, dove, testo, rimedio):
        avvisi.append({"livello": livello, "dove": dove, "testo": testo, "rimedio": rimedio})

    for s in an["saltate"]:
        add("errore", "Lavorazione %d (%s)" % (s["indice"] + 1, s["tipo"]), "Non eseguita: %s" % s["motivo"].replace("SALTATA: ", ""),
            "Correggi le misure nell'albero delle lavorazioni o toglila.")
    facce = contorno_esterno(an["base"])
    fori = an["fori"]
    for f in fori:
        dove = "Foro %d (%s)" % (f["rif"], descrivi_foro(f))
        r_ext = max(f["d"], float((f["lamatura"] or {}).get("d", 0)), float((f["svasatura"] or {}).get("d", 0))) / 2
        db = _dist_bordo(facce, f["x"], f["y"])
        if db is not None:
            parete = db - r_ext
            minimo = max(MIN_PARETE_METALLO, 0.5 * f["d"])
            if parete < 0:
                add("errore", dove, "Il foro (o la sua lamatura) esce dal bordo del pezzo di %s mm." % _num(-parete),
                    "Spostalo verso l'interno di almeno %s mm o riduci il diametro." % _num(-parete + minimo))
            elif parete < minimo:
                add("attenzione", dove, "Parete fra foro e bordo di soli %s mm: si deforma in foratura e sotto carico." % _num(parete),
                    "Lascia almeno %s mm (metà del diametro, minimo %s mm)." % (_num(minimo), _num(MIN_PARETE_METALLO)))
        if f["lamatura"] and float(f["lamatura"]["prof"]) >= f["spessore"] - 1.0:
            if f["lamatura"].get("tolleranza"):
                add("errore", dove, "La sede è profonda %s mm su uno spessore di %s mm: non resta lo spallamento che tiene il cuscinetto." % (
                    _num(f["lamatura"]["prof"]), _num(f["spessore"])), "Aumenta lo spessore di almeno %s mm o usa una sede cieca con anello elastico." % _num(float(f["lamatura"]["prof"]) + 3 - f["spessore"]))
            else:
                add("errore", dove, "La lamatura è profonda %s mm su uno spessore di %s mm: sotto la testa della vite non resta materiale." % (
                    _num(f["lamatura"]["prof"]), _num(f["spessore"])), "Usa una vite a testa ribassata (ISO 7380) o aumenta lo spessore.")
        # tolleranze: quanto costano e cosa servono
        for d_, sig in ((f["d"], f["tolleranza"]), (float((f["lamatura"] or {}).get("d") or 0), (f["lamatura"] or {}).get("tolleranza"))):
            if not sig:
                continue
            grado = int("".join(c for c in sig if c.isdigit()) or 7)
            if grado <= 6:
                add("attenzione", dove, "Tolleranza %s (IT%d) su Ø%s: serve rettifica interna o barenatura fine, costosa." % (sig, grado, _num(d_)),
                    "Se l'accoppiamento lo permette usa IT7 (es. H7): costa molto meno.")
        fz = f.get("funzione") or {}
        if fz.get("tipo") == "foro_spina":
            presa = f["prof"] if not f["passante"] else f["spessore"]
            if presa < 1.5 * f["d"]:
                add("attenzione", dove, "La spina entra solo per %s mm (meno di 1,5 volte il diametro): centra poco." % _num(presa),
                    "Porta la presa ad almeno %s mm o usa una spina più piccola." % _num(1.5 * f["d"]))
        if not f["passante"] and f["prof"] > 10 * f["d_punta"]:
            add("attenzione", dove, "Foro cieco molto profondo (%s volte il diametro): serve punta lunga e scarico truciolo." % _num(f["prof"] / f["d_punta"]),
                "Se possibile fallo passante o riduci la profondità.")
        elif f["passante"] and f["spessore"] > 12 * f["d_punta"]:
            add("attenzione", dove, "Foro lungo %s volte il diametro: la punta può deviare." % _num(f["spessore"] / f["d_punta"]),
                "Aumenta il diametro o prevedi foratura da entrambi i lati.")
        if f["d_punta"] < 1.0:
            add("attenzione", dove, "Foro sotto 1 mm: punte fragili, si rompono facilmente.", "Valuta elettroerosione o un diametro maggiore.")
        if f["filetto"]:
            d = f["d"]
            if not f["passante"]:
                utile = f["prof"]
                if utile > 2.5 * d:
                    add("consiglio", dove, "Filetto profondo %s mm: oltre 1,5–2 volte il diametro non aumenta la tenuta." % _num(utile),
                        "Riduci a %s mm: risparmi tempo di maschiatura." % _num(2 * d))
                if utile < d:
                    add("attenzione", dove, "Filetto di soli %s mm: la vite tiene poco (meno di un diametro)." % _num(utile),
                        "Porta il filetto ad almeno %s mm o usa un dado." % _num(1.5 * d))
                if f["spessore"] - f["prof"] < 1.0:
                    add("attenzione", dove, "Il fondo del foro filettato resta quasi a filo dell'altra faccia (%s mm)." % _num(f["spessore"] - f["prof"]),
                        "Fallo passante oppure lascia almeno 1 mm di fondo.")
            elif f["spessore"] < 1.0 * d:
                add("attenzione", dove, "Filetto passante su %s mm di spessore: meno di un diametro di presa." % _num(f["spessore"]),
                    "Usa un dado o un inserto filettato.")
        if f["tolleranza"] and not f["passante"] and f["prof"] < f["d"]:
            add("consiglio", dove, "Foro di precisione cieco e corto: l'alesatore ha bisogno di spazio sotto.", "Prevedi uno scarico o fallo passante.")
    # pareti fra fori vicini
    for i, a in enumerate(fori):
        for b in fori[i + 1:]:
            if a["da_sotto"] != b["da_sotto"]:
                continue
            ra = max(a["d"], float((a["lamatura"] or {}).get("d", 0))) / 2
            rb = max(b["d"], float((b["lamatura"] or {}).get("d", 0))) / 2
            parete = math.hypot(a["x"] - b["x"], a["y"] - b["y"]) - ra - rb
            if parete < 0:
                add("errore", "Fori %d e %d" % (a["rif"], b["rif"]), "I fori (o le lamature) si sovrappongono di %s mm." % _num(-parete),
                    "Distanziali di almeno %s mm o riduci i diametri." % _num(-parete + MIN_PARETE_METALLO))
            elif parete < MIN_PARETE_METALLO:
                add("attenzione", "Fori %d e %d" % (a["rif"], b["rif"]), "Parete di soli %s mm fra i due fori." % _num(parete),
                    "Lascia almeno %s mm." % _num(MIN_PARETE_METALLO))
    for t in an["tasche"]:
        d = t["dati"]
        nome = "Asola" if t["tipo"] == "asola" else "Tasca"
        dove = "%s in (%s; %s)" % (nome, _num((d.get("centro") or [0, 0])[0]), _num((d.get("centro") or [0, 0])[1]))
        if t["tipo"] == "tasca" and d.get("forma", "rett") == "rett" and t["raggio_angoli"] <= 0:
            add("attenzione", dove, "Angoli interni vivi: una fresa li lascia sempre arrotondati (raggio della fresa).",
                "Indica «raggio %s» o più, oppure accetta l'erosione a filo." % _num(max(1, min(t["larghezza_min"] / 4, 6))))
        if t["raggio_angoli"] and t["raggio_angoli"] < 1.0:
            add("attenzione", dove, "Raggio degli angoli di %s mm: serve una fresa di Ø%s, lenta e fragile." % (_num(t["raggio_angoli"]), _num(2 * t["raggio_angoli"])),
                "Porta il raggio ad almeno 3 mm se il pezzo accoppiato lo permette.")
        if not t["passante"] and t["prof"] > 4 * t["larghezza_min"]:
            add("attenzione", dove, "Profonda %s mm e larga %s: la fresa lunga vibra e si flette." % (_num(t["prof"]), _num(t["larghezza_min"])),
                "Riduci la profondità o allarga la cava (rapporto massimo 4:1).")
        if not t["passante"]:
            sotto = t["spessore"] - t["prof"]
            if sotto <= 0:
                add("errore", dove, "È più profonda del pezzo (%s mm su %s): diventa passante." % (_num(t["prof"]), _num(t["spessore"])),
                    "Scrivi «passante» se è voluto, altrimenti riduci la profondità.")
            elif sotto < MIN_PARETE_METALLO:
                add("errore", dove, "Sul fondo restano solo %s mm di materiale." % _num(sotto), "Riduci la profondità o falla passante.")
        db = _dist_bordo(facce, float((d.get("centro") or [0, 0])[0]), float((d.get("centro") or [0, 0])[1]))
        if db is not None and t["tipo"] in ("tasca", "asola"):
            meta = (max(float(d.get("l", 0)), float(d.get("w", 0)), float(d.get("d", 0)), float(d.get("lunghezza", 0))) / 2) or t["larghezza_min"] / 2
            if db < t["larghezza_min"] / 2 + MIN_PARETE_METALLO and db < meta:
                add("attenzione", dove, "È molto vicina al bordo: la parete esterna può risultare sottile.", "Controlla la parete in tavola o spostala.")
    if an["guscio"] and an["guscio"]["spessore"] < 1.5:
        add("attenzione", "Guscio", "Pareti di %s mm: lavorandole si deformano e vibrano." % _num(an["guscio"]["spessore"]),
            "Per pezzi lavorati di macchina resta sopra 1,5–2 mm; sotto, pensa a lamiera piegata.")
    if officina:
        from ..officina import scegli_macchina
        from ..progetto.analisi import grezzo
        g = grezzo(an)
        tipo = "tornio" if an["base"].get("tipo") == "rivoluzione" else "fresa"
        mac = scegli_macchina(officina, tipo, (g["y"], g["x"]) if tipo == "tornio" else (g["x"], g["y"], g["z"]))
        if not mac.get("interna"):
            add("attenzione", "Officina", "Nessuna macchina interna adatta: %s." % (mac.get("motivo") or ""),
                "La lavorazione va a «%s»%s: controlla tempi di consegna e costi." % (mac["nome"].replace("Terzista: ", ""), " (circa %d giorni)" % mac["giorni"] if mac.get("giorni") else ""))
    ing = an["ingombro"]
    if min(ing["x"], ing["y"], ing["z"]) < 1.0:
        add("attenzione", "Pezzo", "Uno spessore sotto 1 mm: difficile da bloccare in macchina.", "Valuta il taglio laser da lamiera.")
    if not avvisi:
        add("consiglio", "Pezzo", "Nessun problema trovato dalle regole di officina.", "Controlla comunque tolleranze e accoppiamenti con il tecnico.")
    ordine = {"errore": 0, "attenzione": 1, "consiglio": 2}
    avvisi.sort(key=lambda a: ordine[a["livello"]])
    return {"avvisi": avvisi, "errori": sum(a["livello"] == "errore" for a in avvisi),
            "attenzioni": sum(a["livello"] == "attenzione" for a in avvisi)}
