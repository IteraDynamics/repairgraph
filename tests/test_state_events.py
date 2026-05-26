import pytest

from repairgraph.state.events import (
    action_blocked_event,
    action_completed_event,
    action_marked_not_applicable_event,
    action_started_event,
    blocker_added_event,
    blocker_resolved_event,
    make_event_id,
    make_repair_event,
    phase_completed_event,
    phase_started_event,
    qa_gate_failed_event,
    qa_gate_marked_not_applicable_event,
    qa_gate_opened_event,
    qa_gate_passed_event,
    session_completed_event,
    session_started_event,
    utc_now_iso,
    validate_event_target,
)
from repairgraph.state.schema import RepairEvent


def test_utc_now_iso_returns_zulu_timestamp():
    timestamp = utc_now_iso()

    assert timestamp.endswith("Z")
    assert "T" in timestamp


def test_make_event_id_uses_expected_prefix():
    event_id = make_event_id()

    assert event_id.startswith("evt_")
    assert len(event_id) > len("evt_")


def test_validate_event_target_accepts_compatible_pair():
    validate_event_target("action_completed", "action")


def test_validate_event_target_rejects_unknown_event_type():
    with pytest.raises(ValueError, match="Invalid event type"):
        validate_event_target("unknown_event", "action")


def test_validate_event_target_rejects_incompatible_target_type():
    with pytest.raises(ValueError, match="not compatible"):
        validate_event_target("action_completed", "session")


def test_make_repair_event_with_explicit_values():
    event = make_repair_event(
        event_id="evt_fixed",
        timestamp="2026-01-01T10:00:00Z",
        event_type="action_completed",
        actor="technician",
        target_type="action",
        target_id="replace_component:rear_pillar_separator",
        notes="Completed with supporting photos.",
        evidence={"photo_ids": ["photo_001"]},
    )

    assert isinstance(event, RepairEvent)
    assert event.event_id == "evt_fixed"
    assert event.timestamp == "2026-01-01T10:00:00Z"
    assert event.event_type == "action_completed"
    assert event.actor == "technician"
    assert event.target_type == "action"
    assert event.target_id == "replace_component:rear_pillar_separator"
    assert event.evidence == {"photo_ids": ["photo_001"]}


def test_make_repair_event_autofills_event_id_and_timestamp():
    event = make_repair_event(
        event_type="session_started",
        actor="advisor",
        target_type="session",
        target_id="session_001",
    )

    assert event.event_id.startswith("evt_")
    assert event.timestamp.endswith("Z")


def test_make_repair_event_rejects_incompatible_target():
    with pytest.raises(ValueError, match="not compatible"):
        make_repair_event(
            event_type="qa_gate_passed",
            actor="technician",
            target_type="action",
            target_id="replace_component:rear_pillar_separator",
        )


def test_session_started_event():
    event = session_started_event(
        session_id="session_001",
        actor="advisor",
        event_id="evt_session_started",
        timestamp="2026-01-01T10:00:00Z",
    )

    assert event.event_type == "session_started"
    assert event.target_type == "session"
    assert event.target_id == "session_001"


def test_session_completed_event():
    event = session_completed_event(
        session_id="session_001",
        actor="advisor",
        event_id="evt_session_completed",
        timestamp="2026-01-01T11:00:00Z",
    )

    assert event.event_type == "session_completed"
    assert event.target_type == "session"


def test_phase_started_event():
    event = phase_started_event(
        phase_id="phase:3",
        actor="technician",
        event_id="evt_phase_started",
        timestamp="2026-01-01T10:00:00Z",
    )

    assert event.event_type == "phase_started"
    assert event.target_type == "phase"
    assert event.target_id == "phase:3"


def test_phase_completed_event():
    event = phase_completed_event(
        phase_id="phase:3",
        actor="technician",
        event_id="evt_phase_completed",
        timestamp="2026-01-01T10:00:00Z",
    )

    assert event.event_type == "phase_completed"
    assert event.target_type == "phase"


def test_action_started_event():
    event = action_started_event(
        action_id="replace_component:rear_pillar_separator",
        actor="technician",
        event_id="evt_action_started",
        timestamp="2026-01-01T10:00:00Z",
    )

    assert event.event_type == "action_started"
    assert event.target_type == "action"


def test_action_completed_event():
    event = action_completed_event(
        action_id="replace_component:rear_pillar_separator",
        actor="technician",
        event_id="evt_action_completed",
        timestamp="2026-01-01T10:00:00Z",
    )

    assert event.event_type == "action_completed"
    assert event.target_type == "action"


def test_action_blocked_event():
    event = action_blocked_event(
        action_id="replace_component:rear_pillar_separator",
        actor="technician",
        event_id="evt_action_blocked",
        timestamp="2026-01-01T10:00:00Z",
        notes="Waiting for structural verification.",
    )

    assert event.event_type == "action_blocked"
    assert event.notes == "Waiting for structural verification."


def test_action_marked_not_applicable_event_requires_reason_as_notes():
    event = action_marked_not_applicable_event(
        action_id="replace_component:roof_panel",
        actor="technician",
        reason="Roof panel operation not required on this repair.",
        event_id="evt_action_na",
        timestamp="2026-01-01T10:00:00Z",
    )

    assert event.event_type == "action_marked_not_applicable"
    assert event.notes == "Roof panel operation not required on this repair."


def test_qa_gate_opened_event():
    event = qa_gate_opened_event(
        gate_id="qa:material_compliance:critical:1",
        actor="system",
        event_id="evt_qa_opened",
        timestamp="2026-01-01T10:00:00Z",
    )

    assert event.event_type == "qa_gate_opened"
    assert event.target_type == "qa_gate"


def test_qa_gate_passed_event():
    event = qa_gate_passed_event(
        gate_id="qa:material_compliance:critical:1",
        actor="technician",
        event_id="evt_qa_passed",
        timestamp="2026-01-01T10:00:00Z",
        evidence={"scan": "passed"},
    )

    assert event.event_type == "qa_gate_passed"
    assert event.evidence == {"scan": "passed"}


def test_qa_gate_failed_event():
    event = qa_gate_failed_event(
        gate_id="qa:material_compliance:critical:1",
        actor="technician",
        event_id="evt_qa_failed",
        timestamp="2026-01-01T10:00:00Z",
        notes="Material verification failed.",
    )

    assert event.event_type == "qa_gate_failed"
    assert event.notes == "Material verification failed."


def test_qa_gate_marked_not_applicable_event_requires_reason_as_notes():
    event = qa_gate_marked_not_applicable_event(
        gate_id="qa:dimensional_verification:high:1",
        actor="technician",
        reason="Dimension check not applicable to this selected operation.",
        event_id="evt_qa_na",
        timestamp="2026-01-01T10:00:00Z",
    )

    assert event.event_type == "qa_gate_marked_not_applicable"
    assert event.notes == "Dimension check not applicable to this selected operation."


def test_blocker_added_event():
    event = blocker_added_event(
        blocker_id="blocker:qa:material_compliance:critical:1",
        actor="system",
        event_id="evt_blocker_added",
        timestamp="2026-01-01T10:00:00Z",
    )

    assert event.event_type == "blocker_added"
    assert event.target_type == "blocker"


def test_blocker_resolved_event():
    event = blocker_resolved_event(
        blocker_id="blocker:qa:material_compliance:critical:1",
        actor="technician",
        event_id="evt_blocker_resolved",
        timestamp="2026-01-01T10:00:00Z",
        notes="Required QA documentation uploaded.",
    )

    assert event.event_type == "blocker_resolved"
    assert event.notes == "Required QA documentation uploaded."
