"""
Topology viewer payload builder for RepairGraph.

Assembles a JSON-serializable payload for the interactive topology viewer
by combining RepairState workflow intelligence with spatial region mapping.
Reuses existing timeline, replay, and state modules without duplicating logic.
"""
from __future__ import annotations

from typing import Any

from repairgraph.state.blockers import summarize_blockers
from repairgraph.state.export_json import ADVISORY_NOTE
from repairgraph.state.next_actions import summarize_next_actions
from repairgraph.state.replay import build_state_diff, replay_repair_state, summarize_state_diff
from repairgraph.state.schema import RepairEvent, RepairState
from repairgraph.state.timeline import (
    build_action_timeline,
    build_event_timeline,
    build_phase_timeline,
)
from repairgraph.viewer.topology_layout import (
    ACTION_STATUS_COLORS,
    PHASE_STATUS_COLORS,
    QA_STATUS_COLORS,
    VEHICLE_REGIONS,
    ZONE_STATUS_COLORS,
)

_GENERATED_BY = "repairgraph.viewer.topology_payload"


def _match_region_to_zones(region: dict, zones: list) -> list[dict]:
    """Return zone records whose zone_id matches any of the region's zone_keys."""
    keys = [k.lower() for k in region["zone_keys"]]
    matched = []
    for z in zones:
        zid = z.get("zone_id", "").lower()
        if any(k in zid for k in keys):
            matched.append(z)
    return matched


def _zone_status_for_region(matched_zones: list[dict]) -> str:
    """Derive representative status for a region from its matched zones.

    Priority: blocked > active > pending > complete > inactive
    """
    priority = ["blocked", "active", "pending", "complete", "inactive"]
    statuses = {z.get("status", "inactive") for z in matched_zones}
    if not statuses:
        return "inactive"
    for p in priority:
        if p in statuses:
            return p
    return "inactive"


def _serialize_zone(z: Any) -> dict:
    return {
        "zone_id": z.zone_id,
        "label": z.label,
        "status": z.status,
        "active_phase": z.active_phase,
        "active_actions": list(z.active_actions),
        "material_classification": z.material_classification,
        "risk_flags": list(z.risk_flags),
    }


def _serialize_action(a: Any) -> dict:
    return {
        "action_id": a.action_id,
        "phase": a.phase,
        "action_type": a.action_type,
        "target": a.target,
        "status": a.status,
        "zone_refs": list(a.zone_refs),
        "requires_qa": a.requires_qa,
    }


def _serialize_phase(p: Any) -> dict:
    return {
        "phase": p.phase,
        "name": p.name,
        "label": p.label,
        "status": p.status,
        "active_zones": list(p.active_zones),
        "completed_actions": list(p.completed_actions),
        "pending_actions": list(p.pending_actions),
        "blocked_by": list(p.blocked_by),
    }


def _serialize_qa_gate(g: Any) -> dict:
    return {
        "gate_id": g.gate_id,
        "category": g.category,
        "priority": g.priority,
        "status": g.status,
        "related_phase": g.related_phase,
        "zone_refs": list(g.zone_refs),
        "check": g.check,
        "blocks_completion": g.blocks_completion,
    }


def _serialize_blocker(b: Any) -> dict:
    return {
        "blocker_id": b.blocker_id,
        "type": b.type,
        "severity": b.severity,
        "status": b.status,
        "blocks": list(b.blocks),
        "reason": b.reason,
        "related_zones": list(b.related_zones),
        "related_actions": list(b.related_actions),
    }


def _serialize_event(e: Any) -> dict:
    return {
        "event_id": e.event_id,
        "timestamp": e.timestamp,
        "event_type": e.event_type,
        "actor": e.actor,
        "target_type": e.target_type,
        "target_id": e.target_id,
        "notes": e.notes,
    }


def build_region_map(state: RepairState) -> list[dict]:
    """Build a list of viewer region records with status derived from RepairState zones."""
    zones_serial = [_serialize_zone(z) for z in state.zones]
    regions = []
    for reg in VEHICLE_REGIONS:
        matched = _match_region_to_zones(reg, zones_serial)
        status = _zone_status_for_region(matched)
        color = ZONE_STATUS_COLORS.get(status, ZONE_STATUS_COLORS["inactive"])
        regions.append({
            "id": reg["id"],
            "label": reg["label"],
            "status": status,
            "fill": color["fill"],
            "stroke": color["stroke"],
            "matched_zones": matched,
            "zone_count": len(matched),
        })
    return regions


