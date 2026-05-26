"""Tests for the AR workflow payload builder (repairgraph.state.ar_payload)."""
import json

import pytest

from repairgraph.state.ar_payload import (
    ADVISORY_NOTE,
    GENERATED_BY,
    SCHEMA_NAME,
    SCHEMA_VERSION,
    SOURCE_SCHEMA_NAME,
    SOURCE_SCHEMA_VERSION,
    build_action_guidance_items,
    build_ar_workflow_payload,
    build_blocker_items,
    build_qa_gate_items,
    build_zone_overlay_items,
)
from repairgraph.state.schema import (
    ActionState,
    Blocker,
    PhaseState,
    QAGateState,
    RepairSession,
    RepairState,
    ZoneActivation,
)


# ---------------------------------------------------------------------------
# Fixture
# ---------------------------------------------------------------------------

@pytest.fixture
def sample_state() -> RepairState:
    """Minimal RepairState covering all status/role branches."""
    session = RepairSession(
        session_id="test_session_001",
        oem="Honda",
        year=2025,
        model="Accord",
        operation="rear_side_outer_panel_replacement",
        status="in_progress",
        current_phase="component_replacement",
    )
    phases = [
        PhaseState(phase=1, name="preparation", label="Preparation Phase", status="complete"),
        PhaseState(
            phase=2,
            name="component_replacement",
            label="Component Replacement",
            status="in_progress",
            active_zones=["zone_a"],
            pending_actions=["action_pending_001"],
        ),
        PhaseState(phase=3, name="finishing", label="Finishing", status="blocked"),
    ]
    actions = [
        ActionState(
            action_id="action_completed_001",
            phase=1,
            action_type="remove_component",
            target="rear_panel",
            status="complete",
            zone_refs=["zone_d"],
            requires_qa=False,
            evidence={"source_type": "normalized_procedure", "interpretation": "advisory"},
        ),
        ActionState(
            action_id="action_in_progress_001",
            phase=2,
            action_type="replace_component",
            target="outer_panel",
            status="in_progress",
            zone_refs=["zone_a"],
            requires_qa=True,
        ),
        ActionState(
            action_id="action_pending_001",
            phase=2,
            action_type="apply_corrosion_protection",
            target="inner_panel",
            status="pending",
            zone_refs=["zone_b"],
            requires_qa=True,
        ),
        ActionState(
            action_id="action_blocked_001",
            phase=2,
            action_type="apply_joining_method",
            target="bracket",
            status="blocked",
            zone_refs=["zone_c"],
            requires_qa=False,
        ),
        ActionState(
            action_id="action_na_001",
            phase=1,
            action_type="verify",
            target="component_x",
            status="not_applicable",
            zone_refs=[],
            requires_qa=False,
        ),
    ]
    qa_gates = [
        QAGateState(
            gate_id="qa_gate_blocking_001",
            category="material_compliance",
            priority="critical",
            status="open",
            related_phase=2,
            zone_refs=["zone_a"],
            check="Verify OEM joining method for UHSS zone",
            blocks_completion=True,
        ),
        QAGateState(
            gate_id="qa_gate_passed_001",
            category="corrosion",
            priority="high",
            status="passed",
            related_phase=1,
            zone_refs=["zone_b"],
            check="Verify corrosion protection applied",
            blocks_completion=False,
        ),
        QAGateState(
            gate_id="qa_gate_na_001",
            category="structural",
            priority="medium",
            status="not_applicable",
            related_phase=1,
            zone_refs=[],
            check="Verify structural integrity",
            blocks_completion=False,
        ),
        QAGateState(
            gate_id="qa_gate_context_001",
            category="documentation",
            priority="low",
            status="in_review",
            related_phase=2,
            zone_refs=["zone_c"],
            check="Review documentation",
            blocks_completion=False,
        ),
        QAGateState(
            gate_id="qa_gate_blocking_failed_001",
            category="material_compliance",
            priority="critical",
            status="failed",
            related_phase=2,
            zone_refs=["zone_c"],
            check="Verify weld spec compliance",
            blocks_completion=True,
        ),
    ]
    zones = [
        ZoneActivation(
            zone_id="zone_a",
            label="Zone A",
            status="active",
            active_phase=2,
            active_actions=["action_in_progress_001"],
            material_classification="UHSS",
            risk_flags=["high_strength_steel"],
        ),
        ZoneActivation(zone_id="zone_b", label="Zone B", status="inactive", active_phase=None),
        ZoneActivation(
            zone_id="zone_c",
            label="Zone C",
            status="blocked",
            active_phase=2,
            material_classification="HSS",
        ),
        ZoneActivation(zone_id="zone_d", label="Zone D", status="complete", active_phase=1),
        ZoneActivation(zone_id="zone_e", label="Zone E", status="pending", active_phase=None),
    ]
    blockers = [
        Blocker(
            blocker_id="blocker_critical_001",
            type="qa_gate",
            severity="critical",
            status="open",
            blocks=["phase:2", "session_completion"],
            reason="Critical UHSS joining verification unresolved.",
            related_zones=["zone_a"],
            related_actions=["action_blocked_001"],
        ),
        Blocker(
            blocker_id="blocker_high_001",
            type="material_risk",
            severity="high",
            status="open",
            blocks=["phase:2"],
            reason="High-risk material zone unresolved.",
            related_zones=["zone_c"],
            related_actions=[],
        ),
        Blocker(
            blocker_id="blocker_resolved_001",
            type="documentation_required",
            severity="medium",
            status="resolved",
            blocks=["phase:1"],
            reason="Documentation gap resolved.",
            related_zones=[],
            related_actions=[],
        ),
    ]

    return RepairState(
        session=session,
        phases=phases,
        actions=actions,
        qa_gates=qa_gates,
        zones=zones,
        blockers=blockers,
        events=[],
        next_recommended_actions=["action_in_progress_001", "action_pending_001"],
    )


