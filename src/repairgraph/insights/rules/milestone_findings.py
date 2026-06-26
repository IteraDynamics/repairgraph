"""Milestone / positive progress insight rules."""
from __future__ import annotations

from repairgraph.insights.schema import InsightFinding
from repairgraph.state.schema import RepairState


def completed_actions(state: RepairState) -> list[InsightFinding]:
    complete = [a for a in state.actions if a.status == "complete"]
    if not complete:
        return []
    total = len(state.actions)
    pct = int(100 * len(complete) / total) if total else 0
    action_types = sorted({a.action_type for a in complete})
    return [InsightFinding(
        finding_id="milestone_completed_actions",
        severity="informational",
        category="milestone",
        title=f"{len(complete)} of {total} repair actions completed ({pct}%)",
        explanation=(
            f"{len(complete)} repair procedures are complete including: {', '.join(action_types[:5])}."
            + (" And others." if len(action_types) > 5 else "")
        ),
        recommended_action="Continue with next planned actions per phase sequence.",
        supporting_evidence=(
            f"complete={len(complete)}",
            f"total={total}",
            f"pct={pct}%",
        ),
        confidence="high",
    )]


def next_recommended_action(state: RepairState) -> list[InsightFinding]:
    if not state.next_recommended_actions:
        return []
    next_act = state.next_recommended_actions[0]
    return [InsightFinding(
        finding_id="milestone_next_action",
        severity="informational",
        category="milestone",
        title=f"Next recommended technician action: {next_act.replace('_', ' ')}",
        explanation=(
            f"Based on current repair state, the next action is: {next_act.replace('_', ' ')}. "
            f"{'Additional actions queued: ' + str(len(state.next_recommended_actions) - 1) if len(state.next_recommended_actions) > 1 else ''}"
        ),
        recommended_action=f"Assign technician to: {next_act.replace('_', ' ')}",
        supporting_evidence=(
            f"next_action={next_act}",
            f"queued_actions={len(state.next_recommended_actions)}",
        ),
        confidence="high",
    )]


def phases_complete(state: RepairState) -> list[InsightFinding]:
    complete = [p for p in state.phases if p.status == "complete"]
    if not complete:
        return []
    total = len([p for p in state.phases if p.status != "not_applicable"])
    labels = [p.label for p in complete]
    return [InsightFinding(
        finding_id="milestone_phases_complete",
        severity="informational",
        category="milestone",
        title=f"{len(complete)} repair phase{'s' if len(complete) > 1 else ''} successfully completed",
        explanation=f"Completed phases: {', '.join(labels)}. {total - len(complete)} phase(s) remain.",
        recommended_action="Advance to the next in-progress phase.",
        supporting_evidence=(
            f"complete_phases={len(complete)}",
            f"total_applicable_phases={total}",
        ),
        confidence="high",
    )]


def repair_packet_complete(manifest_dict: dict) -> list[InsightFinding]:
    if manifest_dict.get("readiness") != "ready":
        return []
    oem = manifest_dict.get("detected_packet", {}).get("oem", "OEM")
    model = manifest_dict.get("detected_packet", {}).get("model", "")
    return [InsightFinding(
        finding_id="milestone_packet_complete",
        severity="informational",
        category="milestone",
        title=f"OEM repair packet complete — {oem} {model}",
        explanation=(
            f"All required documents are present and classified for {oem} {model}. "
            "The repair packet is ready to support the full workflow."
        ),
        recommended_action="Proceed with workflow — packet is complete.",
        supporting_evidence=(
            f"readiness=ready",
            f"oem={oem}",
            f"model={model}",
        ),
        confidence="high",
    )]
