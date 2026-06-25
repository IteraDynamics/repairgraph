"""
Tests for the topology viewer payload builder.

Covers: region map derivation, inspector payloads, replay snapshots,
full payload structure, and legend completeness.
"""
import pytest

from repairgraph.state.demo import (
    build_accord_demo_events,
    build_accord_initial_state,
    build_accord_projected_state,
)
from repairgraph.viewer.topology_layout import VEHICLE_REGIONS
from repairgraph.viewer.topology_payload import (
    build_inspector_payload,
    build_region_map,
    build_replay_snapshots,
    build_topology_viewer_payload,
)


@pytest.fixture(scope="module")
def initial():
    return build_accord_initial_state()


@pytest.fixture(scope="module")
def events(initial):
    return build_accord_demo_events(initial)


@pytest.fixture(scope="module")
def projected():
    return build_accord_projected_state()


# ---- region map ----

class TestBuildRegionMap:
    def test_returns_one_entry_per_region(self, projected):
        region_map = build_region_map(projected)
        assert len(region_map) == len(VEHICLE_REGIONS)

    def test_each_entry_has_required_keys(self, projected):
        for entry in build_region_map(projected):
            assert "id" in entry
            assert "label" in entry
            assert "status" in entry
            assert "fill" in entry
            assert "stroke" in entry
            assert "matched_zones" in entry
            assert "zone_count" in entry

    def test_status_is_valid(self, projected):
        valid = {"inactive", "pending", "active", "complete", "blocked"}
        for entry in build_region_map(projected):
            assert entry["status"] in valid, f"Bad status {entry['status']} for {entry['id']}"

    def test_fill_is_hex_color(self, projected):
        for entry in build_region_map(projected):
            assert entry["fill"].startswith("#"), f"fill not hex for {entry['id']}"

    def test_ids_match_region_layout(self, projected):
        ids = {r["id"] for r in build_region_map(projected)}
        expected = {r["id"] for r in VEHICLE_REGIONS}
        assert ids == expected

    def test_zone_count_is_non_negative(self, projected):
        for entry in build_region_map(projected):
            assert entry["zone_count"] >= 0


# ---- inspector payload ----

class TestBuildInspectorPayload:
    def test_returns_dict(self, projected):
        payload = build_inspector_payload(projected, "region_hood")
        assert isinstance(payload, dict)

    def test_required_keys(self, projected):
        payload = build_inspector_payload(projected, "region_roof")
        for key in ("region_id", "region_label", "zones", "procedures", "phases",
                    "qa_gates", "blockers", "next_actions", "action_count",
                    "open_blocker_count", "open_qa_count"):
            assert key in payload, f"Missing key: {key}"

    def test_unknown_region_returns_error(self, projected):
        payload = build_inspector_payload(projected, "region_does_not_exist")
        assert "error" in payload

    def test_region_id_matches(self, projected):
        for reg in VEHICLE_REGIONS:
            payload = build_inspector_payload(projected, reg["id"])
            assert payload.get("region_id") == reg["id"]

    def test_procedures_have_action_fields(self, projected):
        for reg in VEHICLE_REGIONS:
            payload = build_inspector_payload(projected, reg["id"])
            for proc in payload["procedures"]:
                assert "action_id" in proc
                assert "status" in proc
                assert "target" in proc

    def test_action_count_matches_procedures(self, projected):
        for reg in VEHICLE_REGIONS:
            payload = build_inspector_payload(projected, reg["id"])
            assert payload["action_count"] == len(payload["procedures"])

    def test_open_blocker_count_consistent(self, projected):
        for reg in VEHICLE_REGIONS:
            payload = build_inspector_payload(projected, reg["id"])
            open_blockers = sum(1 for b in payload["blockers"] if b["status"] == "open")
            assert payload["open_blocker_count"] == open_blockers


# ---- replay snapshots ----

