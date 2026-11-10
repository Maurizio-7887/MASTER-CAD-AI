"""Regression checks for logout and expired sessions with PostgreSQL-connected CAD."""
import os
import unittest
from cloud_app import app

class SessionTests(unittest.TestCase):
    def setUp(self):
        os.environ["MASTER_CAD_PASSWORD"]="test-password"
        app.config.update(TESTING=True,SESSION_COOKIE_SECURE=False)
        self.client=app.test_client()

    def sign_in(self):
        response=self.client.post("/login",data={"password":"test-password"})
        self.assertEqual(response.status_code,302)
        with self.client.session_transaction() as sess:
            self.assertTrue(sess.permanent)
            return sess["csrf"]

    def test_logout_requires_auth_and_csrf(self):
        self.assertEqual(self.client.post("/logout").status_code,302)
        csrf=self.sign_in()
        self.assertEqual(self.client.get("/").status_code,200)
        self.assertIn(b'id="esci"',self.client.get("/").data)
        self.assertIn(b'id="logout"',self.client.get("/parla").data)
        self.assertEqual(self.client.post("/logout").status_code,403)
        response=self.client.post("/logout",headers={"X-CSRF-Token":csrf})
        self.assertEqual(response.status_code,200)
        self.assertTrue(response.json["ok"])
        self.assertEqual(self.client.get("/").status_code,302)
        self.assertEqual(self.client.get("/api/status").status_code,401)

    def test_stale_editor_session_is_unauthorized(self):
        self.sign_in()
        with self.client.session_transaction() as sess:
            sess.clear()
        response=self.client.post("/api/interpret",json={"text":"piastra lunghezza 120 larghezza 60 spessore 5"})
        self.assertEqual(response.status_code,401)
        self.assertEqual(response.json["error"],"Accesso richiesto")
        self.assertEqual(self.client.get("/").status_code,302)
        login=self.client.get("/login?expired=1")
        self.assertEqual(login.status_code,200)
        self.assertIn("Sessione scaduta".encode(),login.data)

if __name__=="__main__":unittest.main()