# ---------------------------------------------------------------------------
# Top-level payload structure
# ---------------------------------------------------------------------------

def test_build_ar_workflow_payload_returns_dict(sample_state):
    payload = build_ar_workflow_payload(sample_state)
    assert isinstance(payload, dict)


def test_build_ar_workflow_payload_is_json_serializable(sample_state):
    payload = build_ar_workflow_payload(sample_state)
    serialized = json.dumps(payload)
    roundtripped = json.loads(serialized)
    assert isinstance(roundtripped, dict)


def test_top_level_metadata_schema_name(sample_state):
    payload = build_ar_workflow_payload(sample_state)
    assert payload["schema_name"] == SCHEMA_NAME
    assert payload["schema_name"] == "repairgraph.ar_workflow_payload"


def test_top_level_metadata_schema_version(sample_state):
    payload = build_ar_workflow_payload(sample_state)
    assert payload["schema_version"] == SCHEMA_VERSION
    assert payload["schema_version"] == "0.1"


def test_top_level_metadata_advisory_flag(sample_state):
    payload = build_ar_workflow_payload(sample_state)
    assert payload["advisory"] is True


def test_top_level_metadata_generated_by(sample_state):
    payload = build_ar_workflow_payload(sample_state)
    assert payload["generated_by"] == GENERATED_BY
    assert payload["generated_by"] == "repairgraph.state.ar_payload"


def test_top_level_metadata_advisory_note_present(sample_state):
    payload = build_ar_workflow_payload(sample_state)
    assert "advisory_note" in payload
    assert len(payload["advisory_note"]) > 0


def test_top_level_keys_all_present(sample_state):
    payload = build_ar_workflow_payload(sample_state)
    for key in ("schema_name", "schema_version", "advisory", "generated_by",
                "advisory_note", "session", "workflow_summary", "active_context",
                "overlays", "source_state"):
        assert key in payload, f"Missing top-level key: {key}"


# ---------------------------------------------------------------------------
# Session metadata
# ---------------------------------------------------------------------------

def test_session_metadata_preserved(sample_state):
    payload = build_ar_workflow_payload(sample_state)
    session = payload["session"]
    assert session["session_id"] == "test_session_001"
    assert session["oem"] == "Honda"
    assert session["year"] == 2025
    assert session["model"] == "Accord"
    assert session["operation"] == "rear_side_outer_panel_replacement"
    assert session["status"] == "in_progress"
    assert session["current_phase"] == "component_replacement"


def test_session_keys_all_present(sample_state):
    payload = build_ar_workflow_payload(sample_state)
    for key in ("session_id", "oem", "year", "model", "operation", "status", "current_phase"):
        assert key in payload["session"], f"Missing session key: {key}"


# ---------------------------------------------------------------------------
# Workflow summary counts
# ---------------------------------------------------------------------------

def test_workflow_summary_phase_count_matches_state(sample_state):
    payload = build_ar_workflow_payload(sample_state)
    assert payload["workflow_summary"]["phase_count"] == len(sample_state.phases)


def test_workflow_summary_action_count_matches_state(sample_state):
    payload = build_ar_workflow_payload(sample_state)
    assert payload["workflow_summary"]["action_count"] == len(sample_state.actions)


