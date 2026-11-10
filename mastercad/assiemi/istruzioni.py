"""Istruzioni di montaggio dall'assieme: sequenza, coppie di serraggio, ordine a croce, cuscinetti a pressa o a caldo,
spinatura in opera, controlli finali, tempo e costo del montaggio con la tariffa del banco della tua officina.
"""
import math

from ..progetto.analisi import _num

# Coppie di serraggio viti classe 8.8, attrito μ = 0,12, 90 % dello snervamento (VDI 2230, tabelle per viti a testa cilindrica)
COPPIE_88 = {"M3": 1.3, "M4": 3.0, "M5": 5.9, "M6": 10.1, "M8": 24.6, "M10": 48.0, "M12": 84.0, "M16": 206.0, "M20": 415.0}
ALFA_ACCIAIO = 12e-6          # dilatazione termica dell'anello interno (1/K)
T_MAX_CUSCINETTO = 120        # °C: oltre si rovinano tempra e lubrificante
# tempi standard di banco (minuti), da tarare con i tempi veri
TEMPI = {"posa": 1.5, "vite_mano": 0.4, "vite_serraggio": 0.5, "alesatura_opera": 3.0, "pulizia": 2.0, "spina": 1.0,
         "pressa": 3.0, "riscaldo": 12.0, "inserimento": 2.0, "controlli": 3.0}


