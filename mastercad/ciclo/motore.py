"""Ciclo di lavoro: fasi, operazioni, utensili, parametri di taglio, tempi e programma CNC (ISO/Fanuc).

Regole fisse di officina (nessun codice generato a caso): velocità di taglio dal materiale, avanzamenti da tabella,
tempi = percorso / avanzamento + accessori. È una base di partenza per il programmatore, da simulare prima di lavorare.
"""
import math

import cadquery as cq

from ..materiali import materiale as dati_materiale
from ..officina import scegli_macchina
from ..progetto.analisi import _num, contorno_esterno, grezzo, descrivi_foro  # noqa: F401

FRESE = (2, 3, 4, 5, 6, 8, 10, 12, 16, 20)
DIAM_MAX_PUNTA = 25.0       # oltre, il foro si fresa a interpolazione
GIRI_MAX = 8000


def _giri(vc, d):
    return int(min(GIRI_MAX, 1000 * vc / (math.pi * max(d, 0.5))))


def _f_punta(d, m):
    """Avanzamento al giro della punta (mm/giro), scalato sul materiale."""
    return round((0.012 * d + 0.03) * m["fz"] / 0.06, 3)


def _fresa_per(larghezza, raggio=0.0):
    lim = larghezza * 0.7
    if raggio > 0:
        lim = min(lim, raggio * 2)
    scelte = [d for d in FRESE if d <= lim]
    return scelte[-1] if scelte else FRESE[0]


class _Utensili:
    def __init__(self):
        self.elenco, self._idx = [], {}

    def prendi(self, chiave, descrizione, d):
        if chiave not in self._idx:
            self._idx[chiave] = len(self.elenco) + 1
            self.elenco.append({"T": len(self.elenco) + 1, "descrizione": descrizione, "d": d})
        return self._idx[chiave]


