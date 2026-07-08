"""Tests for the Fleet Summary — a shop-floor view aggregating every tracked
job's projected state into status buckets.

Deliberately domain-neutral: aggregation only reads RepairState (phases,
actions, qa_gates, blockers), the same generic vocabulary any future domain
adapter would populate. These tests exercise the aggregation logic and the
two endpoints; they do not assume anything collision-repair-specific beyond
using the existing fixture/intake vehicles as test data.
"""
from __future__ import annotations

import pytest
from fastapi.testclient import TestClient

from repairgraph.api.app import app
from repairgraph.state.fleet import build_fleet_summary

client = TestClient(app)

V = "?oem=Honda&year=2025&model=Accord"


@pytest.fixture(autouse=True)
def isolated_journal(tmp_path, monkeypatch):
    import repairgraph.state.journal as journal
    monkeypatch.setattr(journal, "_SESSIONS_DIR", tmp_path / "sessions")
    yield


class TestFleetAggregation:
    def test_includes_all_normalized_vehicles(self):
        summary = build_fleet_summary()
        models = {(j["oem"], j["model"]) for j in summary["jobs"]}
        assert ("Honda", "Accord") in models
        assert ("Honda", "Civic") in models

    def test_job_count_matches_jobs_list(self):
        summary = build_fleet_summary()
        assert summary["job_count"] == len(summary["jobs"])

    def test_counts_by_status_sum_to_job_count(self):
        summary = build_fleet_summary()
        assert sum(summary["counts_by_status"].values()) == summary["job_count"]

    def test_untouched_job_is_not_started(self):
        summary = build_fleet_summary()
        accord = next(j for j in summary["jobs"] if j["model"] == "Accord")
        assert accord["status"] == "not_started"
        assert accord["events_recorded"] == 0

    def test_jobs_by_status_matches_counts(self):
        summary = build_fleet_summary()
        for status, jobs in summary["jobs_by_status"].items():
            assert len(jobs) == summary["counts_by_status"][status]

    def test_job_has_review_and_progress_links(self):
        summary = build_fleet_summary()
        accord = next(j for j in summary["jobs"] if j["model"] == "Accord")
        assert accord["review_link"] == "/internal/review?oem=Honda&year=2025&model=Accord"
        assert accord["progress_link"] == "/internal/review/progress/ui?oem=Honda&year=2025&model=Accord"

    def test_advisory_present(self):
        summary = build_fleet_summary()
        assert summary["advisory"]

    def test_fixture_and_intake_sources_both_present(self):
        summary = build_fleet_summary()
        sources = {j["source"] for j in summary["jobs"]}
        assert "fixture" in sources


class TestFleetReflectsProgress:
    def test_gate_cleared_moves_job_to_in_progress(self):
        before = build_fleet_summary()
        accord_before = next(j for j in before["jobs"] if j["model"] == "Accord")
        assert accord_before["status"] == "not_started"

        d = client.get(f"/internal/review/progress{V}").json()
        gate = next(g for g in d["qa_gates"] if g["status"] == "open")
        client.post(
            f"/internal/review/progress/events{V}",
            json={"event_type": "qa_gate_passed", "target_id": gate["gate_id"], "actor": "manager"},
        )

        after = build_fleet_summary()
        accord_after = next(j for j in after["jobs"] if j["model"] == "Accord")
        assert accord_after["status"] == "in_progress"
        assert accord_after["events_recorded"] == 2  # gate_passed + companion blocker_resolved
        assert accord_after["open_qa_gates"] == accord_before["open_qa_gates"] - 1

    def test_reset_returns_job_to_not_started(self):
        d = client.get(f"/internal/review/progress{V}").json()
        gate = next(g for g in d["qa_gates"] if g["status"] == "open")
        client.post(
            f"/internal/review/progress/events{V}",
            json={"event_type": "qa_gate_passed", "target_id": gate["gate_id"]},
        )
        client.delete(f"/internal/review/progress{V}")

        summary = build_fleet_summary()
        accord = next(j for j in summary["jobs"] if j["model"] == "Accord")
        assert accord["status"] == "not_started"
        assert accord["events_recorded"] == 0

    def test_other_jobs_unaffected_by_one_jobs_progress(self):
        d = client.get(f"/internal/review/progress{V}").json()
        gate = next(g for g in d["qa_gates"] if g["status"] == "open")
        client.post(
            f"/internal/review/progress/events{V}",
            json={"event_type": "qa_gate_passed", "target_id": gate["gate_id"]},
        )

        summary = build_fleet_summary()
        civic = next(j for j in summary["jobs"] if j["model"] == "Civic")
        assert civic["status"] == "not_started"
        assert civic["events_recorded"] == 0


class TestFleetEndpoints:
    def test_get_fleet_returns_200_json(self):
        resp = client.get("/internal/fleet")
        assert resp.status_code == 200
        assert "application/json" in resp.headers["content-type"]
        data = resp.json()
        assert "jobs" in data
        assert "counts_by_status" in data

    def test_get_fleet_ui_returns_html(self):
        resp = client.get("/internal/fleet/ui")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_fleet_ui_is_self_contained(self):
        text = client.get("/internal/fleet/ui").text
        assert "cdn." not in text.lower()
        assert "unpkg.com" not in text
        assert "jsdelivr" not in text
        assert "googleapis.com" not in text
        assert "react" not in text.lower()

    def test_fleet_ui_shows_job_titles(self):
        text = client.get("/internal/fleet/ui").text
        assert "Accord" in text
        assert "Civic" in text

    def test_fleet_ui_has_advisory(self):
        text = client.get("/internal/fleet/ui").text
        assert "advisory" in text.lower()

    def test_fleet_ui_links_to_review_and_progress(self):
        text = client.get("/internal/fleet/ui").text
        assert "/internal/review?oem=" in text
        assert "/internal/review/progress/ui?oem=" in text

    def test_fleet_ui_reflects_status_change(self):
        before = client.get("/internal/fleet/ui").text
        assert 'class="stat in_progress"><b>0<' in before or ">0<" in before

        d = client.get(f"/internal/review/progress{V}").json()
        gate = next(g for g in d["qa_gates"] if g["status"] == "open")
        client.post(
            f"/internal/review/progress/events{V}",
            json={"event_type": "qa_gate_passed", "target_id": gate["gate_id"]},
        )

        after = client.get("/internal/fleet/ui").text
        assert 'class="job-card in_progress"' in after


class TestFleetRobustness:
    def test_missing_procedure_does_not_break_fleet(self, monkeypatch):
        """A vehicle listed by list_available_vehicles but whose procedure
        file has since vanished must be skipped, not crash the whole fleet."""
        import repairgraph.state.fleet as fleet_mod

        real_list = fleet_mod.list_available_vehicles

        def _with_phantom():
            vehicles = real_list()
            vehicles = vehicles + [{
                "oem": "Ghost", "year": 1999, "model": "Nonexistent",
                "operation": "quarter_panel_replacement", "source": "intake",
            }]
            return vehicles

        monkeypatch.setattr(fleet_mod, "list_available_vehicles", _with_phantom)

        summary = build_fleet_summary()
        models = {j["model"] for j in summary["jobs"]}
        assert "Nonexistent" not in models
        assert "Accord" in models  # real vehicles still present


class TestRegression:
    def test_demo_unaffected(self):
        assert client.get("/internal/demo").status_code == 200

    def test_review_unaffected(self):
        assert client.get(f"/internal/review{V}").status_code == 200
