"""Assiemi con lo scopo: i pezzi si montano da soli in base a cosa sono i loro fori.

- Due pezzi con fori spina uguali → si impilano allineati sulle spine (si provano 4 rotazioni e il ribaltamento).
- Passaggi vite sopra e filetti sotto, stessa misura → viti ISO 4762 con la lunghezza giusta.
- Una sede cuscinetto → cuscinetto (ISO 15) e albero generato con il tratto k5 dove lavora l'anello interno.
Poi si verifica: accoppiamenti al micron (ISO 492 per gli anelli, ISO 286 per sede e albero), presa di viti e spine,
collisioni fra tutti i pezzi. Il programma propone, tu confermi.
"""
import copy
import hashlib
import json
import math

import cadquery as cq

from ..materiali import materiale as dati_materiale
from ..progetto import lavorazioni as L
from ..progetto.analisi import _num, analizza
from ..tolleranze import iso286
from ..tolleranze.funzioni import CUSCINETTI
from . import commerciali as C

TOL = 0.05
COLORI = [(0.72, 0.76, 0.80), (0.55, 0.68, 0.85), (0.80, 0.72, 0.58), (0.62, 0.78, 0.66), (0.78, 0.66, 0.78), (0.70, 0.70, 0.62)]
COLORE_COMM = {"cuscinetto": (0.85, 0.75, 0.25), "vite": (0.25, 0.25, 0.28), "spina": (0.55, 0.55, 0.6), "albero": (0.60, 0.62, 0.66)}


class Cache:
    def __init__(self):
        self.an = {}

    def analisi(self, progetto):
        k = hashlib.sha1(json.dumps(progetto, sort_keys=True, default=str).encode()).hexdigest()
        if k not in self.an:
            self.an[k] = analizza(progetto)
        return self.an[k]


# ── pose: ribalta (180° attorno a X), ruota attorno a Z, sposta ──
def posa_solido(s, comp):
    if comp.get("asse_z"):               # pezzi torniti: l'asse di rivoluzione X diventa Z
        s = s.rotate(cq.Vector(0, 0, 0), cq.Vector(0, 1, 0), -90)
    if comp.get("capovolto"):
        s = s.rotate(cq.Vector(0, 0, 0), cq.Vector(1, 0, 0), 180)
    if comp.get("rz"):
        s = s.rotate(cq.Vector(0, 0, 0), cq.Vector(0, 0, 1), float(comp["rz"]))
    p = comp.get("pos") or [0, 0, 0]
    return s.translate(cq.Vector(*[float(v) for v in p]))


def _ruota(x, y, z, capovolto, rz):
    if capovolto:
        y, z = -y, -z
    a = math.radians(rz or 0)
    return x * math.cos(a) - y * math.sin(a), x * math.sin(a) + y * math.cos(a), z


def fori_mondo(comp, an, capovolto=None, rz=None, pos=None):
    """Fori del pezzo in coordinate dell'assieme: centro XY, quota d'ingresso, verso (−1 giù, +1 su), facce raggiunte."""
    cap = comp.get("capovolto") if capovolto is None else capovolto
    rot = comp.get("rz", 0) if rz is None else rz
    p = pos if pos is not None else (comp.get("pos") or [0, 0, 0])
    out = []
    for f in an["fori"]:
        verso = 1 if f["da_sotto"] else -1
        x, y, z = _ruota(f["x"], f["y"], f["z_faccia"], cap, rot)
        if cap:
            verso = -verso
        out.append(dict(f, wx=x + p[0], wy=y + p[1], wz=z + p[2], verso=verso))
    return out


def _bbox(comp, an):
    s = posa_solido(an["solido"], comp)
    b = s.BoundingBox()
    return b


def _ruoli(f):
    fz = (f.get("funzione") or {}).get("tipo")
    if fz:
        return fz
    if f["filetto"]:
        return "filetto"
    return "foro"


