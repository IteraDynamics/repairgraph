# Repair Execution State Model

## Purpose

RepairGraph currently models what a repair procedure contains: components, dependencies, joining methods, corrosion requirements, material risks, QA checks, operation sequence, and spatial topology.

The next architectural layer is repair execution state: a structured model of where a repair is in its lifecycle, what has been completed, what remains, what is blocked, which zones are active, and which QA gates must be resolved before progression.

This document defines the first version of that state model. It is intentionally advisory and infrastructure-first. It does not replace OEM procedures, technician judgment, or shop documentation requirements.

## Conceptual shift

```text
static procedure intelligence
    |
    v
stateful repair workflow intelligence
```

RepairGraph should be able to answer:

- What phase is currently active?
- Which operation steps are complete, pending, blocked, or not applicable?
- Which repair zones are active in the current phase?
- Which QA checks remain unresolved?
- What evidence supports the current state?
- What should be verified before moving forward?

## Core principles

1. **OEM primacy** - OEM procedures remain authoritative.
2. **Advisory state** - RepairGraph tracks workflow state; it does not certify repair completion.
3. **Evidence-backed transitions** - Every state transition should carry evidence, operator/source, timestamp, and basis.
4. **Deterministic progression** - State is derived from known operation phases, topology regions, QA gates, and explicit completion events.
5. **No hidden automation authority** - RepairGraph may suggest next actions but should not silently advance repair state without an explicit event.
6. **Append-only event history** - State should be reconstructable from an event ledger.

## Relationship to existing layers

```text
Normalized procedure
    |
    v
Operation sequence
    |
    v
Spatial topology
    |
    v
QA checklist
    |
    v
Repair state model
    |
    v
Execution guidance / AR / workflow UI
```

The state model consumes existing RepairGraph outputs:

| Existing layer | State model usage |
|---|---|
| Sequencing | Defines phases and action order |
| Topology | Maps phases/actions to zones |
| QA checklist | Defines gates and verification items |
| Evidence model | Provides provenance for transitions |
| Supplement inference | Can surface unresolved estimate/documentation candidates |
| Material risk | Can block or warn during joining/verification phases |

## State entities

### RepairSession

Represents one repair workflow instance for one vehicle/operation.

```json
{
  "session_id": "session_2025_honda_accord_qp_001",
  "oem": "Honda",
  "year": 2025,
  "model": "Accord",
  "operation": "rear_side_outer_panel_replacement",
  "status": "in_progress",
  "current_phase": "component_replacement",
  "created_at": "2026-01-01T09:00:00Z",
  "updated_at": "2026-01-01T11:30:00Z"
}
```

Allowed session statuses:

| Status | Meaning |
|---|---|
| `not_started` | Session created but no phase has begun |
| `in_progress` | At least one phase has started and final completion has not occurred |
| `blocked` | Progression is blocked by unresolved dependency or QA gate |
| `ready_for_review` | Operations are complete but final review/QA remains |
| `complete` | Workflow has been marked complete by explicit event |
| `cancelled` | Session abandoned or superseded |

### PhaseState

Represents the state of one operation phase.

```json
{
  "phase": 3,
  "name": "component_replacement",
  "label": "Component Removal and Replacement",
  "status": "in_progress",
  "active_zones": [
    "rear_combination_adapter",
    "rear_pillar_separator",
    "wheel_arch_separator"
  ],
  "completed_actions": [
    "rear_combination_adapter_replace_component"
  ],
  "pending_actions": [
    "rear_pillar_separator_replace_component",
    "wheel_arch_separator_replace_component"
  ],
  "blocked_by": []
}
```

Allowed phase statuses:

| Status | Meaning |
|---|---|
| `not_started` | No action event recorded for this phase |
| `in_progress` | At least one action started/completed, phase not complete |
| `blocked` | Unresolved blocker prevents phase progression |
| `ready_for_review` | Actions complete, QA review pending |
| `complete` | Explicit completion event recorded |
| `not_applicable` | Explicitly marked not applicable with evidence/reason |

### ActionState

Represents one actionable item derived from sequencing, dependencies, joining, corrosion, or verification.

