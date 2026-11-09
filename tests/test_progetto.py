"""Progetto complesso: albero delle lavorazioni, due viste, indicazioni del tecnico in italiano."""
import math
import os
import unittest

from mastercad.progetto import direttive as D
from mastercad.progetto import lavorazioni as L

os.environ.setdefault("MASTER_CAD_PASSWORD", "test-password")
os.environ.setdefault("COOKIE_SECURE", "0")


def flangia_da_foto():
    """Come esce dalla foto: misure un po' sbagliate, fori un po' fuori posto."""
    ents = [{"t": "circle", "c": [0, 0], "r": 49.65}, {"t": "circle", "c": [0.2, -0.1], "r": 14.8}]
    for k in range(4):
        a = math.radians(45 + 90 * k)
        ents.append({"t": "circle", "c": [35.2 * math.cos(a), 34.9 * math.sin(a)], "r": 4.15})
    return ents


def piastra():
    return [{"t": "pline", "pts": [[0, 0], [160, 0], [160, 100], [0, 100]], "closed": True}]


class Albero(unittest.TestCase):
    def test_piastra_complessa_tutte_le_lavorazioni(self):
        prog = {"base": {"tipo": "estrudi", "entita": piastra(), "altezza": 20}, "lavorazioni": [
            {"tipo": "rialzo", "forma": "cerchio", "centro": [80, 50], "d": 50, "h": 10},
            {"tipo": "tasca", "forma": "rett", "centro": [25, 50], "l": 30, "w": 60, "prof": 8, "raggio_angoli": 4},
            {"tipo": "asola", "centro": [135, 50], "lunghezza": 40, "larghezza": 10, "angolo": 90},
            {"tipo": "foro", "x": 80, "y": 50, "d": 20, "lamatura": {"d": 32, "prof": 6}},
            {"tipo": "serie_polare", "centro": [80, 50], "diametro": 36, "n": 6, "foro": {"filetto": "M5", "prof": 10}},
            {"tipo": "serie_rett", "origine": [10, 10], "nx": 2, "ny": 2, "passo_x": 140, "passo_y": 80, "foro": {"d": 6.6, "svasatura": {"d": 13}}},
            {"tipo": "raccordo", "r": 5, "spigoli": "verticali"},
            {"tipo": "smusso", "d": 1, "spigoli": "inferiori"},
            {"tipo": "foro", "x": 500, "y": 500, "d": 5},
            {"tipo": "foro", "x": 40, "y": 40, "d": 5, "sospesa": True},
        ]}
        _, s, storia = L.costruisci(prog)
        self.assertTrue(s.isValid())
        ok = [x["ok"] for x in storia]
        self.assertEqual(ok, [True] * 9 + [False, True], storia)
        self.assertIn("non tocca il pezzo", storia[9]["dettaglio"])
        self.assertTrue(storia[10].get("sospesa"))
        self.assertAlmostEqual(s.BoundingBox().zlen, 30, delta=0.01)
        self.assertLess(s.Volume(), 160 * 100 * 20 + math.pi * 625 * 10)

    def test_fori_sul_rialzo_partono_dal_rialzo(self):
        base = {"tipo": "estrudi", "entita": piastra(), "altezza": 10}
        rialzo = {"tipo": "rialzo", "forma": "cerchio", "centro": [80, 50], "d": 40, "h": 10}
        _, s0, _ = L.costruisci({"base": base, "lavorazioni": [rialzo]})
        _, s1, _ = L.costruisci({"base": base, "lavorazioni": [rialzo, {"tipo": "foro", "x": 80, "y": 50, "d": 10, "prof": 5}, {"tipo": "foro", "x": 20, "y": 20, "d": 10, "prof": 5}]})
        cilindri = 2 * math.pi * 25 * 5
        punte = 2 * math.pi * 25 * (5 / math.tan(math.radians(59))) / 3
        self.assertAlmostEqual(s0.Volume() - s1.Volume(), cilindri + punte, delta=2)

    def test_due_viste_staffa_a_L(self):
        alto = [{"t": "pline", "pts": [[0, 0], [80, 0], [80, 40], [0, 40]], "closed": True}, {"t": "circle", "c": [50, 20], "r": 4}]
        fronte = [{"t": "pline", "pts": [[100, 0], [180, 0], [180, 8], [108, 8], [108, 50], [100, 50]], "closed": True}]
        p = D.da_disegno(fronte, "fronte", D.da_disegno(alto, "alto", {}))
        self.assertEqual(p["base"]["fronte"][0]["pts"][0], [0.0, 0.0], "vista di fronte allineata alla vista dall'alto")
        _, s, storia = L.costruisci(p)
        self.assertAlmostEqual(s.Volume(), (80 * 8 + 8 * 42) * 40 - math.pi * 16 * 8, delta=1)
        self.assertTrue(all(x["ok"] for x in storia))


