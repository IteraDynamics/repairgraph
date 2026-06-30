"""
Operational Narration Layer.

Translates deterministic OperationalPlan output into natural operational
language that technicians, managers, and executives can act on directly.

The narrator is presentation intelligence only. It does not:
  - re-run planning logic
  - inspect source documents
  - invent OEM procedures
  - change OperationalModel

It may rename, simplify, combine, rephrase, and remove implementation
language. It may NOT fabricate repair information.

Primary object: OperationalNarrative
Entry point:    build_narrative(plan) -> OperationalNarrative
"""
from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

from repairgraph.review.operational_planner import OperationalPlan

_ADVISORY = (
    "RepairGraph outputs are advisory workflow intelligence. "
    "They do not certify repair completion, OEM compliance, or repair quality. "
    "All outputs require verification by a qualified technician against OEM procedures."
)

# ---------------------------------------------------------------------------
# Text cleaning — remove internal ID patterns from displayed strings
# ---------------------------------------------------------------------------

# Patterns that must never appear in narrated output
_ID_PATTERNS: list[re.Pattern] = [
    re.compile(r"\bqa:[a-z_]+:[a-z]+:\d+\b\.?\s*", re.I),
    re.compile(r"\bphase:\d+\b", re.I),
    re.compile(r"\bqa_gate\b", re.I),
    re.compile(r"\breplace_component:[a-z_]+\b", re.I),
    re.compile(r"\bworkflow_phase\b", re.I),
    re.compile(r"\bcandidate\b", re.I),
    re.compile(r"\bplanner\b", re.I),
    re.compile(r"\bnode\b", re.I),
    re.compile(r"\bentity\b", re.I),
    re.compile(r"^QA gate remains open:\s*", re.I),
    re.compile(r"^Resolve QA gate [^\s.]+\.\s*(?:Check:\s*)?", re.I),
]

_PREFIX_STRIPS: list[tuple[str, str]] = [
    ("Clear QA gate: ", ""),
    ("Clear QA Gate: ", ""),
    ("Unblock phase: ", ""),
    ("Unblock Phase: ", ""),
    ("Resolve: ", ""),
]


def _strip_internal_ids(text: str) -> str:
    """Remove internal ID patterns from a user-facing string."""
    for pat in _ID_PATTERNS:
        text = pat.sub("", text)
    return text.strip()


def _strip_prefixes(text: str) -> str:
    """Remove machine-generated prefixes like 'Clear QA gate:'."""
    for prefix, replacement in _PREFIX_STRIPS:
        if text.startswith(prefix):
            text = replacement + text[len(prefix):]
    return text.strip()


def _clean(text: str) -> str:
    """Full cleaning pipeline: strip internal IDs then machine prefixes."""
    return _strip_prefixes(_strip_internal_ids(text)).strip()


# ---------------------------------------------------------------------------
# Component part name → natural label mapping
# ---------------------------------------------------------------------------

_PART_LABELS: dict[str, str] = {
    "front_lower_edge": "front lower edge reinforcement",
    "front_upper_edge": "front upper edge reinforcement",
    "quarter_pillar_stiffener": "quarter pillar stiffener",
    "rear_combination_adapter": "rear combination adapter",
    "rear_combination_adapter_lower": "rear combination adapter lower",
    "rear_inner_panel": "rear inner panel",
    "rear_pillar_gutter": "rear pillar gutter",
    "rear_pillar_gutter_lower": "rear pillar gutter lower",
    "wheel_arch_separator": "wheel arch separator",
    "rear_pillar_separator": "rear pillar separator",
    "outer_panel": "outer panel",
    "inner_panel": "inner panel",
    "pillar_reinforcement": "pillar reinforcement",
    "door_aperture": "door aperture reinforcement",
}

_PHASE_LABELS: dict[str, str] = {
    "panel_installation_and_joining": "structural panel installation and joining",
    "corrosion_protection": "corrosion protection application",
    "post_repair_verification": "final structural verification",
    "pre_repair_assessment": "pre-repair assessment",
    "structural_repair": "structural repair",
    "component_removal": "component removal",
    "alignment": "dimensional alignment",
    "calibration": "ADAS calibration",
    "documentation": "documentation and sign-off",
}