def ordine_croce(punti):
    """Indici dei punti in sequenza «a croce»: si gira attorno al baricentro e si salta al punto opposto."""
    n = len(punti)
    if n <= 2:
        return list(range(n))
    cx, cy = sum(p[0] for p in punti) / n, sum(p[1] for p in punti) / n
    giro = sorted(range(n), key=lambda i: math.atan2(punti[i][1] - cy, punti[i][0] - cx))
    if n % 2 == 0:
        out = []
        for k in range(n // 2):
            out += [giro[k], giro[k + n // 2]]
        return out
    passo = (n + 1) // 2
    return [giro[(k * passo) % n] for k in range(n)]


def montaggio_cuscinetto(d, interferenza_um):
    """A pressa (piccoli) o a caldo: temperatura per aprire l'anello interno di interferenza + 10 µm di gioco di infilaggio."""
    dT = (interferenza_um / 1000.0) / (ALFA_ACCIAIO * d)      # quanto deve dilatarsi l'anello per annullare l'interferenza
    t = 20 + dT + 10                                            # + margine per infilarlo prima che si raffreddi
    caldo = {"delta": math.ceil(dT), "temperatura": int(min(T_MAX_CUSCINETTO, math.ceil(t / 5) * 5)), "basta": t <= T_MAX_CUSCINETTO}
    return {"metodo": "pressa" if d <= 40 else "caldo", "caldo": caldo}


def passi(comps, commerciali, legami, officina=None):
    nomi = {c["id"]: c["nome"] for c in comps}
    comm = {c["id"]: c for c in commerciali}
    out = []

    def passo(titolo, azioni, nuovi=(), attrezzi=(), tempo=0.0, controllo=None):
        out.append({"n": len(out) + 1, "titolo": titolo, "azioni": list(azioni), "nuovi": list(nuovi), "attrezzi": list(attrezzi),
                    "tempo_min": round(tempo, 1), "controllo": controllo})

    base = next((c for c in comps if c.get("tipo") == "pezzo" and not c.get("generato")), None)
    if base:
        passo("Prepara «%s» sul banco" % base["nome"], ["Pulisci e sgrassa le facce di appoggio e i fori; togli le bave dai filetti.",
                                                         "Appoggia il pezzo sul banco con la faccia di montaggio verso l'alto."],
              [base["id"]], ["Panno, sgrassante, soffiatore"], TEMPI["posa"])
    for lg in legami:
        if lg["tipo"] == "impila":
            A, B = nomi.get(lg["sotto"]), nomi.get(lg["sopra"])
            viti = lg.get("comm_viti") or []
            spine = lg.get("comm_spine") or []
            seq = ordine_croce([(v["wx"], v["wy"]) for v in viti])
            m = viti[0]["m"] if viti else None
            coppia = COPPIE_88.get(m)
            elenco = ", ".join("n.%d (%s; %s)" % (k + 1, _num(viti[i]["wx"]), _num(viti[i]["wy"])) for k, i in enumerate(seq))
            serraggio = (["Avvita a mano tutte le %d viti %s×%d fino ad accostare la testa." % (len(viti), m, viti[0]["L"]),
                          "Prima passata al 50%%: %s N·m, nell'ordine a croce %s." % (_num(round(coppia / 2, 1)), elenco),
                          "Seconda passata al 100%%: %s N·m, stesso ordine." % _num(coppia),
                          "Segna le teste con il pennarello: si vede subito se una vite non è stata serrata."] if viti and coppia else [])
            attrezzi_v = ["Chiave dinamometrica %s–%s N·m, esagono %s" % (_num(round(coppia * 0.5)), _num(round(coppia * 1.2)), _num({"M3": 2.5, "M4": 3, "M5": 4, "M6": 5, "M8": 6, "M10": 8, "M12": 10, "M16": 14, "M20": 17}.get(m, 6)))] if coppia else []
            t_viti = len(viti) * (TEMPI["vite_mano"] + TEMPI["vite_serraggio"])
            if lg.get("in_opera") and spine:
                io = lg["in_opera"]
                passo("Appoggia «%s» su «%s»" % (B, A), ["Appoggia «%s» allineando i fori delle viti; le spine si mettono dopo, in opera." % B],
                      [lg["sopra"]], [], TEMPI["posa"])
                passo("Serra le viti", serraggio, [v["cid"] for v in viti], attrezzi_v, t_viti)
                prof = max(s["L"] for s in spine) + 1
                passo("Alesa in opera i fori spina", [
                    "Con i pezzi serrati, passa la punta Ø%s nei prefori attraverso «%s» fino a %s mm di profondità totale." % (_num(io["preforo"]), B, _num(prof)),
                    "Alesa Ø%s %s con alesatore a macchina (trapano a colonna o radiale), lubrificando; profondità %s mm." % (_num(io["d"]), io["sigla"], _num(prof)),
                    "Soffia via i trucioli e controlla con il tampone P/NP Ø%s %s." % (_num(io["d"]), io["sigla"]),
                    "Perché in opera: " + io["motivo"]],
                    [], ["Punta Ø%s, alesatore Ø%s %s, tampone P/NP" % (_num(io["preforo"]), _num(io["d"]), io["sigla"])],
                    len(spine) * TEMPI["alesatura_opera"] + TEMPI["pulizia"], "Tampone P/NP Ø%s %s passa in tutti i fori spina" % (_num(io["d"]), io["sigla"]))
                passo("Pianta le spine", ["Pianta le %d spine %s con mazzuola in ottone o pressa fino a battuta: %s." % (
                    len(spine), spine[0]["nome"].replace("Spina ", ""), "devono entrare in entrambi i pezzi")], [s["cid"] for s in spine],
                    ["Mazzuola in ottone o pressa"], len(spine) * TEMPI["spina"])
            else:
                if spine:
                    passo("Pianta le spine in «%s»" % A, ["Pianta le %d spine %s nei fori di «%s» fino a battuta." % (len(spine), spine[0]["nome"].replace("Spina ", ""), A)],
                          [s["cid"] for s in spine], ["Mazzuola in ottone o pressa"], len(spine) * TEMPI["spina"])
                passo("Appoggia «%s» su «%s»" % (B, A), ["Infila «%s» sulle spine%s senza forzare." % (B, "" if spine else " allineando i fori delle viti")], [lg["sopra"]], [], TEMPI["posa"])
                if serraggio:
                    passo("Serra le viti", serraggio, [v["cid"] for v in viti], attrezzi_v, t_viti)
        elif lg["tipo"] == "cuscinetto":
            c = comm.get(lg["cid"])
            if not c:
                continue
            d = lg["d"]
            mc = montaggio_cuscinetto(d, lg.get("interferenza_max_um", 0))
            nuovi = [lg["cid"]] + ([lg["albero"]] if lg.get("albero") else [])
            if lg.get("albero"):
                if mc["metodo"] == "pressa":
                    az = ["Lubrifica leggermente il tratto Ø%s k5 dell'albero." % _num(d),
                          "Pianta il cuscinetto %s sull'albero con la pressa e una bussola che spinge SOLO sull'anello interno, fino allo spallamento." % lg["codice"],
                          "Mai spingere sull'anello esterno: la forza passerebbe dalle sfere e segnerebbe le piste.",
                          "In alternativa a caldo: scaldatore a induzione a %d °C (servono almeno +%d K sull'ambiente), mai fiamma libera." % (mc["caldo"]["temperatura"], mc["caldo"]["delta"])]
                    att, tm = ["Pressa, bussola di montaggio per anello interno Ø%s" % _num(d)], TEMPI["pressa"]
                else:
                    az = ["Scalda il cuscinetto %s con lo scaldatore a induzione a %d °C (servono almeno +%d K per aprire l'interferenza), mai fiamma libera." % (lg["codice"], mc["caldo"]["temperatura"], mc["caldo"]["delta"]),
                          "Infilalo subito fino allo spallamento e tienilo premuto finché si raffredda."]
                    att, tm = ["Scaldatore a induzione, guanti termici"], TEMPI["riscaldo"]
                passo("Monta il cuscinetto %s sull'albero" % lg["codice"], az + ["Interferenza calcolata: fino a %s µm (k5 su anello ISO 492)." % _num(lg.get("interferenza_max_um", 0))],
                      nuovi, att, tm, "L'anello interno appoggia sullo spallamento: lo spessimetro 0,03 non entra")
                passo("Inserisci albero e cuscinetto nella sede di «%s»" % nomi.get(lg["pezzo"]), [
                    "Lubrifica la sede e infila il gruppo spingendo sull'anello esterno: l'accoppiamento è con gioco (%s), deve entrare a mano." % lg.get("esterno", ""),
                    "Se serve forza, fermati: la sede è fuori tolleranza o il cuscinetto è storto."], [], [], TEMPI["inserimento"])
            else:
                passo("Inserisci il cuscinetto %s nella sede di «%s»" % (lg["codice"], nomi.get(lg["pezzo"])), ["Spingi sull'anello esterno, accoppiamento %s." % lg.get("esterno", "")],
                      nuovi, [], TEMPI["inserimento"])
    finali = ["Tutte le viti hanno il segno di serraggio."]
    if any(lg["tipo"] == "cuscinetto" and lg.get("albero") for lg in legami):
        finali.append("Ruota l'albero a mano: gira libero, senza punti duri né rumore.")
    finali.append("Nessuna parte tocca dove non deve (verifica collisioni del programma superata).")
    passo("Controlli finali", finali, [], [], TEMPI["controlli"], "Firma del montatore")
    totale = sum(p["tempo_min"] for p in out)
    banco = float(((officina or {}).get("costi") or {}).get("banco") or 32)
    return {"passi": out, "tempo_min": round(totale, 1), "costo_banco_ora": banco, "costo": round(totale / 60 * banco, 2),
            "nota": "Tempi standard di banco: stima da tarare con i tempi veri del montaggio."}
