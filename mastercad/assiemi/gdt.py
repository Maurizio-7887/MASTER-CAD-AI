"""Tolleranze geometriche dedotte dall'assieme (ISO 1101, riferimenti ISO 5459, massimo materiale ISO 2692).

Il disegnatore di solito le scrive «a occhio». Qui si calcolano da come il pezzo viene montato:
- viti (perno fisso): il gioco fra passaggio e vite, T = H − F, si divide fra i due pezzi; nel filetto serve il campo proiettato Ⓟ;
- spine: se il gioco minimo spina/foro è nullo o negativo (m6 in H7) nessuna tolleranza di interasse garantisce il montaggio
  con fori lavorati separatamente → si alesano in opera; altrimenti tolleranza di posizione = gioco minimo / 2 per pezzo;
- sede cuscinetto: cilindricità IT6/2, oscillazione totale dello spallamento IT6, perpendicolarità all'appoggio dal
  disallineamento ammesso; sull'albero cilindricità IT5/2 e spallamento IT5 (raccomandazioni dei cataloghi per la classe normale).
Ogni valore dice perché, la norma e con che strumento si controlla; poi si confronta con la precisione delle tue macchine.
"""
import math

from ..officina import capacita
from ..progetto.analisi import _num
from ..progetto.lavorazioni import PASSAGGIO
from ..tolleranze import iso286
from ..tolleranze.funzioni import CUSCINETTI

SERIE = (0.002, 0.003, 0.004, 0.005, 0.006, 0.008, 0.01, 0.012, 0.015, 0.02, 0.025, 0.03, 0.04, 0.05, 0.06, 0.08,
         0.1, 0.12, 0.15, 0.2, 0.25, 0.3, 0.4, 0.5, 0.6, 0.8, 1.0)
SIMBOLI = {"posizione": "⌖", "planarita": "⏥", "perpendicolarita": "⟂", "cilindricita": "⌭", "oscillazione_totale": "⌰", "coassialita": "◎"}
NOMI = {"posizione": "Posizione", "planarita": "Planarità", "perpendicolarita": "Perpendicolarità", "cilindricita": "Cilindricità",
        "oscillazione_totale": "Oscillazione totale", "coassialita": "Coassialità"}
DISALLINEAMENTO_SFERE = 2 / 60     # gradi: quota del disallineamento (2'–10' a catalogo) lasciata all'alloggiamento
PINZA_PREFORO = 0.2                # sovrametallo sul diametro per alesare in opera


def tt(v):
    """Valore di tolleranza con i millesimi: 0,008 e non 0,01."""
    return ("%.3f" % float(v)).rstrip("0").rstrip(".").replace(".", ",")


def arrotonda(v):
    """Valore della serie preferita, per difetto (il calcolo è un massimo da non superare)."""
    return max([s for s in SERIE if s <= v + 1e-9] or [SERIE[0]])


def it(d, grado):
    return iso286.IT[grado][iso286._campo(d)] / 1000.0


class Pezzo:
    """Raccoglie riferimenti (A, B, C…) e tolleranze di un componente."""

    def __init__(self, comp):
        self.comp = comp
        self.riferimenti, self.voci, self.in_opera = [], [], []

    def lettera(self, chiave, descrizione, **geo):
        for r in self.riferimenti:
            if r["chiave"] == chiave:
                return r["lettera"]
        L = "ABCDEFGHJKLMNP"[len(self.riferimenti)]
        self.riferimenti.append(dict(geo, chiave=chiave, lettera=L, elemento=descrizione))
        return L

    def voce(self, simbolo, valore, elemento, perche, norma, controllo, riferimenti=(), diametrale=False, modificatori=(), fori=(), tratto=None, lavorazione="fresa"):
        self.voci.append({"simbolo": simbolo, "segno": SIMBOLI[simbolo], "nome": NOMI[simbolo], "valore": round(valore, 4), "diametrale": diametrale,
                          "modificatori": list(modificatori), "riferimenti": list(riferimenti), "elemento": elemento, "perche": perche,
                          "norma": norma, "controllo": controllo, "fori": [{"x": round(f["x"], 3), "y": round(f["y"], 3), "d": f["d"]} for f in fori],
                          "tratto": tratto, "lavorazione": lavorazione})

    def dati(self):
        return {"riferimenti": [{k: v for k, v in r.items() if k != "chiave"} for r in self.riferimenti], "voci": self.voci, "in_opera": self.in_opera}


