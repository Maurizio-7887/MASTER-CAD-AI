"""Assiemi con lo scopo: proposte dai fori funzionali, verifiche, collisioni, distinta, albero generato."""
import os
import unittest

from mastercad.assiemi import montaggio as M
from mastercad.ciclo import motore
from mastercad.progetto import direttive as D
from mastercad.progetto.analisi import analizza
from mastercad.tavola import disegno_tecnico as DT
from mastercad.tolleranze.funzioni import applica_funzione

os.environ.setdefault("MASTER_CAD_PASSWORD", "test-password")
os.environ.setdefault("COOKIE_SECURE", "0")


def piastre():
    base = {"base": {"tipo": "estrudi", "entita": [{"t": "pline", "pts": [[0, 0], [200, 0], [200, 120], [0, 120]], "closed": True}], "altezza": 25}, "lavorazioni": []}
    base = D.applica("foro M8 filettato profondo 18 in 40,30; foro M8 filettato profondo 18 in 160,30; foro M8 filettato profondo 18 in 40,90; "
                     "foro M8 filettato profondo 18 in 160,90; foro spina Ø8 in 50,60 profonda 16; foro spina Ø8 in 150,60 profonda 16; foro Ø30 in 100,60", base)["progetto"]
    sup = {"base": {"tipo": "estrudi", "entita": [{"t": "pline", "pts": [[0, 0], [140, 0], [140, 80], [0, 80]], "closed": True}], "altezza": 20}, "lavorazioni": []}
    sup = D.applica("foro spina Ø8 in 20,40; foro spina Ø8 in 120,40; sede cuscinetto 6204 in 70,40", sup)["progetto"]
    for x, y in ((10, 10), (130, 10), (10, 70), (130, 70)):
        sup["lavorazioni"].append(applica_funzione({"tipo": "foro", "x": x, "y": y}, {"tipo": "passaggio_vite", "componente": "M8"}))
    return {"nome": "Supporto cuscinetto", "componenti": [
        {"id": "A", "tipo": "pezzo", "nome": "Piastra base", "progetto": base, "pos": [0, 0, 0]},
        {"id": "B", "tipo": "pezzo", "nome": "Supporto", "progetto": sup, "pos": [0, 0, 0], "rz": 90, "capovolto": True}]}


class Assiemi(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ass = piastre()
        cls.proposte = M.proponi(cls.ass)
        cls.r = M.monta(cls.ass, cls.proposte)

    def test_proposte(self):
        imp = next(p for p in self.proposte if p["tipo"] == "impila")
        self.assertEqual((imp["pos"], imp["rz"], imp["capovolto"]), ([30.0, 20.0, 25.0], 0, False), "trova da solo rotazione e posizione")
        self.assertEqual((len(imp["spine"]), len(imp["viti"])), (2, 4))
        self.assertTrue(any(p["tipo"] == "cuscinetto" and p["codice"] == "6204" for p in self.proposte))

    def test_verifiche(self):
        v = {x["voce"]: x for x in self.r["verifiche"]}
        self.assertFalse([x for x in self.r["verifiche"] if x["livello"] == "errore"], self.r["verifiche"])
        self.assertIn("Ø47: da 0 a 36 µm (sempre gioco)", v["Cuscinetto 6204 · anello esterno"]["testo"])
        self.assertIn("Ø20: da -21 a -2 µm (sempre interferenza)", v["Cuscinetto 6204 · anello interno"]["testo"])
        self.assertTrue(any(k.startswith("Vite M8×25") for k in v))
        self.assertTrue(any(k.startswith("Spina Ø8×28") for k in v))
        self.assertIn("Nessuna compenetrazione", v["Collisioni"]["testo"])

    def test_distinta_e_albero(self):
        dist = {d["descrizione"]: d for d in self.r["distinta"]}
        self.assertEqual(dist["Vite ISO 4762 M8×25 8.8"]["quantita"], 4)
        self.assertEqual(dist["Spina ISO 8734 Ø8×28"]["quantita"], 2)
        self.assertEqual(dist["Cuscinetto 6204 (d20×D47×B14)"]["quantita"], 1)
        albero = next(c for c in self.r["componenti"] if c.get("generato"))
        an = analizza(albero["progetto"])
        c = motore.calcola(an, "C45")
        self.assertTrue(any(f["nome"] == "Rettifica" for f in c["fasi"]))
        self.assertIn("Ø20 k5 (+0,011/+0,002)", " ".join(x["descrizione"] for x in c["piano_controllo"]))
        tav = DT.genera(an, {"nome": "Albero"})
        self.assertTrue(any("k5" in n for n in tav["note"]))
        self.assertTrue(M.esporta_glb(self.r["solidi"]).startswith(b"glTF"))

    def test_collisione(self):
        ass = piastre()
        ass["componenti"][1].update(pos=[10, 10, 5], rz=0, capovolto=False)     # supporto affondato nella base
        r = M.monta(ass, [])
        self.assertTrue(any(v["voce"] == "Collisione" for v in r["verifiche"]))

    def test_vite_troppo_lunga(self):
        ass = piastre()
        prog = ass["componenti"][0]["progetto"]
        for l in prog["lavorazioni"]:
            if l.get("filetto") == "M8":
                l["prof"] = 6
        r = M.monta(ass, M.proponi(ass))
        self.assertTrue(any(v["livello"] == "errore" and v["voce"].startswith("Vite M8") for v in r["verifiche"]))


class Http(unittest.TestCase):
    def test_api(self):
        from cloud_app import app
        with app.test_client() as c:
            self.assertEqual(c.post("/login", data={"password": os.environ["MASTER_CAD_PASSWORD"]}).status_code, 302)
            with c.session_transaction() as s:
                h = {"X-CSRF-Token": s["csrf"]}
            self.assertEqual(c.get("/assiemi").status_code, 200)
            ass = piastre()
            r = c.post("/api/assiemi/proponi", json={"assieme": ass}, headers=h)
            self.assertEqual(r.status_code, 200, r.get_data(as_text=True)[:300])
            prop = r.get_json()["proposte"]
            r = c.post("/api/assiemi/monta", json={"assieme": ass, "montaggi": prop}, headers=h)
            self.assertEqual(r.status_code, 200, r.get_data(as_text=True)[:300])
            j = r.get_json()
            self.assertEqual(c.get(j["glb"]).data[:4], b"glTF")
            self.assertIn("<svg", j["qr"])
            ass["uid"] = "testassieme01"
            self.assertEqual(c.post("/api/assiemi", json={"assieme": ass}, headers=h).status_code, 200)
            self.assertEqual(c.get("/api/assiemi/testassieme01").get_json()["nome"], "Supporto cuscinetto")
            self.assertEqual(c.post("/api/assiemi/proponi", json={"assieme": {"componenti": []}}, headers=h).status_code, 400)


if __name__ == "__main__":
    unittest.main()
