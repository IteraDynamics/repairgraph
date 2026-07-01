"""
Execution Package Engine v0.

The Operational Planner answers: "What is the highest-leverage thing to do next?"
The Execution Package answers: "What does it mean to actually perform that work?"

An ExecutionPackage converts a single Next Best Action from the OperationalPlan
into a structured, executable unit of work.  It answers five questions:

  1. What are we trying to accomplish?      → objective
  2. What must already be true?             → prerequisites
  3. What must be verified?                 → required_verifications
  4. What work is performed?                → execution_steps
  5. How do we know we're done?             → completion_criteria
  6. What becomes available afterwards?     → expected_unlocks

Platform principles
-------------------
- ExecutionPackage is domain-agnostic.  No collision vocabulary lives here.
- Domain projections (CollisionWorkPackage) translate for specific audiences.
- The engine never invents OEM instructions or repair procedures.
- All outputs are advisory.  Qualified technician review is always required.

Inputs
------
- OperationalPlan   (from operational_planner.build_operational_plan)
- OperationalNarrative (from narrator.build_narrative)
- OperationalModel  (for domain context, state detail)

The engine does not re-run planner logic or duplicate Root Cause Analysis.
"""
from __future__ import annotations

import re
import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from repairgraph.core.operational_model import OperationalModel
from repairgraph.review.narrator import OperationalNarrative
from repairgraph.review.operational_planner import OperationalPlan

_ADVISORY = (
    "This execution package is advisory workflow intelligence. "
    "It organizes work but does not replace OEM repair procedures or certify "
    "repair completion, compliance, or quality. "
    "All steps require verification by a qualified technician against "
    "applicable OEM procedures."
)

# ---------------------------------------------------------------------------
# Generic prerequisite / verification / step / criterion builders
# ---------------------------------------------------------------------------

_QA_CATEGORY_PREREQS: dict[str, str] = {
    "material_compliance": "OEM material classification and joining method confirmed for this repair area.",
    "joining_compliance": "Approved joining method verified against OEM procedure.",
    "corrosion_protection": "Corrosion protection requirements reviewed and materials available.",
    "component_replacement": "Replacement component authorization confirmed against OEM procedure.",
    "dimensional_verification": "Body dimensional baseline recorded prior to repair.",
    "calibration": "ADAS calibration requirements identified and equipment available.",
    "documentation": "Repair documentation package complete and available.",
    "inspection": "Inspection prerequisites satisfied and area accessible.",
}

_QA_CATEGORY_VERIFICATIONS: dict[str, str] = {
    "material_compliance": "Confirm OEM material specification and joining method before proceeding.",
    "joining_compliance": "Verify each joining method (spot weld, plug weld, adhesive, etc.) against OEM specification.",
    "corrosion_protection": "Verify sealer, adhesive, and undercoating application points per OEM procedure.",
    "component_replacement": "Verify replacement requirements for all affected components against OEM procedure.",
    "dimensional_verification": "Confirm sheet thickness, tensile strength, zinc treatment, and body dimensions.",
    "calibration": "Confirm calibration targets and procedures are available before final verification.",
    "documentation": "Verify all required documentation is complete and signed off.",
    "inspection": "Complete required inspection checklist before advancing workflow.",
}

_BLOCKER_TYPE_PREREQS: dict[str, str] = {
    "qa_gate": "All prerequisite QA gates satisfied before beginning this work.",
    "material_risk": "Material classification and associated risk confirmed.",
    "corrosion_requirement": "Corrosion protection requirements reviewed.",
    "dependency": "All upstream dependencies resolved before starting.",
    "documentation_required": "Required documentation available and reviewed.",
    "manual_hold": "Manual hold released by authorized personnel.",
}


def _qa_category_from_gate_id(gate_id: str) -> str:
    """Extract category segment from a QA gate ID like 'qa:material_compliance:critical:2'."""
    parts = gate_id.split(":")
    return parts[1] if len(parts) > 1 else ""