```json
{
  "action_id": "replace_component:rear_pillar_separator",
  "phase": 3,
  "action_type": "replace_component",
  "target": "rear_pillar_separator",
  "status": "pending",
  "zone_refs": ["rear_pillar_separator"],
  "requires_qa": true,
  "evidence": {
    "source_type": "normalized_procedure",
    "basis": ["procedure_dependency", "replace_component"],
    "confidence": "high",
    "requires_oem_verification": true,
    "interpretation": "advisory"
  }
}
```

Allowed action statuses:

| Status | Meaning |
|---|---|
| `pending` | Action has not started |
| `in_progress` | Work has begun |
| `complete` | Explicit completion event recorded |
| `blocked` | Action cannot proceed due to unresolved requirement |
| `not_applicable` | Explicitly excluded with reason/evidence |
| `needs_review` | Action requires QA or supervisor review |

### QAGateState

Represents a verification requirement that may block progression or final completion.

```json
{
  "gate_id": "qa:material_compliance:rear_roof_rail_upper",
  "category": "material_compliance",
  "priority": "critical",
  "status": "open",
  "related_phase": 4,
  "zone_refs": ["rear_roof_rail_upper"],
  "check": "Verify OEM-specified joining method for joins adjacent to rear roof rail upper (1500 MPa UHSS)",
  "blocks_completion": true,
  "evidence": {
    "source_type": "normalized_structure",
    "basis": ["material_strength_at_or_above_uhss_threshold", "vehicle_structure_material_map"],
    "confidence": "medium",
    "requires_oem_verification": true,
    "interpretation": "advisory"
  }
}
```

Allowed QA gate statuses:

| Status | Meaning |
|---|---|
| `open` | Gate unresolved |
| `in_review` | Gate under review |
| `passed` | Explicit pass event recorded |
| `failed` | Explicit fail event recorded |
| `not_applicable` | Explicitly excluded with reason/evidence |

### ZoneActivation

Represents whether a repair zone is currently active, pending, complete, or blocked.

```json
{
  "zone_id": "rear_pillar_separator",
  "label": "rear pillar separator",
  "status": "active",
  "active_phase": 3,
  "active_actions": ["replace_component:rear_pillar_separator"],
  "material_classification": null,
  "risk_flags": []
}
```

Allowed zone statuses:

| Status | Meaning |
|---|---|
| `inactive` | Zone not currently involved |
| `pending` | Zone will be involved in a future phase |
| `active` | Zone is involved in the current phase |
| `complete` | All zone-linked actions/gates complete |
| `blocked` | Zone has an unresolved blocker |

## Event ledger

Repair state should be event-sourced. The current state is a projection of append-only events.

Example event:

```json
{
  "event_id": "evt_001",
  "timestamp": "2026-01-01T10:15:00Z",
  "event_type": "action_completed",
  "actor": "technician",
  "target_type": "action",
  "target_id": "replace_component:rear_combination_adapter",
  "notes": "Adapter replaced and documented.",
  "evidence": {
    "source_type": "manual_review",
    "basis": ["technician_confirmation"],
    "confidence": "medium",
    "requires_oem_verification": true,
    "interpretation": "advisory"
  }
}
```

Recommended event types:

| Event type | Meaning |
|---|---|
| `session_started` | Repair session begins |
| `phase_started` | Phase begins |
| `phase_completed` | Phase explicitly completed |
| `action_started` | Action begins |
| `action_completed` | Action explicitly completed |
| `action_blocked` | Action blocked by requirement |
| `action_marked_not_applicable` | Action excluded with reason |
| `qa_gate_opened` | QA gate created/opened |
| `qa_gate_passed` | QA gate passed |
| `qa_gate_failed` | QA gate failed |
| `qa_gate_marked_not_applicable` | Gate excluded with reason |
| `blocker_added` | Explicit blocker added |
| `blocker_resolved` | Blocker resolved |
| `session_completed` | Session marked complete |
| `session_cancelled` | Session cancelled |

## Blockers

A blocker prevents phase or session progression until resolved.