def build_inspector_payload(state: RepairState, region_id: str) -> dict:
    """Return the inspector panel payload for a specific region_id.

    Includes all relevant procedures, actions, phases, QA gates, blockers,
    and next actions for that region, drawing directly from RepairState.
    """
    region_def = next((r for r in VEHICLE_REGIONS if r["id"] == region_id), None)
    if region_def is None:
        return {"error": f"Unknown region: {region_id}"}

    zones_serial = [_serialize_zone(z) for z in state.zones]
    matched_zones = _match_region_to_zones(region_def, zones_serial)
    matched_zone_ids = {z["zone_id"] for z in matched_zones}

    # Actions touching this region's zones
    region_actions = [
        _serialize_action(a)
        for a in state.actions
        if matched_zone_ids.intersection(set(a.zone_refs))
    ]
    action_ids = {a["action_id"] for a in region_actions}

    # Phases that contain these actions
    phase_nums = {a["phase"] for a in region_actions}
    region_phases = [_serialize_phase(p) for p in state.phases if p.phase in phase_nums]

    # QA gates for these zones
    region_qa = [
        _serialize_qa_gate(g)
        for g in state.qa_gates
        if matched_zone_ids.intersection(set(g.zone_refs))
    ]

    # Blockers for these zones or actions
    region_blockers = [
        _serialize_blocker(b)
        for b in state.blockers
        if (
            matched_zone_ids.intersection(set(b.related_zones))
            or action_ids.intersection(set(b.related_actions))
        )
    ]

    # Dependencies: zone relationships from events/zones
    next_actions_for_region = [
        a_id for a_id in state.next_recommended_actions if a_id in action_ids
    ]

    return {
        "region_id": region_id,
        "region_label": region_def["label"],
        "zones": matched_zones,
        "procedures": region_actions,
        "phases": region_phases,
        "qa_gates": region_qa,
        "blockers": region_blockers,
        "next_actions": next_actions_for_region,
        "action_count": len(region_actions),
        "open_blocker_count": sum(1 for b in region_blockers if b["status"] == "open"),
        "open_qa_count": sum(1 for g in region_qa if g["status"] in {"open", "in_review"}),
    }


def build_replay_snapshots(initial: RepairState, events: list[RepairEvent]) -> list[dict]:
    """Build ordered replay snapshots for the timeline scrubber.

    Each snapshot contains the event that triggered it, a state summary,
    and region map so the viewer can update without re-computing.
    """
    snapshots = replay_repair_state(initial, events)
    result = []
    prev = initial
    for i, (event, snap) in enumerate(zip(events, snapshots)):
        diff = build_state_diff(prev, snap)
        diff_summary = summarize_state_diff(diff)
        result.append({
            "step": i + 1,
            "event": _serialize_event(event),
            "region_map": build_region_map(snap),
            "state_summary": {
                "session_status": snap.session.status,
                "active_phase_ids": [p.name for p in snap.phases if p.status == "in_progress"],
                "completed_action_count": sum(1 for a in snap.actions if a.status == "complete"),
                "open_blocker_count": sum(1 for b in snap.blockers if b.status == "open"),
                "open_qa_count": sum(1 for g in snap.qa_gates if g.status in {"open", "in_review"}),
                "next_recommended_actions": list(snap.next_recommended_actions),
            },
            "diff_summary": diff_summary,
        })
        prev = snap
    return result


def build_topology_viewer_payload(
    initial: RepairState,
    events: list[RepairEvent],
) -> dict:
    """Assemble the complete topology viewer payload.

    Combines:
    - session metadata
    - current (projected) region map
    - event timeline
    - phase / action timelines
    - replay snapshots (one per event)
    - inspector payloads for all regions
    - legend definitions
    - filter metadata
    """
    from repairgraph.state.project import project_repair_state

    projected = project_repair_state(initial, events)

    # Pre-build inspector payloads for all regions
    inspector_payloads = {
        reg["id"]: build_inspector_payload(projected, reg["id"])
        for reg in VEHICLE_REGIONS
    }

    event_timeline = build_event_timeline(projected)
    phase_timeline = build_phase_timeline(projected)
    action_timeline = build_action_timeline(projected)
    replay_snapshots = build_replay_snapshots(initial, events)

    initial_region_map = build_region_map(initial)

    return {
        "schema_name": "repairgraph.viewer.topology",
        "generated_by": _GENERATED_BY,
        "advisory": True,
        "advisory_note": ADVISORY_NOTE,
        "session": {
            "session_id": projected.session.session_id,
            "oem": projected.session.oem,
            "year": projected.session.year,
            "model": projected.session.model,
            "operation": projected.session.operation,
            "status": projected.session.status,
            "current_phase": projected.session.current_phase,
        },
        "region_map": build_region_map(projected),
        "initial_region_map": initial_region_map,
        "regions_meta": [
            {"id": r["id"], "label": r["label"], "zone_keys": r["zone_keys"]}
            for r in VEHICLE_REGIONS
        ],
        "event_timeline": event_timeline,
        "phase_timeline": phase_timeline,
        "action_timeline": action_timeline,
        "replay_snapshots": replay_snapshots,
        "inspector_payloads": inspector_payloads,
        "workflow_summary": {
            "phase_count": len(projected.phases),
            "action_count": len(projected.actions),
            "qa_gate_count": len(projected.qa_gates),
            "blocker_count": len(projected.blockers),
            "event_count": len(projected.events),
            "open_blocker_count": sum(1 for b in projected.blockers if b.status == "open"),
            "complete_action_count": sum(1 for a in projected.actions if a.status == "complete"),
        },
        "blockers_summary": summarize_blockers(projected),
        "next_actions_summary": summarize_next_actions(projected),
        "legend": {
            "zone_states": [
                {"status": k, "color": v["fill"], "border": v["stroke"], "label": v["label"]}
                for k, v in ZONE_STATUS_COLORS.items()
            ],
            "action_states": [
                {"status": k, "color": v}
                for k, v in ACTION_STATUS_COLORS.items()
            ],
            "qa_states": [
                {"status": k, "color": v}
                for k, v in QA_STATUS_COLORS.items()
            ],
            "phase_states": [
                {"status": k, "color": v}
                for k, v in PHASE_STATUS_COLORS.items()
            ],
        },
    }