def _clean_reason(raw: str) -> str:
    """Strip 'QA gate remains open:' prefix and trailing punctuation."""
    text = re.sub(r"^QA gate remains open:\s*", "", raw, flags=re.I).strip()
    return text


def _strip_gate_id_patterns(text: str) -> str:
    """Remove raw QA gate IDs and internal prefixes."""
    text = re.sub(r"\bqa:[a-z_]+:[a-z]+:\d+\b\.?\s*", "", text, flags=re.I)
    text = re.sub(r"^QA gate remains open:\s*", "", text, flags=re.I)
    text = re.sub(r"^Clear QA gate:\s*", "", text, flags=re.I)
    return text.strip()


# ---------------------------------------------------------------------------
# Core ExecutionPackage dataclass
# ---------------------------------------------------------------------------

@dataclass
class ExecutionPackage:
    """A structured, executable unit of work derived from an OperationalPlan.

    Domain-agnostic.  Never contains OEM repair instructions.
    """
    package_id: str
    title: str
    objective: str
    status: str                          # blocked | in_progress | ready | complete
    priority: str                        # critical | high | medium | low
    prerequisites: list[str]            = field(default_factory=list)
    required_verifications: list[str]   = field(default_factory=list)
    execution_steps: list[str]          = field(default_factory=list)
    completion_criteria: list[str]      = field(default_factory=list)
    expected_unlocks: list[str]         = field(default_factory=list)
    blocked_by: list[str]               = field(default_factory=list)
    risk_reduction: str                 = ""
    confidence: str                     = "medium"
    supporting_evidence: list[str]      = field(default_factory=list)
    generated_at: str                   = ""
    advisory: str                       = _ADVISORY

    def to_dict(self) -> dict[str, Any]:
        return {
            "package_id": self.package_id,
            "title": self.title,
            "objective": self.objective,
            "status": self.status,
            "priority": self.priority,
            "prerequisites": self.prerequisites,
            "required_verifications": self.required_verifications,
            "execution_steps": self.execution_steps,
            "completion_criteria": self.completion_criteria,
            "expected_unlocks": self.expected_unlocks,
            "blocked_by": self.blocked_by,
            "risk_reduction": self.risk_reduction,
            "confidence": self.confidence,
            "supporting_evidence": self.supporting_evidence,
            "generated_at": self.generated_at,
            "advisory": self.advisory,
        }


# ---------------------------------------------------------------------------
# CollisionWorkPackage — domain projection for collision repair
# ---------------------------------------------------------------------------

@dataclass
class CollisionWorkPackage:
    """Collision-domain projection of an ExecutionPackage.

    Renames fields and applies collision-appropriate terminology while the
    ExecutionPackage itself remains domain-agnostic.
    """
    package_id: str
    work_package_title: str
    purpose: str
    repair_status: str
    urgency: str
    before_you_start: list[str]         = field(default_factory=list)
    verifications_required: list[str]   = field(default_factory=list)
    work_to_perform: list[str]          = field(default_factory=list)
    done_when: list[str]                = field(default_factory=list)
    what_this_unlocks: list[str]        = field(default_factory=list)
    currently_blocked_by: list[str]     = field(default_factory=list)
    risk_note: str                      = ""
    confidence: str                     = "medium"
    technician_brief: str               = ""
    manager_brief: str                  = ""
    advisory: str                       = _ADVISORY

    def to_dict(self) -> dict[str, Any]:
        return {
            "package_id": self.package_id,
            "work_package_title": self.work_package_title,
            "purpose": self.purpose,
            "repair_status": self.repair_status,
            "urgency": self.urgency,
            "before_you_start": self.before_you_start,
            "verifications_required": self.verifications_required,
            "work_to_perform": self.work_to_perform,
            "done_when": self.done_when,
            "what_this_unlocks": self.what_this_unlocks,
            "currently_blocked_by": self.currently_blocked_by,
            "risk_note": self.risk_note,
            "confidence": self.confidence,
            "technician_brief": self.technician_brief,
            "manager_brief": self.manager_brief,
            "advisory": self.advisory,
        }