_QA_CONCERN_LABELS: dict[str, str] = {
    "material_compliance": "OEM material and joining requirements",
    "corrosion": "corrosion protection requirements",
    "calibration": "calibration requirements",
    "components": "component replacement requirements",
    "dimensions": "dimensional verification",
    "inspection": "final inspection requirements",
    "joining": "joining procedure requirements",
    "documentation": "documentation requirements",
}


def _narrate_part(raw: str) -> str:
    """Convert a snake_case part name to natural language."""
    key = raw.lower().strip()
    if key in _PART_LABELS:
        return _PART_LABELS[key]
    # Generic: split on underscore, title-case
    return raw.replace("_", " ").strip()


def _narrate_phase(raw: str) -> str:
    """Convert a phase name/id to natural language."""
    key = raw.lower().strip()
    if key in _PHASE_LABELS:
        return _PHASE_LABELS[key]
    return raw.replace("_", " ").strip()


def _narrate_action_label(raw: str) -> str:
    """Translate a machine action label into task language.

    Handles:
      - "Replace Component: some_part_name."
      - "Clear QA gate: Verify ..."
      - "Unblock phase: ..."
      - Plain text (pass through after cleaning)
    """
    text = raw.strip().rstrip(".")

    # Replace Component pattern
    m = re.match(r"Replace Component:\s*(.+)", text, re.I)
    if m:
        part = _narrate_part(m.group(1).strip().rstrip(".").rstrip())
        # Strip trailing "(complete)" if present
        part = re.sub(r"\s*\(complete\)\s*$", "", part, flags=re.I).strip()
        return f"Install {part}."

    # Clear QA gate pattern
    m = re.match(r"Clear QA gate:\s*(.+)", text, re.I)
    if m:
        inner = _strip_internal_ids(m.group(1).strip().rstrip("."))
        if not inner:
            inner = "Verify the OEM procedure for this repair step"
        if not inner.endswith(".") and not inner.endswith("?"):
            inner = inner + "."
        return inner

    # Unblock phase pattern
    m = re.match(r"Unblock (?:and resume:?\s*|phase:?\s*)(.+)", text, re.I)
    if m:
        phase = _narrate_phase(m.group(1).strip().rstrip("."))
        return f"Resume {phase}."

    # "workflow:..." type
    m = re.match(r"[A-Za-z ]+:\s*(.+)", text)
    if m:
        cleaned = _clean(m.group(1).strip().rstrip("."))
        if cleaned:
            return cleaned + "."

    # Fall through: clean IDs and return
    cleaned = _clean(text)
    if cleaned and not cleaned.endswith("."):
        cleaned = cleaned + "."
    return cleaned


def _narrate_unlock_label(unlock: dict[str, Any]) -> str:
    """Produce a natural-language unlock description."""
    utype = unlock.get("unlock_type", "")
    raw_label = unlock.get("label", "")

    if utype == "phase":
        phase = _narrate_phase(raw_label or unlock.get("unlock_id", ""))
        return f"{phase.capitalize()} can begin."
    if utype == "qa_gate":
        cleaned = _clean(raw_label)
        return cleaned if cleaned else "Additional verification step enabled."
    if utype == "action":
        return _narrate_action_label(raw_label)
    if utype == "risk":
        return raw_label or "Operational risk reduced."
    if utype == "finding":
        return "Documentation completeness improved."
    return _clean(raw_label) or "Downstream work enabled."


# ---------------------------------------------------------------------------
# Sentence-level narration helpers
# ---------------------------------------------------------------------------

def _narrate_next_best_task(plan: OperationalPlan) -> str:
    """Produce a natural task sentence from next_best_action.display_label."""
    raw = plan.next_best_action.display_label
    return _narrate_action_label(raw)


def _narrate_why_now(plan: OperationalPlan) -> str:
    """Translate why_now from graph-speak to operational prose."""
    raw = plan.next_best_action.why_now or ""

    # Replace known ID fragments
    text = raw
    text = re.sub(r"'([^']+)' phase", lambda m: f"the {_narrate_phase(m.group(1))} phase", text, flags=re.I)
    text = re.sub(r"highest-priority blocking QA gate", "highest-priority open verification requirement", text, flags=re.I)
    text = re.sub(r"high-priority blocking QA gate", "high-priority open verification requirement", text, flags=re.I)
    text = re.sub(r"QA gate", "verification requirement", text, flags=re.I)
    text = re.sub(r"\bClearing it\b", "Completing this verification", text)
    text = _strip_internal_ids(text)
    return text.strip()