def _faccia(comp, an, sopra):
    """Faccia di contatto nelle coordinate del pezzo: quella alta se il pezzo sta sotto, ribaltata se capovolto."""
    alta = (not sopra) != bool(comp.get("capovolto"))
    ing = an["ingombro"]
    return ("faccia superiore" if alta else "faccia inferiore"), (ing["zmax"] if alta else ing["zmin"])


def _planarita(P, comp, an, sopra, altro):
    nome, z = _faccia(comp, an, sopra)
    L = P.lettera("faccia", "%s, appoggio su «%s»" % (nome, altro["nome"]), tipo="faccia", z=round(z, 3))
    ing = an["ingombro"]
    diag = math.hypot(ing["x"], ing["y"])
    t = 0.02 if diag <= 200 else 0.03 if diag <= 400 else 0.05
    if not any(v["simbolo"] == "planarita" for v in P.voci):
        P.voce("planarita", t, "%s [%s]" % (nome.capitalize(), L),
               "Giunzione serrata con viti e centrata con spine: una faccia non piana si flette al serraggio e carica le spine (regola d'officina per diagonali fino a %s mm)." % _num(diag if diag > 200 else 200),
               "ISO 1101", "Piano di riscontro e comparatore, o CMM", lavorazione="fresa")
    return L