def project_collision_work_package(
    pkg: ExecutionPackage,
    narrative: OperationalNarrative,
) -> CollisionWorkPackage:
    """Project an ExecutionPackage into a CollisionWorkPackage.

    Applies collision-domain vocabulary and pulls narrated messages from
    the OperationalNarrative.
    """
    # Map generic status to collision language
    status_labels = {
        "blocked": "Blocked — Prerequisites Not Met",
        "in_progress": "In Progress",
        "ready": "Ready to Begin",
        "complete": "Complete",
    }
    urgency_labels = {
        "critical": "Critical — Act Now",
        "high": "High Priority",
        "medium": "Normal Priority",
        "low": "Low Priority",
    }

    return CollisionWorkPackage(
        package_id=pkg.package_id,
        work_package_title=pkg.title,
        purpose=pkg.objective,
        repair_status=status_labels.get(pkg.status, pkg.status.replace("_", " ").title()),
        urgency=urgency_labels.get(pkg.priority, pkg.priority.title()),
        before_you_start=pkg.prerequisites,
        verifications_required=pkg.required_verifications,
        work_to_perform=pkg.execution_steps,
        done_when=pkg.completion_criteria,
        what_this_unlocks=pkg.expected_unlocks,
        currently_blocked_by=pkg.blocked_by,
        risk_note=pkg.risk_reduction,
        confidence=pkg.confidence,
        technician_brief=narrative.technician_message,
        manager_brief=narrative.manager_message,
        advisory=_ADVISORY,
    )


# ---------------------------------------------------------------------------
# Builder helpers
# ---------------------------------------------------------------------------

def _derive_title(plan: OperationalPlan, narrative: OperationalNarrative) -> str:
    """Derive a short, human-readable work package title."""
    action_type = plan.next_best_action.action_type
    domain_ctx = plan.next_best_action.domain_context or ""

    # Use the narrated task but truncate to a headline length
    task = narrative.next_best_task
    # Strip trailing period for use as title
    title = task.rstrip(".")
    # If very long, truncate at a natural boundary
    if len(title) > 80:
        # Try to cut at a comma or "before"
        for sep in (" before ", ", ", " and "):
            idx = title.find(sep)
            if 20 < idx < 80:
                title = title[:idx]
                break
        else:
            title = title[:77] + "…"
    return title


def _derive_objective(plan: OperationalPlan, narrative: OperationalNarrative, model: OperationalModel) -> str:
    """Derive a one-sentence objective for the package."""
    task = narrative.next_best_task.rstrip(".")
    progress = narrative.expected_progress.rstrip(".")

    ctx = model.domain_context.context_data
    vehicle = ctx.get("vehicle", {})
    oem = vehicle.get("oem", "")
    oem_ref = f" for this {oem} repair" if oem else ""

    action_type = plan.next_best_action.action_type
    if action_type == "qa_gate":
        return (
            f"Complete the required verification{oem_ref} so that downstream work can proceed. "
            f"{progress}."
        ).replace("..", ".")
    if action_type == "blocker":
        return (
            f"Resolve the current blocker{oem_ref} to restore forward progress. "
            f"{progress}."
        ).replace("..", ".")
    if action_type in ("workflow", "phase"):
        return (
            f"Advance the workflow{oem_ref} by completing the next recommended task. "
            f"{progress}."
        ).replace("..", ".")
    return f"Complete the next highest-leverage task{oem_ref}. {progress}.".replace("..", ".")


def _derive_status(plan: OperationalPlan) -> str:
    """Map overall plan status to package status."""
    return plan.overall_status if plan.overall_status in ("blocked", "in_progress", "ready", "complete") else "in_progress"


