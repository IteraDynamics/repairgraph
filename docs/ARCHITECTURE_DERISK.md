# Architecture De-Risk: Is the Core Actually Domain-Agnostic?

Three sprints of collision-repair-only development raised an obvious risk:
`operational_model.py` and `core/interfaces.py` are documented as
domain-agnostic, but nothing had ever tried to compile a non-collision
domain through them. A "generic" layer that has only ever seen one domain's
data is generic by assertion, not by proof.

This pass built a second, deliberately different domain — **aviation
maintenance** (an A320 landing gear 100-hour inspection task card) — and
pushed it through the *unmodified* compiler, state-projection engine, and
insights engine, using only their public generic surface. This is a stress
test, not a second product: there is no aviation review page, no aviation
intake pipeline, no aviation fixture data store. The goal was narrowly to
answer "does the core hold," not to build a second vertical.

## What was built

- `src/repairgraph/adapters/aviation.py` — `AviationDomainAdapter`, satisfying
  the same `DomainAdapter` protocol as `CollisionDomainAdapter`. Task card ID,
  ATA chapter, aircraft type/registration, airworthiness directives in place
  of OEM/model/repair-area.
- `tests/fixtures/aviation_task_card.py` — a `RepairState` built **directly**
  from the generic dataclasses (`RepairSession`, `PhaseState`, `ActionState`,
  `QAGateState`, `Blocker`, `ZoneActivation`) with no topology, no procedure
  JSON, no OEM data. Deliberately bypasses `initialize_repair_state`,
  `build_operation_sequence`, `generate_qa_checklist`, and
  `build_topology_graph` — those are collision-coupled helper functions, not
  core, and using them would have proven nothing about portability (see
  findings below for why).
- `tests/test_domain_portability.py` — 17 tests compiling the aviation state
  through `RepairGraphCompiler.compile_from_state`, replaying progress events
  through `project_repair_state`, and running `build_insight_payload`
  against it.

## What holds — proven, not assumed

| Layer | Result |
| --- | --- |
| `DomainAdapter` protocol (`core/interfaces.py`) | Genuinely generic. `AviationDomainAdapter` satisfies it with zero protocol changes. |
| `RepairGraphCompiler.compile_from_state` | Compiles aviation state with **no code changes**. `topology=None` is handled cleanly — spatial topology is optional, not assumed. |
| `OperationalModel` / `WorkflowSummary` / `AdvisoryNotice` / `ExportLinks` | All populate correctly from aviation data. `to_dict()` is fully JSON-serializable. |
| State schema (`RepairSession`, `PhaseState`, `ActionState`, `QAGateState`, `Blocker`, `ZoneActivation`) | Represents a task card with no awkwardness — phases/actions/QA-gates/blockers is genuinely domain-neutral vocabulary. |
| Event engine (`state/events.py`, `state/project.py`, `state/replay.py`) | `qa_gate_passed`, `blocker_resolved`, `action_started/completed` all project correctly on aviation events. State progression (Sprint: state progression) generalizes without modification. |
| Fleet dashboard (`state/fleet.py`) | Not directly tested here (it reads from `data/normalized/`, a collision-specific file layout), but its aggregation logic already only touches `RepairState`, consistent with this test's findings. |

## What's coupled to collision repair — findings, not fixed here

Three real coupling points surfaced. None of these block collision-repair
development; all three are documented so they're deliberate debt, not
invisible debt.

### 1. `insights/engine.py` runs collision rules unconditionally

`build_insight_payload()` always calls `material_findings.uhss_detected`,
`material_findings.joining_verification_required`,
`compliance_findings.corrosion_protection_blocked`,
`compliance_findings.corrosion_qa_open` — regardless of `domain_context.domain`.
Most of these degrade gracefully (they check for zones/gates that don't exist
in aviation data and simply return no findings). **One does not degrade
gracefully**: `compliance_findings.calibration_not_identified` fires
unconditionally whenever no `calibration`-category QA gate exists — which is
true of a landing gear inspection, where "calibration" is meaningless. The
aviation model gets a collision-flavored false positive
(`compliance_calibration_not_identified`) with no way to suppress it.
`test_domain_portability.py::TestKnownCouplingInsightsEngine` pins this down
as a regression trap — if it's fixed, that test should start failing and be
updated.

**Fix direction**: gate rule modules by `domain_context.domain`, or move
domain-specific rule sets into the adapter itself (an adapter-supplied list of
applicable rule modules), so a new domain doesn't inherit collision findings
by default.

### 2. `topology/builder.py`'s zone classifier is collision vocabulary, not generic

`_classify_zone()` pattern-matches on `stiffener`, `separator`, `gutter`,
`rail`, `pillar`, `sill`, `wheel_arch`, `panel` — all collision body-panel
terms. It falls back to `"unknown"` for anything else rather than crashing,
so aviation zone IDs like `main_gear_strut` would classify as `unknown` /
`unknown` / `unknown` with zero useful structure. This wasn't exercised in
this stress test (the aviation fixture uses `topology=None`, which the
compiler accepts cleanly) — but it means **any domain needing spatial/
structural topology cannot reuse `build_topology_graph`** as-is.

**Fix direction**: classification vocabulary should come from the adapter
(or a domain-specific classifier plugin), not be hardcoded in the "generic"
topology builder.

### 3. `RepairSession` fields are named after collision concepts

`RepairSession` has `oem`, `year`, `model`, `operation` — no generic
`primary_identifier` / `secondary_identifier` slots. The aviation adapter's
`from_repair_state` has to reuse `session.oem` to mean "aircraft type" and
`session.model` to mean "registration," which works but is a naming leak:
reading `RepairState` code cold, you'd assume every domain has an OEM and a
vehicle model. This is the most cosmetic of the three findings — it doesn't
block anything — but it's the first thing a second real adapter author would
trip on.

**Fix direction**: rename to domain-neutral fields (`primary_id`,
`secondary_id`, `context_label`) when a second domain actually needs the
session schema to carry more than a generic label — not worth an invasive
rename for a stress test alone.

### Known, deliberate non-finding: the review/product layer

`review/review_payload.py`, `review/review_page.py`, `review/routes.py`,
`ExecutionPackage` → `CollisionWorkPackage` projection, and the intake→
normalize pipeline are **collision-repair product code**, not core. They
assume `domain_context.context_data["vehicle"]`, OEM terminology, and the
`data/normalized/<oem>/<year>_<model>/` file layout throughout. This is
correct and expected — they are the first commercial application described
in the platform vision, not the reasoning engine itself. A second domain
would get its own product layer (its own review UI, its own intake), built
on the same core. Nothing here recommends touching them.

## Bottom line

The core claim — `OperationalModel`, `RepairGraphCompiler`, the state schema,
and the event/replay engine are domain-agnostic — **holds**. A second,
unrelated domain compiles through all of it with zero core code changes.
The three findings above are the concrete, now-documented cost of adding a
real second domain later: gate the insights rule modules, make topology
classification pluggable, and consider renaming `RepairSession`'s collision-
named fields. None are large; all are cheaper to fix now, with one domain's
worth of code depending on the current shape, than after a second real
vertical is built on top of them.
