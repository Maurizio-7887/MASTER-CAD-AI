"""Officina: tavola, ciclo/CNC, preventivo, fattibilità, libreria, AR, controllo qualità, corso, home a tile."""
import json
import math
import os
import struct
import unittest

from mastercad.ar import glb_in_metri
from mastercad.ciclo import motore
from mastercad.corso import tempo_lavorato
from mastercad.corso.valuta import valuta
from mastercad.fattibilita.regole import verifica
from mastercad.libreria import catalogo as C
from mastercad.preventivo import calcola as preventivo
from mastercad.progetto import direttive as D
from mastercad.progetto import lavorazioni as L
from mastercad.progetto.analisi import analizza
from mastercad.qualita.confronto import confronta
from mastercad.tavola import disegno_tecnico as DT

os.environ.setdefault("MASTER_CAD_PASSWORD", "test-password")
os.environ.setdefault("COOKIE_SECURE", "0")


def flangia():
    p = {"base": {"tipo": "estrudi", "entita": [{"t": "circle", "c": [0, 0], "r": 50}], "altezza": 15}, "lavorazioni": [], "nome": "Flangia prova"}
    return D.applica("foro centrale Ø30 H7 con lamatura Ø40 profonda 5; 4 fori M8 lamati su interasse 70; foro M6 filettato profondo 12 in 0,25; "
                     "rialzo Ø50 alto 6; smusso 0.5 bordi superiori", p)["progetto"]


def piastra(lav=""):
    p = {"base": {"tipo": "estrudi", "entita": [{"t": "pline", "pts": [[0, 0], [120, 0], [120, 80], [0, 80]], "closed": True}], "altezza": 12}, "lavorazioni": []}
    return D.applica(lav, p)["progetto"] if lav else p


class Analisi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.an = analizza(flangia())

    def test_fori_partono_dalla_faccia_giusta(self):
        fori = {f["rif"]: f for f in self.an["fori"]}
        self.assertAlmostEqual(fori[1]["z_faccia"], 21, delta=1e-6)        # sul rialzo
        self.assertAlmostEqual(fori[2]["z_faccia"], 15, delta=1e-6)        # sulla base
        self.assertTrue(fori[2]["passante"])
        self.assertEqual(fori[6]["filetto"], "M6")
        self.assertEqual(fori[6]["passo"], 1.0)

    def test_ciclo_e_programma(self):
        c = motore.calcola(self.an, "C45")
        ops = [o["descrizione"] for f in c["fasi"] for o in f["operazioni"]]
        self.assertTrue(any("interpolazione elicoidale Ø30" in o for o in ops), "foro grande fresato, non forato")
        self.assertTrue(any(o.startswith("Barenatura Ø30 H7") for o in ops))
        self.assertTrue(any(o.startswith("Maschiatura M6") for o in ops))
        self.assertTrue(any(o.startswith("Lamatura Ø15") for o in ops))
        self.assertGreater(c["tempi"]["macchina_min"], 5)
        g = motore.programma(self.an, c, "Flangia")
        g.encode("ascii")                                                   # solo ASCII per i controlli CNC
        self.assertTrue(g.startswith("%\nO1001"))
        self.assertIn("G98 G84", g)
        self.assertIn("G3 X", g)
        self.assertTrue(g.rstrip().endswith("M30\n%".strip()) or g.rstrip().endswith("%"))
        self.assertNotIn("G81 X0 Y0 ", g, "il foro Ø30 non si centrina: si interpola")

    def test_preventivo_cala_con_la_quantita(self):
        c = motore.calcola(self.an, "S235")
        v = preventivo(self.an, c, {"quantita": [1, 10, 100], "margine": 20})
        prezzi = [r["prezzo"] for r in v["righe"]]
        self.assertEqual([r["quantita"] for r in v["righe"]], [1, 10, 100])
        self.assertTrue(prezzi[0] > prezzi[1] > prezzi[2] > 0)
        self.assertAlmostEqual(v["righe"][0]["prezzo"], v["righe"][0]["costo"] * 1.2, delta=0.02)
        self.assertGreater(v["kg_grezzo"], v["kg_finito"])
        with self.assertRaises(ValueError):
            preventivo(self.an, c, {"trattamento": "anodizzazione"})

    def test_tavola_in_tre_formati(self):
        tav = DT.genera(self.an, {"nome": "Flangia prova", "materiale": "C45", "disegnatore": "Prova"})
        self.assertTrue(tav["sezione"])
        self.assertEqual(len(tav["tabella_fori"]), 6)
        self.assertEqual(tav["viti"], [{"descrizione": "ISO 4762 M8×20", "quantita": 4}])
        svg = DT.svg(tav)
        self.assertIn("SEZIONE A-A", svg)
        self.assertIn("Flangia prova", svg)
        self.assertTrue(DT.pdf(tav).startswith(b"%PDF"))
        dxf = DT.dxf(tav)
        for layer in (b"VISIBILI", b"NASCOSTE", b"ASSI", b"QUOTE", b"SEZIONE"):
            self.assertIn(layer, dxf)
        self.assertTrue(dxf.rstrip().endswith(b"EOF"))