def _derive_priority(plan: OperationalPlan) -> str:
    """Derive priority from the NBA severity/confidence."""
    sev = plan.next_best_action.confidence  # "high"/"medium"/"low" from scorer
    # Map planner confidence to priority
    action_type = plan.next_best_action.action_type
    if action_type == "qa_gate":
        # Inspect the gate priority from the candidate_id
        cid = plan.next_best_action.action_id
        if "critical" in cid:
            return "critical"
        if "high" in cid:
            return "high"
    if sev == "high":
        return "high"
    if sev == "medium":
        return "medium"
    return "low"


def _build_prerequisites(plan: OperationalPlan, model: OperationalModel) -> list[str]:
    """Build the list of conditions that must be true before work begins."""
    prereqs: list[str] = []
    state = model.state
    if not state:
        return ["All upstream work items resolved."]

    action_type = plan.next_best_action.action_type
    action_id = plan.next_best_action.action_id  # e.g. "qa:qa:material_compliance:critical:2"

    if action_type == "qa_gate":
        # Extract category from gate id
        # action_id format: "qa:<gate_id>" where gate_id = "qa:material_compliance:critical:2"
        inner_gate_id = action_id.removeprefix("qa:")
        category = _qa_category_from_gate_id(inner_gate_id)
        cat_prereq = _QA_CATEGORY_PREREQS.get(category)
        if cat_prereq:
            prereqs.append(cat_prereq)

        # Add any specific domain prereqs from zones
        ctx = model.domain_context.context_data
        repair = ctx.get("repair", {})
        if repair.get("structural_involvement"):
            prereqs.append("Structural involvement confirmed and repair area assessed.")

        # Material classification prereq if UHSS zone present
        for zone in state.zones:
            mc = (zone.material_classification or "").upper()
            if "UHSS" in mc or "ULTRA" in mc:
                prereqs.append("Ultra-high-strength steel (UHSS) zone identified — joining method must be OEM-specified.")
                break

        # Corrosion prereq if required
        if ctx.get("corrosion_protection_required"):
            prereqs.append("Corrosion protection requirements reviewed before any structural joining.")

    elif action_type == "blocker":
        blocker_id = action_id.removeprefix("blocker:")
        blocker = next((b for b in state.blockers if b.blocker_id == blocker_id), None)
        if blocker:
            p = _BLOCKER_TYPE_PREREQS.get(blocker.type)
            if p:
                prereqs.append(p)

    elif action_type in ("workflow", "phase"):
        # Generic: upstream QA satisfied
        open_critical = [g for g in state.qa_gates if g.status in ("open", "in_review") and g.priority == "critical"]
        if open_critical:
            prereqs.append("All critical-priority verification gates cleared before proceeding.")
        prereqs.append("Preceding phases complete or confirmed not applicable.")

    elif action_type == "evidence":
        prereqs.append("Required documentation identified and procurement initiated.")

    if not prereqs:
        prereqs.append("No additional prerequisites identified beyond standard workflow requirements.")

    return prereqs


