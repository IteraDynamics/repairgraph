import pytest

from repairgraph.state.schema import (
    ActionState,
    Blocker,
    PhaseState,
    QAGateState,
    RepairEvent,
    RepairSession,
    RepairState,
    ZoneActivation,
)


def test_create_repair_session():
    session = RepairSession(
        session_id="session_001",
        oem="Honda",
        year=2025,
        model="Accord",
        operation="rear_side_outer_panel_replacement",
        status="not_started",
    )

    assert session.session_id == "session_001"
    assert session.status == "not_started"


def test_invalid_repair_session_status_rejected():
    with pytest.raises(ValueError, match="Invalid session status"):
        RepairSession(
            session_id="session_001",
            oem="Honda",
            year=2025,
            model="Accord",
            operation="rear_side_outer_panel_replacement",
            status="done",
        )


def test_create_phase_state():
    phase = PhaseState(
        phase=3,
        name="component_replacement",
        label="Component Removal and Replacement",
        status="in_progress",
        active_zones=["rear_pillar_separator"],
    )

    assert phase.phase == 3
    assert phase.status == "in_progress"
    assert phase.active_zones == ["rear_pillar_separator"]


def test_invalid_phase_status_rejected():
    with pytest.raises(ValueError, match="Invalid phase status"):
        PhaseState(
            phase=1,
            name="pre_repair_inspection",
            label="Pre-Repair Inspection",
            status="started",
        )


def test_create_action_state():
    action = ActionState(
        action_id="replace_component:rear_pillar_separator",
        phase=3,
        action_type="replace_component",
        target="rear_pillar_separator",
        status="pending",
        zone_refs=["rear_pillar_separator"],
        requires_qa=True,
    )

    assert action.action_id == "replace_component:rear_pillar_separator"
    assert action.requires_qa is True


def test_invalid_action_status_rejected():
    with pytest.raises(ValueError, match="Invalid action status"):
        ActionState(
            action_id="replace_component:rear_pillar_separator",
            phase=3,
            action_type="replace_component",
            target="rear_pillar_separator",
            status="waiting",
        )


def test_create_qa_gate_state():
    gate = QAGateState(
        gate_id="qa:material_compliance:rear_roof_rail_upper",
        category="material_compliance",
        priority="critical",
        status="open",
        related_phase=4,
        zone_refs=["rear_roof_rail_upper"],
        blocks_completion=True,
    )

    assert gate.status == "open"
    assert gate.blocks_completion is True


def test_invalid_qa_gate_status_rejected():
    with pytest.raises(ValueError, match="Invalid QA gate status"):
        QAGateState(
            gate_id="qa:material_compliance:rear_roof_rail_upper",
            category="material_compliance",
            priority="critical",
            status="unresolved",
        )


def test_create_zone_activation():
    zone = ZoneActivation(
        zone_id="rear_pillar_separator",
        label="rear pillar separator",
        status="active",
        active_phase=3,
        active_actions=["replace_component:rear_pillar_separator"],
    )

    assert zone.status == "active"
    assert zone.active_phase == 3


def test_invalid_zone_status_rejected():
    with pytest.raises(ValueError, match="Invalid zone status"):
        ZoneActivation(
            zone_id="rear_pillar_separator",
            label="rear pillar separator",
            status="current",
        )


def test_create_blocker():
    blocker = Blocker(
        blocker_id="blocker:qa:rear_roof_rail_upper_joining",
        type="qa_gate",
        severity="critical",
        status="open",
        blocks=["phase:4", "session_completion"],
        related_zones=["rear_roof_rail_upper"],
    )

    assert blocker.type == "qa_gate"
    assert blocker.severity == "critical"


def test_invalid_blocker_type_rejected():
    with pytest.raises(ValueError, match="Invalid blocker type"):
        Blocker(
            blocker_id="blocker:bad",
            type="unknown_type",
            severity="critical",
            status="open",
        )


def test_invalid_blocker_severity_rejected():
    with pytest.raises(ValueError, match="Invalid blocker severity"):
        Blocker(
            blocker_id="blocker:bad",
            type="qa_gate",
            severity="urgent",
            status="open",
        )


def test_invalid_blocker_status_rejected():
    with pytest.raises(ValueError, match="Invalid blocker status"):
        Blocker(
            blocker_id="blocker:bad",
            type="qa_gate",
            severity="critical",
            status="pending",
        )


def test_create_repair_event():
    event = RepairEvent(
        event_id="evt_001",
        timestamp="2026-01-01T10:15:00Z",
        event_type="action_completed",
        actor="technician",
        target_type="action",
        target_id="replace_component:rear_combination_adapter",
    )

    assert event.event_type == "action_completed"
    assert event.target_type == "action"


def test_invalid_event_type_rejected():
    with pytest.raises(ValueError, match="Invalid event type"):
        RepairEvent(
            event_id="evt_001",
            timestamp="2026-01-01T10:15:00Z",
            event_type="operation_done",
            actor="technician",
            target_type="action",
            target_id="replace_component:rear_combination_adapter",
        )


def test_invalid_event_target_type_rejected():
    with pytest.raises(ValueError, match="Invalid target type"):
        RepairEvent(
            event_id="evt_001",
            timestamp="2026-01-01T10:15:00Z",
            event_type="action_completed",
            actor="technician",
            target_type="operation",
            target_id="replace_component:rear_combination_adapter",
        )


def test_default_lists_are_isolated():
    first = PhaseState(phase=1, name="a", label="A", status="not_started")
    second = PhaseState(phase=2, name="b", label="B", status="not_started")

    first.active_zones.append("rear_side_outer_panel")

    assert second.active_zones == []


def test_create_repair_state_aggregate():
    session = RepairSession(
        session_id="session_001",
        oem="Honda",
        year=2025,
        model="Accord",
        operation="rear_side_outer_panel_replacement",
        status="in_progress",
        current_phase="component_replacement",
    )
    phase = PhaseState(
        phase=3,
        name="component_replacement",
        label="Component Removal and Replacement",
        status="in_progress",
    )
    action = ActionState(
        action_id="replace_component:rear_pillar_separator",
        phase=3,
        action_type="replace_component",
        target="rear_pillar_separator",
        status="pending",
    )

    state = RepairState(
        session=session,
        phases=[phase],
        actions=[action],
        next_recommended_actions=["replace_component:rear_pillar_separator"],
    )

    assert state.session.session_id == "session_001"
    assert len(state.phases) == 1
    assert len(state.actions) == 1
    assert state.next_recommended_actions == ["replace_component:rear_pillar_separator"]
    assert "advisory workflow projections" in state.interpretation_note
