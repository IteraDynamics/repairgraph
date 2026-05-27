"""
Mermaid diagram export for RepairGraph repair state.

Produces deterministic, text-based Mermaid visualizations of workflow timeline,
phase flow, blockers, and zone activation from a RepairState snapshot.

All diagrams are advisory workflow intelligence. They do not certify repair
completion, OEM compliance, or repair quality.
"""
from __future__ import annotations

import re

from repairgraph.state.schema import RepairState


def _mmd_id(s: str) -> str:
    """Sanitize a string for use as a Mermaid node or participant ID."""
    return re.sub(r"[^a-zA-Z0-9_]", "_", s)


def _short_ts(ts: str) -> str:
    """Extract the time portion (HH:MM:SS) from an ISO timestamp."""
    if "T" in ts:
        time_part = ts.split("T")[1].rstrip("Z")
        return time_part[:8]
    return ts


def build_workflow_timeline_mermaid(state: RepairState) -> str:
    """Build a Mermaid sequenceDiagram showing the event ledger as a workflow timeline.

    Each event appears as a message from the actor participant to the target-type
    participant, labelled with the event type and timestamp. Participants are
    declared in encounter order (actors) and target-type order (system components).

    Returns a minimal placeholder diagram if no events are recorded.
    """
    if not state.events:
        lines = [
            "sequenceDiagram",
            f"    %% Advisory: RepairGraph workflow timeline"
            f" ({state.session.year} {state.session.oem} {state.session.model})",
            "    %% No events recorded",
        ]
        return "\n".join(lines)

    actor_order: list[tuple[str, str]] = []
    seen_actors: set[str] = set()
    target_types: set[str] = set()

    for event in state.events:
        actor_id = _mmd_id(event.actor)
        if actor_id not in seen_actors:
            actor_order.append((actor_id, event.actor))
            seen_actors.add(actor_id)
        target_types.add(event.target_type)

    lines = [
        "sequenceDiagram",
        f"    %% Advisory: RepairGraph workflow timeline"
        f" ({state.session.year} {state.session.oem} {state.session.model})",
    ]

    for actor_id, actor_label in actor_order:
        lines.append(f"    participant {actor_id} as {actor_label}")

    for ttype in sorted(target_types):
        lines.append(f"    participant {_mmd_id(ttype)} as {ttype}")

    for event in state.events:
        actor_id = _mmd_id(event.actor)
        target_p = _mmd_id(event.target_type)
        ts = _short_ts(event.timestamp)
        label = f"{event.event_type} [{ts}]"
        lines.append(f"    {actor_id}->>{target_p}: {label}")

    return "\n".join(lines)


def build_phase_flow_mermaid(state: RepairState) -> str:
    """Build a Mermaid flowchart showing repair phases in sequence with status styling.

    Phases are rendered as nodes in phase order, connected by directed edges.
    Node colour reflects phase status (in_progress=amber, complete=green,
    blocked=red, not_started=grey).
    """
    phases_sorted = sorted(state.phases, key=lambda p: p.phase)

    lines = [
        "flowchart LR",
        f"    %% Advisory: RepairGraph phase flow"
        f" ({state.session.year} {state.session.oem} {state.session.model})",
    ]

    phase_node_ids: list[str] = []
    status_groups: dict[str, list[str]] = {}

    for phase in phases_sorted:
        node_id = f"P{phase.phase}"
        label = f"{phase.label}\\n{phase.status}"
        lines.append(f'    {node_id}["{label}"]')
        phase_node_ids.append(node_id)
        status_groups.setdefault(phase.status, []).append(node_id)

    for i in range(len(phase_node_ids) - 1):
        lines.append(f"    {phase_node_ids[i]} --> {phase_node_ids[i + 1]}")

    lines.append("    classDef in_progress fill:#f90,stroke:#666,color:#000")
    lines.append("    classDef complete fill:#9f9,stroke:#666,color:#000")
    lines.append("    classDef blocked fill:#f66,stroke:#666,color:#000")
    lines.append("    classDef ready_for_review fill:#9cf,stroke:#666,color:#000")
    lines.append("    classDef not_started fill:#ddd,stroke:#666,color:#000")
    lines.append("    classDef not_applicable fill:#eee,stroke:#888,color:#888")

    for status, node_ids in status_groups.items():
        cls = status.replace(" ", "_")
        lines.append(f"    class {','.join(node_ids)} {cls}")

    return "\n".join(lines)