def _build_verifications(plan: OperationalPlan, model: OperationalModel) -> list[str]:
    """Build required verifications — what must be checked/documented."""
    verifications: list[str] = []
    state = model.state
    if not state:
        return ["Verify all open QA gates before advancing workflow."]

    action_type = plan.next_best_action.action_type
    action_id = plan.next_best_action.action_id

    if action_type == "qa_gate":
        inner_gate_id = action_id.removeprefix("qa:")
        category = _qa_category_from_gate_id(inner_gate_id)

        # Primary verification from category
        cat_ver = _QA_CATEGORY_VERIFICATIONS.get(category)
        if cat_ver:
            verifications.append(cat_ver)

        # Related open gates in same category — list their checks
        gate = next((g for g in state.qa_gates if g.gate_id == inner_gate_id), None)
        if gate and gate.related_phase is not None:
            same_phase_gates = [
                g for g in state.qa_gates
                if g.related_phase == gate.related_phase
                and g.gate_id != inner_gate_id
                and g.status in ("open", "in_review")
            ]
            for g in same_phase_gates[:4]:
                check = _strip_gate_id_patterns(g.check or g.gate_id)
                if check and check not in verifications:
                    verifications.append(check + ("." if not check.endswith(".") else ""))

    elif action_type == "blocker":
        blocker_id = action_id.removeprefix("blocker:")
        blocker = next((b for b in state.blockers if b.blocker_id == blocker_id), None)
        if blocker and blocker.reason:
            cleaned = _clean_reason(blocker.reason)
            verifications.append(cleaned + ("." if not cleaned.endswith(".") else ""))

    elif action_type in ("workflow", "phase"):
        # List any open high-priority gates related to the phase
        phase_id = None
        for p in state.phases:
            if f"phase:{p.name}" == action_id or f"workflow:{p.name}" == action_id:
                phase_id = p.phase
                break
        open_gates = [
            g for g in state.qa_gates
            if g.status in ("open", "in_review")
            and g.priority in ("critical", "high")
            and (phase_id is None or g.related_phase == phase_id)
        ]
        for g in open_gates[:4]:
            check = _strip_gate_id_patterns(g.check or g.gate_id)
            if check:
                verifications.append(check + ("." if not check.endswith(".") else ""))

    if not verifications:
        verifications.append("Verify all open QA gates for this work area before advancing.")

    return verifications


def _build_execution_steps(plan: OperationalPlan, narrative: OperationalNarrative) -> list[str]:
    """Build generic, non-OEM execution steps from the narrated task queue.

    Steps describe work organisation, not repair procedures.
    """
    steps: list[str] = []
    action_type = plan.next_best_action.action_type

    # Step 1: always the primary task
    primary = narrative.next_best_task.rstrip(".")
    steps.append(f"Complete the primary verification task: {primary}.")

    if action_type == "qa_gate":
        steps.append(
            "Document the verification outcome and retain records per shop procedure."
        )
        steps.append(
            "Confirm all related verification items in the same category before closing the gate."
        )
        steps.append(
            "Once the primary gate is cleared, advance the workflow to the next recommended step."
        )

    elif action_type == "blocker":
        steps.append("Resolve the identified blocker and update the repair record.")
        steps.append("Confirm resolution with responsible party before continuing.")
        steps.append("Advance workflow after confirmation.")

    elif action_type in ("workflow", "phase"):
        steps.append(
            "Begin work according to OEM procedures after all prerequisites are satisfied."
        )
        steps.append("Progress through the workflow in phase order.")
        steps.append("Document each completed step before advancing to the next.")

    elif action_type == "evidence":
        steps.append("Obtain and review the missing documentation.")
        steps.append("File documentation with the repair record before proceeding.")

    # Add narrated today queue items (skip if they duplicate the primary)
    for item in narrative.today[1:3]:
        if item not in steps and item.rstrip(".") != primary:
            steps.append(item if item.endswith(".") else item + ".")

    return steps


def _build_completion_criteria(plan: OperationalPlan, narrative: OperationalNarrative) -> list[str]:
    """Build the conditions that define 'done' for this package."""
    criteria: list[str] = [
        "Primary verification or task completed and documented.",
        "All prerequisite conditions satisfied and on record.",
    ]

    action_type = plan.next_best_action.action_type
    if action_type == "qa_gate":
        criteria.append("Blocking QA gate cleared and status updated in repair record.")
        criteria.append("Workflow advances to the next phase.")
    elif action_type == "blocker":
        criteria.append("Blocker resolved and status updated.")
        criteria.append("Affected workflow items unblocked.")
    elif action_type in ("workflow", "phase"):
        criteria.append("Phase work complete and documented.")
        criteria.append("Next recommended actions identified and queued.")

    if plan.expected_unlocks:
        criteria.append("Expected downstream work confirmed as available.")

    return criteria