# ── proposte ──
def _miglior_impilaggio(A, anA, B, anB):
    """Cerca rotazione, ribaltamento e spostamento di B appoggiato sopra A che allineano spine (o viti)."""
    bA = _bbox(A, anA)
    foriA = [f for f in fori_mondo(A, anA) if f["passante"] or (abs(f["wz"] - bA.zmax) < 0.01 and f["verso"] < 0)]
    migliore = None
    for cap in (False, True):
        for rz in (0, 90, 180, 270):
            prova = dict(B, capovolto=cap, rz=rz, pos=[0, 0, 0])
            bB = _bbox(prova, anB)
            foriB = [f for f in fori_mondo(prova, anB) if f["passante"] or (abs(f["wz"] - bB.zmin) < 0.01 and f["verso"] > 0)]
            for tipoA, tipoB in (("foro_spina", "foro_spina"), ("filetto", "passaggio_vite")):
                PA = [f for f in foriA if _ruoli(f) == tipoA]
                PB = [f for f in foriB if _ruoli(f) == tipoB]
                for a in PA:
                    for b in PB:
                        if not _compatibili(a, b):
                            continue
                        t = (a["wx"] - b["wx"], a["wy"] - b["wy"])
                        coppie = _coppie(PA, PB, t)
                        if len(coppie) < 2:
                            continue
                        pos = [t[0], t[1], bA.zmax - bB.zmin]
                        spine = coppie if tipoA == "foro_spina" else []
                        viti = _coppie([f for f in foriA if _ruoli(f) == "filetto"], [f for f in foriB if _ruoli(f) == "passaggio_vite"], t)
                        punti = len(spine) * 10 + len(viti) * 3 - (1 if cap else 0)
                        if migliore is None or punti > migliore["punti"]:
                            migliore = {"punti": punti, "capovolto": cap, "rz": rz, "pos": [round(v, 4) for v in pos],
                                        "spine": [(a_["rif"], b_["rif"]) for a_, b_ in spine], "viti": [(a_["rif"], b_["rif"]) for a_, b_ in viti]}
    return migliore


def _compatibili(a, b):
    ra, rb = _ruoli(a), _ruoli(b)
    if ra == "foro_spina":
        return abs(a["d"] - b["d"]) < 0.01
    fa = a["filetto"]
    vb = ((b.get("funzione") or {}).get("componente") or "").upper()
    return fa and fa == vb


def _coppie(PA, PB, t):
    out, usati = [], set()
    for b in PB:
        for a in PA:
            if a["rif"] in usati or not _compatibili(a, b):
                continue
            if math.hypot(a["wx"] - (b["wx"] + t[0]), a["wy"] - (b["wy"] + t[1])) < TOL:
                out.append((a, b))
                usati.add(a["rif"])
                break
    return out


def proponi(assieme, cache=None):
    cache = cache or Cache()
    comps = [c for c in assieme.get("componenti") or [] if c.get("tipo") == "pezzo"]
    proposte = []
    posati = {}
    for i, B in enumerate(comps):
        anB = cache.analisi(B["progetto"])
        if i == 0:
            posati[B["id"]] = B
        else:
            migliore, sotto = None, None
            for A in list(posati.values()):
                anA = cache.analisi(A["progetto"])
                m = _miglior_impilaggio(A, anA, B, anB)
                if m and (migliore is None or m["punti"] > migliore["punti"]):
                    migliore, sotto = m, A
            if migliore:
                desc = "«%s» sopra «%s»" % (B["nome"], sotto["nome"])
                if migliore["spine"]:
                    d = next(f["d"] for f in cache.analisi(sotto["progetto"])["fori"] if f["rif"] == migliore["spine"][0][0])
                    desc += ", allineati con %d spine Ø%s" % (len(migliore["spine"]), _num(d))
                if migliore["viti"]:
                    m_ = next(f["filetto"] for f in cache.analisi(sotto["progetto"])["fori"] if f["rif"] == migliore["viti"][0][0])
                    desc += ", %d viti %s" % (len(migliore["viti"]), m_)
                if migliore["capovolto"] or migliore["rz"]:
                    desc += " (%s%s)" % ("capovolto, " if migliore["capovolto"] else "", "ruotato di %d°" % migliore["rz"])
                proposte.append({"tipo": "impila", "sopra": B["id"], "sotto": sotto["id"], "capovolto": migliore["capovolto"], "rz": migliore["rz"],
                                 "pos": migliore["pos"], "spine": migliore["spine"], "viti": migliore["viti"], "descrizione": desc})
                posati[B["id"]] = dict(B, capovolto=migliore["capovolto"], rz=migliore["rz"], pos=migliore["pos"])
            else:
                posati[B["id"]] = B
        for f in anB["fori"]:
            fz = f.get("funzione") or {}
            if fz.get("tipo") == "sede_cuscinetto" and fz.get("componente") in CUSCINETTI:
                d, D, Bw = CUSCINETTI[fz["componente"]]
                proposte.append({"tipo": "cuscinetto", "pezzo": B["id"], "foro": f["rif"], "codice": fz["componente"], "albero": True,
                                 "descrizione": "Cuscinetto %s nella sede del foro %d di «%s» + albero Ø%g k5 generato" % (fz["componente"], f["rif"], B["nome"], d)})
    return proposte


