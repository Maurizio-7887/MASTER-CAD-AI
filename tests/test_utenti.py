"""Utenti personali (primo accesso con cambio password), segnalazioni dall'officina."""
import io
import os
import unittest
import uuid

os.environ.setdefault("MASTER_CAD_PASSWORD", "test-password")
os.environ.setdefault("COOKIE_SECURE", "0")

from cloud_app import app  # noqa: E402
from mastercad import utenti as U  # noqa: E402


def csrf(c):
    with c.session_transaction() as s:
        return {"X-CSRF-Token": s["csrf"]}


class Utenti(unittest.TestCase):
    def setUp(self):
        U._errori.clear()

    def tearDown(self):
        U._errori.clear()

    def admin(self):
        c = app.test_client()
        self.assertEqual(c.post("/login", data={"password": os.environ["MASTER_CAD_PASSWORD"]}).status_code, 302)
        return c

    def test_password_temporanea_e_luca(self):
        p = U.password_temporanea()
        self.assertEqual(len(p), 17)
        self.assertTrue(any(ch.isdigit() for ch in p))
        self.assertTrue(U.UTENTI_INIZIALI[0][3].startswith("pbkdf2:sha256:600000$"), "solo l'hash, mai la password")
        with self.assertRaises(ValueError):
            U.valida_password("corta1A")
        with self.assertRaises(ValueError):
            U.valida_password("tuttominuscole123")
        U.valida_password("Officina-2026")

    def test_ciclo_di_vita(self):
        a = self.admin()
        nome = "t" + uuid.uuid4().hex[:8]
        r = a.post("/api/utenti", json={"username": nome, "nome": "Tecnico prova"}, headers=csrf(a)).get_json()
        pw = r["password"]
        self.assertEqual(a.post("/api/utenti", json={"username": nome, "nome": "x"}, headers=csrf(a)).status_code, 400, "doppione")
        self.assertEqual(a.post("/api/utenti", json={"username": "ADMIN", "nome": "x"}, headers=csrf(a)).status_code, 400)

        t = app.test_client()
        self.assertEqual(t.post("/login", data={"utente": nome, "password": "sbagliata"}).status_code, 401)
        r = t.post("/login", data={"utente": nome.upper(), "password": pw})
        self.assertEqual(r.headers["Location"], "/cambia-password")
        self.assertEqual(t.get("/disegno").headers["Location"], "/cambia-password", "prima si cambia la password")
        self.assertEqual(t.get("/api/officina").status_code, 403)
        tok = csrf(t)["X-CSRF-Token"]
        self.assertEqual(t.post("/cambia-password", data={"attuale": pw, "nuova": "Officina-2026", "ripeti": "Officina-2026"}).status_code, 403, "senza token")
        self.assertEqual(t.post("/cambia-password", data={"csrf": tok, "attuale": pw, "nuova": "debole", "ripeti": "debole"}).status_code, 400)
        r = t.post("/cambia-password", data={"csrf": tok, "attuale": pw, "nuova": "Officina-2026", "ripeti": "Officina-2026"})
        self.assertEqual(r.status_code, 302)
        h = t.get("/")
        self.assertEqual(h.status_code, 200)
        self.assertIn(b'data-utente="Tecnico prova"', h.data)
        self.assertIn(b'id="suggerisci"', h.data)
        self.assertNotIn(b'href="/utenti"', h.data)
        self.assertEqual(t.get("/api/utenti").status_code, 403, "il tecnico non gestisce gli utenti")

        n = app.test_client()
        self.assertEqual(n.post("/login", data={"utente": nome, "password": pw}).status_code, 401, "la temporanea non vale più")
        self.assertEqual(n.post("/login", data={"utente": nome, "password": "Officina-2026"}).headers["Location"], "/")

        self.assertEqual(a.post("/api/utenti/" + nome, json={"azione": "disattiva"}, headers=csrf(a)).status_code, 200)
        self.assertEqual(app.test_client().post("/login", data={"utente": nome, "password": "Officina-2026"}).status_code, 401)
        r = a.post("/api/utenti/" + nome, json={"azione": "reimposta"}, headers=csrf(a)).get_json()
        self.assertEqual(app.test_client().post("/login", data={"utente": nome, "password": r["password"]}).headers["Location"], "/cambia-password")
        self.assertTrue(any(u["username"] == "luca" for u in a.get("/api/utenti").get_json()), "Luca c'è già")

    def test_troppi_tentativi(self):
        c = app.test_client()
        for _ in range(U.TENTATIVI):
            c.post("/login", data={"utente": "nessuno", "password": "x"})
        self.assertEqual(c.post("/login", data={"password": os.environ["MASTER_CAD_PASSWORD"]}).status_code, 429)


class Segnalazioni(unittest.TestCase):
    def test_segnalazione_con_pezzo_e_foto(self):
        U._errori.clear()
        a = app.test_client()
        a.post("/login", data={"password": os.environ["MASTER_CAD_PASSWORD"]})
        nome = "s" + uuid.uuid4().hex[:8]
        pw = a.post("/api/utenti", json={"username": nome, "nome": "Luca prova"}, headers=csrf(a)).get_json()["password"]
        t = app.test_client()
        t.post("/login", data={"utente": nome, "password": pw})
        t.post("/cambia-password", data={"csrf": csrf(t)["X-CSRF-Token"], "attuale": pw, "nuova": "Officina-2026", "ripeti": "Officina-2026"})
        self.assertEqual(t.get("/segnalazioni").status_code, 200)
        png = b"\x89PNG\r\n\x1a\n" + b"0" * 50
        r = t.post("/api/segnalazioni", data={"tipo": "calcolo", "testo": "Le spine da noi sono con foro filettato di estrazione", "pagina": "/assiemi",
                                              "progetto": '{"base": {"tipo": "estrudi"}, "nome": "Piastra"}', "immagine": (io.BytesIO(png), "s.png")},
                   headers=csrf(t), content_type="multipart/form-data")
        self.assertEqual(r.status_code, 200, r.get_data(as_text=True))
        n = r.get_json()["id"]
        self.assertEqual(t.post("/api/segnalazioni", data={"testo": "x"}, headers=csrf(t)).status_code, 400)
        self.assertEqual(t.post("/api/segnalazioni", data={"testo": "foto finta", "immagine": (io.BytesIO(b"GIF89a"), "a.gif")}, headers=csrf(t),
                                content_type="multipart/form-data").status_code, 400)
        mie = t.get("/api/segnalazioni").get_json()
        self.assertTrue(all(s["utente"] == nome for s in mie))
        self.assertEqual(t.get("/api/segnalazioni/%d/immagine" % n).data, png)
        self.assertEqual(t.post("/api/segnalazioni/%d" % n, json={"stato": "fatta"}, headers=csrf(t)).status_code, 403)
        self.assertEqual(a.post("/api/segnalazioni/%d" % n, json={"stato": "in lavorazione", "risposta": "Ottima idea, la facciamo"}, headers=csrf(a)).status_code, 200)
        s = t.get("/api/segnalazioni/%d" % n).get_json()
        self.assertEqual((s["stato"], s["risposta"], s["progetto"]["nome"]), ("in lavorazione", "Ottima idea, la facciamo", "Piastra"))
        self.assertEqual(t.get("/api/segnalazioni/esporta").status_code, 403)
        e = a.get("/api/segnalazioni/esporta")
        self.assertIn(b"foro filettato di estrazione", e.data)


if __name__ == "__main__":
    unittest.main()