```json
{
  "blocker_id": "blocker:qa:rear_roof_rail_upper_joining",
  "type": "qa_gate",
  "severity": "critical",
  "status": "open",
  "blocks": ["phase:4", "session_completion"],
  "reason": "UHSS joining verification is unresolved.",
  "related_zones": ["rear_roof_rail_upper"],
  "related_actions": ["apply_joining_method:mig_brazing"]
}
```

Blocker types:

| Type | Example |
|---|---|
| `qa_gate` | Critical QA item unresolved |
| `dependency` | Prior action incomplete |
| `material_risk` | UHSS joining verification unresolved |
| `corrosion_requirement` | Sealer/adhesive/undercoating gate unresolved |
| `manual_hold` | User/supervisor hold |
| `documentation_required` | Photo, scan, invoice, or estimate documentation missing |

## State projection rules

Initial implementation should be conservative:

1. A session begins as `not_started`.
2. Starting an action starts its phase and session.
3. Completing an action does not automatically complete the phase unless all phase actions are complete or not applicable.
4. Critical QA gates block session completion by default.
5. `not_applicable` requires an explicit event and reason.
6. Phase completion requires no unresolved blockers for that phase.
7. Session completion requires all phases complete/not applicable and all blocking QA gates passed/not applicable.
8. RepairGraph may recommend next actions but should not advance state without explicit events.

## Repair state output shape

A projected state object should look like:

```json
{
  "session": {
    "session_id": "session_001",
    "status": "in_progress",
    "current_phase": "component_replacement"
  },
  "phases": [],
  "actions": [],
  "qa_gates": [],
  "zones": [],
  "blockers": [],
  "next_recommended_actions": [],
  "interpretation_note": "Repair state outputs are advisory workflow projections derived from RepairGraph procedure data and explicit state events. They do not certify repair completion and require OEM and shop-process verification."
}
```

## Future AR enablement

The state model is the missing layer between topology and live AR guidance.

| AR requirement | State model support |
|---|---|
| Show current step | `current_phase` + active `ActionState` |
| Highlight current zone | `ZoneActivation.status == active` |
| Warn before joining | open material/QA blockers |
| Show next operation | `next_recommended_actions` |
| Require verification before moving on | blocking `QAGateState` |
| Track repair progression | event ledger + state projection |

## Non-goals for v0

- No certification of repair quality
- No automated completion without explicit event
- No replacement of OEM procedure review
- No technician surveillance or productivity scoring
- No claims that a repair is compliant solely because state is complete

## Implementation plan

Recommended modules:

```text
src/repairgraph/state/
  __init__.py
  schema.py              # dataclasses / allowed statuses
  initialize.py          # build initial state from sequence + topology + QA
  events.py              # event dataclasses and validation
  project.py             # apply event ledger to current state
  blockers.py            # derive blockers from QA/material/dependency state
  next_actions.py        # recommend next advisory action(s)
  cli.py                 # export sample state projections
```

Recommended tests:

```text
tests/test_state_schema.py
tests/test_state_initialize.py
tests/test_state_events.py
tests/test_state_projection.py
tests/test_state_blockers.py
tests/test_state_next_actions.py
```

## First implementation milestone

Milestone 0.7 should implement:

1. State schema dataclasses with validation
2. Initial state projection from existing sequence/topology/QA outputs
3. Append-only event application
4. Basic blocker derivation
5. Next-action recommendation
6. CLI export for all Honda seed procedures
7. Tests for state initialization, projection, blockers, and advisory semantics

## AR Workflow Payload Contract

The AR workflow payload contract defines a stable, machine-readable payload shape
that AR technician interfaces, workflow UIs, and API clients can consume.
It is built on top of the existing repair state layer and is not a renderer, UI,
or API endpoint.

**Module:** `repairgraph.state.ar_payload`

**CLI command:**

```bash
python -m repairgraph.state.ar_cli
```

**Output path:**

```text
data/extracted/state/accord_ar_workflow_payload.json
```

**Advisory caveat:** All AR workflow payload outputs are advisory workflow
intelligence derived from RepairGraph procedure data and explicit state events.
They do not certify repair completion, OEM compliance, or repair quality.
OEM procedure verification and qualified technician review are required before
acting on any recommendation.

**Top-level payload sections:**