# ── montaggio e verifiche ──
def _albero(codice, sopra_mm, sotto_mm, lato="su"):
    """Albero per il cuscinetto: tratto Ø d k5 lungo B (anello interno), spallamento, codolo sporgente."""
    d, D, B = CUSCINETTI[codice]
    spall = d + max(3.0, (D - d) * 0.18)           # diametro di spallamento minimo (catalogo: d_a min)
    x0 = 0.0
    tratti = [(d - 1.0, sotto_mm), (d, B), (spall, 4.0), (d, sopra_mm)]
    pts, x = [[0, 0]], 0.0
    for diam, lung in tratti:
        pts += [[x, diam / 2], [x + lung, diam / 2]]
        x += lung
    pts.append([x, 0])
    progetto = {"nome": "Albero cuscinetto %s" % codice, "materiale": "C45",
                "base": {"tipo": "rivoluzione", "entita": [{"t": "pline", "pts": pts, "closed": True}], "asse": [[0, 0], [1, 0]], "angolo": 360},
                "lavorazioni": [{"tipo": "smusso", "d": 0.5, "spigoli": "tutti"}],
                "quote_funzionali": [{"diametro": d, "sigla": "k5", "da": x0 + sotto_mm, "a": x0 + sotto_mm + B,
                                      "perche": "Sede anello interno cuscinetto %s (carico rotante: accoppiamento con interferenza)" % codice,
                                      "norma": "ISO 286, catalogo cuscinetti"},
                                     {"diametro": spall, "sigla": None, "da": sotto_mm + B, "a": sotto_mm + B + 4,
                                      "perche": "Spallamento: appoggio dell'anello interno", "norma": "ISO 15 / catalogo (d_a min)"}]}
    return progetto, sotto_mm


def _accoppiamento(nome, d, foro, albero):
    """foro, albero: (sup, inf) in µm. Restituisce testo e tipo."""
    gmax = foro[0] - albero[1]
    gmin = foro[1] - albero[0]
    tipo = "gioco" if gmin >= 0 else "interferenza" if gmax <= 0 else "incerto"
    return {"voce": nome, "testo": "Ø%s: da %s a %s µm (%s)" % (_num(d), _num(gmin), _num(gmax), {"gioco": "sempre gioco", "interferenza": "sempre interferenza", "incerto": "incerto"}[tipo]),
            "tipo": tipo, "gioco_min_um": gmin, "gioco_max_um": gmax}


