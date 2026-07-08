"""
Fleet summary — a shop-floor view across every tracked job.

Aggregates the per-vehicle progress projection (state/journal.py +
state/project.py) into one summary across all vehicles present in
data/normalized/. This is the first surface that answers a manager's
question rather than a technician's: not "what's next on this job" but
"which jobs need attention right now."

Deliberately domain-neutral: "job" here is a vehicle repair session today,
but the aggregation only depends on RepairState (phases/actions/qa_gates/
blockers), which is the same generic vocabulary any future domain adapter
(aviation, industrial maintenance, ...) would populate. Nothing here assumes
collision-repair specifics.

No database — this scans the same file-based stores everything else uses
(data/normalized/, data/sessions/) on each request. Fleets of the size this
tool is designed for (a shop's active jobs) make that fine; the moment fleet
size makes recompiling state per request costly is the moment persistence
should move to something with an index, not before.
"""
from __future__ import annotations

from typing import Any

from repairgraph.core.vehicle_store import list_available_vehicles
from repairgraph.state.journal import load_session_events
from repairgraph.state.project import project_repair_state

_ADVISORY = (
    "Fleet summary outputs are advisory workflow intelligence aggregated across "
    "tracked jobs. They do not certify repair completion, OEM compliance, or "
    "repair quality. Each job requires verification by a qualified technician "
    "against its applicable OEM procedures."
)


def _job_status(state) -> str:
    """Coarse status bucket for dashboard grouping."""
    if state.session.status in ("complete", "ready_for_review"):
        return "ready"
    if state.session.status == "blocked":
        return "blocked"
    if state.session.status == "cancelled":
        return "cancelled"
    if any(a.status in ("in_progress", "complete") for a in state.actions) or any(
        g.status not in ("open",) for g in state.qa_gates
    ):
        return "in_progress"
    return "not_started"


def _job_summary(vehicle: dict[str, Any]) -> dict[str, Any] | None:
    """Build one job's fleet-row summary. Returns None if the procedure or
    structure cannot be loaded (never lets one bad job break the fleet view)."""
    oem, year, model = vehicle["oem"], vehicle["year"], vehicle["model"]

    try:
        from repairgraph.query.loader import load_procedure, load_vehicle_structure
        from repairgraph.state.initialize import initialize_repair_state

        procedure = load_procedure(oem, year, model)
        if procedure is None:
            return None
        structure = load_vehicle_structure(oem, year, model)
        initial_state = initialize_repair_state(procedure, structure)
    except Exception:
        return None

    events = load_session_events(oem, year, model)
    if events:
        try:
            state = project_repair_state(initial_state, events)
        except ValueError:
            state = initial_state
            events = []
    else:
        state = initial_state

    open_gates = [g for g in state.qa_gates if g.status == "open"]
    open_blockers = [b for b in state.blockers if b.status == "open"]
    critical_open = [
        g for g in open_gates if g.blocks_completion and g.priority == "critical"
    ]

    return {
        "oem": oem,
        "year": year,
        "model": model,
        "operation": vehicle.get("operation", ""),
        "source": vehicle.get("source", "unknown"),
        "status": _job_status(state),
        "session_status": state.session.status,
        "events_recorded": len(events),
        "open_qa_gates": len(open_gates),
        "critical_open_qa_gates": len(critical_open),
        "open_blockers": len(open_blockers),
        "pending_actions": sum(1 for a in state.actions if a.status == "pending"),
        "complete_actions": sum(1 for a in state.actions if a.status == "complete"),
        "total_actions": len(state.actions),
        "next_recommended_action": (
            state.next_recommended_actions[0] if state.next_recommended_actions else None
        ),
        "review_link": f"/internal/review?oem={oem}&year={year}&model={model}",
        "progress_link": f"/internal/review/progress/ui?oem={oem}&year={year}&model={model}",
    }


def build_fleet_summary() -> dict[str, Any]:
    """Return a fleet-wide summary across every job in data/normalized/.

    Jobs are grouped by coarse status (blocked / in_progress / not_started /
    ready / cancelled) so a manager can see where attention is needed without
    opening each job individually.
    """
    vehicles = list_available_vehicles()
    jobs: list[dict[str, Any]] = []

    for vehicle in vehicles:
        summary = _job_summary(vehicle)
        if summary is not None:
            jobs.append(summary)

    by_status: dict[str, list[dict[str, Any]]] = {
        "blocked": [], "in_progress": [], "not_started": [], "ready": [], "cancelled": [],
    }
    for job in jobs:
        by_status[job["status"]].append(job)

    # Most urgent first within a bucket: more open blockers/gates surfaces first.
    for bucket in by_status.values():
        bucket.sort(key=lambda j: (-j["open_blockers"], -j["open_qa_gates"]))

    return {
        "job_count": len(jobs),
        "counts_by_status": {status: len(bucket) for status, bucket in by_status.items()},
        "jobs_by_status": by_status,
        "jobs": jobs,
        "advisory": _ADVISORY,
    }