| Section | Description |
|---|---|
| `schema_name` | Always `"repairgraph.ar_workflow_payload"` |
| `schema_version` | Always `"0.1"` |
| `advisory` | Always `true` |
| `generated_by` | Always `"repairgraph.state.ar_payload"` |
| `advisory_note` | Human-readable advisory disclaimer |
| `session` | Session identity: session_id, oem, year, model, operation, status, current_phase |
| `workflow_summary` | Aggregate counts: phases, actions, QA gates, blockers, open blockers, events, next actions |
| `active_context` | Active/blocked phase and zone IDs; next action IDs |
| `overlays` | Lists of zone overlays, action guidance, QA gate items, and blocker items — each with a `guidance_role` or `overlay_role` classifier |
| `source_state` | Source schema reference: `"repairgraph.repair_state"` v0.1 |

**Public functions:**

- `build_ar_workflow_payload(state)` — builds the complete payload dict
- `build_zone_overlay_items(state)` — zone items with `overlay_role`
- `build_action_guidance_items(state)` — action items with `guidance_role`
- `build_qa_gate_items(state)` — QA gate items with `guidance_role`
- `build_blocker_items(state)` — blocker items with `guidance_role`

## Implementation status

All core state workflow modules are implemented.

| Module | Status |
|---|---|
| `schema.py` | implemented |
| `initialize.py` | implemented |
| `events.py` | implemented |
| `project.py` | implemented |
| `export_json.py` | implemented |
| `blockers.py` | implemented |
| `next_actions.py` | implemented |
| `cli.py` | implemented |
| `ar_payload.py` | implemented |
| `ar_cli.py` | implemented |
| `demo.py` | implemented |
| `api/app.py` | implemented |
| `api/state_routes.py` | implemented |

Tests implemented:

| Test file | Status |
|---|---|
| `tests/test_state_schema.py` | implemented |
| `tests/test_state_initialize.py` | implemented |
| `tests/test_state_events.py` | implemented |
| `tests/test_state_project.py` | implemented |
| `tests/test_state_export.py` | implemented |
| `tests/test_state_blockers.py` | implemented |
| `tests/test_state_next_actions.py` | implemented |
| `tests/test_state_cli.py` | implemented |
| `tests/test_state_ar_payload.py` | implemented |
| `tests/test_state_ar_cli.py` | implemented |
| `tests/test_state_api.py` | implemented |

## API delivery

State workflow and AR payload intelligence is also available through a local
FastAPI application. Endpoints are deterministic and serve the same outputs as
the CLI tools, without writing any files.

**Modules:**

- `repairgraph.api.app` — FastAPI application
- `repairgraph.api.state_routes` — Internal state router (`/internal/state/accord/*`)

**Endpoints:**

| Endpoint | Response |
|---|---|
| `GET /internal/state/accord/initial` | Initial Accord RepairState (no events applied) |
| `GET /internal/state/accord/projected` | Projected state after deterministic demo event ledger |
| `GET /internal/state/accord/ar-payload` | AR workflow payload for projected state |
| `GET /internal/state/accord/summary` | Compact summary: session, counts, blockers, next actions |

All responses are generated from the same `state/demo.py` helper functions used
by the CLI tools. No files are written on any request.

**Response schemas:**

- `/initial` and `/projected`: `repairgraph.repair_state` v0.1 — same schema as `export_state_to_dict()`
- `/ar-payload`: `repairgraph.ar_workflow_payload` v0.1 — same schema as `build_ar_workflow_payload()`
- `/summary`: `repairgraph.repair_state.summary` — compact subset

All responses include `advisory: true` and an `advisory_note` field.

## CLI usage

Initialize a Honda 2025 Accord repair state, apply a deterministic sample event
ledger, project the resulting state, and export to JSON:

```bash
python -m repairgraph.state.cli
```

Output:

```text
data/extracted/state/accord_projected_state.json
```

The summary printed to stdout includes session status, phase/action/QA gate/blocker
counts, number of events applied, and next recommended action count.

## Advisory note

All generated state JSON is **advisory workflow intelligence** derived from
RepairGraph procedure data and explicit state events.

It is not certification of repair completion, OEM compliance, or repair quality.
All state projections require OEM procedure verification and qualified technician
review before acting on any recommendation.