def monta(assieme, montaggi, cache=None):
    cache = cache or Cache()
    comps = [copy.deepcopy(c) for c in assieme.get("componenti") or []]
    per_id = {c["id"]: c for c in comps}
    verifiche, esclusi, commerciali = [], set(), []

    def esito(livello, voce, testo, norma=""):
        verifiche.append({"livello": livello, "voce": voce, "testo": testo, "norma": norma})

    for m in montaggi or []:
        if m.get("tipo") == "impila":
            A, B = per_id.get(m["sotto"]), per_id.get(m["sopra"])
            if not A or not B:
                continue
            anA, anB = cache.analisi(A["progetto"]), cache.analisi(B["progetto"])
            B.update(capovolto=bool(m.get("capovolto")), rz=float(m.get("rz") or 0), pos=[0, 0, 0])
            bA, bB = _bbox(A, anA), _bbox(B, anB)
            fB0 = {f["rif"]: f for f in fori_mondo(B, anB)}
            fA = {f["rif"]: f for f in fori_mondo(A, anA)}
            ref = (m.get("spine") or m.get("viti") or [None])[0]
            if ref:
                t = (fA[ref[0]]["wx"] - fB0[ref[1]]["wx"], fA[ref[0]]["wy"] - fB0[ref[1]]["wy"])
            else:
                t = tuple((m.get("pos") or [0, 0])[:2])
            B["pos"] = [t[0], t[1], bA.zmax - bB.zmin]
            fB = {f["rif"]: f for f in fori_mondo(B, anB)}
            interfaccia = bA.zmax
            for ra, rb in m.get("spine") or []:
                a, b = fA[ra], fB[rb]
                if math.hypot(a["wx"] - b["wx"], a["wy"] - b["wy"]) > TOL:
                    esito("errore", "Spina %s/%s" % (A["nome"], B["nome"]), "I fori %d e %d non sono allineati" % (ra, rb))
                    continue
                d = a["d"]
                presa_a = a["prof"] if not a["passante"] else a["spessore"]
                presa_b = b["prof"] if not b["passante"] else b["spessore"]
                Lsp = C.lunghezza_spina(d, presa_a, presa_b)
                pa = min(presa_a, Lsp / 2)
                if Lsp - pa > presa_b:
                    pa = Lsp - presa_b
                cid = "sp%d_%s" % (len(commerciali) + 1, B["id"])
                commerciali.append({"id": cid, "tipo": "spina", "nome": "Spina ISO 8734 Ø%s×%d" % (_num(d), Lsp), "codice": "ISO 8734 %sx%d" % (_num(d), Lsp),
                                    "solido": C.solido_spina(d, Lsp).translate(cq.Vector(a["wx"], a["wy"], interfaccia - pa))})
                esclusi |= {(cid, A["id"]), (cid, B["id"])}
                ok = pa >= d and Lsp - pa >= d
                acc = _accoppiamento("Spina Ø%s m6 nel foro H7" % _num(d), d, iso286.scostamenti(d, a["tolleranza"] or "H7"), iso286.scostamenti(d, "m6"))
                esito("ok" if ok else "attenzione", "Spina Ø%s×%d (fori %d ↔ %d)" % (_num(d), Lsp, ra, rb),
                      "Presa %s mm in «%s» e %s mm in «%s»%s. %s" % (_num(pa), A["nome"], _num(Lsp - pa), B["nome"], "" if ok else " — meno di un diametro: centra poco", acc["testo"]),
                      "ISO 8734, ISO 286")
            for ra, rb in m.get("viti") or []:
                a, b = fA[ra], fB[rb]
                vite = a["filetto"]
                lam = float((b["lamatura"] or {}).get("prof") or 0)
                presa = b["spessore"] - lam
                disponibile = a["prof"] if not a["passante"] else a["spessore"]
                mat_a = "alluminio" if str(A.get("materiale") or "").upper().startswith("AL") else "acciaio"
                Lv, avv, ok = C.lunghezza_vite(vite, presa, disponibile, mat_a)
                cid = "vt%d_%s" % (len(commerciali) + 1, B["id"])
                testa_z = b["wz"] - lam if b["verso"] < 0 else b["wz"]
                commerciali.append({"id": cid, "tipo": "vite", "nome": "Vite ISO 4762 %s×%d 8.8" % (vite, Lv), "codice": "ISO 4762 %sx%d-8.8" % (vite, Lv),
                                    "solido": C.solido_vite(vite, Lv).translate(cq.Vector(b["wx"], b["wy"], testa_z))})
                esclusi |= {(cid, A["id"]), (cid, B["id"])}
                d = float(vite[1:])
                testo = "Presa %s mm + avvitamento %s mm (%s d) su filetto disponibile %s mm" % (_num(presa), _num(avv), _num(avv / d), _num(disponibile))
                if not ok:
                    esito("errore", "Vite %s (fori %d ↔ %d)" % (vite, ra, rb), testo + ": nessuna lunghezza unificata va bene. Allunga il filetto in «%s» o usa una vite più corta con rondella." % A["nome"], "ISO 4762, regola 1–2 d")
                else:
                    esito("ok", "Vite %s×%d (fori %d ↔ %d)" % (vite, Lv, ra, rb), testo, "ISO 4762, avvitamento 1,5 d in acciaio / 2 d in alluminio")
        elif m.get("tipo") == "cuscinetto":
            A = per_id.get(m["pezzo"])
            if not A:
                continue
            anA = cache.analisi(A["progetto"])
            f = next((x for x in fori_mondo(A, anA) if x["rif"] == m["foro"]), None)
            codice = m.get("codice")
            if not f or codice not in CUSCINETTI:
                esito("errore", "Cuscinetto", "Sede o sigla del cuscinetto non trovate")
                continue
            d, D, Bw = CUSCINETTI[codice]
            z0 = f["wz"] - Bw if f["verso"] < 0 else f["wz"]
            cid = "cu%d_%s" % (len(commerciali) + 1, A["id"])
            commerciali.append({"id": cid, "tipo": "cuscinetto", "nome": "Cuscinetto %s (d%g×D%g×B%g)" % (codice, d, D, Bw), "codice": codice,
                                "solido": C.solido_cuscinetto(codice).translate(cq.Vector(f["wx"], f["wy"], z0))})
            esclusi.add((cid, A["id"]))
            sede = f["lamatura"] if f["lamatura"] else {"d": f["d"], "tolleranza": f["tolleranza"]}
            sig = sede.get("tolleranza") or "H7"
            if abs(float(sede["d"]) - D) > 0.01:
                esito("errore", "Cuscinetto %s" % codice, "La sede è Ø%s ma il cuscinetto ha D=%g" % (_num(sede["d"]), D))
            est = _accoppiamento("Anello esterno in sede %s" % sig, D, iso286.scostamenti(D, sig), C.iso492(D, True))
            esito("ok" if est["tipo"] != "interferenza" else "attenzione", "Cuscinetto %s · anello esterno" % codice,
                  est["testo"] + " — alloggiamento fisso: l'anello esterno deve poter scorrere assialmente (lato libero).", "ISO 492 classe normale, ISO 286")
            if m.get("albero", True):
                spess = f["spessore"]
                sotto = max(2.0, spess - Bw + 3.0)
                prog_alb, _ = _albero(codice, float(m.get("sporgenza") or 30), sotto)
                aid = "al%d_%s" % (len(commerciali) + 1, A["id"])
                z_alb = z0 - sotto if f["verso"] < 0 else z0 + Bw + sotto
                alb = {"id": aid, "tipo": "pezzo", "nome": prog_alb["nome"], "progetto": prog_alb, "materiale": "C45", "generato": True,
                       "asse_z": True, "capovolto": f["verso"] > 0, "rz": 0, "pos": [f["wx"], f["wy"], z_alb]}
                comps.append(alb)
                per_id[aid] = alb
                esclusi.add((aid, cid))
                inn = _accoppiamento("Albero k5 nell'anello interno", d, C.iso492(d), iso286.scostamenti(d, "k5"))
                esito("ok" if inn["tipo"] != "gioco" else "errore", "Cuscinetto %s · anello interno" % codice,
                      inn["testo"] + " — carico rotante sull'anello interno: serve interferenza (montaggio a pressa o a caldo).", "ISO 492 classe normale, ISO 286 k5")
                passaggio = f["d"]
                gioco = (passaggio - (d - 1.0)) / 2
                esito("ok" if gioco >= 0.5 else "attenzione", "Albero nel passaggio di «%s»" % A["nome"], "Gioco radiale %s mm fra albero (Ø%s) e foro di passaggio (Ø%s)." % (
                    _num(gioco), _num(d - 1), _num(passaggio)), "")

    # solidi posati
    solidi = {}
    for i, c in enumerate(comps):
        if c.get("tipo") == "pezzo":
            solidi[c["id"]] = (posa_solido(cache.analisi(c["progetto"])["solido"], c), c, COLORI[i % len(COLORI)] if not c.get("generato") else COLORE_COMM["albero"])
    for c in commerciali:
        solidi[c["id"]] = (c["solido"], c, COLORE_COMM[c["tipo"]])
    # collisioni (prima il riquadro, poi il solido)
    ids = list(solidi)
    for i, a in enumerate(ids):
        for b in ids[i + 1:]:
            if (a, b) in esclusi or (b, a) in esclusi:
                continue
            sa, sb = solidi[a][0], solidi[b][0]
            ba, bb = sa.BoundingBox(), sb.BoundingBox()
            if ba.xmin > bb.xmax or bb.xmin > ba.xmax or ba.ymin > bb.ymax or bb.ymin > ba.ymax or ba.zmin > bb.zmax or bb.zmin > ba.zmax:
                continue
            try:
                v = sa.intersect(sb).Volume()
            except Exception:
                v = 0.0
            if v > 1.0:
                esito("errore", "Collisione", "«%s» e «%s» si compenetrano per %s mm³" % (solidi[a][1]["nome"], solidi[b][1]["nome"], _num(v)), "")
    if not any(v["voce"] == "Collisione" for v in verifiche):
        esito("ok", "Collisioni", "Nessuna compenetrazione fra i %d componenti" % len(solidi), "")
    return {"componenti": comps, "commerciali": commerciali, "solidi": solidi, "verifiche": verifiche, "distinta": distinta(comps, commerciali, cache)}


