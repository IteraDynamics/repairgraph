"""Failure-mode coverage for intake: what happens when a real evaluator
uploads something the pipeline can't cleanly classify.

None of these should crash the endpoint, silently misclassify content as
an OEM procedure it isn't, or leave the reviewer looking at unexplained
demo data (that last part is covered end-to-end by combining this with the
demo-notice fix — see TestUnrelatedDocumentEndToEnd below and
test_demo_notice.py).
"""
from __future__ import annotations

import io
import os

from fastapi.testclient import TestClient

from repairgraph.api.app import app
from repairgraph.core.vehicle_store import clear_active_vehicle

client = TestClient(app)


def _upload(filename: str, content: bytes, content_type: str = "text/plain"):
    clear_active_vehicle()
    return client.post(
        "/internal/intake/classify",
        files={"files": (filename, io.BytesIO(content), content_type)},
    )


class TestEmptyFile:
    def test_returns_200(self):
        resp = _upload("empty.txt", b"")
        assert resp.status_code == 200

    def test_flags_readiness_incomplete(self):
        resp = _upload("empty.txt", b"")
        assert resp.json()["readiness"] == "incomplete"

    def test_warns_file_is_empty(self):
        resp = _upload("empty.txt", b"")
        warnings = resp.json()["files"][0]["warnings"]
        assert any("empty" in w.lower() for w in warnings)

    def test_does_not_set_active_vehicle(self):
        _upload("empty.txt", b"")
        resp = client.get("/internal/review/vehicles")
        assert resp.json()["active_vehicle"] is None


class TestImageOnlyPDFNoTextLayer:
    """A structurally valid PDF with no extractable text (as a scanned
    image-only PDF would look to pdftotext)."""

    PDF_NO_TEXT = (
        b"%PDF-1.4\n"
        b"1 0 obj<</Type/Catalog/Pages 2 0 R>>endobj\n"
        b"2 0 obj<</Type/Pages/Kids[3 0 R]/Count 1>>endobj\n"
        b"3 0 obj<</Type/Page/Parent 2 0 R/MediaBox[0 0 200 200]>>endobj\n"
        b"xref\n0 4\n0000000000 65535 f \n"
        b"trailer<</Size 4/Root 1 0 R>>\nstartxref\n0\n%%EOF"
    )

    def test_returns_200(self):
        resp = _upload("scanned.pdf", self.PDF_NO_TEXT, "application/pdf")
        assert resp.status_code == 200

    def test_does_not_crash_and_reports_low_confidence(self):
        resp = _upload("scanned.pdf", self.PDF_NO_TEXT, "application/pdf")
        f = resp.json()["files"][0]
        assert f["confidence"] == 0.0
        assert f["document_role"] == "unknown"

    def test_does_not_fabricate_oem_detection(self):
        resp = _upload("scanned.pdf", self.PDF_NO_TEXT, "application/pdf")
        assert resp.json()["detected_packet"]["detected_oem"] is None


class TestUnrelatedDocument:
    """A real, readable text document with nothing to do with OEM repair
    procedures — must not be falsely classified as one."""

    RECIPE = (
        b"Chocolate Chip Cookie Recipe\n\n"
        b"Ingredients: 2 cups flour, 1 cup butter, 1 cup sugar, 2 eggs, chocolate chips.\n"
        b"Preheat oven to 375F. Mix ingredients. Bake for 10 minutes until golden brown."
    )

    def test_returns_200(self):
        resp = _upload("recipe.txt", self.RECIPE)
        assert resp.status_code == 200

    def test_no_oem_falsely_detected(self):
        resp = _upload("recipe.txt", self.RECIPE)
        assert resp.json()["detected_packet"]["detected_oem"] is None

    def test_role_is_unknown_not_guessed(self):
        resp = _upload("recipe.txt", self.RECIPE)
        assert resp.json()["files"][0]["document_role"] == "unknown"

    def test_readiness_reflects_no_usable_content(self):
        resp = _upload("recipe.txt", self.RECIPE)
        assert resp.json()["readiness"] == "incomplete"

    def test_does_not_set_active_vehicle(self):
        _upload("recipe.txt", self.RECIPE)
        resp = client.get("/internal/review/vehicles")
        assert resp.json()["active_vehicle"] is None


class TestRandomBinaryContent:
    """Arbitrary bytes with a .txt extension — must never crash the parser."""

    def test_returns_200_not_500(self):
        resp = _upload("garbage.txt", os.urandom(5000))
        assert resp.status_code == 200


class TestControlCharactersAndUnicodeNoise:
    """OEM-recognizable content interspersed with null bytes and zero-width
    unicode — classification should still work despite the noise."""

    def test_still_detects_real_content_through_noise(self):
        noisy = (
            "2025 Honda Accord Quarter Panel \x00\x01\x02 Replacement spot weld "
            + ("​" * 50) + " seam sealer"
        ).encode("utf-8")
        resp = _upload("noisy.txt", noisy)
        assert resp.status_code == 200
        pkt = resp.json()["detected_packet"]
        assert pkt["detected_oem"] == "Honda"
        assert pkt["detected_model"] == "Accord"


class TestUnrelatedDocumentEndToEnd:
    """The full path an evaluator would actually take: upload something
    that doesn't classify, then look at the review page. It must read as
    an honest 'this isn't your data' rather than silently rendering
    unrelated demo results."""

    def test_review_after_irrelevant_upload_shows_demo_notice(self):
        _upload("recipe.txt", TestUnrelatedDocument.RECIPE)
        resp = client.get("/internal/review")
        assert '<div class="rr-demo-notice' in resp.text
        assert "not data you uploaded" in resp.text.lower()
