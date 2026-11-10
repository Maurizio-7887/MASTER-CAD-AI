"""Scopo delle quote (ISO 286, cuscinetti, spine), officina reale, versioni e decisioni, dal carico alla forma."""
import copy
import json
import os
import unittest

from mastercad.ciclo import motore
from mastercad.fattibilita.regole import verifica
from mastercad.generativo.topologia import ottimizza
from mastercad.officina import PREDEFINITA, scegli_macchina, valida
from mastercad.progetto import direttive as D
from mastercad.progetto import lavorazioni as L
from mastercad.progetto.analisi import analizza, descrivi_foro
from mastercad.tolleranze import iso286
from mastercad.tolleranze.funzioni import applica_funzione, impatto
from mastercad.versioni import differenze

os.environ.setdefault("MASTER_CAD_PASSWORD", "test-password")
os.environ.setdefault("COOKIE_SECURE", "0")


def piastra(testo="", s=20):
    p = {"base": {"tipo": "estrudi", "entita": [{"t": "pline", "pts": [[0, 0], [160, 0], [160, 100], [0, 100]], "closed": True}], "altezza": s}, "lavorazioni": []}
    return D.applica(testo, p)["progetto"] if testo else p


class Iso286(unittest.TestCase):
    def test_tabelle(self):
        self.assertEqual(iso286.scostamenti(47, "H7"), (25, 0))
        self.assertEqual(iso286.scostamenti(20, "g6"), (-7, -20))
        self.assertEqual(iso286.scostamenti(20, "k5"), (11, 2))
        self.assertEqual(iso286.scostamenti(30, "K7"), (6, -15))
        self.assertEqual(iso286.scostamenti(62, "P7"), (-21, -51))
        self.assertEqual(iso286.scostamenti(8, "m6"), (15, 6))
        self.assertEqual(iso286.scostamenti(25, "js6"), (6.5, -6.5))
        with self.assertRaises(ValueError):
            iso286.scostamenti(600, "H7")

    def test_accoppiamenti_e_catena(self):
        self.assertEqual(iso286.accoppiamento(20, "H7", "g6")["tipo"], "con gioco")
        self.assertEqual(iso286.accoppiamento(8, "H7", "m6")["tipo"], "incerto")
        self.assertEqual(iso286.accoppiamento(30, "H7", "p6")["tipo"], "con interferenza")
        r = iso286.catena([{"nominale": 50, "sup": .1, "inf": -.1, "verso": 1}, {"nominale": 20, "sup": .05, "inf": 0, "verso": -1},
                           {"nominale": 29.5, "sup": 0, "inf": -.1, "verso": -1}])
        self.assertEqual((r["nominale"], r["max_peggiore"], r["min_peggiore"]), (0.5, 0.7, 0.35))
        self.assertTrue(r["min_peggiore"] <= r["min_rss"] < r["max_rss"] <= r["max_peggiore"])