def distinta(comps, commerciali, cache):
    pezzi, comm = {}, {}
    for c in comps:
        if c.get("tipo") != "pezzo":
            continue
        k = c["nome"]
        an = cache.analisi(c["progetto"])
        mat = str(c.get("materiale") or c["progetto"].get("materiale") or "S235").upper()
        try:
            dens = dati_materiale(mat)["densita"]
        except ValueError:
            dens = 7.85
        r = pezzi.setdefault(k, {"livello": 2, "tipo": "Pezzo a disegno" + (" (generato)" if c.get("generato") else ""), "descrizione": k,
                                 "materiale": mat, "massa_kg": round(an["volume"] / 1e6 * dens, 3), "quantita": 0, "norma": "a disegno"})
        r["quantita"] += 1
    for c in commerciali:
        r = comm.setdefault(c["nome"], {"livello": 2, "tipo": "Commerciale", "descrizione": c["nome"], "materiale": "", "massa_kg": None, "quantita": 0,
                                        "norma": {"cuscinetto": "ISO 15", "vite": "ISO 4762 cl. 8.8", "spina": "ISO 8734"}[c["tipo"]]})
        r["quantita"] += 1
    return list(pezzi.values()) + sorted(comm.values(), key=lambda r: r["descrizione"])


def esporta_glb(solidi, esploso=False):
    from ..ar import glb_in_metri
    import tempfile
    from pathlib import Path
    a = cq.Assembly()
    ordine = sorted(solidi.items(), key=lambda kv: kv[1][0].BoundingBox().zmin)
    z0 = min((s.BoundingBox().zmin for s, _, _ in solidi.values()), default=0)
    for i, (k, (s, c, col)) in enumerate(ordine):
        if esploso:      # esploso lungo Z: ogni componente si allontana in proporzione alla sua quota, i commerciali un po' di più
            b = s.BoundingBox()
            extra = 1.6 if c.get("tipo") in ("vite", "cuscinetto") else 1.0
            s = s.translate(cq.Vector(0, 0, ((b.zmin + b.zmax) / 2 - z0) * 1.4 * extra))
        a.add(s, name="%s_%d" % ("".join(ch for ch in k if ch.isalnum()), i), color=cq.Color(*col))
    with tempfile.TemporaryDirectory(prefix="cad-assieme-") as tmp:
        p = Path(tmp) / "assieme.glb"
        a.export(str(p))
        return glb_in_metri(p.read_bytes())
