"""Regression tests for safe image-to-dimension extraction.

OCR emits only dimension candidates; no invented shape or certified geometry.
"""
import io
import os
import unittest
from unittest.mock import patch, Mock
from PIL import Image
from mastercad.image_quotes import scan_dimensions, inspect_image

class ImageOCRTests(unittest.TestCase):
    def test_recognizes_labeled_dimensions(self):
        got=scan_dimensions("Lunghezza 120 mm\nLarghezza 80 mm\nSpessore 5 mm\nØ 8")
        fields={x["field"]:x["value_mm"] for x in got}
        self.assertEqual(fields["length"],120)
        self.assertEqual(fields["width"],80)
        self.assertEqual(fields["thickness"],5)
        self.assertEqual(fields["diameter"],8)
        self.assertTrue(all(x["verified"] is False for x in got))

    def test_recognizes_drawing_notation(self):
        got=scan_dimensions("120 x 80 x 5 mm")
        self.assertEqual([x["value_mm"] for x in got],[120,80,5])

    def test_rejects_invalid_files(self):
        with self.assertRaisesRegex(ValueError,"non valida"):
            inspect_image(b"not an image")
        with self.assertRaisesRegex(ValueError,"massimo 4 MB"):
            inspect_image(b"x"*4000001)

    @patch("mastercad.image_quotes.subprocess.run")
    def test_ocr_explicitly_requires_confirmation(self,run):
        run.return_value=Mock(returncode=0,stdout=b"Length 120 mm Width 60 mm Thickness 5 mm")
        img=Image.new("RGB",(100,50),"white")
        stream=io.BytesIO()
        img.save(stream,format="PNG")
        got=inspect_image(stream.getvalue())
        self.assertEqual(len(got["dimensions"]),3)
        self.assertFalse(got["geometry_inferred"])
        self.assertTrue(got["requires_manual_confirmation"])
        self.assertEqual(run.call_args.args[0][0],"tesseract")

    def test_authenticated_endpoint(self):
        os.environ["MASTER_CAD_PASSWORD"]="test-password"
        os.environ["FLASK_SECRET_KEY"]="test-signing-key-long"
        os.environ["COOKIE_SECURE"]="0"
        from cloud_app import app
        app.config.update(TESTING=True,SESSION_COOKIE_SECURE=False)
        with app.test_client() as client:
            self.assertEqual(client.post("/api/image/inspect").status_code,401)
            self.assertEqual(client.post("/login",data={"password":"test-password"}).status_code,302)
            with client.session_transaction() as sess:csrf=sess["csrf"]
            self.assertEqual(client.post("/api/image/inspect").status_code,403)
            with patch("cloud_app.inspect_image",return_value={"text":"120x80x5","dimensions":[],"geometry_inferred":False,"requires_manual_confirmation":True}):
                res=client.post("/api/image/inspect",data={"image":(io.BytesIO(b"test"),"drawing.png")},headers={"X-CSRF-Token":csrf})
                self.assertEqual(res.status_code,200)
                self.assertFalse(res.json["geometry_inferred"])

if __name__=="__main__":
    unittest.main()
