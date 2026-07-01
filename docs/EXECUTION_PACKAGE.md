# Execution Package Engine v0

## Overview

The Execution Package Engine converts a single Next Best Action from the
OperationalPlanner into a **structured, executable unit of work**.

It answers six questions:

| Question | Field |
|---|---|
| What are we trying to accomplish? | `objective` |
| What must already be true? | `prerequisites` |
| What must be verified? | `required_verifications` |
| What work is performed? | `execution_steps` |
| How do we know we're done? | `completion_criteria` |
| What becomes available afterwards? | `expected_unlocks` |

---

## Architecture

```
OperationalModel
       │
       ▼
RepairGraphCompiler
       │
       ▼
RootCauseAnalysis          ◄─ build_root_cause_analysis(model)
       │
       ▼
OperationalPlan            ◄─ build_operational_plan(model, rca)
       │
       ▼
OperationalNarrative       ◄─ build_narrative(plan)
       │
       ▼
ExecutionPackage           ◄─ build_execution_package(plan, narrative, model)
       │
       ▼
CollisionWorkPackage       ◄─ project_collision_work_package(pkg, narrative)
```

The `ExecutionPackage` is **domain-agnostic**.  
The `CollisionWorkPackage` is a **domain projection** for collision repair shops.

---

## ExecutionPackage — platform abstraction

`ExecutionPackage` lives in `src/repairgraph/core/execution_package.py`.

It is domain-agnostic: it contains no collision vocabulary, no OEM-specific
instructions, and no references to vehicle makes or models.

### Fields

| Field | Type | Description |
|---|---|---|
| `package_id` | `str` | UUID generated fresh on each build |
| `title` | `str` | Short headline (≤80 chars) derived from the narrated next best task |
| `objective` | `str` | One-sentence goal statement |
| `status` | `str` | `blocked` / `in_progress` / `ready` / `complete` |
| `priority` | `str` | `critical` / `high` / `medium` / `low` |
| `prerequisites` | `list[str]` | Conditions that must be true before work begins |
| `required_verifications` | `list[str]` | What must be checked/documented |
| `execution_steps` | `list[str]` | Work organisation steps (not OEM procedures) |
| `completion_criteria` | `list[str]` | Conditions that define "done" |
| `expected_unlocks` | `list[str]` | What becomes available after completion (max 6) |
| `blocked_by` | `list[str]` | Human-readable blockers, IDs stripped |
| `risk_reduction` | `str` | Narrated risk summary |
| `confidence` | `str` | `high` / `medium` / `low` |
| `supporting_evidence` | `list[str]` | Brief contextual evidence (max 5) |
| `generated_at` | `str` | ISO 8601 UTC timestamp |
| `advisory` | `str` | Mandatory advisory notice |

### Determinism

All fields except `package_id` and `generated_at` are deterministic.
Given the same `OperationalModel`, the same plan will produce the same
execution package. This makes the engine safe for integration testing.

---

## CollisionWorkPackage — domain projection

`CollisionWorkPackage` translates `ExecutionPackage` into collision-repair
vocabulary for technicians and shop managers.

### Field mapping

| ExecutionPackage | CollisionWorkPackage |
|---|---|
| `title` | `work_package_title` |
| `objective` | `purpose` |
| `status` → label | `repair_status` |
| `priority` → label | `urgency` |
| `prerequisites` | `before_you_start` |
| `required_verifications` | `verifications_required` |
| `execution_steps` | `work_to_perform` |
| `completion_criteria` | `done_when` |
| `expected_unlocks` | `what_this_unlocks` |
| `blocked_by` | `currently_blocked_by` |
| `risk_reduction` | `risk_note` |

Additional fields from the `OperationalNarrative`:

| Source | CollisionWorkPackage field |
|---|---|
| `narrative.technician_message` | `technician_brief` |
| `narrative.manager_message` | `manager_brief` |

### Status labels

| Internal | Human label |
|---|---|
| `blocked` | Blocked — Prerequisites Not Met |
| `in_progress` | In Progress |
| `ready` | Ready to Begin |
| `complete` | Complete |

### Urgency labels

| Internal | Human label |
|---|---|
| `critical` | Critical — Act Now |
| `high` | High Priority |
| `medium` | Normal Priority |
| `low` | Low Priority |

---

## Content principles

### The engine NEVER invents OEM procedures

`execution_steps` describes **work organisation**, not repair techniques:
- ✅ "Complete the primary verification task: …"
- ✅ "Document the verification outcome and retain records per shop procedure."
- ✅ "Confirm all related verification items before closing the gate."
- ❌ "Apply seam sealer at 3 mm width along the pinch weld."
- ❌ "Weld at 180 A using plug weld method per Honda procedure 14-22."

OEM procedures are the responsibility of the technician. The engine
organises work and surfaces verification requirements; it never prescribes
how the work is physically performed.

### All outputs are advisory

Every `ExecutionPackage` and `CollisionWorkPackage` carries an `advisory`
field that must be surfaced to the user. No output from this engine
constitutes a certification of repair quality or OEM compliance.

### No internal IDs in output

Internal identifiers (`qa:material_compliance:critical:2`, `blocker:...`,
`phase:...`) are stripped from all human-facing fields before output.
The narrator layer handles this for narrated fields; the engine strips
remaining IDs from `prerequisites`, `blocked_by`, and `execution_steps`.

---

## API endpoints

| Method | Path | Response |
|---|---|---|
| `GET` | `/internal/review/package` | `CollisionWorkPackage` as JSON + `execution_package` key |
| `GET` | `/internal/review` | HTML page including "Current Work Package" section |

The JSON endpoint also includes the inner `ExecutionPackage` as
`execution_package` for inspection and integration testing.

---

## Review page sections

The HTML review page renders `CollisionWorkPackage` in a "Current Work
Package" tab with five sections:

1. **Before You Start** — prerequisites that must be satisfied
2. **Verifications Required** — what must be checked/documented
3. **Work to Perform** — execution steps
4. **Done When** — completion criteria
5. **What This Unlocks** — downstream work that becomes available

Team briefs (technician and manager) appear at the bottom of the section.

---

## Integration

```python
from repairgraph.adapters.collision import CollisionDomainAdapter
from repairgraph.core.compiler import RepairGraphCompiler
from repairgraph.core.execution_package import build_execution_package, project_collision_work_package
from repairgraph.review.operational_planner import build_operational_plan
from repairgraph.review.narrator import build_narrative
from repairgraph.review.root_cause import build_root_cause_analysis

adapter = CollisionDomainAdapter(oem="Honda", year=2025, model="Accord",
    operation="quarter_panel_replacement", repair_area="left_rear",
    structural_involvement=True, calibration_required=True,
    corrosion_protection_required=True)

model = RepairGraphCompiler().compile_demo(adapter=adapter)
rca   = build_root_cause_analysis(model)
plan  = build_operational_plan(model, rca=rca)
nar   = build_narrative(plan)
pkg   = build_execution_package(plan, nar, model)
work  = project_collision_work_package(pkg, nar)

print(work.work_package_title)
print(work.repair_status)
for step in work.work_to_perform:
    print(f"  • {step}")
```

---

## Constraints (do not violate)

- Do not add databases, auth, ML, LLMs, scheduling, or technician assignment.
- Do not refactor `OperationalModel`, `RepairGraphCompiler`, `CollisionDomainAdapter`,
  the topology engine, or the state engine.
- `ExecutionPackage` must remain domain-agnostic: no collision vocabulary.
- `CollisionWorkPackage` must remain a pure projection: no new planning logic.
- No CDN, no external JS, no frameworks in the review page.
- All outputs are advisory.