def test_workflow_summary_qa_gate_count_matches_state(sample_state):
    payload = build_ar_workflow_payload(sample_state)
    assert payload["workflow_summary"]["qa_gate_count"] == len(sample_state.qa_gates)


def test_workflow_summary_blocker_count_matches_state(sample_state):
    payload = build_ar_workflow_payload(sample_state)
    assert payload["workflow_summary"]["blocker_count"] == len(sample_state.blockers)


def test_workflow_summary_open_blocker_count(sample_state):
    payload = build_ar_workflow_payload(sample_state)
    open_count = sum(1 for b in sample_state.blockers if b.status == "open")
    assert payload["workflow_summary"]["open_blocker_count"] == open_count


def test_workflow_summary_event_count_matches_state(sample_state):
    payload = build_ar_workflow_payload(sample_state)
    assert payload["workflow_summary"]["event_count"] == len(sample_state.events)


def test_workflow_summary_next_action_count_matches_state(sample_state):
    payload = build_ar_workflow_payload(sample_state)
    assert payload["workflow_summary"]["next_action_count"] == len(sample_state.next_recommended_actions)


def test_workflow_summary_keys_all_present(sample_state):
    payload = build_ar_workflow_payload(sample_state)
    for key in ("phase_count", "action_count", "qa_gate_count", "blocker_count",
                "open_blocker_count", "event_count", "next_action_count"):
        assert key in payload["workflow_summary"], f"Missing workflow_summary key: {key}"


# ---------------------------------------------------------------------------
# Active context
# ---------------------------------------------------------------------------

def test_active_context_keys_all_present(sample_state):
    payload = build_ar_workflow_payload(sample_state)
    for key in ("active_phase_ids", "active_zone_ids", "blocked_phase_ids",
                "blocked_zone_ids", "next_action_ids"):
        assert key in payload["active_context"], f"Missing active_context key: {key}"


def test_active_context_active_phase_ids_are_lists(sample_state):
    payload = build_ar_workflow_payload(sample_state)
    assert isinstance(payload["active_context"]["active_phase_ids"], list)


def test_active_context_active_phase_ids_contain_in_progress(sample_state):
    payload = build_ar_workflow_payload(sample_state)
    in_progress = [p.name for p in sample_state.phases if p.status == "in_progress"]
    assert payload["active_context"]["active_phase_ids"] == in_progress


def test_active_context_blocked_phase_ids_contain_blocked(sample_state):
    payload = build_ar_workflow_payload(sample_state)
    blocked = [p.name for p in sample_state.phases if p.status == "blocked"]
    assert payload["active_context"]["blocked_phase_ids"] == blocked


def test_active_context_active_zone_ids_match_active_zones(sample_state):
    payload = build_ar_workflow_payload(sample_state)
    active_zone_ids = {z.zone_id for z in sample_state.zones if z.status == "active"}
    assert set(payload["active_context"]["active_zone_ids"]) == active_zone_ids


def test_active_context_next_action_ids_match_state(sample_state):
    payload = build_ar_workflow_payload(sample_state)
    assert payload["active_context"]["next_action_ids"] == list(sample_state.next_recommended_actions)


# ---------------------------------------------------------------------------
# Zone overlay items
# ---------------------------------------------------------------------------

def test_zone_overlays_count_matches_state(sample_state):
    zones = build_zone_overlay_items(sample_state)
    assert len(zones) == len(sample_state.zones)


def test_zone_overlay_required_fields(sample_state):
    zones = build_zone_overlay_items(sample_state)
    for zone in zones:
        for field in ("zone_id", "label", "status", "active_phase", "active_actions",
                      "material_classification", "risk_flags", "overlay_role"):
            assert field in zone, f"Zone overlay missing field: {field}"


def test_zone_overlay_active_role(sample_state):
    zones = build_zone_overlay_items(sample_state)
    active = [z for z in zones if z["zone_id"] == "zone_a"]
    assert len(active) == 1
    assert active[0]["overlay_role"] == "active_repair_zone"


def test_zone_overlay_blocked_role(sample_state):
    zones = build_zone_overlay_items(sample_state)
    blocked = [z for z in zones if z["zone_id"] == "zone_c"]
    assert len(blocked) == 1
    assert blocked[0]["overlay_role"] == "blocked_zone"


def test_zone_overlay_completed_role(sample_state):
    zones = build_zone_overlay_items(sample_state)
    completed = [z for z in zones if z["zone_id"] == "zone_d"]
    assert len(completed) == 1
    assert completed[0]["overlay_role"] == "completed_zone"