class Scopo(unittest.TestCase):
    def test_indicazioni_con_componenti(self):
        r = D.applica("sede cuscinetto 6204 in 80,50; foro spina Ø8 m6 in 40,50; boccola 20x23 in 120,50; sede cuscinetto 6205 K7 cieca in 30,20", piastra())
        self.assertEqual(r["non_capito"], [])
        l = r["progetto"]["lavorazioni"]
        self.assertEqual((l[0]["d"], l[0]["lamatura"]), (22.0, {"d": 47.0, "prof": 14.0, "tolleranza": "H7"}))
        self.assertEqual(l[1]["tolleranza"], "H7", "m6 è la spina, non il foro")
        self.assertEqual((l[2]["d"], l[2]["tolleranza"]), (23.0, "H7"))
        self.assertEqual((l[3]["d"], l[3]["prof"], l[3]["lamatura"] if "lamatura" in l[3] else None, l[3]["tolleranza"]), (52.0, 15.0, None, "K7"))
        an = analizza(r["progetto"])
        self.assertIn("sede Ø47 H7 (+0,025/0)×14 — cuscinetto 6204", descrivi_foro(an["fori"][0], True))

    def test_cambio_componente_e_impatto(self):
        p = piastra("sede cuscinetto 6204 in 80,50", s=15)
        q = copy.deepcopy(p)
        q["lavorazioni"][0] = applica_funzione(q["lavorazioni"][0], {"tipo": "sede_cuscinetto", "componente": "6205"})
        imp = impatto(p, q)
        self.assertIn("Foro 1: Ø sede/lamatura 47 → 52 mm", imp["modifiche"])
        self.assertTrue(imp["problemi_restano"], "sede da 14–15 mm su 15 mm: lo spallamento manca in entrambi i casi")
        self.assertFalse(imp["problemi_nuovi"])
        with self.assertRaises(ValueError):
            applica_funzione(q["lavorazioni"][0], {"tipo": "sede_cuscinetto", "componente": "9999"})

    def test_ciclo_e_controllo(self):
        an = analizza(piastra("sede cuscinetto 6204 in 80,50; foro spina Ø8 in 40,50; foro M6 filettato profondo 12 in 140,80"))
        c = motore.calcola(an, "C45")
        ops = [o["descrizione"] for f in c["fasi"] for o in f["operazioni"]]
        self.assertTrue(any(o.startswith("Barenatura sede Ø47 H7") for o in ops))
        self.assertTrue(any(o.startswith("Alesatura Ø8 H7") for o in ops))
        piano = " | ".join(x["descrizione"] for x in c["piano_controllo"])
        self.assertIn("Ø47 H7 (+0,025/0): tampone P/NP — P 47,000 · NP 47,025", piano)
        self.assertIn("filetto M6 6H", piano)
        g = motore.programma(an, c, "x")
        self.assertIn("G76", g)
        g.encode("ascii")


class Officina(unittest.TestCase):
    def test_terzista_quando_non_entra(self):
        off = valida(json.loads(json.dumps(PREDEFINITA)))
        self.assertTrue(scegli_macchina(off, "fresa", (300, 200, 50))["interna"])
        m = scegli_macchina(off, "fresa", (1200, 400, 50))
        self.assertFalse(m["interna"])
        self.assertIn("Terzista fresature grandi", m["nome"])
        self.assertIn("non entra", m["motivo"])
        an = analizza({"base": {"tipo": "estrudi", "entita": [{"t": "pline", "pts": [[0, 0], [1100, 0], [1100, 300], [0, 300]], "closed": True}], "altezza": 20},
                       "lavorazioni": [{"tipo": "foro", "x": 50, "y": 50, "d": 10}]})
        c = motore.calcola(an, "S235", off)
        self.assertEqual(c["terzisti"][0]["fase"], 20)
        self.assertEqual(c["fasi"][1]["costo_ora"], 70)
        testi = " ".join(a["testo"] for a in verifica(an, off)["avvisi"])
        self.assertIn("Nessuna macchina interna adatta", testi)

    def test_validazione(self):
        with self.assertRaises(ValueError):
            valida({"macchine": [{"tipo": "teletrasporto", "costo_ora": 10}]})
        with self.assertRaises(ValueError):
            valida({"macchine": [{"tipo": "fresa", "costo_ora": -5}]})


class Versioni(unittest.TestCase):
    def test_differenze_per_identificativo(self):
        a = piastra("foro Ø10 in 20,20; sede cuscinetto 6204 in 80,50")
        for i, l in enumerate(a["lavorazioni"]):
            l["id"] = "L%d" % i
        b = copy.deepcopy(a)
        b["lavorazioni"][1] = applica_funzione(b["lavorazioni"][1], {"tipo": "sede_cuscinetto", "componente": "6205"})
        b["lavorazioni"].pop(0)
        b["lavorazioni"].append({"id": "N1", "tipo": "smusso", "d": 1, "spigoli": "superiori"})
        b["base"]["altezza"] = 25
        d = differenze(a, b)
        self.assertIn("Spessore 20 → 25 mm", d)
        self.assertTrue(any(x.startswith("~ Sede cuscinetto 6204 → Sede cuscinetto 6205") for x in d))
        self.assertTrue(any(x.startswith("− Foro Ø10") for x in d))
        self.assertIn("+ Smusso", d)


