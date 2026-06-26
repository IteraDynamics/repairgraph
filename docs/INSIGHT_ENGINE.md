# RepairGraph Insight Engine

## Overview

The insight engine (`repairgraph/insights/`) transforms RepairGraph's raw workflow state and intake manifest into a prioritized list of operational findings. It surfaces what matters, in what order, with a recommended action for each finding — without any AI, LLM, or inference.

All logic is deterministic, rule-based, and unit-tested.

## Output: InsightPayload

```python
@dataclass
class InsightPayload:
    schema_name: str          # "repairgraph.insights.payload"
    advisory: bool            # Always True
    overall_status: str       # "blocked" | "at_risk" | "ready" | "complete" | "unknown"
    risk_level: str           # "critical" | "high" | "medium" | "low" | "none"
    findings: list[InsightFinding]   # All findings, sorted by severity
    top_findings: list[InsightFinding]  # First 5 findings (property)
    summary_headline: str     # One-sentence status summary
    next_action: str          # Next recommended technician action
    finding_counts: dict      # Count per severity level
```

Each `InsightFinding` has:
- `finding_id` — stable identifier for deduplication and reference
- `severity` — one of: `critical`, `high`, `medium`, `low`, `informational`
- `category` — one of: `qa`, `workflow`, `material`, `compliance`, `intake`, `milestone`
- `title` — concise description of the finding
- `explanation` — why this matters operationally
- `recommended_action` — what the technician or supervisor should do
- `supporting_evidence` — tuple of `key=value` strings from the underlying data
- `confidence` — `high`, `medium`, or `low`

## Severity Priority Order

Findings are always sorted in this order — never alphabetically:

| Severity | Order | Meaning |
|---|---|---|
| `critical` | 0 | Must be resolved before repair can advance |
| `high` | 1 | Requires prompt attention; may block phases |
| `medium` | 2 | Should be resolved before final sign-off |
| `low` | 3 | Advisory — low risk but worth tracking |
| `informational` | 4 | Confirms progress; no action required |

Within the same severity, findings are sorted by `category` then `finding_id`.

## Finding Categories

### `qa` — Quality Gate Findings
- **critical_qa_open**: One finding per open critical-priority QA gate
- **high_qa_open_by_category**: One finding per category of open high-priority QA gates
- **medium_qa_open**: Summary finding for open medium-priority QA gates

### `workflow` — Phase and Blocker Findings
- **critical_blockers_open**: One finding per critical open blocker
- **repair_cannot_advance**: Produced when 2+ phases are simultaneously blocked
- **blocked_phases**: One finding per blocked phase

### `material` — Steel Classification Findings
- **uhss_detected**: When any zone has `material_classification` in `{"UHSS", "BORON"}`
- **joining_verification_required**: When UHSS zones exist alongside open joining QA gates
- **hss_detected**: When any zone has `material_classification == "HSS"`

### `compliance` — OEM Compliance Findings
- **corrosion_protection_blocked**: When the corrosion protection phase is blocked
- **corrosion_qa_open**: When corrosion-category QA gates are open
- **calibration_not_identified**: When no calibration actions or QA gates exist in the workflow

### `intake` — Document Packet Findings
- **missing_critical_roles**: Missing `repair_procedure`, `materials`, or `corrosion_protection` documents
- **readiness_concern**: When packet readiness is not `"ready"`
- **missing_important_roles**: Missing `welding`, `dimensions`, or `calibration` documents
- **conflicting_oem**: Multiple OEMs detected across documents
- **low_confidence_files**: Files classified below 50% confidence

### `milestone` — Progress Confirmations (Informational)
- **phases_complete**: Phases that have reached `complete` status
- **completed_actions**: Count of completed repair procedures
- **next_action**: The next recommended technician action from repair state
- **packet_complete**: Confirmation when intake readiness is `"ready"`

## Entry Point

```python
from repairgraph.insights import build_insight_payload

payload = build_insight_payload(
    state: RepairState,
    manifest_dict: dict | None = None,   # from orchestrator.build_intake_demo_payload()
)
```

The orchestrator (`repairgraph/demo/orchestrator.py`) calls this automatically and includes the result as `payload["insights"]` in the full demo payload.

## Replay Enrichment

```python
from repairgraph.insights.replay_enrichment import enrich_replay_step

enriched = enrich_replay_step(step_dict)
# Returns {**step_dict, "significance": "Plain English explanation."}
```

Each replay step gets a `significance` field that explains the operational impact of the event — the "So what?" for technicians and supervisors reviewing the audit trail.

## Architecture

```
repairgraph/insights/
├── __init__.py              # Public API: build_insight_payload, InsightFinding, InsightPayload
├── schema.py                # InsightFinding (frozen dataclass), InsightPayload, SEVERITY_ORDER
├── engine.py                # build_insight_payload() — orchestrates all rule modules
├── replay_enrichment.py     # enrich_replay_step() — adds significance to replay events
└── rules/
    ├── __init__.py
    ├── qa_findings.py        # QA gate rules
    ├── workflow_findings.py  # Phase and blocker rules
    ├── material_findings.py  # UHSS/HSS material rules
    ├── compliance_findings.py # Corrosion and calibration rules
    ├── intake_findings.py    # Document packet rules
    └── milestone_findings.py # Informational progress rules
```

## Design Constraints

- **No AI/LLM/inference**: All rules are deterministic Python functions.
- **No duplicated logic**: Rules read from `RepairState` and `manifest_dict` — they do not re-derive what the state engine already knows.
- **Deduplication by `finding_id`**: If two rules produce the same `finding_id`, the first one wins (rule order in `engine.py` defines precedence).
- **Advisory only**: `InsightPayload.advisory` is always `True`. Outputs require OEM verification and qualified technician review.

## Tests

```
tests/insights/
├── test_schema.py           # InsightFinding and InsightPayload schema
├── test_engine.py           # Engine output shape, sorting, status derivation
├── test_prioritization.py   # Severity sort ordering (critical before informational, etc.)
├── test_replay_enrichment.py # enrich_replay_step() behavior
├── test_demo_integration.py # Orchestrator and demo page integration
└── test_rules.py            # Individual rule module outputs
```

Run: `python -m pytest tests/insights/ -q`