def build_blocker_flow_mermaid(state: RepairState) -> str:
    """Build a Mermaid flowchart showing blockers and their targets.

    Each blocker node shows its ID, type, severity, and status. Directed edges
    connect each blocker to what it blocks. Open blockers are coloured red;
    resolved blockers are coloured green.
    """
    lines = [
        "flowchart TD",
        f"    %% Advisory: RepairGraph blocker flow"
        f" ({state.session.year} {state.session.oem} {state.session.model})",
    ]

    if not state.blockers:
        lines.append('    NB["No blockers"]')
        return "\n".join(lines)

    open_node_ids: list[str] = []
    resolved_node_ids: list[str] = []

    for blocker in state.blockers:
        node_id = _mmd_id(blocker.blocker_id)
        label = (
            f"{blocker.blocker_id[:24]}\\n"
            f"{blocker.type} / {blocker.severity}\\n"
            f"{blocker.status.upper()}"
        )
        lines.append(f'    {node_id}["{label}"]')
        if blocker.status == "open":
            open_node_ids.append(node_id)
        else:
            resolved_node_ids.append(node_id)

    seen_targets: set[str] = set()
    for blocker in state.blockers:
        b_node_id = _mmd_id(blocker.blocker_id)
        for block_target in blocker.blocks:
            target_node_id = _mmd_id(block_target)
            if target_node_id not in seen_targets:
                lines.append(f'    {target_node_id}(("{block_target}"))')
                seen_targets.add(target_node_id)
            edge_label = "blocks" if blocker.status == "open" else "resolved"
            lines.append(f"    {b_node_id} -->|{edge_label}| {target_node_id}")

    lines.append("    classDef open_blocker fill:#f66,stroke:#333,color:#000")
    lines.append("    classDef resolved_blocker fill:#9f9,stroke:#333,color:#000")

    if open_node_ids:
        lines.append(f"    class {','.join(open_node_ids)} open_blocker")
    if resolved_node_ids:
        lines.append(f"    class {','.join(resolved_node_ids)} resolved_blocker")

    return "\n".join(lines)


def build_zone_activation_mermaid(state: RepairState) -> str:
    """Build a Mermaid flowchart showing zone activation states.

    Each zone appears as a node labelled with its name, optional material
    classification, and current status. Node colour reflects activation state
    (active=amber, complete=green, blocked=red, inactive=grey, pending=yellow).
    """
    lines = [
        "flowchart LR",
        f"    %% Advisory: RepairGraph zone activation"
        f" ({state.session.year} {state.session.oem} {state.session.model})",
    ]

    if not state.zones:
        lines.append('    NZ["No zones"]')
        return "\n".join(lines)

    status_groups: dict[str, list[str]] = {}

    for zone in state.zones:
        node_id = _mmd_id(zone.zone_id)
        material_line = f"\\n{zone.material_classification}" if zone.material_classification else ""
        label = f"{zone.label}{material_line}\\n{zone.status}"
        lines.append(f'    {node_id}["{label}"]')
        status_groups.setdefault(zone.status, []).append(node_id)

    lines.append("    classDef active fill:#f90,stroke:#666,color:#000")
    lines.append("    classDef complete fill:#9f9,stroke:#666,color:#000")
    lines.append("    classDef blocked fill:#f66,stroke:#666,color:#000")
    lines.append("    classDef inactive fill:#ddd,stroke:#666,color:#000")
    lines.append("    classDef pending fill:#ff9,stroke:#666,color:#000")

    for status, node_ids in status_groups.items():
        lines.append(f"    class {','.join(node_ids)} {status}")

    return "\n".join(lines)
