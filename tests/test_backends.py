"""GPU bypass and feature tree tests: entirely CPU and network-free."""
import io
import os
import unittest
from unittest.mock import patch
from mastercad.backends import capability, infer_with_gpu, _safe_worker_url
from mastercad.history import operations

class BackendTests(unittest.TestCase):
    def test_gpu_bypass_offline(self):
        with patch.dict(os.environ,{},clear=True):
            state=capability()
            self.assertEqual(state["active_backend"],"online-cpu")
            self.assertFalse(state["gpu"]["configured"])
            with self.assertRaisesRegex(ValueError,"non configurato"):
                infer_with_gpu(b"image")
    def test_public_https_worker_only(self):
        with patch.dict(os.environ,{"MASTER_CAD_GPU_WORKER_URL":"http://localhost:9000","MASTER_CAD_GPU_WORKER_TOKEN":"t"},clear=True):
            with self.assertRaises(ValueError):_safe_worker_url()
        with patch.dict(os.environ,{"MASTER_CAD_GPU_WORKER_URL":"https://gpu.example.org","MASTER_CAD_GPU_WORKER_TOKEN":"t"},clear=True):
            self.assertEqual(_safe_worker_url(),"https://gpu.example.org/infer")
    def test_feature_history_matches_generated_holes(self):
        data={"kind":"plate","length":120,"width":60,"thickness":5,
              "holes":[{"x":-30,"y":-15,"diameter":8},{"x":30,"y":15,"diameter":8}]}
        history=operations(data)
        self.assertEqual([x["operation"] for x in history["steps"]],
                         ["sketch_rectangle","extrude","pocket_through","pocket_through"])
        self.assertEqual(len(history["steps"]),4)
        self.assertEqual(history["source"],"mastercad-generated")
    def test_gpu_route_disabled_not_fake(self):
        with patch.dict(os.environ,{"MASTER_CAD_PASSWORD":"pw","COOKIE_SECURE":"0"},clear=False):
            os.environ.pop("MASTER_CAD_GPU_WORKER_URL",None)
            os.environ.pop("MASTER_CAD_GPU_WORKER_TOKEN",None)
            from cloud_app import app
            app.config.update(TESTING=True,SESSION_COOKIE_SECURE=False)
            with app.test_client() as c:
                self.assertEqual(c.post("/login",data={"password":"pw"}).status_code,302)
                with c.session_transaction() as sess:csrf=sess["csrf"]
                state=c.get("/api/status")
                self.assertEqual(state.status_code,200)
                self.assertEqual(state.json["backends"]["active_backend"],"online-cpu")
                response=c.post("/api/image/infer-gpu",headers={"X-CSRF-Token":csrf})
                self.assertEqual(response.status_code,503)
                self.assertEqual(response.json["fallback"],"/api/image/inspect")
if __name__=="__main__":unittest.main()
