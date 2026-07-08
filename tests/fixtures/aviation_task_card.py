"""
A minimal aviation maintenance task-card RepairState, built directly from
the generic state/schema.py dataclasses — no initialize_repair_state,
build_operation_sequence, generate_qa_checklist, or build_topology_graph.

Those collision helper functions are themselves coupled to collision
vocabulary (see docs/ARCHITECTURE_DERISK.md), so using them here would not
prove anything about the core's portability. This fixture proves the
opposite question: can RepairState/RepairEvent/project_repair_state/
RepairGraphCompiler represent and compile a genuinely different domain
using only their public, generic surface?

Scenario: an A320-200 100-hour landing gear inspection task card
(ATA chapter 32), loosely modeled on a real task-card structure —
three phases, four actions, two QA gates, one blocker.
"""
from __future__ import annotations

from repairgraph.state.schema import (
    ActionState,
    Blocker,
    PhaseState,
    QAGateState,
    RepairSession,
    RepairState,
    ZoneActivation,
)


def build_aviation_initial_state() -> RepairState:
    session = RepairSession(
        session_id="session_a320_n12345_tc_32_11_04",
        # RepairSession has no aviation-native fields (aircraft_type,
        # registration, task_card_id) — it only has oem/year/model/operation,
        # which are collision vocabulary. Reused here as the closest-fit slots;
        # flagged in docs/ARCHITECTURE_DERISK.md as a real coupling point.
        oem="Airbus",
        year=0,
        model="A320-200",
        operation="tc_32_11_04_landing_gear_100hr_inspection",
        status="not_started",
    )

    phases = [
        PhaseState(
            phase=1, name="pre_inspection", label="Pre-Inspection Setup",
            status="not_started",
            pending_actions=["chock_aircraft:main_gear", "review_ad:AD-2024-11-07"],
        ),
        PhaseState(
            phase=2, name="gear_inspection", label="Landing Gear Inspection",
            status="not_started",
            pending_actions=["inspect_component:main_gear_strut", "torque_check:main_gear_axle_nut"],
        ),
        PhaseState(
            phase=3, name="closeout", label="Closeout and Return to Service",
            status="not_started",
            pending_actions=[],
        ),
    ]

    actions = [
        ActionState(
            action_id="chock_aircraft:main_gear", phase=1,
            action_type="chock_aircraft", target="main_gear", status="pending",
            zone_refs=["main_gear"],
        ),
        ActionState(
            action_id="review_ad:AD-2024-11-07", phase=1,
            action_type="review_airworthiness_directive", target="AD-2024-11-07",
            status="pending", requires_qa=True,
        ),
        ActionState(
            action_id="inspect_component:main_gear_strut", phase=2,
            action_type="inspect_component", target="main_gear_strut",
            status="pending", zone_refs=["main_gear_strut"], requires_qa=True,
        ),
        ActionState(
            action_id="torque_check:main_gear_axle_nut", phase=2,
            action_type="torque_check", target="main_gear_axle_nut",
            status="pending", zone_refs=["main_gear_axle_nut"], requires_qa=True,
        ),
    ]

    qa_gates = [
        QAGateState(
            gate_id="qa:airworthiness:critical:1", category="airworthiness",
            priority="critical", status="open", related_phase=1,
            check="Confirm AD-2024-11-07 applicability and compliance status.",
            blocks_completion=True,
        ),
        QAGateState(
            gate_id="qa:torque_verification:high:1", category="torque_verification",
            priority="high", status="open", related_phase=2,
            zone_refs=["main_gear_axle_nut"],
            check="Verify main gear axle nut torque against task card spec.",
            blocks_completion=True,
        ),
    ]

    zones = [
        ZoneActivation(zone_id="main_gear", label="Main Landing Gear", status="inactive"),
        ZoneActivation(zone_id="main_gear_strut", label="Main Gear Strut", status="inactive"),
        ZoneActivation(zone_id="main_gear_axle_nut", label="Main Gear Axle Nut", status="inactive"),
    ]

    blockers = [
        Blocker(
            blocker_id="blocker:qa:airworthiness:critical:1", type="qa_gate",
            severity="critical", status="open",
            blocks=["session_completion", "phase:1"],
            reason="Airworthiness directive AD-2024-11-07 not yet reviewed.",
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
        next_recommended_actions=list(phases[0].pending_actions),
        interpretation_note=(
            "Initial task-card state is an advisory workflow projection. "
            "It does not certify airworthiness and requires sign-off by a "
            "qualified inspector against the applicable maintenance manual."
        ),
    )
