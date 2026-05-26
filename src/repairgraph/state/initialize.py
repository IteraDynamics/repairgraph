from __future__ import annotations

from repairgraph.inference.qa_checklist import generate_qa_checklist
from repairgraph.inference.sequencing import build_operation_sequence
from repairgraph.state.schema import (
    ActionState,
    Blocker,
    PhaseState,
    QAGateState,
    RepairSession,
    RepairState,
    ZoneActivation,
)
from repairgraph.topology.builder import build_topology_graph


def _phase_actions(phase: dict) -> list[dict]:
    return phase.get("actions") or phase.get("operations") or []


def _checklist_items(qa_checklist: dict) -> list[dict]:
    if qa_checklist.get("items"):
        return qa_checklist["items"]

    items = []
    for group_key in ("checklist", "checks", "qa_items"):
        value = qa_checklist.get(group_key)
        if isinstance(value, list):
            items.extend(value)

    by_priority = qa_checklist.get("by_priority", {})
    if isinstance(by_priority, dict):
        for value in by_priority.values():
            if isinstance(value, list):
                items.extend(value)

    by_category = qa_checklist.get("by_category", {})
    if isinstance(by_category, dict):
        for value in by_category.values():
            if isinstance(value, list):
                items.extend(value)

    seen = set()
    deduped = []
    for item in items:
        marker = repr(sorted(item.items()))
        if marker not in seen:
            seen.add(marker)
            deduped.append(item)

    return deduped


def _action_id(action: dict) -> str:
    action_name = action.get("action") or action.get("type") or "unknown_action"
    target = (
        action.get("target")
        or action.get("zone")
        or action.get("method")
        or action.get("requirement")
        or action.get("component")
        or "general"
    )
    return f"{action_name}:{target}"


def _action_target(action: dict) -> str:
    return (
        action.get("target")
        or action.get("zone")
        or action.get("method")
        or action.get("requirement")
        or action.get("component")
        or "general"
    )


def _zone_refs_for_action(action: dict, topology_zone_ids: set[str]) -> list[str]:
    refs = []

    for key in ("target", "zone", "component"):
        value = action.get(key)
        if value in topology_zone_ids:
            refs.append(value)

    return sorted(set(refs))


def _requires_qa(action: dict) -> bool:
    action_name = action.get("action") or action.get("type") or ""
    return action_name in {
        "apply_joining_method",
        "apply_corrosion_protection",
        "verify",
    }


def _priority_blocks_completion(priority: str) -> bool:
    return priority in {"critical", "high"}


def _qa_gate_id(item: dict, index: int) -> str:
    category = item.get("category", "general")
    priority = item.get("priority", "unknown")
    return f"qa:{category}:{priority}:{index}"


def _qa_related_phase(item: dict) -> int | None:
    category = item.get("category", "")

    if category in {"material_compliance", "joining_verification"}:
        return 4
    if category == "corrosion_protection":
        return 5
    if category in {"dimensional_verification", "completeness"}:
        return 6

    return None


def _qa_zone_refs(item: dict, topology_zone_ids: set[str]) -> list[str]:
    refs = []

    for key in ("target", "component", "zone"):
        value = item.get(key)
        if value in topology_zone_ids:
            refs.append(value)

    for value in item.get("zone_refs", []) or []:
        if value in topology_zone_ids:
            refs.append(value)

    return sorted(set(refs))


def _qa_check_text(item: dict) -> str:
    return (
        item.get("check")
        or item.get("description")
        or item.get("item")
        or item.get("title")
        or item.get("recommendation")
        or "Review QA gate against OEM procedure."
    )


def _make_session(procedure: dict) -> RepairSession:
    return RepairSession(
        session_id=(
            f"session_{procedure.get('year')}_"
            f"{procedure.get('oem', 'unknown').lower()}_"
            f"{procedure.get('model', 'unknown').lower().replace('-', '_').replace(' ', '_')}_"
            f"{procedure.get('operation', 'repair')}"
        ),
        oem=procedure.get("oem", "unknown"),
        year=procedure.get("year", 0),
        model=procedure.get("model", "unknown"),
        operation=procedure.get("operation", "unknown"),
        status="not_started",
        current_phase=None,
    )


def _topology_actions(topology) -> list[dict]:
    actions = []

    for zone in topology.zones:
        action_type = "replace_component"
        if zone.zone_id in {"rear_side_outer_panel", "roof_panel"}:
            action_type = "panel_operation"

        actions.append(
            {
                "action": action_type,
                "target": zone.zone_id,
                "zone": zone.zone_id,
            }
        )

    return actions


