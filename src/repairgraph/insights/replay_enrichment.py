"""Replay step enrichment — adds plain-English significance to each event."""
from __future__ import annotations

_SIGNIFICANCE: dict[str, str] = {
    "session_started": "Repair session opened. The workflow clock starts here — all phases and actions are now tracked.",
    "phase_started": "A new repair phase is now active. Technicians should begin work on the tasks listed for this phase.",
    "phase_completed": "This phase is fully closed — all actions complete and QA gates passed. Downstream phases can now begin.",
    "action_started": "A billable repair action has begun. Time and material tracking should be active.",
    "action_completed": "Repair procedure verified complete. This reduces open action count and may unblock dependent phases.",
    "action_blocked": "A repair action cannot proceed. Investigate the blocker before assigning technician time to this task.",
    "action_marked_not_applicable": "This action is confirmed not needed for this vehicle. Workflow adjusted accordingly.",
    "qa_gate_opened": "A quality hold is now active. Work in the affected zone should pause until the gate is cleared.",
    "qa_gate_passed": "Quality check passed and documented. This gate no longer blocks progression.",
    "qa_gate_failed": "Quality check failed. The associated work must be redone or reviewed before repair can continue.",
    "qa_gate_marked_not_applicable": "This quality check is not required for this repair scope. Gate closed without action.",
    "blocker_added": "A new hold has been placed on the repair. Review the blocker reason before scheduling further work.",
    "blocker_resolved": "A blocker has been cleared. Dependent actions and phases may now resume.",
    "session_completed": "All phases and QA gates are closed. Repair is complete and ready for final delivery inspection.",
    "session_cancelled": "Repair session was cancelled. No further workflow actions will be tracked.",
}


def enrich_replay_step(step: dict) -> dict:
    """Return step dict with a 'significance' key added.

    Significance is a plain-English explanation of why this event matters
    operationally — the 'So what?' for shop supervisors reviewing the audit trail.
    """
    event = step.get("event", {})
    event_type = event.get("event_type", "")
    diff = step.get("diff_summary", {})

    base = _SIGNIFICANCE.get(event_type, "State update recorded.")

    # Augment with diff context when available
    additions = []
    if diff.get("actions_completed"):
        additions.append(f"Actions completed: {', '.join(diff['actions_completed'])}.")
    if diff.get("blockers_resolved"):
        additions.append(f"Blockers resolved: {', '.join(diff['blockers_resolved'])}.")
    if diff.get("blockers_added"):
        additions.append(f"New blockers: {', '.join(diff['blockers_added'])}.")
    if diff.get("phases_changed"):
        phase_info = diff["phases_changed"]
        if isinstance(phase_info, list):
            additions.append(f"Phase changes: {', '.join(str(p) for p in phase_info)}.")

    significance = base
    if additions:
        significance = base.rstrip(".") + ". " + " ".join(additions)

    return {**step, "significance": significance}