class TestBuildReplaySnapshots:
    def test_returns_one_snapshot_per_event(self, initial, events):
        snapshots = build_replay_snapshots(initial, events)
        assert len(snapshots) == len(events)

    def test_snapshot_keys(self, initial, events):
        snapshots = build_replay_snapshots(initial, events)
        for snap in snapshots:
            assert "step" in snap
            assert "event" in snap
            assert "region_map" in snap
            assert "state_summary" in snap
            assert "diff_summary" in snap

    def test_steps_are_sequential(self, initial, events):
        snapshots = build_replay_snapshots(initial, events)
        for i, snap in enumerate(snapshots):
            assert snap["step"] == i + 1

    def test_each_snapshot_has_full_region_map(self, initial, events):
        snapshots = build_replay_snapshots(initial, events)
        for snap in snapshots:
            assert len(snap["region_map"]) == len(VEHICLE_REGIONS)

    def test_empty_events_returns_empty_list(self, initial):
        snapshots = build_replay_snapshots(initial, [])
        assert snapshots == []

    def test_event_has_required_fields(self, initial, events):
        snapshots = build_replay_snapshots(initial, events)
        for snap in snapshots:
            ev = snap["event"]
            assert "event_id" in ev
            assert "event_type" in ev
            assert "timestamp" in ev

    def test_state_summary_keys(self, initial, events):
        snapshots = build_replay_snapshots(initial, events)
        for snap in snapshots:
            ss = snap["state_summary"]
            assert "session_status" in ss
            assert "completed_action_count" in ss
            assert "open_blocker_count" in ss


# ---- full payload ----

class TestBuildTopologyViewerPayload:
    def test_returns_dict(self, initial, events):
        payload = build_topology_viewer_payload(initial, events)
        assert isinstance(payload, dict)

    def test_schema_name(self, initial, events):
        payload = build_topology_viewer_payload(initial, events)
        assert payload["schema_name"] == "repairgraph.viewer.topology"

    def test_advisory_flag(self, initial, events):
        payload = build_topology_viewer_payload(initial, events)
        assert payload["advisory"] is True

    def test_session_fields(self, initial, events):
        payload = build_topology_viewer_payload(initial, events)
        session = payload["session"]
        assert session["oem"] == "Honda"
        assert session["year"] == 2025
        assert session["model"] == "Accord"
        assert "operation" in session
        assert "status" in session

    def test_region_map_present(self, initial, events):
        payload = build_topology_viewer_payload(initial, events)
        assert len(payload["region_map"]) == len(VEHICLE_REGIONS)

    def test_initial_region_map_present(self, initial, events):
        payload = build_topology_viewer_payload(initial, events)
        assert len(payload["initial_region_map"]) == len(VEHICLE_REGIONS)

    def test_replay_snapshots_count(self, initial, events):
        payload = build_topology_viewer_payload(initial, events)
        assert len(payload["replay_snapshots"]) == len(events)

    def test_inspector_payloads_for_all_regions(self, initial, events):
        payload = build_topology_viewer_payload(initial, events)
        for reg in VEHICLE_REGIONS:
            assert reg["id"] in payload["inspector_payloads"]

    def test_timelines_present(self, initial, events):
        payload = build_topology_viewer_payload(initial, events)
        assert isinstance(payload["event_timeline"], list)
        assert isinstance(payload["phase_timeline"], list)
        assert isinstance(payload["action_timeline"], list)

    def test_workflow_summary_keys(self, initial, events):
        payload = build_topology_viewer_payload(initial, events)
        ws = payload["workflow_summary"]
        for key in ("phase_count", "action_count", "qa_gate_count", "blocker_count",
                    "event_count", "open_blocker_count", "complete_action_count"):
            assert key in ws

    def test_legend_zone_states_complete(self, initial, events):
        payload = build_topology_viewer_payload(initial, events)
        statuses = {s["status"] for s in payload["legend"]["zone_states"]}
        assert {"inactive", "pending", "active", "complete", "blocked"}.issubset(statuses)

    def test_is_deterministic(self, initial, events):
        p1 = build_topology_viewer_payload(initial, events)
        p2 = build_topology_viewer_payload(initial, events)
        assert p1["session"] == p2["session"]
        assert len(p1["replay_snapshots"]) == len(p2["replay_snapshots"])