def calcola(an, codice_materiale="S235", officina=None):
    """Ciclo completo dal progetto analizzato (vedi progetto.analisi.analizza)."""
    m = dati_materiale(codice_materiale)
    g = grezzo(an)
    ing = an["ingombro"]
    ut = _Utensili()
    tornito = an["base"].get("tipo") == "rivoluzione"
    lato_a, lato_b = [], []
    pz_z = ing["z"]

    def op(lista, descrizione, T=None, giri=None, vf=None, tempo=0.0, dati=None):
        lista.append({"descrizione": descrizione, "T": T, "giri": giri, "vf": vf, "tempo": round(tempo, 2), "dati": dati or {}})

    # ── fresatura: spianatura e contorno ──
    fr_sp = ut.prendi("spianatrice", "Fresa a spianare Ø50, 5 inserti, metallo duro", 50)
    n = _giri(m["vc_fresa"], 50)
    vf = int(n * 5 * m["fz"] * 1.5)
    if not tornito:
        area = g["x"] * g["y"]
        passate = max(1, math.ceil((g["z"] - pz_z) / 2 / 1.0))
        t = area / (0.7 * 50) / vf * passate + 0.5
        op(lato_a, "Spianatura faccia superiore (sovrametallo %s mm)" % _num((g["z"] - pz_z) / 2), fr_sp, n, vf, t, {"tipo": "spianatura"})
        op(lato_b, "Spianatura faccia inferiore a spessore %s mm" % _num(pz_z), fr_sp, n, vf, t, {"tipo": "spianatura"})
        d_cont = 12 if pz_z <= 30 else 16
        fr_c = ut.prendi("fresa%d" % d_cont, "Fresa cilindrica Ø%d, 3 taglienti, metallo duro" % d_cont, d_cont)
        n = _giri(m["vc_fresa"], d_cont)
        vfc = int(n * 3 * m["fz"])
        facce = contorno_esterno(an["base"])
        perim = sum(f.outerWire().Length() for f in facce) or 2 * (ing["x"] + ing["y"])
        passate = math.ceil(pz_z / d_cont) + 1
        op(lato_a, "Contornatura esterna (sgrossatura + finitura), perimetro %s mm" % _num(perim), fr_c, n, vfc,
           perim * passate / vfc + 0.5, {"tipo": "contorno", "d": d_cont})
        interni = sum(len(f.innerWires()) for f in facce)
        if interni:
            pi_ = sum(w.Length() for f in facce for w in f.innerWires())
            op(lato_a, "Contornatura delle %d aperture interne del profilo" % interni, fr_c, n, vfc, pi_ * passate / vfc + 0.3,
               {"tipo": "contorno_interno", "d": d_cont})
    else:
        tn = _giri(m["vc_tornio"], g["y"])
        mrr = m["vc_tornio"] * 1000 * 0.25 * 2.0          # mm³/min: vc × f 0,25 × ap 2
        tolto = max(0.0, g["volume"] - an["volume_pieno"])
        op(lato_a, "Tornitura: sfacciatura, sgrossatura e finitura del profilo (%s cm³ da togliere)" % _num(tolto / 1000),
           ut.prendi("tornio", "Utensile da tornio CNMG 120408, metallo duro", 0), tn, None, tolto / mrr + 3 + an["ingombro"]["x"] / 60,
           {"tipo": "tornitura"})
        op(lato_a, "Troncatura a lunghezza %s mm" % _num(ing["x"]), ut.prendi("troncatore", "Troncatore lama 3 mm", 3), tn // 2, None,
           g["y"] / 2 / (0.05 * max(1, tn // 2)) + 0.3, {"tipo": "troncatura"})

    # ── rialzi: si toglie il materiale tutto attorno ──
    for r in an["rialzi"]:
        d = 16
        T = ut.prendi("fresa16", "Fresa cilindrica Ø16, 3 taglienti, metallo duro", 16)
        n = _giri(m["vc_fresa"], d)
        vfr = int(n * 3 * m["fz"])
        vol = max(0.0, g["x"] * g["y"] - r["area"]) * r["h"]
        mrr = 0.5 * d * min(r["h"], d) * vfr
        op(lato_a, "Fresatura attorno al rialzo (altezza %s mm)" % _num(r["h"]), T, n, vfr, vol / mrr + r["perimetro"] / vfr + 0.5,
           {"tipo": "rialzo", "lav": r["dati"], "d": d})

    # ── tasche e asole ──
    for t in an["tasche"]:
        d = _fresa_per(t["larghezza_min"], t["raggio_angoli"])
        if t["tipo"] == "asola" and t["larghezza_min"] in FRESE:
            d = t["larghezza_min"]
        T = ut.prendi("fresa%g" % d, "Fresa cilindrica Ø%g, 3 taglienti, metallo duro" % d, d)
        n = _giri(m["vc_fresa"], d)
        vft = max(20, int(n * 3 * m["fz"] * (0.6 if d < 6 else 1)))
        vol = t["area"] * t["prof"]
        ap = min(t["prof"], d * (0.5 if d < 6 else 1))
        mrr = 0.5 * d * ap * vft
        nome = "Asola" if t["tipo"] == "asola" else "Tasca"
        op(lato_a, "%s %s (sgrossatura + finitura pareti)" % (nome, "passante" if t["passante"] else "profonda %s mm" % _num(t["prof"])),
           T, n, vft, vol / max(mrr, 1) + t["perimetro"] * math.ceil(t["prof"] / max(ap, 0.1)) / vft + 0.3,
           {"tipo": t["tipo"], "lav": t["dati"], "d": d, "prof": t["prof"]})

    # ── fori: centrino, punta, alesatore, maschio, lamatore, svasatore ──
    for lato, fori in ((lato_a, [f for f in an["fori"] if not f["da_sotto"]]), (lato_b, [f for f in an["fori"] if f["da_sotto"]])):
        if not fori:
            continue
        # fori grandi (oltre Ø25): niente punta gigante, si fresano a interpolazione elicoidale
        grandi = [f for f in fori if f["d_punta"] > DIAM_MAX_PUNTA]
        for f in grandi:
            D = _fresa_per(f["d_punta"] * 0.7)
            T = ut.prendi("fresa%g" % D, "Fresa cilindrica Ø%g, 3 taglienti, metallo duro" % D, D)
            n = _giri(m["vc_fresa"], D)
            vfi = int(n * 3 * m["fz"] * 0.6)
            giri_elica = math.ceil((f["prof"] + 0.5) / max(0.5, D * 0.1)) + 1
            percorso = giri_elica * math.pi * (f["d_punta"] - D) * 1.5
            op(lato, "Fresatura a interpolazione elicoidale Ø%s (foro %d)%s" % (_num(f["d_punta"]), f["rif"], " – sgrossatura, finitura con barenatore" if f["tolleranza"] else ""),
               T, n, vfi, percorso / vfi + 0.3, {"tipo": "interpolazione", "d": D, "fori": [f["rif"]]})
            if f["tolleranza"]:
                Tb = ut.prendi("bareno%g" % f["d"], "Testina di barenatura Ø%s %s" % (_num(f["d"]), f["tolleranza"]), f["d"])
                nb = _giri(m["vc_fresa"] * 0.6, f["d"])
                op(lato, "Barenatura Ø%s %s (foro %d)" % (_num(f["d"]), f["tolleranza"], f["rif"]), Tb, nb, int(0.08 * nb), (f["prof"] + 3) / (0.08 * nb) * 2 + 0.3,
                   {"tipo": "barenatura", "fori": [f["rif"]]})
        fori_p = [f for f in fori if f["d_punta"] <= DIAM_MAX_PUNTA]
        if fori_p:
            Tc = ut.prendi("centrino", "Punta a centrare Ø10 a 90°, HSS-Co", 10)
            n = _giri(m["vc_punta"] * 1.2, 10)
            op(lato, "Centrinatura di %d fori" % len(fori_p), Tc, n, int(n * 0.08), 0.12 * len(fori_p), {"tipo": "centrino", "fori": [f["rif"] for f in fori_p]})
        per_punta = {}
        for f in fori_p:
            per_punta.setdefault(round(f["d_punta"] - (0.2 if f["tolleranza"] else 0), 2), []).append(f)
        for dp, gruppo in sorted(per_punta.items()):
            T = ut.prendi("punta%g" % dp, "Punta elicoidale Ø%s, HSS-Co%s" % (_num(dp), " (preforo per alesare)" if gruppo[0]["tolleranza"] else ""), dp)
            n = _giri(m["vc_punta"], dp)
            fv = _f_punta(dp, m)
            tempo = sum((f["prof"] + 0.3 * dp + 2) / (fv * n) * (1.3 if f["prof"] > 3 * dp else 1) for f in gruppo) + 0.05 * len(gruppo)
            opera = sum(1 for f in gruppo if f.get("in_opera"))
            op(lato, "Foratura Ø%s (%d fori)%s" % (_num(dp), len(gruppo), " – %d prefori: alesatura in opera al montaggio" % opera if opera else ""), T, n, int(fv * n), tempo,
               {"tipo": "foratura", "d": dp, "fori": [f["rif"] for f in gruppo]})
        for f in fori_p:
            if f["tolleranza"] and not f.get("in_opera"):
                T = ut.prendi("alesatore%g" % f["d"], "Alesatore Ø%s %s, metallo duro" % (_num(f["d"]), f["tolleranza"]), f["d"])
                n = _giri(m["vc_punta"] * 0.5, f["d"])
                op(lato, "Alesatura Ø%s %s (foro %d)" % (_num(f["d"]), f["tolleranza"], f["rif"]), T, n, int(0.2 * n),
                   (f["prof"] + 3) / (0.2 * n) * 2 + 0.1, {"tipo": "alesatura", "fori": [f["rif"]]})
        for fil in sorted({f["filetto"] for f in fori if f["filetto"]}):
            gr = [f for f in fori if f["filetto"] == fil]
            p = gr[0]["passo"]
            T = ut.prendi("maschio" + fil, "Maschio %s×%s a macchina, HSS-E" % (fil, _num(p)), gr[0]["d"])
            n = _giri(m["vc_maschio"], gr[0]["d"])
            op(lato, "Maschiatura %s (%d fori)" % (fil, len(gr)), T, n, round(n * p, 1),
               sum(2 * (f["prof"] + 2) / (p * n) for f in gr) + 0.08 * len(gr), {"tipo": "maschiatura", "fori": [f["rif"] for f in gr]})
        lam = {}
        for f in fori:
            if not f["lamatura"]:
                continue
            dl = float(f["lamatura"]["d"])
            if dl > DIAM_MAX_PUNTA or f["lamatura"].get("tolleranza"):     # sede (es. cuscinetto): fresata e poi barenata
                D = _fresa_per(min(dl - f["d_punta"], dl) * 0.9 if dl - f["d_punta"] > 4 else dl * 0.6)
                T = ut.prendi("fresa%g" % D, "Fresa cilindrica Ø%g, 3 taglienti, metallo duro" % D, D)
                n = _giri(m["vc_fresa"], D)
                vfi = int(n * 3 * m["fz"] * 0.6)
                pl = float(f["lamatura"]["prof"])
                op(lato, "Fresatura sede Ø%s × %s (foro %d)" % (_num(dl), _num(pl), f["rif"]), T, n, vfi,
                   math.pi * dl * (pl / max(0.5, D * 0.1) + 3) / vfi + 0.3, {"tipo": "sede", "d": D, "fori": [f["rif"]]})
                if f["lamatura"].get("tolleranza"):
                    Tb = ut.prendi("bareno%g" % dl, "Testina di barenatura Ø%s %s" % (_num(dl), f["lamatura"]["tolleranza"]), dl)
                    nb = _giri(m["vc_fresa"] * 0.6, dl)
                    op(lato, "Barenatura sede Ø%s %s (foro %d)" % (_num(dl), f["lamatura"]["tolleranza"], f["rif"]), Tb, nb, int(0.08 * nb),
                       (pl + 2) / (0.08 * nb) * 2 + 0.3, {"tipo": "barenatura_sede", "fori": [f["rif"]]})
                continue
            lam.setdefault(dl, []).append(f)
        for dl, gr in sorted(lam.items()):
            T = ut.prendi("lamatore%g" % dl, "Fresa per lamature Ø%s con pilota" % _num(dl), dl)
            n = _giri(m["vc_punta"] * 1.2, dl)
            op(lato, "Lamatura Ø%s (%d fori)" % (_num(dl), len(gr)), T, n, int(0.1 * n),
               sum((float(f["lamatura"]["prof"]) + 1) / (0.1 * n) for f in gr) + 0.1 * len(gr), {"tipo": "lamatura", "fori": [f["rif"] for f in gr]})
        sv = [f for f in fori if f["svasatura"]]
        if sv:
            T = ut.prendi("svasatore", "Svasatore a 90° Ø20, HSS", 20)
            n = _giri(m["vc_punta"], 16)
            op(lato, "Svasatura (%d fori)" % len(sv), T, n, int(0.08 * n), 0.2 * len(sv), {"tipo": "svasatura", "fori": [f["rif"] for f in sv]})

    # ── spigoli ──
    for s in an["spigoli"]:
        lista = lato_b if s["spigoli"] == "inferiori" else lato_a
        if s["tipo"] == "smusso":
            T = ut.prendi("smussatore", "Fresa a smussare 90° Ø10", 10)
        else:
            T = ut.prendi("raggio%g" % s["valore"], "Fresa a raggiare R%s" % _num(s["valore"]), 10)
        n = _giri(m["vc_fresa"], 10)
        vfs = int(n * 2 * m["fz"])
        op(lista, "%s %s sugli spigoli %s (%s mm di spigolo)" % ("Smusso" if s["tipo"] == "smusso" else "Raccordo R", _num(s["valore"]),
                                                                s["spigoli"], _num(s["lunghezza"])), T, n, vfs, s["lunghezza"] / vfs + 0.3,
           {"tipo": s["tipo"], "valore": s["valore"], "spigoli": s["spigoli"]})
    if an["guscio"]:
        gsc = an["guscio"]
        T = ut.prendi("fresa10", "Fresa cilindrica Ø10, 3 taglienti, metallo duro", 10)
        n = _giri(m["vc_fresa"], 10)
        vfg = int(n * 3 * m["fz"])
        op(lato_a, "Svuotatura (guscio, pareti %s mm)" % _num(gsc["spessore"]), T, n, vfg, gsc["volume"] / (0.5 * 10 * 5 * vfg) + 1,
           {"tipo": "guscio"})

    off = officina or _officina_predefinita()
    if tornito:
        mac_a = scegli_macchina(off, "tornio", (g["y"], g["x"]))
    else:
        mac_a = scegli_macchina(off, "fresa", (g["x"], g["y"], g["z"]))
    sega = scegli_macchina(off, "sega", (g["y"], g["x"]))
    banco = float(off["costi"]["banco"])
    fasi = [{"n": 10, "nome": "Taglio del grezzo", "macchina": sega["nome"], "costo_ora": sega["costo_ora"], "tipo_fase": "taglio", "operazioni": [
        {"descrizione": "Taglio: " + g["descrizione"], "T": None, "giri": None, "vf": None,
         "tempo": round(g["sezione"] / m["taglio"] + 1.0, 2), "dati": {"tipo": "taglio"}}]}]
    fasi.append(dict(_fase(mac_a), n=20, nome="Lavorazione lato A" if not tornito else "Tornitura", operazioni=lato_a, programma=True))
    if tornito and lato_b:
        mac_b = scegli_macchina(off, "fresa", (g["x"], g["y"], g["z"]))
        fasi.append(dict(_fase(mac_b), n=30, nome="Forature e fresature trasversali", operazioni=lato_b))
    elif lato_b:
        fasi.append(dict(_fase(mac_a), n=30, nome="Lavorazione lato B (pezzo girato)", operazioni=lato_b))
    rettifiche = [q for q in an.get("quote_funzionali") or [] if q.get("sigla") and int("".join(c for c in q["sigla"] if c.isdigit()) or 9) <= 6]
    if rettifiche:
        mac_r = scegli_macchina(off, "rettifica", (max(q["diametro"] for q in rettifiche) + 10, an["ingombro"]["x"]))
        ops = [{"descrizione": "Rettifica cilindrica Ø%s %s, lunghezza %s mm (%s)" % (_num(q["diametro"]), q["sigla"], _num(float(q["a"]) - float(q["da"])), q.get("perche", "")[:60]),
                "T": None, "giri": None, "vf": None, "tempo": round(2.0 + (float(q["a"]) - float(q["da"])) * 0.08, 2), "dati": {"tipo": "rettifica"}} for q in rettifiche]
        fasi.append(dict(_fase(mac_r), n=fasi[-1]["n"] + 10, nome="Rettifica", operazioni=ops))
    n_part = len(an["fori"]) + len(an["tasche"]) + len(an["spigoli"])
    fasi.append({"n": fasi[-1]["n"] + 10, "nome": "Sbavatura e pulizia", "macchina": "Banco", "costo_ora": banco, "tipo_fase": "banco",
                 "operazioni": [{"descrizione": "Sbavatura spigoli e fori, soffiatura", "T": None, "giri": None, "vf": None,
                                 "tempo": round(1.0 + 0.08 * n_part, 2), "dati": {}}]})
    piano = piano_controllo(an)
    fasi.append({"n": fasi[-1]["n"] + 10, "nome": "Controllo", "macchina": "Sala metrologica / banco", "costo_ora": banco, "tipo_fase": "controllo",
                 "operazioni": [{"descrizione": c["descrizione"], "T": None, "giri": None, "vf": None, "tempo": c["tempo"], "dati": {"strumento": c["strumento"]}}
                                for c in piano]})
    macchina_fasi = [f for f in fasi if f.get("tipo_fase") == "macchina"]
    tempo_macchina = sum(o["tempo"] for f in macchina_fasi for o in f["operazioni"])
    tempo_banco = sum(o["tempo"] for f in fasi if f.get("tipo_fase") != "macchina" for o in f["operazioni"])
    attrezzaggio = 30 * len(macchina_fasi) + 4 * len(ut.elenco) + 10
    terzi = [{"fase": f["n"], "macchina": f["macchina"], "motivo": f.get("motivo"), "giorni": f.get("giorni")} for f in fasi if f.get("interna") is False]
    return {"materiale": m["nome"], "codice_materiale": codice_materiale, "grezzo": g, "fasi": fasi, "utensili": ut.elenco,
            "piano_controllo": piano, "terzisti": terzi,
            "tempi": {"macchina_min": round(tempo_macchina, 1), "banco_min": round(tempo_banco, 1),
                      "attrezzaggio_min": round(attrezzaggio, 1), "tornito": tornito}}


def _fase(mac):
    return {"macchina": mac["nome"], "costo_ora": mac["costo_ora"], "interna": mac.get("interna", True), "motivo": mac.get("motivo"),
            "giorni": mac.get("giorni"), "tipo_fase": "macchina"}


def _officina_predefinita():
    from ..officina import PREDEFINITA
    return PREDEFINITA


def piano_controllo(an):
    """Cosa controllare e con che strumento: tamponi P/NP per i fori in tolleranza, tamponi filettati, calibro per il resto."""
    from ..tolleranze.funzioni import limiti_foro
    from ..tolleranze import iso286
    piano, visti = [], set()
    for f in an["fori"]:
        if f.get("in_opera"):
            if ("o", f["d"]) not in visti:
                visti.add(("o", f["d"]))
                n = sum(1 for g in an["fori"] if g.get("in_opera") and g["d"] == f["d"])
                piano.append({"descrizione": "%d× preforo Ø%s per spina: alesato e controllato in opera al montaggio (tampone P/NP %s)" % (n, _num(f["d"] - 0.2), f["tolleranza"] or "H7"),
                              "strumento": "Calibro (preforo)", "tempo": 0.1 * n})
            continue
        for lim in limiti_foro(f):
            chiave = ("t", lim["testo"])
            n = sum(1 for g in an["fori"] if any(x["testo"] == lim["testo"] for x in limiti_foro(g)))
            if chiave in visti:
                continue
            visti.add(chiave)
            piano.append({"descrizione": "%d× %s: tampone P/NP — P %s · NP %s" % (n, lim["testo"], _num3(lim["min"]), _num3(lim["max"])),
                          "strumento": "Tampone P/NP %s %s" % (_num(lim["nominale"]), lim["sigla"]), "tempo": 0.3 * n})
        if f["filetto"] and ("f", f["filetto"]) not in visti:
            visti.add(("f", f["filetto"]))
            n = sum(1 for g in an["fori"] if g["filetto"] == f["filetto"])
            piano.append({"descrizione": "%d× filetto %s 6H: tampone filettato P/NP" % (n, f["filetto"]), "strumento": "Tampone filettato %s 6H" % f["filetto"],
                          "tempo": 0.25 * n})
    for q in an.get("quote_funzionali") or []:
        if not q.get("sigla"):
            continue
        try:
            lim = iso286.limiti(q["diametro"], q["sigla"])
        except ValueError:
            continue
        piano.append({"descrizione": "%s: anello P/NP o micrometro — %s ÷ %s (%s)" % (lim["testo"], _num3(lim["min"]), _num3(lim["max"]), q.get("perche", "")[:50]),
                      "strumento": "Micrometro / anello P/NP Ø%s %s" % (_num(q["diametro"]), q["sigla"]), "tempo": 0.5})
    for v in (an.get("tolleranze_geometriche") or {}).get("voci") or []:
        piano.append({"descrizione": "%s %s%s mm%s su %s: %s" % (v.get("nome", ""), "Ø" if v.get("diametrale") else "", ("%.3f" % float(v["valore"])).rstrip("0").rstrip(".").replace(".", ","),
                                                                  (" rif. " + "|".join(v["riferimenti"])) if v.get("riferimenti") else "", v.get("elemento", ""), v.get("controllo", "")),
                      "strumento": v.get("controllo", ""), "tempo": 1.5 if "CMM" in (v.get("controllo") or "") else 0.8})
    piano.append({"descrizione": "Ingombri, posizione fori e quote libere: calibro (ISO 2768-m)", "strumento": "Calibro a corsoio", "tempo": 1.0 + 0.05 * len(an["fori"])})
    return piano


def _num3(v):
    return ("%.3f" % float(v)).replace(".", ",")


# ── programma CNC ──
def _r(v):
    return ("%.3f" % v).rstrip("0").rstrip(".") if abs(v) >= 0.0005 else "0"


def _rett(cx, cy, L, W, ang):
    c, s = math.cos(math.radians(ang)), math.sin(math.radians(ang))
    pts = [(-L / 2, -W / 2), (L / 2, -W / 2), (L / 2, W / 2), (-L / 2, W / 2), (-L / 2, -W / 2)]
    return [(cx + x * c - y * s, cy + x * s + y * c) for x, y in pts]


def _punti_filo(wire, passo=0.5):
    n = max(8, min(2000, int(wire.Length() / passo)))
    return [(p.x, p.y) for p in wire.positions([i / n for i in range(n + 1)])]


def programma(an, ciclo, nome="PEZZO"):
    """Programma ISO (Fanuc/Haas) della fase 20 su centro di lavoro. Zero: X0 Y0 origine del disegno, Z0 faccia alta finita."""
    if ciclo["tempi"]["tornito"]:
        return None
    ztop = an["ingombro"]["zmax"]
    zbase = an["ingombro"]["zmin"]
    righe = ["%", "O1001 (MASTER CAD AI - %s)" % nome.upper()[:40].replace("(", "").replace(")", ""),
             "(MATERIALE: %s - GREZZO: %s)" % (ciclo["materiale"].upper(), ciclo["grezzo"]["descrizione"].upper()),
             "(ZERO PEZZO G54: X0 Y0 ORIGINE DEL DISEGNO, Z0 FACCIA SUPERIORE FINITA)",
             "(PROGRAMMA DI PARTENZA: SIMULARE E VERIFICARE PRIMA DI LAVORARE)",
             "G21 G17 G40 G49 G80 G90 G94",
             "(CICLI FISSI CON G98: RITORNO ALLA QUOTA INIZIALE TRA UN FORO E L'ALTRO)"]
    fori = {f["rif"]: f for f in an["fori"]}
    fase = next(f for f in ciclo["fasi"] if f["n"] == 20)
    if fase.get("interna") is False:
        righe.append("(FASE AFFIDATA A %s: PROGRAMMA INDICATIVO)" % fase["macchina"].upper()[:50])
    ut = {u["T"]: u for u in ciclo["utensili"]}
    gr = ciclo["grezzo"]
    x0, y0 = an["ingombro"]["xmin"] - 3, an["ingombro"]["ymin"] - 3
    from ..progetto.lavorazioni import base as _base
    z_base = _base(an["base"])[0].BoundingBox().zmax - ztop     # faccia alta della base (sotto gli eventuali rialzi)

    def cambio(o, primo_xy):
        T = o["T"]
        righe.extend(["", "(%s)" % o["descrizione"].upper()[:70].replace("(", "").replace(")", ""),
                      "T%d M6 (%s)" % (T, ut[T]["descrizione"].upper()[:40].replace("(", "").replace(")", "")),
                      "G54 G0 X%s Y%s" % (_r(primo_xy[0]), _r(primo_xy[1])), "S%d M3" % (o["giri"] or 1000),
                      "G43 H%d Z50. M8" % T])

    def fine():
        righe.extend(["G80 M9", "G91 G28 Z0", "G90"])

    def percorso(pts, z_lista, vf, chiuso=True):
        for z in z_lista:
            righe.append("G0 X%s Y%s" % (_r(pts[0][0]), _r(pts[0][1])))
            righe.append("G0 Z2.")
            righe.append("G1 Z%s F%d" % (_r(z), max(20, vf // 3)))
            righe.append("G1 X%s Y%s F%d" % (_r(pts[1][0]), _r(pts[1][1]), vf))
            righe.extend("X%s Y%s" % (_r(x), _r(y)) for x, y in pts[2:])
            righe.append("G0 Z5.")

    def quote(prof, ap):
        n = max(1, math.ceil(prof / ap))
        return [-prof * (i + 1) / n for i in range(n)]

    for o in fase["operazioni"]:
        d = o["dati"]
        tipo = d.get("tipo")
        if tipo == "spianatura":
            cambio(o, (x0 - 30, y0))
            sovra = (gr["z"] - an["ingombro"]["z"]) / 2
            passi = [sovra / 2, 0] if sovra > 0.6 else [0]
            ys, y = [], y0
            while y <= y0 + gr["y"] + 1:
                ys.append(y)
                y += 35
            for z in passi:
                righe.append("G0 Z%s" % _r(z + 2))
                righe.append("G1 Z%s F%d" % (_r(z), o["vf"]))
                for i, y in enumerate(ys):
                    xa, xb = (x0 - 30, x0 + gr["x"] + 30) if i % 2 == 0 else (x0 + gr["x"] + 30, x0 - 30)
                    righe.append("G1 X%s Y%s F%d" % (_r(xa), _r(y), o["vf"]))
                    righe.append("X%s" % _r(xb))
                righe.append("G0 Z5.")
            fine()
        elif tipo in ("contorno", "contorno_interno"):
            r = d["d"] / 2
            facce = contorno_esterno(an["base"])
            fili = []
            for f in facce:
                try:
                    if tipo == "contorno":
                        fili += f.outerWire().offset2D(r, "arc")
                    else:
                        for w in f.innerWires():
                            fili += w.offset2D(-r, "arc")
                except Exception:
                    continue
            if not fili:
                righe.append("(%s: PERCORSO NON CALCOLABILE, USARE IL CAM)" % tipo.upper())
                continue
            pts0 = _punti_filo(fili[0])
            cambio(o, pts0[0])
            for w in fili:
                percorso(_punti_filo(w), quote(ztop - zbase + 0.5, d["d"]), o["vf"])
            fine()
        elif tipo in ("tasca", "asola"):
            lav, D = d["lav"], d["d"]
            r = D / 2
            pz = d["prof"] + (0.5 if lav.get("prof") in (None, "", "passante") else 0)
            cx, cy = float(lav["centro"][0]), float(lav["centro"][1])
            cambio(o, (cx, cy))
            zs = quote(pz, D * 0.5 if D < 6 else D)
            if tipo == "asola" or lav.get("forma") == "asola":
                L, W, a = float(lav["lunghezza"]), float(lav["larghezza"]), math.radians(float(lav.get("angolo") or 0))
                h = (L - W) / 2
                A, B = (cx - h * math.cos(a), cy - h * math.sin(a)), (cx + h * math.cos(a), cy + h * math.sin(a))
                for z in zs:            # discesa a rampa lungo l'asse dell'asola
                    righe += ["G0 X%s Y%s" % (_r(A[0]), _r(A[1])), "G0 Z2.", "G1 Z%s F%d" % (_r(z + 0.5), max(20, o["vf"] // 3)),
                              "G1 X%s Y%s Z%s F%d" % (_r(B[0]), _r(B[1]), _r(z), o["vf"] // 2), "G1 X%s Y%s" % (_r(A[0]), _r(A[1])), "G0 Z5."]
                if W - D > 0.05:
                    o_ = (W - D) / 2
                    nx, ny = -math.sin(a), math.cos(a)
                    for z in zs:
                        righe += ["G0 X%s Y%s" % (_r(A[0] + nx * o_), _r(A[1] + ny * o_)), "G0 Z2.", "G1 Z%s F%d" % (_r(z), max(20, o["vf"] // 3)),
                                  "G1 X%s Y%s F%d" % (_r(B[0] + nx * o_), _r(B[1] + ny * o_), o["vf"]),
                                  "G2 X%s Y%s I%s J%s" % (_r(B[0] - nx * o_), _r(B[1] - ny * o_), _r(-nx * o_), _r(-ny * o_)),
                                  "G1 X%s Y%s" % (_r(A[0] - nx * o_), _r(A[1] - ny * o_)),
                                  "G2 X%s Y%s I%s J%s" % (_r(A[0] + nx * o_), _r(A[1] + ny * o_), _r(nx * o_), _r(ny * o_)), "G0 Z5."]
            elif lav.get("forma") == "cerchio":
                R = float(lav["d"]) / 2 - r
                passi = max(1, math.ceil(R / (0.45 * D)))
                for z in zs:
                    righe += ["G0 X%s Y%s" % (_r(cx), _r(cy)), "G0 Z2.", "G1 Z%s F%d" % (_r(z), max(20, o["vf"] // 4))]
                    for k in range(1, passi + 1):
                        rr = R * k / passi
                        righe += ["G1 X%s Y%s F%d" % (_r(cx + rr), _r(cy), o["vf"]), "G3 X%s Y%s I%s J0" % (_r(cx + rr), _r(cy), _r(-rr))]
                    righe.append("G0 Z5.")
            elif lav.get("forma", "rett") == "rett":
                L, W, a = float(lav["l"]) - D, float(lav["w"]) - D, float(lav.get("angolo") or 0)
                passi = max(1, math.ceil(max(L, W) / 2 / (0.45 * D)))
                for z in zs:
                    righe += ["G0 X%s Y%s" % (_r(cx), _r(cy)), "G0 Z2.", "G1 Z%s F%d" % (_r(z), max(20, o["vf"] // 4))]
                    for k in range(1, passi + 1):
                        for x, y in _rett(cx, cy, max(0.01, L * k / passi), max(0.01, W * k / passi), a):
                            righe.append("G1 X%s Y%s F%d" % (_r(x), _r(y), o["vf"]))
                    righe.append("G0 Z5.")
            else:
                righe.append("(TASCA A CONTORNO LIBERO: USARE IL CAM)")
            fine()
        elif tipo == "rialzo":
            lav, D = d["lav"], d["d"]
            cx, cy = float(lav["centro"][0]), float(lav["centro"][1])
            h = float(lav["h"])
            semi = math.hypot(gr["x"], gr["y"]) / 2 + D
            cambio(o, (cx + semi, cy))
            if lav.get("forma") == "cerchio":
                r0 = float(lav["d"]) / 2 + D / 2
                passi = max(1, math.ceil((semi - r0) / (0.45 * D)))
                for z in quote(h, D):
                    righe += ["G0 X%s Y%s" % (_r(cx + semi), _r(cy)), "G0 Z2.", "G1 Z%s F%d" % (_r(z), max(20, o["vf"] // 3))]
                    for k in range(passi, -1, -1):
                        rr = r0 + (semi - r0) * k / passi
                        righe += ["G1 X%s Y%s F%d" % (_r(cx + rr), _r(cy), o["vf"]), "G2 X%s Y%s I%s J0" % (_r(cx + rr), _r(cy), _r(-rr))]
                    righe.append("G0 Z5.")
            elif lav.get("forma", "rett") == "rett":
                L0, W0, a = float(lav["l"]) + D, float(lav["w"]) + D, float(lav.get("angolo") or 0)
                passi = max(1, math.ceil(semi / (0.45 * D)))
                for z in quote(h, D):
                    for k in range(passi, -1, -1):
                        pts = _rett(cx, cy, L0 + 2 * semi * k / passi, W0 + 2 * semi * k / passi, a)
                        percorso(pts, [z], o["vf"])
            else:
                righe.append("(RIALZO A CONTORNO LIBERO: USARE IL CAM)")
            fine()
        elif tipo == "interpolazione":
            sel = [fori[r] for r in d.get("fori", []) if r in fori]
            if not sel:
                continue
            f = sel[0]
            D = d["d"]
            R = (f["d_punta"] - D) / 2
            zf = f["z_faccia"] - ztop
            fondo = zf - f["prof"] - (0.5 if f["passante"] else 0)
            passo_z = max(0.5, D * 0.1)
            cambio(o, (f["x"] + R, f["y"]))
            righe += ["G0 Z%s" % _r(zf + 2), "G1 Z%s F%d" % (_r(zf + 0.2), o["vf"])]
            z = zf
            while z > fondo + 1e-6:          # elica: un giro ogni «passo_z» di discesa
                z = max(fondo, z - passo_z)
                righe.append("G3 X%s Y%s Z%s I%s J0 F%d" % (_r(f["x"] + R), _r(f["y"]), _r(z), _r(-R), o["vf"]))
            righe += ["G3 X%s Y%s I%s J0" % (_r(f["x"] + R), _r(f["y"]), _r(-R)), "G1 X%s Y%s" % (_r(f["x"]), _r(f["y"])), "G0 Z5."]
            fine()
        elif tipo == "sede":
            sel = [fori[r] for r in d.get("fori", []) if r in fori]
            if not sel:
                continue
            f = sel[0]
            D = d["d"]
            dl, pl = float(f["lamatura"]["d"]), float(f["lamatura"]["prof"])
            zf = f["z_faccia"] - ztop
            R = dl / 2 - D / 2 - (0.15 if f["lamatura"].get("tolleranza") else 0)       # sovrametallo per la barenatura
            passo_z = max(0.5, D * 0.1)
            cambio(o, (f["x"] + R, f["y"]))
            righe += ["G0 Z%s" % _r(zf + 2), "G1 Z%s F%d" % (_r(zf + 0.2), o["vf"])]
            z = zf
            while z > zf - pl + 1e-6:
                z = max(zf - pl, z - passo_z)
                righe.append("G3 X%s Y%s Z%s I%s J0 F%d" % (_r(f["x"] + R), _r(f["y"]), _r(z), _r(-R), o["vf"]))
            passi = max(1, math.ceil(R / (0.45 * D)))
            for k in range(passi, 0, -1):        # fondo piano della sede: cerchi verso il centro
                rr = R * k / passi
                righe += ["G1 X%s Y%s" % (_r(f["x"] + rr), _r(f["y"])), "G3 X%s Y%s I%s J0" % (_r(f["x"] + rr), _r(f["y"]), _r(-rr))]
            righe += ["G1 X%s Y%s" % (_r(f["x"]), _r(f["y"])), "G0 Z5."]
            fine()
        elif tipo == "barenatura_sede":
            sel = [fori[r] for r in d.get("fori", []) if r in fori]
            if not sel:
                continue
            f = sel[0]
            zf = f["z_faccia"] - ztop
            cambio(o, (f["x"], f["y"]))
            righe.append("G98 G76 X%s Y%s Z%s R%s Q0.1 F%d (BARENATURA SEDE)" % (_r(f["x"]), _r(f["y"]), _r(zf - float(f["lamatura"]["prof"])), _r(zf + 2), o["vf"]))
            fine()
        elif tipo == "barenatura":
            sel = [fori[r] for r in d.get("fori", []) if r in fori]
            if not sel:
                continue
            f = sel[0]
            zf = f["z_faccia"] - ztop
            cambio(o, (f["x"], f["y"]))
            righe.append("G98 G76 X%s Y%s Z%s R%s Q0.1 F%d (BARENATURA DI FINITURA)" % (_r(f["x"]), _r(f["y"]), _r(zf - f["prof"] - (1 if f["passante"] else 0)), _r(zf + 2), o["vf"]))
            fine()
        elif tipo in ("centrino", "foratura", "alesatura", "maschiatura", "lamatura", "svasatura"):
            sel = [fori[r] for r in d.get("fori", []) if r in fori]
            if not sel:
                continue
            cambio(o, (sel[0]["x"], sel[0]["y"]))
            for f in sel:
                zf = f["z_faccia"] - ztop                    # faccia del foro rispetto a Z0 (es. foro sul rialzo o sulla base)
                R = zf + 2
                if tipo == "centrino":
                    ciclo_ = "G98 G81 X%s Y%s Z%s R%s F%d" % (_r(f["x"]), _r(f["y"]), _r(zf - min(f["d_punta"], 8) / 2 - 0.3), _r(R), o["vf"])
                elif tipo == "foratura":
                    dp = d["d"]
                    z = zf - f["prof"] - (0.3 * dp + 1 if f["passante"] else 0.3 * dp)
                    ciclo_ = "G98 G83 X%s Y%s Z%s R%s Q%s F%d" % (_r(f["x"]), _r(f["y"]), _r(z), _r(R), _r(max(1, dp)), o["vf"])
                elif tipo == "alesatura":
                    ciclo_ = "G98 G85 X%s Y%s Z%s R%s F%d" % (_r(f["x"]), _r(f["y"]), _r(zf - f["prof"] - (1 if f["passante"] else 0)), _r(R), o["vf"])
                elif tipo == "maschiatura":
                    filetto = f["prof"] if not f["passante"] else f["prof"] + 1
                    if not f["passante"]:
                        filetto = max(f["d"], f["prof"] - 3 * f["passo"])      # resta lo spazio per l'imbocco del maschio
                    ciclo_ = "G98 G84 X%s Y%s Z%s R%s F%s" % (_r(f["x"]), _r(f["y"]), _r(zf - filetto), _r(R + 3), _r(o["vf"]))
                elif tipo == "lamatura":
                    ciclo_ = "G98 G82 X%s Y%s Z%s R%s P300 F%d" % (_r(f["x"]), _r(f["y"]), _r(zf - float(f["lamatura"]["prof"])), _r(R), o["vf"])
                else:
                    sv = f["svasatura"]
                    zz = (float(sv["d"]) / 2) / math.tan(math.radians(float(sv.get("angolo", 90)) / 2))
                    ciclo_ = "G98 G82 X%s Y%s Z%s R%s P200 F%d" % (_r(f["x"]), _r(f["y"]), _r(zf - zz), _r(R), o["vf"])
                righe.append(ciclo_)
            fine()
        elif tipo == "smusso" and d.get("spigoli") in ("superiori", "tutti"):
            c = d["valore"]
            fili = []
            for f in contorno_esterno(an["base"]):
                try:
                    fili += f.outerWire().offset2D(0.5, "arc")
                except Exception:
                    pass
            if not fili:
                continue
            p0 = _punti_filo(fili[0])
            cambio(o, p0[0])
            for w in fili:              # fresa a 90°: punta a Z-(c+0,5), asse 0,5 mm fuori dal bordo
                percorso(_punti_filo(w), [z_base - c - 0.5], o["vf"])
            righe.append("(SMUSSI DEI FORI: CON SVASATORE O A MANO)")
            fine()
        elif tipo == "raccordo":
            righe += ["", "(%s: PERCORSO 3D, USARE IL CAM)" % o["descrizione"].upper()[:60].replace("(", "").replace(")", "")]
        elif tipo == "guscio":
            righe += ["", "(SVUOTATURA DEL GUSCIO: PERCORSO 3D, USARE IL CAM)"]
    righe += ["", "M5", "G91 G28 Z0", "G28 X0 Y0", "G90", "M30", "%"]
    return _ascii("\n".join(righe) + "\n")


def _ascii(testo):
    """I controlli CNC vogliono solo ASCII: Ø→D, ×→X, °→DEG, lettere accentate senza accento."""
    import unicodedata
    for a, b in (("Ø", "D"), ("ø", "D"), ("×", "X"), ("°", "DEG"), ("–", "-"), ("—", "-"), ("’", "'")):
        testo = testo.replace(a, b)
    return unicodedata.normalize("NFKD", testo).encode("ascii", "ignore").decode("ascii")


def tabella_fori(an):
    return [{"rif": f["rif"], "x": round(f["x"], 3), "y": round(f["y"], 3), "descrizione": descrivi_foro(f)} for f in an["fori"]]