def _build_expected_unlocks(plan: OperationalPlan, narrative: OperationalNarrative) -> list[str]:
    """Build human-readable unlock descriptions."""
    # Use the already-narrated unlocks from the narrative
    unlocks = list(narrative.expected_unlocks)

    # Also surface later-queue items as downstream availability
    for item in narrative.next[:3]:
        label = item.rstrip(".")
        entry = f"{label} becomes available."
        if entry not in unlocks:
            unlocks.append(entry)

    if not unlocks:
        unlocks.append("Downstream workflow stages become available.")

    return unlocks[:6]


def _build_blocked_by(plan: OperationalPlan) -> list[str]:
    """Return human-readable blocked_by entries without internal IDs."""
    out: list[str] = []
    for raw in plan.blocked_by:
        cleaned = _clean_reason(raw)
        if cleaned and cleaned not in out:
            out.append(cleaned + ("." if not cleaned.endswith(".") else ""))
    return out[:5]


def _build_risk_reduction(plan: OperationalPlan, narrative: OperationalNarrative) -> str:
    """Return the narrated risk reduction summary."""
    return narrative.risk_summary or plan.risk_reduction


def _build_supporting_evidence(plan: OperationalPlan, model: OperationalModel) -> list[str]:
    """Build a short supporting evidence list."""
    items: list[str] = []
    state = model.state
    if state:
        # High-confidence evidence: material zones
        for zone in state.zones:
            mc = (zone.material_classification or "").upper()
            if mc:
                items.append(f"Material classification in repair zone: {mc}.")
                break
        # Passed gates as positive evidence
        passed = [g for g in state.qa_gates if g.status == "passed"]
        if passed:
            items.append(f"{len(passed)} QA gate(s) already satisfied.")

    ctx = model.domain_context.context_data
    vehicle = ctx.get("vehicle", {})
    if vehicle.get("oem"):
        oem = vehicle["oem"]
        year = vehicle.get("year", "")
        vmodel = vehicle.get("model", "")
        items.append(f"Repair context: {oem} {year} {vmodel}".strip() + ".")

    # Pull from plan supporting_evidence (already cleaned by narrator caller)
    for ev in plan.supporting_evidence[:2]:
        if isinstance(ev, str) and ev not in items:
            # Skip raw Python dict strings
            if not ev.startswith("{") and "action_id" not in ev:
                items.append(ev)

    return items[:5]


# ---------------------------------------------------------------------------
# Public entry point — generic ExecutionPackage
# ---------------------------------------------------------------------------

def build_execution_package(
    plan: OperationalPlan,
    narrative: OperationalNarrative,
    model: OperationalModel,
) -> ExecutionPackage:
    """Build a domain-agnostic ExecutionPackage from planner + narrator + model.

    Does not re-run planning logic. Does not inspect source documents.
    Does not invent OEM procedures.

    Args:
        plan:      The OperationalPlan from build_operational_plan().
        narrative: The OperationalNarrative from build_narrative().
        model:     The OperationalModel for domain context and state.

    Returns:
        An ExecutionPackage representing one structured unit of work.
    """
    return ExecutionPackage(
        package_id=str(uuid.uuid4()),
        title=_derive_title(plan, narrative),
        objective=_derive_objective(plan, narrative, model),
        status=_derive_status(plan),
        priority=_derive_priority(plan),
        prerequisites=_build_prerequisites(plan, model),
        required_verifications=_build_verifications(plan, model),
        execution_steps=_build_execution_steps(plan, narrative),
        completion_criteria=_build_completion_criteria(plan, narrative),
        expected_unlocks=_build_expected_unlocks(plan, narrative),
        blocked_by=_build_blocked_by(plan),
        risk_reduction=_build_risk_reduction(plan, narrative),
        confidence=plan.confidence,
        supporting_evidence=_build_supporting_evidence(plan, model),
        generated_at=datetime.now(timezone.utc).isoformat(),
        advisory=_ADVISORY,
    )
