"""Disegno come AutoCAD (profili 2D → ESTRUDI / RIVOLUZIONE) e reverse engineering da foto."""
import io
import math
import os
import unittest

import cv2
import numpy as np

from mastercad import profili
from mastercad.reverse.foto import ricostruisci

os.environ.setdefault("MASTER_CAD_PASSWORD", "test-password")
os.environ.setdefault("COOKIE_SECURE", "0")


def piastra_con_raccordo():
    return [{"t": "line", "a": [0, 0], "b": [100, 0]}, {"t": "line", "a": [100, 0], "b": [100, 50]},
            {"t": "arc", "c": [90, 50], "r": 10, "a0": 0, "a1": 90}, {"t": "line", "a": [90, 60], "b": [0, 60]},
            {"t": "line", "a": [0, 60], "b": [0, 0]}, {"t": "circle", "c": [20, 30], "r": 5},
            {"t": "pline", "pts": [[40, 20], [60, 20], [60, 40], [40, 40]], "closed": True}]


def png(img):
    ok, b = cv2.imencode(".png", img)
    return b.tobytes()


class Profili(unittest.TestCase):
    def test_estrudi_contorno_con_arco_e_fori(self):
        _, solido, info = profili.estrudi(piastra_con_raccordo(), 8)
        atteso = (100 * 60 - (100 - math.pi * 25) - math.pi * 25 - 400) * 8
        self.assertAlmostEqual(solido.Volume(), atteso, delta=1)
        self.assertEqual((info["regioni"], info["fori"]), (1, 2))

    def test_rivoluzione_perno(self):
        mezza = [{"t": "pline", "pts": [[0, 0], [50, 0], [50, 10], [30, 10], [30, 15], [0, 15]], "closed": True}]
        _, solido, _ = profili.rivoluzione(mezza, [0, 0], [1, 0])
        self.assertAlmostEqual(solido.Volume(), math.pi * (100 * 20 + 225 * 30), delta=1)

    def test_errori_chiari(self):
        with self.assertRaisesRegex(ValueError, "estremo aperto"):
            profili.estrudi([{"t": "line", "a": [0, 0], "b": [10, 0]}, {"t": "line", "a": [10, 0], "b": [10, 10]}], 5)
        with self.assertRaisesRegex(ValueError, "attraversa l'asse"):
            profili.rivoluzione([{"t": "pline", "pts": [[0, -5], [10, -5], [10, 5], [0, 5]], "closed": True}], [0, 0], [1, 0])