class Fattibilita(unittest.TestCase):
    def test_regole(self):
        an = analizza(piastra("foro Ø10 in 3,40; 2 fori Ø8 in 60,40; tasca 30x20 profonda 10.8 in 60,40; foro M6 filettato profondo 4 in 100,20"))
        testi = " | ".join(a["testo"] for a in verifica(an)["avvisi"])
        self.assertIn("esce dal bordo", testi)
        self.assertIn("Angoli interni vivi", testi)
        self.assertIn("Sul fondo restano solo 1,2 mm", testi)
        self.assertIn("Filetto di soli 4 mm", testi)

    def test_pezzo_pulito(self):
        an = analizza(piastra("2x2 fori Ø9 passo 80x40; tasca 30x20 profonda 4 in 60,40 raggio 4"))
        an["tasche"][0]["dati"]["origine"] = None
        r = verifica(an)
        self.assertEqual(r["errori"], 0)


class Libreria(unittest.TestCase):
    def test_tutti_i_pezzi_si_costruiscono(self):
        for c in C.CATALOGO:
            r = C.genera(c["codice"], {})
            _, s, storia = L.costruisci(r["progetto"])
            self.assertTrue(all(x["ok"] for x in storia), (c["codice"], storia))
            self.assertTrue(s.isValid())
            self.assertTrue(r["tavola"])

    def test_flangia_en1092(self):
        r = C.genera("flangia_en1092", {"dn": 100})
        an = analizza(r["progetto"])
        self.assertAlmostEqual(an["ingombro"]["x"], 220, delta=0.01)
        self.assertEqual(len(an["fori"]), 9)
        with self.assertRaises(ValueError):
            C.genera("piastra_base", {"l": "abc"})


class Qualita(unittest.TestCase):
    def test_conforme_e_non_conforme(self):
        prog = piastra("2x2 fori Ø10 passo 80x40")
        prog["lavorazioni"][0]["origine"] = [20, 20]
        an = analizza(prog)
        # «foto» ruotata di 90° e spostata: il programma la riallinea
        foto = [{"t": "pline", "pts": [[200, 100], [280, 100], [280, 220], [200, 220]], "closed": True}]
        for x, y in ((20, 20), (100, 20), (20, 60), (100, 60)):
            foto.append({"t": "circle", "c": [200 + 80 - y, 100 + x], "r": 5.05})
        r = confronta(an, foto)
        self.assertEqual(r["esito"], "CONFORME", r["righe"])
        foto[-1]["c"] = [foto[-1]["c"][0] + 1.5, foto[-1]["c"][1]]
        r = confronta(an, foto)
        self.assertEqual(r["esito"], "NON CONFORME")
        self.assertEqual(sum(1 for x in r["righe"] if x["esito"] == "KO"), 1)