def test_zone_overlay_inactive_and_pending_role(sample_state):
    zones = build_zone_overlay_items(sample_state)
    for zone_id in ("zone_b", "zone_e"):
        items = [z for z in zones if z["zone_id"] == zone_id]
        assert len(items) == 1
        assert items[0]["overlay_role"] == "inactive_context_zone"


def test_zone_overlay_material_classification_preserved(sample_state):
    zones = build_zone_overlay_items(sample_state)
    zone_a = next(z for z in zones if z["zone_id"] == "zone_a")
    assert zone_a["material_classification"] == "UHSS"


def test_zone_overlay_risk_flags_preserved(sample_state):
    zones = build_zone_overlay_items(sample_state)
    zone_a = next(z for z in zones if z["zone_id"] == "zone_a")
    assert "high_strength_steel" in zone_a["risk_flags"]


# ---------------------------------------------------------------------------
# Action guidance items
# ---------------------------------------------------------------------------

def test_action_guidance_count_matches_state(sample_state):
    actions = build_action_guidance_items(sample_state)
    assert len(actions) == len(sample_state.actions)


def test_action_guidance_required_fields(sample_state):
    actions = build_action_guidance_items(sample_state)
    for action in actions:
        for field in ("action_id", "action_type", "target", "phase", "status",
                      "zone_refs", "requires_qa", "guidance_role", "evidence"):
            assert field in action, f"Action guidance missing field: {field}"


def test_next_recommended_actions_tagged_correctly(sample_state):
    actions = build_action_guidance_items(sample_state)
    next_ids = set(sample_state.next_recommended_actions)
    for action in actions:
        if action["action_id"] in next_ids:
            assert action["guidance_role"] == "next_recommended_action", (
                f"Action {action['action_id']} should be next_recommended_action"
            )


def test_action_guidance_role_completed(sample_state):
    actions = build_action_guidance_items(sample_state)
    completed = next(a for a in actions if a["action_id"] == "action_completed_001")
    # action_completed_001 is not in next_recommended_actions
    assert completed["guidance_role"] == "completed_action"


def test_action_guidance_role_blocked(sample_state):
    actions = build_action_guidance_items(sample_state)
    blocked = next(a for a in actions if a["action_id"] == "action_blocked_001")
    assert blocked["guidance_role"] == "blocked_action"


def test_action_guidance_role_not_applicable(sample_state):
    actions = build_action_guidance_items(sample_state)
    na = next(a for a in actions if a["action_id"] == "action_na_001")
    assert na["guidance_role"] == "not_applicable_action"


def test_action_guidance_next_recommended_takes_precedence_over_in_progress(sample_state):
    # action_in_progress_001 is both in_progress and in next_recommended_actions
    actions = build_action_guidance_items(sample_state)
    action = next(a for a in actions if a["action_id"] == "action_in_progress_001")
    assert action["guidance_role"] == "next_recommended_action"


def test_action_guidance_pending_not_in_next_gets_pending_role():
    # A pending action NOT in next_recommended_actions should be pending_context_action
    session = RepairSession(
        session_id="s1", oem="Honda", year=2025, model="Accord",
        operation="test_op", status="not_started",
    )
    action = ActionState(
        action_id="a_pending", phase=1, action_type="remove_component",
        target="panel", status="pending",
    )
    state = RepairState(session=session, actions=[action], next_recommended_actions=[])
    items = build_action_guidance_items(state)
    assert items[0]["guidance_role"] == "pending_context_action"


# ---------------------------------------------------------------------------
# QA gate items
# ---------------------------------------------------------------------------

def test_qa_gate_count_matches_state(sample_state):
    gates = build_qa_gate_items(sample_state)
    assert len(gates) == len(sample_state.qa_gates)


def test_qa_gate_required_fields(sample_state):
    gates = build_qa_gate_items(sample_state)
    for gate in gates:
        for field in ("gate_id", "category", "priority", "status", "related_phase",
                      "zone_refs", "check", "blocks_completion", "guidance_role", "evidence"):
            assert field in gate, f"QA gate item missing field: {field}"


def test_qa_gate_blocking_open_role(sample_state):
    gates = build_qa_gate_items(sample_state)
    blocking_open = next(g for g in gates if g["gate_id"] == "qa_gate_blocking_001")
    assert blocking_open["guidance_role"] == "blocking_open_qa_gate"


def test_qa_gate_blocking_failed_role(sample_state):
    gates = build_qa_gate_items(sample_state)
    blocking_failed = next(g for g in gates if g["gate_id"] == "qa_gate_blocking_failed_001")
    assert blocking_failed["guidance_role"] == "blocking_open_qa_gate"


def test_qa_gate_passed_role(sample_state):
    gates = build_qa_gate_items(sample_state)
    passed = next(g for g in gates if g["gate_id"] == "qa_gate_passed_001")
    assert passed["guidance_role"] == "passed_qa_gate"