class Foto(unittest.TestCase):
    def test_piastra_dall_alto_con_misura(self):
        img = np.full((700, 900, 3), 235, np.uint8)
        cv2.rectangle(img, (150, 150), (750, 550), (40, 40, 40), -1)
        cv2.circle(img, (250, 350), 50, (235, 235, 235), -1)
        cv2.circle(img, (650, 350), 50, (235, 235, 235), -1)
        r = ricostruisci(png(img), "alto", "misura", 120, "larghezza")
        self.assertEqual(r["info"]["fori"], 2)
        cerchi = [e for e in r["entita"] if e["t"] == "circle"]
        self.assertEqual(len(cerchi), 2)
        self.assertAlmostEqual(cerchi[0]["r"], 10, delta=0.4)
        self.assertAlmostEqual(r["info"]["altezza_mm"], 80, delta=0.6)
        _, solido, _ = profili.estrudi(r["entita"], 10)
        self.assertAlmostEqual(solido.Volume(), (120 * 80 - 2 * math.pi * 100) * 10, delta=1500)

    def test_flangia_su_foglio_a4_in_prospettiva(self):
        W, H = 1188, 840
        foglio = np.full((H, W, 3), 245, np.uint8)
        cv2.circle(foglio, (594, 420), 200, (30, 30, 30), -1)
        cv2.circle(foglio, (594, 420), 60, (245, 245, 245), -1)
        for k in range(4):
            a = k * math.pi / 2
            cv2.circle(foglio, (int(594 + 140 * math.cos(a)), int(420 + 140 * math.sin(a))), 16, (245, 245, 245), -1)
        foto = np.full((1200, 1600, 3), 60, np.uint8)
        M = cv2.getPerspectiveTransform(np.float32([[0, 0], [W, 0], [W, H], [0, H]]), np.float32([[220, 180], [1400, 240], [1350, 1050], [260, 1000]]))
        cv2.warpPerspective(foglio, M, (1600, 1200), dst=foto, borderMode=cv2.BORDER_TRANSPARENT)
        r = ricostruisci(png(foto), "alto", "a4")
        raggi = sorted(e["r"] for e in r["entita"] if e["t"] == "circle")
        self.assertAlmostEqual(raggi[-1], 50, delta=1)      # diametro esterno 100 mm
        self.assertAlmostEqual(raggi[-2], 15, delta=0.8)    # foro centrale 30 mm
        self.assertEqual(len(raggi), 6)

    def test_perno_di_lato(self):
        img = np.full((400, 900, 3), 240, np.uint8)
        cv2.rectangle(img, (100, 150), (500, 250), (30, 30, 30), -1)
        cv2.rectangle(img, (500, 170), (800, 230), (30, 30, 30), -1)
        r = ricostruisci(png(img), "lato", "misura", 70, "larghezza")
        self.assertAlmostEqual(r["info"]["diametro_max_mm"], 10, delta=0.3)
        _, solido, _ = profili.rivoluzione(r["entita"], [0, 0], [1, 0])
        self.assertAlmostEqual(solido.Volume(), math.pi * (25 * 40 + 9 * 30), delta=60)

    def test_foto_senza_pezzo(self):
        with self.assertRaisesRegex(ValueError, "Non distinguo il pezzo"):
            ricostruisci(png(np.full((300, 300, 3), 200, np.uint8)), "alto", "misura", 50)


class Http(unittest.TestCase):
    def test_pagina_solido_e_foto(self):
        from cloud_app import app
        with app.test_client() as c:
            self.assertEqual(c.post("/login", data={"password": os.environ["MASTER_CAD_PASSWORD"]}).status_code, 302)
            with c.session_transaction() as sess:
                csrf = sess["csrf"]
            pagina = c.get("/disegno").get_data(as_text=True)
            self.assertIn("riga di comando".lower(), pagina.lower())
            self.assertIn("comandi.js", pagina)
            self.assertEqual(c.get("/disegno/static/comandi.js").status_code, 200)
            r = c.post("/api/disegno/solido", json={"op": "estrudi", "entita": piastra_con_raccordo(), "altezza": 8}, headers={"X-CSRF-Token": csrf})
            self.assertEqual(r.status_code, 200, r.json)
            self.assertTrue(r.json["mesh"]["triangles"])
            self.assertEqual(c.get(r.json["exports"]["step"]).status_code, 200)
            r = c.post("/api/disegno/solido", json={"op": "estrudi", "entita": [{"t": "line", "a": [0, 0], "b": [1, 0]}], "altezza": 8}, headers={"X-CSRF-Token": csrf})
            self.assertEqual(r.status_code, 400)
            img = np.full((500, 700, 3), 235, np.uint8)
            cv2.rectangle(img, (100, 100), (600, 400), (40, 40, 40), -1)
            r = c.post("/api/reverse/foto", data={"image": (io.BytesIO(png(img)), "pezzo.png"), "vista": "alto", "riferimento": "misura", "misura": "100"},
                       headers={"X-CSRF-Token": csrf}, content_type="multipart/form-data")
            self.assertEqual(r.status_code, 200, r.json)
            self.assertAlmostEqual(r.json["info"]["altezza_mm"], 60, delta=0.5)
            self.assertTrue(r.json["anteprima"].startswith("data:image/jpeg"))


if __name__ == "__main__":
    unittest.main()