def _narrate_expected_progress(plan: OperationalPlan) -> str:
    """Produce an operational progress description, not a node list."""
    unlocks = plan.expected_unlocks
    if not unlocks:
        return "Completing this task removes the current blocking dependency."

    phase_unlocks = [u for u in unlocks if u.unlock_type == "phase"]
    qa_unlocks = [u for u in unlocks if u.unlock_type == "qa_gate"]
    action_unlocks = [u for u in unlocks if u.unlock_type == "action"]

    parts: list[str] = []

    if phase_unlocks:
        phase_names = [_narrate_phase(u.label) for u in phase_unlocks]
        if len(phase_names) == 1:
            parts.append(f"Completing this task allows {phase_names[0]} to begin")
        else:
            joined = ", ".join(phase_names[:-1]) + f" and {phase_names[-1]}"
            parts.append(f"Completing this task allows {joined} to begin")

    if qa_unlocks:
        count = len(qa_unlocks)
        parts.append(f"removes {count} dependent verification requirement{'s' if count != 1 else ''}")

    if action_unlocks:
        count = len(action_unlocks)
        parts.append(f"enables {count} downstream installation step{'s' if count != 1 else ''}")

    if not parts:
        return "Completing this task removes the current blocking dependency."

    sentence = " and ".join(parts)
    if not sentence.endswith("."):
        sentence += "."
    return sentence.capitalize()


def _narrate_queue_items(items: list[str]) -> list[str]:
    """Narrate a list of machine action labels into task language."""
    out: list[str] = []
    for item in items:
        # Remove trailing "(complete)" entries from Today/Next — those belong in Later
        if re.search(r"\(complete\)", item, re.I):
            continue
        narrated = _narrate_action_label(item)
        if narrated:
            out.append(narrated)
    return out


def _narrate_later_items(deferred: list[str]) -> list[str]:
    """Narrate deferred items — include completed items with a 'done' note."""
    out: list[str] = []
    for item in deferred:
        if re.search(r"\(complete\)", item, re.I):
            # Strip the "(complete)" suffix and note it
            core = re.sub(r"\s*\(complete\)\.?\s*$", "", item, flags=re.I).strip()
            narrated = _narrate_action_label(core)
            narrated = re.sub(r"\.$", "", narrated) + " (complete)."
            out.append(narrated)
        else:
            narrated = _narrate_action_label(item)
            if narrated:
                out.append(narrated)
    return out


def _narrate_critical_path(path: list[str]) -> list[str]:
    """Narrate each step of the critical path into operational language."""
    return [_narrate_action_label(step) for step in path if step.strip()]


def _narrate_headline(plan: OperationalPlan) -> str:
    """One-line status headline."""
    status = plan.overall_status
    if status == "blocked":
        return "Repair work is currently blocked and requires immediate attention."
    if status == "at_risk":
        return "Repair work is in progress but at risk — open items require review."
    if status in ("ready", "complete"):
        return "Repair work is on track and ready to proceed."
    return "Repair status requires review before proceeding."


def _narrate_executive_summary(plan: OperationalPlan) -> str:
    """3–5 sentence executive summary in plain operational language."""
    status = plan.overall_status
    nbt = _narrate_next_best_task(plan)
    progress = _narrate_expected_progress(plan)

    open_count = len(plan.blocked_by)

    if status == "blocked":
        lines = [
            "Repair work is currently blocked by unresolved verification requirements.",
        ]
        if open_count > 0:
            lines.append(
                f"There are {open_count} open items holding up forward progress, "
                f"and most downstream work depends on clearing the primary one first."
            )
        lines.append(f"The recommended next task is: {nbt}")
        lines.append(progress)
        lines.append(
            "Once this verification is complete, structural installation can begin "
            "and multiple downstream workflow stages become available."
        )
    elif status == "at_risk":
        lines = [
            "Repair work is in progress but open items present risk.",
            f"The recommended next task is: {nbt}",
            progress,
        ]
    else:
        lines = [
            "Repair is on track.",
            f"The recommended next task is: {nbt}",
        ]

    return " ".join(lines)