def _make_phases(sequence: dict, topology) -> list[PhaseState]:
    topology_actions = _topology_actions(topology)
    phases = []

    for phase in sequence.get("phases", []):
        phase_actions = _phase_actions(phase)

        if not phase_actions and phase.get("name") == "component_replacement":
            phase_actions = topology_actions

        phases.append(
            PhaseState(
                phase=phase.get("phase"),
                name=phase.get("name"),
                label=phase.get("label"),
                status="not_started",
                active_zones=[],
                completed_actions=[],
                pending_actions=[_action_id(action) for action in phase_actions],
                blocked_by=[],
            )
        )

    return phases


def _make_actions(sequence: dict, topology, topology_zone_ids: set[str]) -> list[ActionState]:
    actions = []

    for phase in sequence.get("phases", []):
        phase_actions = _phase_actions(phase)

        if not phase_actions and phase.get("name") == "component_replacement":
            phase_actions = _topology_actions(topology)

        for action in phase_actions:
            action_name = action.get("action") or action.get("type") or "unknown_action"
            actions.append(
                ActionState(
                    action_id=_action_id(action),
                    phase=phase.get("phase"),
                    action_type=action_name,
                    target=_action_target(action),
                    status="pending",
                    zone_refs=_zone_refs_for_action(action, topology_zone_ids),
                    requires_qa=_requires_qa(action),
                    evidence={
                        "source_type": "derived_inference",
                        "basis": ["operation_sequence", "topology", action_name],
                        "confidence": "medium",
                        "requires_oem_verification": True,
                        "interpretation": "advisory",
                    },
                )
            )

    return actions


def _make_qa_gates(qa_checklist: dict, topology_zone_ids: set[str]) -> list[QAGateState]:
    gates = []

    for index, item in enumerate(_checklist_items(qa_checklist), start=1):
        priority = item.get("priority", "medium")
        gates.append(
            QAGateState(
                gate_id=_qa_gate_id(item, index),
                category=item.get("category", "general"),
                priority=priority,
                status="open",
                related_phase=_qa_related_phase(item),
                zone_refs=_qa_zone_refs(item, topology_zone_ids),
                check=_qa_check_text(item),
                blocks_completion=_priority_blocks_completion(priority),
                evidence=item.get("evidence"),
            )
        )

    return gates


def _make_zones(topology) -> list[ZoneActivation]:
    zones = []

    for zone in topology.zones:
        zones.append(
            ZoneActivation(
                zone_id=zone.zone_id,
                label=zone.label,
                status="inactive",
                active_phase=None,
                active_actions=[],
                material_classification=zone.material_classification,
                risk_flags=[],
            )
        )

    return zones


def _make_blockers(qa_gates: list[QAGateState]) -> list[Blocker]:
    blockers = []

    for gate in qa_gates:
        if not gate.blocks_completion:
            continue

        severity = "critical" if gate.priority == "critical" else "high"
        blocks = ["session_completion"]
        if gate.related_phase is not None:
            blocks.append(f"phase:{gate.related_phase}")

        blockers.append(
            Blocker(
                blocker_id=f"blocker:{gate.gate_id}",
                type="qa_gate",
                severity=severity,
                status="open",
                blocks=blocks,
                reason=f"QA gate remains open: {gate.check}",
                related_zones=gate.zone_refs,
                related_actions=[],
            )
        )

    return blockers


def initialize_repair_state(
    procedure: dict,
    structure: dict | None = None,
    corpus: list[dict] | None = None,
) -> RepairState:
    """
    Build an initial advisory RepairState from existing RepairGraph layers.

    This function does not apply events, mutate state, or advance workflow progress.
    All phases begin as not_started, all actions begin as pending, all zones begin
    as inactive, and blocking QA gates create open blockers.
    """
    corpus = corpus or []

    sequence = build_operation_sequence(procedure)
    topology = build_topology_graph(procedure, structure)
    topology_zone_ids = {zone.zone_id for zone in topology.zones}
    qa_checklist = generate_qa_checklist(procedure, structure, corpus)

    session = _make_session(procedure)
    phases = _make_phases(sequence, topology)
    actions = _make_actions(sequence, topology, topology_zone_ids)
    qa_gates = _make_qa_gates(qa_checklist, topology_zone_ids)
    zones = _make_zones(topology)
    blockers = _make_blockers(qa_gates)

    next_recommended_actions = []
    if phases:
        next_recommended_actions = list(phases[0].pending_actions)

    return RepairState(
        session=session,
        phases=phases,
        actions=actions,
        qa_gates=qa_gates,
        zones=zones,
        blockers=blockers,
        events=[],
        next_recommended_actions=next_recommended_actions,
        interpretation_note=(
            "Initial repair state is an advisory workflow projection derived "
            "from RepairGraph sequence, topology, QA, and normalized procedure data. "
            "It does not certify repair completion and requires OEM and shop-process verification."
        ),
    )