class Direttive(unittest.TestCase):
    def test_tecnico_corregge_la_foto(self):
        p = D.da_foto(flangia_da_foto(), 10)
        self.assertEqual(len(p["lavorazioni"]), 5)
        r = D.applica("diametro esterno 100; spessore 15, foro centrale Ø30 H7 con lamatura Ø40 profonda 5, "
                      "4 fori M8 passanti lamati su interasse 70; foro M6 filettato profondo 12 in 0,40; "
                      "asola 30x8 verticale in -40,0; rialzo Ø60 alto 5; raccordo R1 spigoli superiori; smusso 0.5 bordi inferiori; colore rosso", p)
        self.assertEqual(r["non_capito"], ["colore rosso"])
        prog = r["progetto"]
        tipi = [l["tipo"] for l in prog["lavorazioni"]]
        self.assertEqual(tipi, ["rialzo", "asola", "foro", "serie_polare", "foro", "raccordo", "smusso"], "ordine di officina")
        centrale = prog["lavorazioni"][2]
        self.assertEqual((centrale["x"], centrale["y"], centrale["d"], centrale.get("prof")), (0.0, 0.0, 30.0, None))
        self.assertEqual(centrale["lamatura"], {"d": 40.0, "prof": 5.0})
        serie = prog["lavorazioni"][3]
        self.assertEqual((serie["n"], serie["diametro"], serie["angolo0"], serie["foro"]["d"]), (4, 70.0, 45, 9.0))
        self.assertEqual(serie["foro"]["lamatura"], {"d": 15.0, "prof": 8.6})
        self.assertEqual(prog["lavorazioni"][4]["filetto"], "M6")
        self.assertAlmostEqual(D._ingombro(prog)[2] - D._ingombro(prog)[0], 100, delta=1e-6)
        _, s, storia = L.costruisci(prog)
        self.assertTrue(all(x["ok"] for x in storia), storia)
        self.assertTrue(s.isValid())

    def test_tasca_serie_rett_guscio_e_non_capito(self):
        p = {"base": {"tipo": "estrudi", "entita": piastra(), "altezza": 30}, "lavorazioni": []}
        r = D.applica("tasca 40x20 profonda 6 in 30,50 raggio 4\n2x2 fori Ø6 passo 120x60\nguscio spessore 3 aperto sotto\nlunghezza 200\nbla bla", p)
        lavs = r["progetto"]["lavorazioni"]
        self.assertEqual([l["tipo"] for l in lavs], ["tasca", "serie_rett", "guscio"])
        self.assertEqual(lavs[0]["raggio_angoli"], 4)
        self.assertEqual(lavs[1]["origine"], [20.0, 20.0])
        self.assertEqual(r["non_capito"], ["bla bla"])
        self.assertAlmostEqual(D._ingombro(r["progetto"])[2], 200, delta=1e-6)
        r = D.applica("foro Ø10 in 10,-5 dal centro", p)
        self.assertEqual((r["progetto"]["lavorazioni"][0]["x"], r["progetto"]["lavorazioni"][0]["y"]), (90.0, 45.0))

    def test_ridisegnare_non_doppia_i_fori_del_tecnico(self):
        p = D.da_disegno(flangia_da_foto(), "estrudi", {}, altezza=12)
        r = D.applica("i 4 fori M6 filettati", p)
        p2 = D.da_disegno(flangia_da_foto(), "estrudi", r["progetto"], altezza=12)
        self.assertEqual(len([l for l in p2["lavorazioni"] if l["tipo"] == "foro"]), 5)
        self.assertEqual(sum(1 for l in p2["lavorazioni"] if l.get("filetto") == "M6"), 4)


class Http(unittest.TestCase):
    def test_endpoint_progetto(self):
        from cloud_app import app
        with app.test_client() as c:
            self.assertEqual(c.post("/login", data={"password": os.environ["MASTER_CAD_PASSWORD"]}).status_code, 302)
            with c.session_transaction() as sess:
                csrf = sess["csrf"]
            h = {"X-CSRF-Token": csrf}
            self.assertIn("prog-direttive", c.get("/disegno").get_data(as_text=True))
            r = c.post("/api/progetto/da-disegno", json={"come": "estrudi", "entita": flangia_da_foto(), "altezza": 12}, headers=h)
            self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
            r = c.post("/api/progetto/direttive", json={"testo": "4 fori M8 su interasse 70", "progetto": r.get_json()["progetto"]}, headers=h)
            self.assertEqual(r.status_code, 200)
            prog = r.get_json()["progetto"]
            r = c.post("/api/progetto/costruisci", json={"progetto": prog, "nome": "Flangia"}, headers=h)
            self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
            j = r.get_json()
            self.assertEqual(j["saltate"], 0)
            self.assertTrue(j["mesh"]["triangles"])
            self.assertEqual(c.get(j["exports"]["step"]).status_code, 200)
            self.assertEqual(c.post("/api/progetto/costruisci", json={"progetto": {}}, headers=h).status_code, 400)


if __name__ == "__main__":
    unittest.main()