def _narrate_workflow_summary(plan: OperationalPlan) -> str:
    """Brief workflow status summary."""
    today = _narrate_queue_items(plan.action_queue.get("today", []))
    later = plan.action_queue.get("next", [])
    count_today = len(today)
    count_later = len(later)

    parts = []
    if count_today:
        parts.append(f"{count_today} task{'s' if count_today != 1 else ''} ready for today")
    if count_later:
        parts.append(f"{count_later} task{'s' if count_later != 1 else ''} queued for next")
    if not parts:
        return "No immediate tasks identified."
    return (", ".join(parts)).capitalize() + "."


def _narrate_risk_summary(plan: OperationalPlan) -> str:
    """Operational risk summary without internal IDs."""
    raw = plan.risk_reduction or ""
    # Strip "Reduces:" prefix and clean up
    text = re.sub(r"^Reduces?:\s*", "", raw, flags=re.I).strip().rstrip(".")
    if not text:
        return "Completing this task reduces operational delay risk."
    parts = [p.strip() for p in text.split(",") if p.strip()]
    if len(parts) == 1:
        return f"Completing this task reduces {parts[0]}."
    joined = ", ".join(parts[:-1]) + f" and {parts[-1]}"
    return f"Completing this task reduces {joined}."


def _narrate_technician_message(plan: OperationalPlan, oem: str = "") -> str:
    """Craft a direct foreman-style instruction for the technician."""
    nbt_raw = plan.next_best_action.display_label
    action_type = plan.next_best_action.action_type

    # Extract the core check from QA gate labels
    if action_type == "qa_gate":
        core = _clean(nbt_raw)
        if not core.endswith("."):
            core = core + "."
        oem_ref = f"the {oem} procedure" if oem else "the OEM procedure"
        return (
            f"Before proceeding with structural work, {core[0].lower()}{core[1:]} "
            f"Refer to {oem_ref} for the approved joining method for this repair area. "
            f"Do not begin joining or panel installation until this verification is documented and complete."
        )

    if action_type == "blocker":
        core = _clean(nbt_raw)
        return (
            f"{core} "
            f"This item is blocking further progress and must be resolved before installation work continues."
        )

    if action_type in ("workflow", "phase"):
        narrated = _narrate_action_label(nbt_raw)
        return (
            f"{narrated} "
            f"Confirm all prerequisite verifications are complete before starting this step."
        )

    narrated = _narrate_action_label(nbt_raw)
    return (
        f"{narrated} "
        f"Verify all required documentation is in order before proceeding."
    )


def _narrate_manager_message(plan: OperationalPlan, oem: str = "") -> str:
    """Craft a clear verification responsibility message for the manager."""
    oem_ref = f"{oem} " if oem else "OEM "
    phase_unlocks = [u for u in plan.expected_unlocks if u.unlock_type == "phase"]

    lines: list[str] = [
        f"Confirm {oem_ref}verification requirements have been reviewed and documented before assigning structural installation work.",
    ]
    if phase_unlocks:
        phases = [_narrate_phase(u.label) for u in phase_unlocks]
        phase_str = " and ".join(phases)
        lines.append(
            f"Clearance of the open verification requirement is required before {phase_str} can be assigned."
        )
    lines.append(
        "Ensure corrosion protection documentation is completed before releasing downstream work."
    )
    return " ".join(lines)


def _extract_oem(plan: OperationalPlan) -> str:
    """Try to infer OEM name from plan context."""
    # Check domain_context on NBA
    ctx = plan.next_best_action.domain_context or ""
    # Check why_now for OEM mentions
    why = plan.next_best_action.why_now or ""
    for text in (ctx, why):
        m = re.search(r"\b(Honda|Toyota|Ford|GM|Stellantis|BMW|Mercedes|Audi|Nissan|Hyundai|Kia)\b", text, re.I)
        if m:
            return m.group(1)
    return ""


# ---------------------------------------------------------------------------
# Primary output object
# ---------------------------------------------------------------------------