class Corso(unittest.TestCase):
    def test_voto(self):
        rif = piastra("2x2 fori Ø10 passo 80x40; tasca 30x20 profonda 4 in 60,40 raggio 4")
        self.assertEqual(valuta(rif, rif)["voto"], 10.0)
        spostato = json.loads(json.dumps(rif))
        spostato["base"]["entita"][0]["pts"] = [[x + 50, y - 7] for x, y in spostato["base"]["entita"][0]["pts"]]
        serie = next(x for x in spostato["lavorazioni"] if x["tipo"] == "serie_rett")
        tasca = next(x for x in spostato["lavorazioni"] if x["tipo"] == "tasca")
        serie["origine"] = [o + d for o, d in zip(serie["origine"], (50, -7))]
        tasca["centro"] = [110, 33]
        self.assertEqual(valuta(rif, spostato)["voto"], 10.0, "la posizione sul foglio non conta")
        senza_tasca = json.loads(json.dumps(rif))
        senza_tasca["lavorazioni"] = [x for x in senza_tasca["lavorazioni"] if x["tipo"] != "tasca"]
        v = valuta(rif, senza_tasca)
        self.assertLess(v["voto"], 10)
        self.assertTrue(any("volume" in m for m in v["messaggi"]))

    def test_tempo_lavorato(self):
        import datetime as dt
        t0 = dt.datetime(2026, 11, 10, 9, 0)
        tempi = [t0, t0 + dt.timedelta(minutes=2), t0 + dt.timedelta(minutes=3), t0 + dt.timedelta(minutes=40)]
        self.assertEqual(tempo_lavorato(tempi), 120 + 60 + 30 + 30)


class Ar(unittest.TestCase):
    def test_glb_in_metri(self):
        js = json.dumps({"scene": 0, "scenes": [{"nodes": [0]}], "nodes": [{"mesh": 0}]}).encode()
        js += b" " * ((4 - len(js) % 4) % 4)
        glb = b"glTF" + struct.pack("<II", 2, 20 + len(js)) + struct.pack("<I", len(js)) + b"JSON" + js
        out = glb_in_metri(glb)
        n = struct.unpack("<I", out[12:16])[0]
        self.assertEqual(json.loads(out[20:20 + n])["nodes"][0]["scale"], [0.001] * 3)
        self.assertEqual(struct.unpack("<I", out[8:12])[0], len(out))


