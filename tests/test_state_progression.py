"""Tests for state progression: the session event journal, projection recovery,
progress endpoints, and the review reflecting recorded work.

State progression is what makes the review a live operational picture instead
of a static snapshot: humans record events (gate passed, action completed),
the journal persists them, and every review rebuild replays them over the
initial state.
"""
from __future__ import annotations

import json
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from repairgraph.api.app import app
from repairgraph.query.loader import load_procedure, load_vehicle_structure
from repairgraph.state.events import (
    action_blocked_event,
    action_completed_event,
    action_started_event,
    blocker_resolved_event,
    qa_gate_passed_event,
)
from repairgraph.state.initialize import initialize_repair_state
from repairgraph.state.journal import (
    append_session_events,
    clear_session_events,
    load_session_events,
    session_dir,
)
from repairgraph.state.project import project_repair_state

client = TestClient(app)

V = "?oem=Honda&year=2025&model=Accord"


@pytest.fixture(autouse=True)
def isolated_journal(tmp_path, monkeypatch):
    """Point the session journal at a temp dir so tests never touch data/sessions."""
    import repairgraph.state.journal as journal
    monkeypatch.setattr(journal, "_SESSIONS_DIR", tmp_path / "sessions")
    yield


def _accord_state():
    procedure = load_procedure("Honda", 2025, "Accord")
    structure = load_vehicle_structure("Honda", 2025, "Accord")
    return initialize_repair_state(procedure, structure)


# ---------------------------------------------------------------------------
# Journal store
# ---------------------------------------------------------------------------

