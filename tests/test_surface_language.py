"""Regression tests for primary-surface language cleanup — the review,
progress, and fleet pages should read as product surfaces, not debug logs.

Scope note: raw internal identifiers embedded in the review page's JSON
payload (<script type="application/json">) and in the labeled evidence
list (class="rr-finding-evidence") are out of scope here — those are
explicitly technical/audit areas, not narrative prose a reader encounters
by default. This file checks the parts a person actually reads.
"""
from __future__ import annotations

from fastapi.testclient import TestClient

from repairgraph.api.app import app

client = TestClient(app)

V = "?oem=Honda&year=2025&model=Accord"


def _visible_html(resp) -> str:
    """Strip the embedded JSON payload script tag, if present, leaving
    only what a reader actually sees."""
    text = resp.text
    marker = '<script type="application/json"'
    idx = text.find(marker)
    return text[:idx] if idx != -1 else text


class TestProgressPageStatusLabelsAreHumanized:
    def test_no_raw_underscored_status_in_badges(self):
        resp = client.get(f"/internal/review/progress/ui{V}")
        visible = _visible_html(resp)
        import re
        badge_texts = re.findall(r'class="badge \S+">([^<]*)</span>', visible)
        assert badge_texts, "expected at least one badge on the progress page"
        for text in badge_texts:
            assert "_" not in text, f"raw enum leaked into badge text: {text!r}"

    def test_not_started_reads_as_title_case(self):
        resp = client.get(f"/internal/review/progress/ui{V}")
        visible = _visible_html(resp)
        assert "Not Started" in visible
        assert ">not_started<" not in visible

    def test_session_status_is_humanized(self):
        resp = client.get(f"/internal/review/progress/ui{V}")
        visible = _visible_html(resp)
        assert "Session" in visible
        assert ">not_started<" not in visible


class TestReviewPageBlockerNarrativeIsHumanized:
    def test_no_raw_phase_colon_token_in_narrative_text(self):
        resp = client.get(f"/internal/review{V}")
        visible = _visible_html(resp)
        # The old bug: "is preventing progress on: session_completion, phase:4"
        assert "preventing progress on: session_completion" not in visible
        assert "preventing progress on: phase:" not in visible

    def test_phase_token_reads_as_title_case_when_present(self):
        resp = client.get(f"/internal/review{V}")
        visible = _visible_html(resp)
        if "preventing progress on:" in visible:
            idx = visible.find("preventing progress on:")
            snippet = visible[idx:idx + 120]
            assert "Phase " in snippet or "session completion" in snippet


class TestReviewPageDoesNotShowInternalFilenames:
    def test_fixture_vehicle_does_not_show_internal_json_filename(self):
        resp = client.get(f"/internal/review{V}")
        assert "repair_procedure_quarter_panel.json" not in resp.text

    def test_fixture_vehicle_shows_a_readable_document_label(self):
        resp = client.get(f"/internal/review{V}")
        assert "Honda Accord" in resp.text
        assert "OEM Reference" in resp.text


class TestFleetPageStatusLabelsAreHumanized:
    def test_no_raw_underscored_status_in_stat_labels(self):
        resp = client.get("/internal/fleet/ui")
        visible = _visible_html(resp)
        import re
        labels = re.findall(r'<span>([^<]+)</span>', visible)
        status_labels = [l for l in labels if l not in ("open QA gates", "open blockers")]
        for label in labels:
            if "_" in label:
                raise AssertionError(f"raw enum leaked into fleet label: {label!r}")

    def test_in_progress_reads_as_title_case(self):
        resp = client.get("/internal/fleet/ui")
        visible = _visible_html(resp)
        assert "In Progress" in visible