class Http(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        from cloud_app import app
        cls.app = app

    def _docente(self, c):
        self.assertEqual(c.post("/login", data={"password": os.environ["MASTER_CAD_PASSWORD"]}).status_code, 302)
        with c.session_transaction() as s:
            return {"X-CSRF-Token": s["csrf"]}

    def test_home_e_pagine(self):
        with self.app.test_client() as c:
            self.assertEqual(c.get("/").status_code, 302)
            h = self._docente(c)
            home = c.get("/").get_data(as_text=True)
            for t in ("Dalla foto al 3D", "Disegno tecnico", "Ciclo di lavoro e CNC", "Preventivo istantaneo", "Controllo qualità foto",
                      "Pezzo in realtà aumentata", "Libreria a norma", "Verifica fattibilità", "Pannello docente"):
                self.assertIn(t, home)
            for pag in ("/parla", "/disegno", "/tavola", "/ciclo", "/preventivo", "/fattibilita", "/libreria", "/ar", "/qualita", "/corso/docente"):
                self.assertEqual(c.get(pag).status_code, 200, pag)
            prog = C.genera("piastra_base", {})["progetto"]
            for url in ("/api/tavola", "/api/ciclo", "/api/preventivo", "/api/fattibilita"):
                r = c.post(url, json={"progetto": prog, "materiale": "AL6082"}, headers=h)
                self.assertEqual(r.status_code, 200, (url, r.get_data(as_text=True)[:300]))
            r = c.post("/api/tavola/pdf", json={"progetto": prog}, headers=h)
            self.assertEqual(r.mimetype, "application/pdf")
            r = c.post("/api/ciclo/gcode", json={"progetto": prog}, headers=h)
            self.assertIn("O1001", r.get_data(as_text=True))
            r = c.post("/api/ar", json={"progetto": prog, "nome": "Piastra"}, headers=h)
            self.assertEqual(r.status_code, 200)
            ar = r.get_json()
            self.assertIn("<svg", ar["qr"])
        with self.app.test_client() as anonimo:          # il QR apre la vista senza login
            self.assertEqual(anonimo.get("/ar/v/" + ar["token"]).status_code, 200)
            self.assertEqual(anonimo.get(ar["glb"]).data[:4], b"glTF")
            self.assertEqual(anonimo.get("/ar/v/" + "0" * 32).status_code, 404)
            self.assertEqual(anonimo.get("/tavola").status_code, 302)
            self.assertEqual(anonimo.post("/api/ciclo", json={}).status_code, 401)

    def test_corso_completo(self):
        rif = piastra("2x2 fori Ø10 passo 80x40")
        with self.app.test_client() as d:
            h = self._docente(d)
            corso = d.post("/api/corso/docente/corsi", json={"nome": "Corso di prova"}, headers=h).get_json()
            r = d.post("/api/corso/docente/esercizi", data={"corso_id": corso["id"], "titolo": "Piastra", "indicazioni": "4 fori Ø10",
                                                            "riferimento": json.dumps(rif)}, headers=h)
            self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
            eid = r.get_json()["id"]
        with self.app.test_client() as a:
            pagina = a.get("/corso/entra").get_data(as_text=True)
            tok = pagina.split('name="csrf" value="')[1].split('"')[0]
            r = a.post("/corso/entra", data={"csrf": tok, "codice": corso["codice"].lower(), "nome": "Anna  Bianchi", "pin": "4321"})
            self.assertEqual(r.status_code, 302)
            with a.session_transaction() as s:
                ha = {"X-CSRF-Token": s["csrf"]}
            home = a.get("/").get_data(as_text=True)
            self.assertIn("I miei esercizi", home)
            self.assertNotIn("Pannello docente", home)
            self.assertEqual(a.get("/api/corso/docente/corsi").status_code, 403)
            self.assertEqual(a.get("/corso/docente").status_code, 302)
            self.assertEqual(a.get("/disegno").status_code, 200)
            es = a.get("/api/corso/allievo/esercizi").get_json()
            self.assertEqual(es["esercizi"][0]["titolo"], "Piastra")
            self.assertEqual(a.post("/api/corso/allievo/azioni", json={"azioni": [{"tipo": "comando", "dettaglio": "L", "t": 0}], "esercizio_id": eid,
                                                                       "progetto": rif}, headers=ha).status_code, 200)
            r = a.post("/api/corso/allievo/consegna", json={"esercizio_id": eid, "progetto": rif}, headers=ha)
            self.assertEqual(r.get_json()["esito"]["voto"], 10.0)
        with self.app.test_client() as a2:      # PIN sbagliato
            tok = a2.get("/corso/entra").get_data(as_text=True).split('name="csrf" value="')[1].split('"')[0]
            r = a2.post("/corso/entra", data={"csrf": tok, "codice": corso["codice"], "nome": "anna bianchi", "pin": "0000"})
            self.assertEqual(r.status_code, 400)
        with self.app.test_client() as d:
            h = self._docente(d)
            det = d.get("/api/corso/docente/corso/%d" % corso["id"]).get_json()
            al = det["allievi"][0]
            self.assertEqual((al["nome"], al["consegne"]), ("Anna Bianchi", 1))
            info = d.get("/api/corso/docente/allievo/%d" % al["id"]).get_json()
            self.assertTrue(info["ultimo_progetto"])
            self.assertEqual([z["tipo"] for z in info["azioni"]][-1], "accesso")
            kid = info["consegne"][0]["id"]
            self.assertEqual(d.post("/api/corso/docente/consegna/%d" % kid, json={"voto": "8,5", "commento": "Bene"}, headers=h).status_code, 200)
            self.assertEqual(d.get("/api/corso/docente/allievo/%d" % al["id"]).get_json()["consegne"][0]["voto_docente"], 8.5)


if __name__ == "__main__":
    unittest.main()
