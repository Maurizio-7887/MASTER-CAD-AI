"""Assiemi con lo scopo: proposte dai fori funzionali, verifiche, collisioni, distinta, albero generato."""
import math
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


class TolleranzeEMontaggio(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.ass = piastre()
        cls.r = M.monta(cls.ass, M.proponi(cls.ass))
        cls.per = {c["nome"]: c for c in cls.r["componenti"]}

    def voci(self, nome):
        return self.per[nome]["tolleranze_geometriche"]["voci"]

    def test_viti_perno_fisso(self):
        from mastercad.assiemi.gdt import arrotonda
        self.assertEqual(arrotonda(0.0081), 0.008)
        sup = next(v for v in self.voci("Supporto") if v["elemento"].startswith("4× passaggio vite"))
        self.assertEqual((sup["valore"], sup["modificatori"], sup["diametrale"]), (0.5, ["M"], True), "T = H − F = 9 − 8, metà per pezzo, al massimo materiale")
        base = next(v for v in self.voci("Piastra base") if v["elemento"].startswith("4× filetto M8"))
        self.assertEqual(base["modificatori"][0], "P", "nel filetto il campo è proiettato")
        self.assertIn("Ø8,5", sup["controllo"], "calibro funzionale: perni Ø(H − t)")

    def test_spine_in_opera(self):
        t = self.per["Supporto"]["tolleranze_geometriche"]
        self.assertEqual(len(t["in_opera"][0]["fori"]), 2)
        self.assertIn("nessuna tolleranza di interasse", t["in_opera"][0]["perche"])
        prog = self.per["Piastra base"]["progetto_tollerato"]
        an = analizza(prog)
        self.assertEqual(sum(1 for f in an["fori"] if f["in_opera"]), 2)
        c = motore.calcola(an, "C45")
        ops = [o["descrizione"] for f in c["fasi"] for o in f["operazioni"]]
        self.assertFalse(any(o.startswith("Alesatura Ø8") for o in ops), "l'alesatura si fa al montaggio")
        self.assertTrue(any("alesatura in opera" in o for o in ops))
        tav = DT.genera(an, {"nome": "Piastra base"})
        self.assertTrue(any("alesatura in opera" in n for n in tav["note"]))
        self.assertTrue(any("[A]" in "".join(p.get("t", "") for p in tav["primitive"] if p["k"] == "tx") for _ in [0]))
        DT.pdf(tav)
        DT.dxf(tav)

    def test_cuscinetto_e_officina(self):
        v = {x["simbolo"]: x for x in self.voci("Supporto") if "sede" in x["elemento"].lower() or "Fondo" in x["elemento"]}
        self.assertEqual(v["cilindricita"]["valore"], 0.008, "IT6/2 su Ø47 = 0,008")
        self.assertEqual(v["oscillazione_totale"]["valore"], 0.015, "IT6 su Ø47 = 0,016 → serie 0,015")
        self.assertFalse(v["cilindricita"]["ok_officina"], "il centro di lavoro predefinito garantisce 0,01")
        alb = {x["simbolo"]: x for x in self.voci("Albero cuscinetto 6204")}
        self.assertEqual(alb["cilindricita"]["valore"], 0.004)
        self.assertIn("rettifica", alb["cilindricita"]["consiglio"])
        self.assertTrue(any(x["voce"].startswith("Precisione officina") for x in self.r["verifiche"]))
        from mastercad.officina import PREDEFINITA
        import copy
        off = copy.deepcopy(PREDEFINITA)
        off["macchine"][0]["precisione"] = 0.005
        r = M.monta(self.ass, M.proponi(self.ass), officina=off)
        sup = next(c for c in r["componenti"] if c["nome"] == "Supporto")
        self.assertTrue(all(x["ok_officina"] for x in sup["tolleranze_geometriche"]["voci"]), "con una macchina più precisa niente avvisi")

    def test_istruzioni(self):
        from mastercad.assiemi.istruzioni import montaggio_cuscinetto, ordine_croce
        self.assertEqual(ordine_croce([(0, 0), (10, 0), (10, 10), (0, 10)]), [0, 2, 1, 3], "a croce: diagonali")
        self.assertEqual(len(set(ordine_croce([(math.cos(a), math.sin(a)) for a in range(5)]))), 5)
        mc = montaggio_cuscinetto(20, 21)
        self.assertEqual((mc["metodo"], mc["caldo"]["delta"]), ("pressa", 88), "21 µm / (12e-6 × 20) = 87,5 K")
        ist = self.r["istruzioni"]
        titoli = [p["titolo"] for p in ist["passi"]]
        self.assertLess(titoli.index("Serra le viti"), titoli.index("Alesa in opera i fori spina"))
        self.assertLess(titoli.index("Alesa in opera i fori spina"), titoli.index("Pianta le spine"))
        serr = next(p for p in ist["passi"] if p["titolo"] == "Serra le viti")
        self.assertTrue(any("24,6 N·m" in a for a in serr["azioni"]), "M8 8.8 μ 0,12")
        self.assertEqual(titoli[-1], "Controlli finali")
        self.assertAlmostEqual(ist["costo"], ist["tempo_min"] / 60 * 32, places=2)


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
            self.assertTrue(j["istruzioni"]["passi"][0]["glb"])
            tok = j["montaggio"]["token"]
            with app.test_client() as anonimo:                    # il telefono del montatore non ha fatto login
                self.assertEqual(anonimo.get("/assiemi/m/" + tok).status_code, 200)
                d = anonimo.get("/assiemi/m/%s/dati" % tok).get_json()
                self.assertEqual(len(d["istruzioni"]["passi"]), len(j["istruzioni"]["passi"]))
                self.assertEqual(anonimo.get(d["istruzioni"]["passi"][1]["glb"]).data[:4], b"glTF")
                self.assertEqual(anonimo.post("/assiemi/m/%s/conferma" % tok, json={"passo": 1, "operatore": ""}).status_code, 400)
                r = anonimo.post("/assiemi/m/%s/conferma" % tok, json={"passo": 1, "operatore": "Mario", "esito": "ok"})
                self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
                self.assertEqual(anonimo.post("/assiemi/m/%s/conferma" % tok, json={"passo": 99, "operatore": "Mario"}).status_code, 400)
                self.assertEqual(anonimo.get("/assiemi/m/" + "0" * 32).status_code, 404)
                self.assertEqual(anonimo.get("/api/assiemi/montaggio/" + tok).status_code, 401, "l'avanzamento in ufficio richiede il login")
            self.assertEqual(c.get("/api/assiemi/montaggio/" + tok).get_json()["conferme"][0]["operatore"], "Mario")
            ass["uid"] = "testassieme01"
            self.assertEqual(c.post("/api/assiemi", json={"assieme": ass}, headers=h).status_code, 200)
            self.assertEqual(c.get("/api/assiemi/testassieme01").get_json()["nome"], "Supporto cuscinetto")
            self.assertEqual(c.post("/api/assiemi/proponi", json={"assieme": {"componenti": []}}, headers=h).status_code, 400)


if __name__ == "__main__":
    unittest.main()