def test_qa_gate_not_applicable_role(sample_state):
    gates = build_qa_gate_items(sample_state)
    na = next(g for g in gates if g["gate_id"] == "qa_gate_na_001")
    assert na["guidance_role"] == "not_applicable_qa_gate"


def test_qa_gate_context_role(sample_state):
    gates = build_qa_gate_items(sample_state)
    context = next(g for g in gates if g["gate_id"] == "qa_gate_context_001")
    # blocks_completion=False, status=in_review → context_qa_gate
    assert context["guidance_role"] == "context_qa_gate"


# ---------------------------------------------------------------------------
# Blocker items
# ---------------------------------------------------------------------------

def test_blocker_count_matches_state(sample_state):
    blockers = build_blocker_items(sample_state)
    assert len(blockers) == len(sample_state.blockers)


def test_blocker_required_fields(sample_state):
    blockers = build_blocker_items(sample_state)
    for blocker in blockers:
        for field in ("blocker_id", "type", "severity", "status", "blocks",
                      "reason", "related_zones", "related_actions", "guidance_role"):
            assert field in blocker, f"Blocker item missing field: {field}"


def test_blocker_critical_open_role(sample_state):
    blockers = build_blocker_items(sample_state)
    critical = next(b for b in blockers if b["blocker_id"] == "blocker_critical_001")
    assert critical["guidance_role"] == "critical_open_blocker"


def test_blocker_open_non_critical_role(sample_state):
    blockers = build_blocker_items(sample_state)
    high = next(b for b in blockers if b["blocker_id"] == "blocker_high_001")
    assert high["guidance_role"] == "open_blocker"


def test_blocker_resolved_role(sample_state):
    blockers = build_blocker_items(sample_state)
    resolved = next(b for b in blockers if b["blocker_id"] == "blocker_resolved_001")
    assert resolved["guidance_role"] == "resolved_blocker"


# ---------------------------------------------------------------------------
# Source state metadata
# ---------------------------------------------------------------------------

def test_source_state_metadata_present(sample_state):
    payload = build_ar_workflow_payload(sample_state)
    assert "source_state" in payload


def test_source_state_schema_name(sample_state):
    payload = build_ar_workflow_payload(sample_state)
    assert payload["source_state"]["schema_name"] == SOURCE_SCHEMA_NAME
    assert payload["source_state"]["schema_name"] == "repairgraph.repair_state"


def test_source_state_schema_version(sample_state):
    payload = build_ar_workflow_payload(sample_state)
    assert payload["source_state"]["schema_version"] == SOURCE_SCHEMA_VERSION
    assert payload["source_state"]["schema_version"] == "0.1"


# ---------------------------------------------------------------------------
# Overlays structure
# ---------------------------------------------------------------------------

def test_overlays_section_contains_all_keys(sample_state):
    payload = build_ar_workflow_payload(sample_state)
    for key in ("zones", "actions", "qa_gates", "blockers"):
        assert key in payload["overlays"], f"Missing overlays key: {key}"


def test_overlays_zones_is_list(sample_state):
    payload = build_ar_workflow_payload(sample_state)
    assert isinstance(payload["overlays"]["zones"], list)


def test_overlays_actions_is_list(sample_state):
    payload = build_ar_workflow_payload(sample_state)
    assert isinstance(payload["overlays"]["actions"], list)


def test_overlays_qa_gates_is_list(sample_state):
    payload = build_ar_workflow_payload(sample_state)
    assert isinstance(payload["overlays"]["qa_gates"], list)


def test_overlays_blockers_is_list(sample_state):
    payload = build_ar_workflow_payload(sample_state)
    assert isinstance(payload["overlays"]["blockers"], list)


# ---------------------------------------------------------------------------
# Empty state edge case
# ---------------------------------------------------------------------------

def test_empty_state_payload():
    session = RepairSession(
        session_id="empty_session",
        oem="Honda",
        year=2025,
        model="Accord",
        operation="test_op",
        status="not_started",
    )
    state = RepairState(session=session)
    payload = build_ar_workflow_payload(state)
    assert payload["workflow_summary"]["phase_count"] == 0
    assert payload["workflow_summary"]["action_count"] == 0
    assert payload["workflow_summary"]["open_blocker_count"] == 0
    assert payload["overlays"]["zones"] == []
    assert payload["overlays"]["actions"] == []
    assert payload["overlays"]["qa_gates"] == []
    assert payload["overlays"]["blockers"] == []
    assert payload["active_context"]["next_action_ids"] == []