@dataclass
class OperationalNarrative:
    """Natural-language narration of an OperationalPlan.

    All fields are human-readable strings or lists of strings.
    No internal IDs, gate IDs, or machine concepts appear here.
    """
    headline: str
    next_best_task: str
    why_now: str
    expected_progress: str
    expected_unlocks: list[str]
    today: list[str]
    next: list[str]
    later: list[str]
    critical_path: list[str]
    technician_message: str
    manager_message: str
    executive_summary: str
    workflow_summary: str
    risk_summary: str
    supporting_evidence: list[str]
    confidence: str
    advisory: str = _ADVISORY

    def to_dict(self) -> dict[str, Any]:
        return {
            "headline": self.headline,
            "next_best_task": self.next_best_task,
            "why_now": self.why_now,
            "expected_progress": self.expected_progress,
            "expected_unlocks": self.expected_unlocks,
            "today": self.today,
            "next": self.next,
            "later": self.later,
            "critical_path": self.critical_path,
            "technician_message": self.technician_message,
            "manager_message": self.manager_message,
            "executive_summary": self.executive_summary,
            "workflow_summary": self.workflow_summary,
            "risk_summary": self.risk_summary,
            "supporting_evidence": self.supporting_evidence,
            "confidence": self.confidence,
            "advisory": self.advisory,
        }

    def has_internal_ids(self) -> bool:
        """Return True if any field still contains internal ID patterns.

        Used in tests to verify narration quality.
        """
        _FORBIDDEN = re.compile(
            r"qa:[a-z_]+:[a-z]+:\d+"
            r"|replace_component:[a-z_]+"
            r"|phase:\d+"
            r"|\bqa_gate\b"
            r"|\bworkflow_phase\b"
            r"|\bcandidate\b"
            r"|\bplanner\b",
            re.I,
        )
        all_text = " ".join([
            self.headline, self.next_best_task, self.why_now,
            self.expected_progress, self.executive_summary,
            self.technician_message, self.manager_message,
            self.workflow_summary, self.risk_summary,
            " ".join(self.expected_unlocks),
            " ".join(self.today),
            " ".join(self.next),
            " ".join(self.later),
            " ".join(self.critical_path),
        ])
        return bool(_FORBIDDEN.search(all_text))


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------

def build_narrative(plan: OperationalPlan) -> OperationalNarrative:
    """Translate a deterministic OperationalPlan into natural operational language.

    Args:
        plan: The OperationalPlan produced by build_operational_plan().

    Returns:
        An OperationalNarrative with all fields in human-readable form.
    """
    oem = _extract_oem(plan)

    today_raw = plan.action_queue.get("today", [])
    next_raw = plan.action_queue.get("next", [])
    deferred_raw = plan.action_queue.get("deferred", [])

    today_narrated = _narrate_queue_items(today_raw)
    next_narrated = _narrate_queue_items(next_raw)
    later_narrated = _narrate_later_items(deferred_raw)

    unlocks = [_narrate_unlock_label(u.to_dict()) for u in plan.expected_unlocks]
    critical_path = _narrate_critical_path(plan.critical_path)

    # Supporting evidence: clean raw dicts into readable strings
    evidence: list[str] = []
    for ev in plan.supporting_evidence:
        if isinstance(ev, str):
            # Strip Python dict repr if serialized as string
            if ev.startswith("{") and "action_id" in ev:
                m = re.search(r"'action_id':\s*'([^']+)'", ev)
                if m:
                    part_id = m.group(1).replace("replace_component:", "")
                    evidence.append(f"Component: {_narrate_part(part_id)}")
                    continue
            evidence.append(ev)

    return OperationalNarrative(
        headline=_narrate_headline(plan),
        next_best_task=_narrate_next_best_task(plan),
        why_now=_narrate_why_now(plan),
        expected_progress=_narrate_expected_progress(plan),
        expected_unlocks=unlocks,
        today=today_narrated,
        next=next_narrated,
        later=later_narrated,
        critical_path=critical_path,
        technician_message=_narrate_technician_message(plan, oem),
        manager_message=_narrate_manager_message(plan, oem),
        executive_summary=_narrate_executive_summary(plan),
        workflow_summary=_narrate_workflow_summary(plan),
        risk_summary=_narrate_risk_summary(plan),
        supporting_evidence=evidence,
        confidence=plan.confidence,
        advisory=_ADVISORY,
    )