class TestJournalStore:
    def test_load_missing_journal_returns_empty(self):
        assert load_session_events("Honda", 2025, "Accord") == []

    def test_append_and_load_roundtrip(self):
        state = _accord_state()
        gate = state.qa_gates[0]
        event = qa_gate_passed_event(gate_id=gate.gate_id, actor="manager", notes="checked")

        append_session_events("Honda", 2025, "Accord", [event])
        loaded = load_session_events("Honda", 2025, "Accord")

        assert len(loaded) == 1
        assert loaded[0].event_id == event.event_id
        assert loaded[0].event_type == "qa_gate_passed"
        assert loaded[0].target_id == gate.gate_id
        assert loaded[0].notes == "checked"

    def test_append_preserves_order(self):
        state = _accord_state()
        events = [
            qa_gate_passed_event(gate_id=g.gate_id, actor="manager")
            for g in state.qa_gates[:3]
        ]
        append_session_events("Honda", 2025, "Accord", events[:1])
        append_session_events("Honda", 2025, "Accord", events[1:])

        loaded = load_session_events("Honda", 2025, "Accord")
        assert [e.event_id for e in loaded] == [e.event_id for e in events]

    def test_corrupt_journal_returns_empty(self):
        path = session_dir("Honda", 2025, "Accord") / "events.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("{not json", encoding="utf-8")

        assert load_session_events("Honda", 2025, "Accord") == []

    def test_clear_removes_journal(self):
        state = _accord_state()
        event = qa_gate_passed_event(gate_id=state.qa_gates[0].gate_id, actor="m")
        append_session_events("Honda", 2025, "Accord", [event])

        assert clear_session_events("Honda", 2025, "Accord") is True
        assert load_session_events("Honda", 2025, "Accord") == []
        assert clear_session_events("Honda", 2025, "Accord") is False

    def test_session_dir_slugging(self):
        d = session_dir("Ford", 2022, "F-150")
        assert d.parts[-2:] == ("ford", "2022_f_150")


# ---------------------------------------------------------------------------
# Projection recovery (blocked must not be a dead-end state)
# ---------------------------------------------------------------------------

class TestProjectionRecovery:
    def test_phase_recovers_after_blocker_resolved(self):
        initial = _accord_state()
        blocked_phases = [p for p in initial.phases]

        # Resolve every open blocker: phases blocked by them must recover
        events = [
            blocker_resolved_event(blocker_id=b.blocker_id, actor="manager")
            for b in initial.blockers
        ]
        # Blockers alone don't set phases blocked until a projection runs;
        # run one no-op-ish projection first via a gate pass to trigger recompute
        state = project_repair_state(initial, events)

        assert all(p.status != "blocked" for p in state.phases), [
            (p.name, p.status) for p in state.phases
        ]

    def test_gates_passed_and_blockers_resolved_unblocks_everything(self):
        initial = _accord_state()
        events = []
        for gate in initial.qa_gates:
            events.append(qa_gate_passed_event(gate_id=gate.gate_id, actor="manager"))
        for blocker in initial.blockers:
            events.append(blocker_resolved_event(blocker_id=blocker.blocker_id, actor="manager"))

        state = project_repair_state(initial, events)

        assert all(g.status == "passed" for g in state.qa_gates)
        assert all(b.status == "resolved" for b in state.blockers)
        assert all(p.status != "blocked" for p in state.phases)

    def test_action_blocked_then_completed_recovers_phase(self):
        initial = _accord_state()
        action = initial.actions[0]

        # Clear everything else first so only the blocked action blocks the session
        preamble = [
            qa_gate_passed_event(gate_id=g.gate_id, actor="manager")
            for g in initial.qa_gates
        ] + [
            blocker_resolved_event(blocker_id=b.blocker_id, actor="manager")
            for b in initial.blockers
        ]

        blocked = project_repair_state(
            initial,
            preamble + [action_blocked_event(action_id=action.action_id, actor="tech")],
        )
        phase = next(p for p in blocked.phases if p.phase == action.phase)
        assert phase.status == "blocked"
        assert blocked.session.status == "blocked"

        recovered = project_repair_state(
            blocked, [action_completed_event(action_id=action.action_id, actor="tech")]
        )
        phase = next(p for p in recovered.phases if p.phase == action.phase)
        assert phase.status != "blocked"
        assert action.action_id not in phase.blocked_by
        assert recovered.session.status != "blocked"

    def test_phase_with_in_progress_action_recovers_to_in_progress(self):
        initial = _accord_state()
        actions = [a for a in initial.actions if a.phase == initial.actions[0].phase]
        a1, a2 = actions[0], actions[1] if len(actions) > 1 else (actions[0], None)

        events = [action_started_event(action_id=a1.action_id, actor="tech")]
        if a2:
            events.append(action_blocked_event(action_id=a2.action_id, actor="tech"))
            events.append(action_completed_event(action_id=a2.action_id, actor="tech"))

        state = project_repair_state(initial, events)
        phase = next(p for p in state.phases if p.phase == a1.phase)
        assert phase.status == "in_progress"


# ---------------------------------------------------------------------------
# Progress endpoints
# ---------------------------------------------------------------------------

class TestProgressEndpoints:
    def test_get_progress_initial_state(self):
        resp = client.get(f"/internal/review/progress{V}")
        assert resp.status_code == 200
        d = resp.json()
        assert d["session"]["status"] == "not_started"
        assert d["counts"]["events_recorded"] == 0
        assert d["counts"]["open_qa_gates"] > 0
        assert d["counts"]["open_blockers"] > 0
        assert all(a["status"] == "pending" for a in d["actions"])
        assert d["endpoint_advisory"]

    def test_post_gate_passed_resolves_companion_blocker(self):
        d = client.get(f"/internal/review/progress{V}").json()
        gate = next(g for g in d["qa_gates"] if g["status"] == "open" and g["blocks_completion"])

        resp = client.post(
            f"/internal/review/progress/events{V}",
            json={"event_type": "qa_gate_passed", "target_id": gate["gate_id"], "actor": "manager"},
        )
        assert resp.status_code == 200
        r = resp.json()
        assert r["recorded"] is True
        types = [e["event_type"] for e in r["applied_events"]]
        assert types == ["qa_gate_passed", "blocker_resolved"]
        assert r["open_blockers"] == d["counts"]["open_blockers"] - 1

    def test_post_action_completed(self):
        d = client.get(f"/internal/review/progress{V}").json()
        action = next(a for a in d["actions"] if a["status"] == "pending")

        resp = client.post(
            f"/internal/review/progress/events{V}",
            json={"event_type": "action_completed", "target_id": action["action_id"], "actor": "tech"},
        )
        assert resp.status_code == 200
        d2 = client.get(f"/internal/review/progress{V}").json()
        updated = next(a for a in d2["actions"] if a["action_id"] == action["action_id"])
        assert updated["status"] == "complete"

    def test_post_invalid_event_type_422(self):
        resp = client.post(
            f"/internal/review/progress/events{V}",
            json={"event_type": "warp_drive_engaged", "target_id": "x"},
        )
        assert resp.status_code == 422

    def test_post_unknown_target_422_and_not_journaled(self):
        resp = client.post(
            f"/internal/review/progress/events{V}",
            json={"event_type": "qa_gate_passed", "target_id": "qa:fabricated:high:99"},
        )
        assert resp.status_code == 422
        d = client.get(f"/internal/review/progress{V}").json()
        assert d["counts"]["events_recorded"] == 0

    def test_delete_resets_progress(self):
        d = client.get(f"/internal/review/progress{V}").json()
        gate = next(g for g in d["qa_gates"] if g["status"] == "open")
        client.post(
            f"/internal/review/progress/events{V}",
            json={"event_type": "qa_gate_passed", "target_id": gate["gate_id"]},
        )

        resp = client.delete(f"/internal/review/progress{V}")
        assert resp.status_code == 200
        assert resp.json()["cleared"] is True

        d = client.get(f"/internal/review/progress{V}").json()
        assert d["counts"]["events_recorded"] == 0
        assert all(g["status"] == "open" for g in d["qa_gates"])

    def test_progress_404_without_vehicle_context(self, monkeypatch, tmp_path):
        import repairgraph.core.vehicle_store as vs
        monkeypatch.setattr(vs, "_ACTIVE_VEHICLE_PATH", tmp_path / "nope.json")

        resp = client.get("/internal/review/progress")
        assert resp.status_code == 404

    def test_progress_404_for_unknown_vehicle(self):
        resp = client.get("/internal/review/progress?oem=Fake&year=1999&model=Nothing")
        assert resp.status_code == 404

    def test_events_listed_in_progress(self):
        d = client.get(f"/internal/review/progress{V}").json()
        gate = next(g for g in d["qa_gates"] if g["status"] == "open")
        client.post(
            f"/internal/review/progress/events{V}",
            json={"event_type": "qa_gate_passed", "target_id": gate["gate_id"], "actor": "qa_lead",
                  "notes": "verified against OEM sheet"},
        )
        d = client.get(f"/internal/review/progress{V}").json()
        assert d["counts"]["events_recorded"] >= 1
        first = d["events"][0]
        assert first["actor"] == "qa_lead"
        assert first["notes"] == "verified against OEM sheet"
        assert first["timestamp"]


# ---------------------------------------------------------------------------
# The review reflects recorded progress
# ---------------------------------------------------------------------------

class TestReviewReflectsProgress:
    def _clear_all_gates(self):
        d = client.get(f"/internal/review/progress{V}").json()
        for g in d["qa_gates"]:
            if g["status"] == "open":
                client.post(
                    f"/internal/review/progress/events{V}",
                    json={"event_type": "qa_gate_passed", "target_id": g["gate_id"], "actor": "manager"},
                )

    def test_decision_transitions_from_blocked_when_gates_cleared(self):
        before = client.get(f"/internal/review/payload{V}").json()
        assert before["decision"]["decision"] == "Blocked"

        self._clear_all_gates()

        after = client.get(f"/internal/review/payload{V}").json()
        assert after["decision"]["decision"] != "Blocked"
        assert after["workflow_readiness"]["workflow_readiness"] != "blocked"

    def test_review_page_hero_changes_when_gates_cleared(self):
        before = client.get(f"/internal/review{V}").text
        assert "BLOCKED" in before

        self._clear_all_gates()

        after = client.get(f"/internal/review{V}").text
        assert "PROCEED WITH CAUTION" in after or "READY" in after

    def test_completed_action_moves_workflow_to_in_progress(self):
        self._clear_all_gates()
        d = client.get(f"/internal/review/progress{V}").json()
        action = next(a for a in d["actions"] if a["status"] == "pending")
        client.post(
            f"/internal/review/progress/events{V}",
            json={"event_type": "action_completed", "target_id": action["action_id"]},
        )

        payload = client.get(f"/internal/review/payload{V}").json()
        assert payload["workflow_readiness"]["workflow_readiness"] == "in_progress"

    def test_reset_restores_blocked(self):
        self._clear_all_gates()
        client.delete(f"/internal/review/progress{V}")

        payload = client.get(f"/internal/review/payload{V}").json()
        assert payload["decision"]["decision"] == "Blocked"

    def test_progress_isolated_per_vehicle(self):
        # Recording against the Accord must not affect the CR-V
        crv_url = "/internal/review/progress?oem=Honda&year=2025&model=CR-V"
        before = client.get(crv_url).json()["counts"]

        self._clear_all_gates()

        after = client.get(crv_url).json()["counts"]
        assert after == before
        assert after["events_recorded"] == 0


# ---------------------------------------------------------------------------
# Manifest readiness (fixture vs intake-derived)
# ---------------------------------------------------------------------------

class TestManifestReadiness:
    def test_fixture_vehicle_is_not_insufficient_packet(self):
        payload = client.get(f"/internal/review/payload{V}").json()
        assert payload["decision"]["decision"] != "Insufficient Packet"
        assert payload["documentation"]["readiness"] == "ready"

    def test_intake_vehicle_carries_intake_readiness(self):
        payload = client.get(
            "/internal/review/payload?oem=Hyundai&year=2023&model=Elantra"
        ).json()
        assert payload["documentation"]["readiness"] in ("ready", "partial")


# ---------------------------------------------------------------------------
# Progress UI page
# ---------------------------------------------------------------------------

class TestProgressUI:
    def test_ui_returns_html(self):
        resp = client.get(f"/internal/review/progress/ui{V}")
        assert resp.status_code == 200
        assert "text/html" in resp.headers["content-type"]

    def test_ui_is_self_contained(self):
        text = client.get(f"/internal/review/progress/ui{V}").text
        assert "cdn." not in text.lower()
        assert "unpkg.com" not in text
        assert "jsdelivr" not in text
        assert "googleapis.com" not in text
        assert "react" not in text.lower()

    def test_ui_has_controls_and_advisory(self):
        text = client.get(f"/internal/review/progress/ui{V}").text
        assert "Mark Passed" in text
        assert "Reset Progress" in text
        assert "advisory" in text.lower()

    def test_ui_reflects_recorded_progress(self):
        d = client.get(f"/internal/review/progress{V}").json()
        gate = next(g for g in d["qa_gates"] if g["status"] == "open")
        client.post(
            f"/internal/review/progress/events{V}",
            json={"event_type": "qa_gate_passed", "target_id": gate["gate_id"]},
        )
        text = client.get(f"/internal/review/progress/ui{V}").text
        assert "passed" in text


# ---------------------------------------------------------------------------
# Regression: existing surfaces unaffected
# ---------------------------------------------------------------------------

class TestRegression:
    def test_demo_unaffected(self):
        assert client.get("/internal/demo").status_code == 200

    def test_review_without_journal_is_initial_state(self):
        d = client.get(f"/internal/review/progress{V}").json()
        assert d["session"]["status"] == "not_started"
        payload = client.get(f"/internal/review/payload{V}").json()
        assert payload["decision"]["decision"] == "Blocked"

    def test_state_accord_endpoints_unaffected(self):
        assert client.get("/internal/state/accord/summary").status_code == 200
        assert client.get("/internal/state/accord/projected").status_code == 200
