import os
import unittest
from mastercad.geometry import build, validate, mesh_data
from mastercad.interpret import interpret

class CADTests(unittest.TestCase):
    def test_plate_from_italian(self):
        s=interpret("Crea una piastra lunga 120 mm larga 60 mm spessa 5 mm con quattro fori da 8 mm")
        self.assertEqual(len(s["holes"]),4)
        shape,solid,_=build(s)
        self.assertGreater(solid.Volume(),30000)
        self.assertLess(solid.Volume(),36000)
        self.assertTrue(mesh_data(solid)["triangles"])
    def test_cylinder(self):
        s=interpret("Disegna un cilindro diametro 50 mm altezza 30 mm")
        self.assertEqual(s["diameter"],50)
        self.assertGreater(build(s)[1].Volume(),58000)
    def test_bracket(self):
        s=interpret("Staffa a L lunghezza 120 mm larghezza 60 mm spessore 5 mm altezza 45 mm")
        self.assertGreater(build(s)[1].Volume(),60000)
    def test_missing_dimensions(self):
        with self.assertRaisesRegex(ValueError,"Mancano le quote"):
            interpret("Fai una piastra lunga 100")
    def test_hole_outside(self):
        with self.assertRaisesRegex(ValueError,"bordo"):
            validate({"kind":"plate","length":50,"width":40,"thickness":5,"holes":[{"x":24,"y":0,"diameter":8}]})
    def test_reject_invalid_dimension(self):
        with self.assertRaises(ValueError):
            validate({"kind":"cylinder","diameter":float("inf"),"height":10})
    def test_secure_routes(self):
        os.environ["MASTER_CAD_PASSWORD"]="test-password"
        os.environ["FLASK_SECRET_KEY"]="a-test-signing-key-that-is-long-enough"
        os.environ["COOKIE_SECURE"]="0"
        from cloud_app import app
        app.config.update(TESTING=True,SESSION_COOKIE_SECURE=False)
        with app.test_client() as c:
            self.assertEqual(c.get("/health").status_code,200)
            self.assertEqual(c.get("/").status_code,302)
            self.assertEqual(c.get("/api/status").status_code,401)
            self.assertEqual(c.post("/login",data={"password":"wrong"}).status_code,401)
            self.assertEqual(c.post("/login",data={"password":"test-password"}).status_code,302)
            page=c.get("/")
            self.assertEqual(page.status_code,200)
            self.assertIn(b"MASTER",page.data)
            self.assertNotIn(b"/*__CSRF__*/",page.data)
            self.assertEqual(c.post("/api/interpret",json={"text":"Disegna un cilindro diametro 50 altezza 30"}).status_code,403)
            with c.session_transaction() as sess:csrf=sess["csrf"]
            r=c.post("/api/interpret",json={"text":"Disegna un cilindro diametro 50 altezza 30"},headers={"X-CSRF-Token":csrf})
            self.assertEqual(r.status_code,200)
            self.assertEqual(r.json["spec"]["kind"],"cylinder")
            built=c.post("/api/build",json={"spec":r.json["spec"]},headers={"X-CSRF-Token":csrf})
            self.assertEqual(built.status_code,200)
            self.assertTrue(built.json["mesh"]["triangles"])
            self.assertEqual(c.get(built.json["exports"]["step"]).status_code,200)
            self.assertEqual(c.get(built.json["exports"]["stl"]).status_code,200)

if __name__=="__main__":
    unittest.main()
