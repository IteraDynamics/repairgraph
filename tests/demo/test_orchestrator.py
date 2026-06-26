"""
Tests for the RepairGraph golden-path demo orchestrator.

Verifies intake payload, workflow payload, and full combined payload
correctness, structure, and determinism. All business logic is delegated
to existing modules — these tests verify orchestration only.
"""
import pytest

from repairgraph.demo.orchestrator import (
    build_full_demo_payload,
    build_intake_demo_payload,
    build_workflow_demo_payload,
)


# ── Intake payload ──────────────────────────────────────────────────────────

class TestBuildIntakeDemoPayload:
    def test_returns_dict(self):
        payload = build_intake_demo_payload()
        assert isinstance(payload, dict)

    def test_schema_name(self):
        payload = build_intake_demo_payload()
        assert payload["schema_name"] == "repairgraph.demo.intake"

    def test_has_file_count(self):
        payload = build_intake_demo_payload()
        assert isinstance(payload["file_count"], int)
        assert payload["file_count"] > 0

    def test_has_readiness(self):
        payload = build_intake_demo_payload()
        assert "readiness" in payload
        assert payload["readiness"] in {"ready", "partial", "incomplete", "unprocessable", "unknown"}

    def test_has_detected_packet(self):
        payload = build_intake_demo_payload()
        dp = payload["detected_packet"]
        assert "oem" in dp
        assert "model" in dp
        assert "confidence" in dp

    def test_has_files_list(self):
        payload = build_intake_demo_payload()
        assert isinstance(payload["files"], list)
        assert len(payload["files"]) > 0

    def test_files_have_required_fields(self):
        payload = build_intake_demo_payload()
        for f in payload["files"]:
            assert "filename" in f
            assert "document_role" in f
            assert "confidence" in f

    def test_has_summary(self):
        payload = build_intake_demo_payload()
        assert "summary" in payload
        assert "readiness" in payload["summary"]

    def test_has_diagnostics(self):
        payload = build_intake_demo_payload()
        assert isinstance(payload["diagnostics"], list)

    def test_fixture_packet_key(self):
        payload = build_intake_demo_payload()
        assert "fixture_packet" in payload

    def test_structurally_consistent(self):
        # intake_id is a random UUID per call — compare structural fields
        p1 = build_intake_demo_payload()
        p2 = build_intake_demo_payload()
        assert p1["file_count"] == p2["file_count"]
        assert p1["readiness"] == p2["readiness"]
        assert p1["detected_packet"]["oem"] == p2["detected_packet"]["oem"]


# ── Workflow payload ─────────────────────────────────────────────────────────

class TestBuildWorkflowDemoPayload:
    def test_returns_dict(self):
        payload = build_workflow_demo_payload()
        assert isinstance(payload, dict)

    def test_schema_name(self):
        payload = build_workflow_demo_payload()
        assert payload["schema_name"] == "repairgraph.demo.workflow"

    def test_advisory_flag(self):
        payload = build_workflow_demo_payload()
        assert payload["advisory"] is True

    def test_session_fields(self):
        payload = build_workflow_demo_payload()
        sess = payload["session"]
        assert sess["oem"] == "Honda"
        assert sess["year"] == 2025
        assert sess["model"] == "Accord"
        assert "status" in sess

    def test_workflow_summary_keys(self):
        payload = build_workflow_demo_payload()
        ws = payload["workflow_summary"]
        for key in ("phase_count", "action_count", "qa_gate_count", "blocker_count",
                    "event_count", "zone_count", "open_blocker_count",
                    "complete_action_count", "next_action_count"):
            assert key in ws, f"Missing: {key}"

    def test_workflow_counts_positive(self):
        payload = build_workflow_demo_payload()
        ws = payload["workflow_summary"]
        assert ws["phase_count"] > 0
        assert ws["action_count"] > 0
        assert ws["zone_count"] > 0

    def test_replay_steps_present(self):
        payload = build_workflow_demo_payload()
        assert isinstance(payload["replay_steps"], list)
        assert len(payload["replay_steps"]) > 0

    def test_replay_steps_have_required_fields(self):
        payload = build_workflow_demo_payload()
        for step in payload["replay_steps"]:
            assert "step" in step
            assert "event" in step
            assert "state_summary" in step
            assert "diff_summary" in step

    def test_replay_steps_sequential(self):
        payload = build_workflow_demo_payload()
        for i, step in enumerate(payload["replay_steps"]):
            assert step["step"] == i + 1

    def test_event_has_required_fields(self):
        payload = build_workflow_demo_payload()
        for step in payload["replay_steps"]:
            ev = step["event"]
            assert "event_id" in ev
            assert "event_type" in ev
            assert "timestamp" in ev
            assert "actor" in ev

    def test_timelines_present(self):
        payload = build_workflow_demo_payload()
        assert isinstance(payload["event_timeline"], list)
        assert isinstance(payload["phase_timeline"], list)
        assert isinstance(payload["action_timeline"], list)

    def test_phases_list(self):
        payload = build_workflow_demo_payload()
        assert isinstance(payload["phases"], list)
        assert len(payload["phases"]) > 0
        for p in payload["phases"]:
            assert "phase" in p
            assert "name" in p
            assert "status" in p

    def test_next_actions_present(self):
        payload = build_workflow_demo_payload()
        assert "next_actions" in payload
        assert isinstance(payload["next_actions"], list)

    def test_blockers_summary_present(self):
        payload = build_workflow_demo_payload()
        assert "blockers_summary" in payload

    def test_is_deterministic(self):
        p1 = build_workflow_demo_payload()
        p2 = build_workflow_demo_payload()
        assert p1["session"] == p2["session"]
        assert p1["workflow_summary"] == p2["workflow_summary"]
        assert len(p1["replay_steps"]) == len(p2["replay_steps"])


# ── Full combined payload ────────────────────────────────────────────────────

class TestBuildFullDemoPayload:
    def test_returns_dict(self):
        payload = build_full_demo_payload()
        assert isinstance(payload, dict)

    def test_schema_name(self):
        payload = build_full_demo_payload()
        assert payload["schema_name"] == "repairgraph.demo.full"

    def test_advisory_flag(self):
        payload = build_full_demo_payload()
        assert payload["advisory"] is True

    def test_has_intake(self):
        payload = build_full_demo_payload()
        assert "intake" in payload
        assert payload["intake"]["schema_name"] == "repairgraph.demo.intake"

    def test_has_workflow(self):
        payload = build_full_demo_payload()
        assert "workflow" in payload
        assert payload["workflow"]["schema_name"] == "repairgraph.demo.workflow"

    def test_has_export_links(self):
        payload = build_full_demo_payload()
        links = payload["export_links"]
        assert "workflow_report" in links
        assert "replay_report" in links
        assert "intake_page" in links
        assert "topology_viewer" in links
        assert "visualization_json" in links

    def test_export_links_are_internal_paths(self):
        payload = build_full_demo_payload()
        for key, url in payload["export_links"].items():
            assert url.startswith("/internal/"), f"Non-internal link: {key}={url}"

    def test_structurally_consistent(self):
        # intake_id is a random UUID per call — compare structural fields only
        p1 = build_full_demo_payload()
        p2 = build_full_demo_payload()
        assert p1["schema_name"] == p2["schema_name"]
        assert p1["workflow"]["session"] == p2["workflow"]["session"]
        assert p1["intake"]["file_count"] == p2["intake"]["file_count"]