class Generativo(unittest.TestCase):
    def test_staffa(self):
        r = ottimizza({"larghezza": 120, "altezza": 80, "spessore": 10, "materiale": "S235", "risoluzione": 40, "iterazioni": 30,
                       "viti": [{"x": 12, "y": 15, "vite": "M10"}, {"x": 12, "y": 65, "vite": "M10"}],
                       "carichi": [{"x": 105, "y": 40, "fx": 0, "fy": -6000, "d": 12}], "massa_max_g": 350, "sicurezza": 2})
        self.assertGreaterEqual(r["sicurezza"], 2)
        self.assertIn(r["spessore"], (2, 3, 4, 5, 6, 8, 10, 12, 15, 20))
        _, s, storia = L.costruisci(r["progetto"])
        self.assertTrue(s.isValid())
        self.assertEqual(sum(1 for l in r["progetto"]["lavorazioni"] if l["tipo"] == "foro"), 3)
        self.assertTrue(all(x["ok"] for x in storia[:4]))
        piena = 120 * 80 * r["spessore"] * 7.85 / 1000
        self.assertLess(r["massa_g"], piena * 0.75, "il materiale che non lavora viene tolto")
        with self.assertRaises(ValueError):
            ottimizza({"larghezza": 100, "altezza": 50, "viti": [], "carichi": [{"x": 1, "y": 1, "fy": 1}]})


class Http(unittest.TestCase):
    def test_pagine_e_api(self):
        from cloud_app import app
        with app.test_client() as c:
            self.assertEqual(c.post("/login", data={"password": os.environ["MASTER_CAD_PASSWORD"]}).status_code, 302)
            with c.session_transaction() as s:
                h = {"X-CSRF-Token": s["csrf"]}
            for pag in ("/manuale", "/officina", "/tolleranze", "/versioni", "/generativo"):
                r = c.get(pag)
                self.assertEqual(r.status_code, 200, pag)
                self.assertIn(b'class="bottone aiuto"', r.data)
            self.assertIn(b'id="scopo"', c.get("/manuale").data)
            off = c.get("/api/officina").get_json()
            off["costi"]["margine"] = 30
            self.assertEqual(c.post("/api/officina", json=off, headers=h).status_code, 200)
            self.assertEqual(c.get("/api/officina").get_json()["costi"]["margine"], 30)
            r = c.post("/api/tolleranze/accoppiamento", json={"diametro": "20", "foro": "H7", "albero": "g6"}, headers=h)
            self.assertEqual(r.get_json()["gioco_min_um"], 7)
            p = piastra("sede cuscinetto 6204 in 80,50")
            r = c.post("/api/progetto/funzione", json={"progetto": p, "indice": 0, "funzione": {"tipo": "sede_cuscinetto", "componente": "6206"}}, headers=h)
            self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
            self.assertEqual(r.get_json()["progetto"]["lavorazioni"][0]["lamatura"]["d"], 62.0)
            import uuid
            p["uid"] = uuid.uuid4().hex[:12]
            p["registro"] = [{"quando": "2026-11-10T10:00:00", "chi": "Prova", "cosa": "Sede 6204", "norma": "ISO 15"}]
            r = c.post("/api/versioni", json={"progetto": p, "messaggio": "prima"}, headers=h)
            self.assertEqual(r.get_json()["numero"], 1)
            self.assertEqual(c.post("/api/versioni", json={"progetto": p, "messaggio": ""}, headers=h).status_code, 400)
            v = c.get("/api/versioni?uid=" + p["uid"]).get_json()
            self.assertEqual(v[0]["decisioni"][0]["cosa"], "Sede 6204")
            r = c.post("/api/preventivo", json={"progetto": p, "materiale": "C45", "parametri": {"quantita": [1]}}, headers=h)
            self.assertEqual(r.get_json()["preventivo"]["margine"], 30.0)
            r = c.post("/api/generativo", json={"larghezza": 100, "altezza": 60, "risoluzione": 30, "iterazioni": 15,
                                                "viti": [{"x": 10, "y": 30, "vite": "M8"}], "carichi": [{"x": 90, "y": 30, "fy": -500}]}, headers=h)
            self.assertEqual(r.status_code, 200, r.get_data(as_text=True)[:300])


if __name__ == "__main__":
    unittest.main()