def deduci(comps, legami, cache, officina):
    """Restituisce {id componente: {riferimenti, voci, in_opera}} e gli avvisi di capacità rispetto alla tua officina."""
    per_id = {c["id"]: c for c in comps}
    pezzi = {}

    def P(cid):
        if cid not in pezzi:
            pezzi[cid] = Pezzo(per_id[cid])
        return pezzi[cid]

    for lg in legami:
        if lg["tipo"] == "impila":
            A, B = per_id[lg["sotto"]], per_id[lg["sopra"]]
            anA, anB = cache.analisi(A["progetto"]), cache.analisi(B["progetto"])
            fA = {f["rif"]: f for f in anA["fori"]}
            fB = {f["rif"]: f for f in anB["fori"]}
            PA, PB = P(A["id"]), P(B["id"])
            dA = _planarita(PA, A, anA, False, B)
            dB = _planarita(PB, B, anB, True, A)
            spine = lg.get("spine") or []
            rif_A, rif_B = [dA], [dB]
            if spine:
                d = fA[spine[0][0]]["d"]
                sig = fB[spine[0][1]]["tolleranza"] or "H7"
                foro = iso286.scostamenti(d, sig)
                spina = iso286.scostamenti(d, "m6")
                gmin = (foro[1] - spina[0]) / 1000.0
                t_spina = gmin / 2
                cap = capacita(officina, "fresa")
                testo_gioco = "Spina Ø%s m6 nel foro %s: gioco minimo %s µm" % (_num(d), sig, _num(gmin * 1000))
                if t_spina < cap["precisione"]:
                    motivo = (testo_gioco + (" (interferenza)" if gmin < 0 else "") + ". " +
                              ("Con fori lavorati separatamente nessuna tolleranza di interasse garantisce il montaggio (perno fisso: T = gioco minimo ≤ 0)." if gmin <= 0 else
                               "Con fori lavorati separatamente servirebbe una posizione Ø%s per pezzo (perno fisso: T = gioco minimo); la macchina «%s» fa Ø%s." % (
                                   tt(t_spina), cap["macchina"], tt(cap["precisione"]))) +
                              " Quindi: preforo Ø%s nei due pezzi, poi si alesano insieme Ø%s %s dopo aver serrato le viti." % (_num(d - PINZA_PREFORO), _num(d), sig))
                    for Pz, ff, an, altro in ((PA, [fA[a] for a, _ in spine], anA, B), (PB, [fB[b] for _, b in spine], anB, A)):
                        Pz.in_opera.append({"fori": [{"x": round(f["x"], 3), "y": round(f["y"], 3), "d": f["d"]} for f in ff], "d": d, "sigla": sig,
                                            "preforo": round(d - PINZA_PREFORO, 2), "con": altro["nome"], "perche": motivo})
                        Pz.voce("posizione", arrotonda(PINZA_PREFORO / 2), "%d× preforo spina Ø%s (alesato in opera Ø%s %s)" % (len(ff), _num(d - PINZA_PREFORO), _num(d), sig),
                                "Il preforo deve stare dentro il sovrametallo dell'alesatore: disassamento fra i due pezzi < %s mm. %s" % (tt(PINZA_PREFORO / 2), motivo),
                                "ISO 1101", "Calibro / CMM (preforo)", [Pz.riferimenti[0]["lettera"]], diametrale=True, fori=ff)
                    lg["in_opera"] = {"d": d, "sigla": sig, "preforo": round(d - PINZA_PREFORO, 2), "motivo": motivo}
                else:
                    for Pz, ff in ((PA, [fA[a] for a, _ in spine]), (PB, [fB[b] for _, b in spine])):
                        b0, c0 = ff[0], ff[1] if len(ff) > 1 else None
                        r0 = Pz.riferimenti[0]["lettera"]
                        LB = Pz.lettera("spina%d" % b0["rif"], "foro spina Ø%s %s in (%s; %s)" % (_num(d), sig, _num(b0["x"]), _num(b0["y"])), tipo="foro", x=b0["x"], y=b0["y"], d=d)
                        if c0:
                            LC = Pz.lettera("spina%d" % c0["rif"], "foro spina Ø%s %s in (%s; %s)" % (_num(d), sig, _num(c0["x"]), _num(c0["y"])), tipo="foro", x=c0["x"], y=c0["y"], d=d)
                            Pz.voce("posizione", arrotonda(t_spina), "Foro spina [%s]" % LC, testo_gioco + ": diviso fra i due pezzi, Ø%s per ciascuno (perno fisso)." % tt(t_spina),
                                    "ISO 1101, ISO 2692", "CMM", [r0, LB], diametrale=True, fori=[c0])
                    rif_A = [PA.riferimenti[0]["lettera"]] + [r["lettera"] for r in PA.riferimenti if r["tipo"] == "foro"][:2]
                    rif_B = [PB.riferimenti[0]["lettera"]] + [r["lettera"] for r in PB.riferimenti if r["tipo"] == "foro"][:2]
            viti = lg.get("viti") or []
            if viti:
                vite = fA[viti[0][0]]["filetto"]
                F = float(vite[1:])
                H = float(fB[viti[0][1]]["d"] or PASSAGGIO.get(vite, F + 1))
                T = H - F
                presa = lg.get("presa_vite") or fB[viti[0][1]]["spessore"]
                t = arrotonda(T / 2)
                perche = "Vite %s in passaggio Ø%s: gioco T = H − F = %s mm (perno fisso), metà per pezzo. Al massimo materiale Ⓜ il passaggio più grande regala tolleranza; %s." % (
                    vite, _num(H), _num(T), "riferiti alle spine, che centrano" if len(rif_B) > 1 else "posizione reciproca dei fori, perché sono le viti a posizionare prima della spinatura in opera")
                PB.voce("posizione", t, "%d× passaggio vite Ø%s" % (len(viti), _num(H)), perche, "ISO 1101, ISO 2692", "Calibro funzionale: perni Ø%s nelle posizioni nominali" % tt(H - t),
                        rif_B, diametrale=True, modificatori=["M"], fori=[fB[b] for _, b in viti])
                PA.voce("posizione", t, "%d× filetto %s" % (len(viti), vite), perche + " Nel filetto il campo è proiettato Ⓟ per %s mm: conta dove esce la vite, non il fondo del foro." % _num(presa),
                        "ISO 1101, ISO 10578", "CMM con perni filettati", rif_A, diametrale=True, modificatori=["P", round(presa, 2)], fori=[fA[a] for a, _ in viti])
        elif lg["tipo"] == "cuscinetto":
            A = per_id[lg["pezzo"]]
            an = cache.analisi(A["progetto"])
            f = next(x for x in an["fori"] if x["rif"] == lg["foro"])
            d, D, Bw = CUSCINETTI[lg["codice"]]
            Pz = P(A["id"])
            LS = Pz.lettera("sede%d" % f["rif"], "asse della sede Ø%s del cuscinetto %s" % (_num(D), lg["codice"]), tipo="asse", x=f["x"], y=f["y"], d=D)
            Pz.voce("cilindricita", arrotonda(it(D, 6) / 2), "Sede Ø%s [%s]" % (_num(D), LS),
                    "Anello esterno sottile: copia la forma della sede. Per cuscinetti di classe normale la sede va entro IT6/2 (= %s mm)." % tt(it(D, 6) / 2),
                    "ISO 1101, raccomandazioni catalogo cuscinetti", "CMM o rotondimetro", fori=[f], lavorazione="fresa")
            Pz.voce("oscillazione_totale", arrotonda(it(D, 6)), "Fondo sede (appoggio anello esterno)",
                    "Se l'appoggio non è perpendicolare all'asse l'anello si inclina: IT6 (= %s mm) per la classe normale." % tt(it(D, 6)),
                    "ISO 1101, raccomandazioni catalogo cuscinetti", "Comparatore su spina di riscontro nella sede, o CMM", [LS], fori=[f], lavorazione="fresa")
            if Pz.riferimenti and Pz.riferimenti[0]["tipo"] == "faccia":
                t = Bw * math.tan(math.radians(DISALLINEAMENTO_SFERE))
                Pz.voce("perpendicolarita", arrotonda(t), "Asse sede [%s]" % LS,
                        "Cuscinetto a sfere: disallineamento ammesso 2'–10' a catalogo, 2' lasciati all'alloggiamento: su B = %s mm fanno %s mm." % (_num(Bw), tt(t)),
                        "ISO 1101", "CMM", [Pz.riferimenti[0]["lettera"]], diametrale=True, fori=[f], lavorazione="fresa")
            if lg.get("albero") and lg["albero"] in per_id:
                Al = P(lg["albero"])
                q = next((q for q in per_id[lg["albero"]]["progetto"].get("quote_funzionali") or [] if q.get("sigla") == "k5"), None)
                if q:
                    LA = Al.lettera("k5", "asse del tratto Ø%s k5" % _num(d), tipo="asse", d=d, tratto=[q["da"], q["a"]])
                    Al.voce("cilindricita", arrotonda(it(d, 5) / 2), "Tratto Ø%s k5 [%s]" % (_num(d), LA),
                            "L'anello interno montato con interferenza copia l'albero: IT5/2 (= %s mm) per la classe normale." % tt(it(d, 5) / 2),
                            "ISO 1101, raccomandazioni catalogo cuscinetti", "Micrometro in più sezioni, o rotondimetro", tratto=[q["da"], q["a"]], lavorazione="tornio")
                    Al.voce("oscillazione_totale", arrotonda(it(d, 5)), "Spallamento dell'anello interno",
                            "Appoggio dell'anello interno: IT5 (= %s mm) rispetto all'asse del tratto k5." % tt(it(d, 5)),
                            "ISO 1101, raccomandazioni catalogo cuscinetti", "Tra punte con comparatore", [LA], tratto=[q["a"], q["a"]], lavorazione="tornio")
    avvisi = []
    for cid, Pz in pezzi.items():
        for v in Pz.voci:
            cap = capacita(officina, v["lavorazione"])
            v["capacita"] = cap
            v["ok_officina"] = v["valore"] >= cap["precisione"] - 1e-9
            if not v["ok_officina"]:
                if v["lavorazione"] == "tornio":
                    alt = capacita(officina, "rettifica")
                    consiglio = "rettifica cilindrica (%s, %s mm): il ciclo la prevede già" % (alt["macchina"], tt(alt["precisione"]))
                else:
                    consiglio = "barenatura di finitura con testina micrometrica e controllo a CMM, oppure terzista con alesatrice di precisione"
                v["consiglio"] = consiglio
                avvisi.append({"pezzo": Pz.comp["nome"], "testo": "%s %s mm su %s: la macchina «%s» garantisce %s mm → %s." % (
                    v["nome"], tt(v["valore"]), v["elemento"], cap["macchina"], tt(cap["precisione"]), consiglio)})
    return {cid: Pz.dati() for cid, Pz in pezzi.items()}, avvisi


def applica(progetto, dati, assieme):
    """Scrive tolleranze e lavorazioni in opera nel progetto del pezzo (per tavola, ciclo e controllo)."""
    p = dict(progetto)
    p["tolleranze_geometriche"] = dict(dati, assieme=assieme)
    fori_opera = [(f["x"], f["y"]) for g in dati.get("in_opera") or [] for f in g["fori"]]
    lavs = []
    for lav in p.get("lavorazioni") or []:
        if isinstance(lav, dict) and lav.get("tipo") == "foro" and any(abs(float(lav.get("x", 1e9)) - x) < 0.01 and abs(float(lav.get("y", 1e9)) - y) < 0.01 for x, y in fori_opera):
            lav = dict(lav, in_opera=True)
        lavs.append(lav)
    p["lavorazioni"] = lavs
    return p
