# Architecture De-Risk: Is the Core Actually Domain-Agnostic?

Three sprints of collision-repair-only development raised an obvious risk:
`operational_model.py` and `core/interfaces.py` are documented as
domain-agnostic, but nothing had ever tried to compile a non-collision
domain through them. A "generic" layer that has only ever seen one domain's
data is generic by assertion, not by proof.

This pass built a second, deliberately different domain — **aviation
maintenance** (an A320 landing gear 100-hour inspection task card) — and
pushed it through the *unmodified* compiler, state-projection engine, and
insights engine, using only their public generic surface. This was a stress
test, not a second product: there was no aviation review page, no aviation
intake pipeline, no aviation fixture data store. The goal was narrowly to
answer "does the core hold," not to build a second vertical.

**Status: all three coupling findings below have since been fixed.** The
"Findings" section is kept in its original form — including the original
fix directions — with a resolution note added to each, since the reasoning
for *why* each was a risk is still the useful part.

**The stress-test scaffolding itself was removed after serving its
purpose** (`adapters/aviation.py`, the aviation `RepairState` fixture, and
the portability test suite). Collision repair is the only vertical actually
under development right now; the intent of this pass was strictly to
validate that the *core* doesn't secretly assume collision data, not to
begin building a second product. Keeping a named-but-unused aviation adapter
in the tree would misrepresent that. What remains permanently is the fixed
code itself (domain-gated insights, pluggable zone classification, generic
session accessors) — the part that actually reduces risk for whenever a real
second vertical is brought in, by a domain expert, later. This document
stays as the historical record of what was tested and why.

## What holds — proven, not assumed

| Layer | Result |
| --- | --- |
| `DomainAdapter` protocol (`core/interfaces.py`) | Genuinely generic. A second adapter satisfied it with zero protocol changes. |
| `RepairGraphCompiler.compile_from_state` | Compiled aviation state with **no code changes**. `topology=None` is handled cleanly — spatial topology is optional, not assumed. |
| `OperationalModel` / `WorkflowSummary` / `AdvisoryNotice` / `ExportLinks` | All populated correctly from aviation data. `to_dict()` was fully JSON-serializable. |
| State schema (`RepairSession`, `PhaseState`, `ActionState`, `QAGateState`, `Blocker`, `ZoneActivation`) | Represented a task card with no awkwardness — phases/actions/QA-gates/blockers is genuinely domain-neutral vocabulary. |
| Event engine (`state/events.py`, `state/project.py`, `state/replay.py`) | `qa_gate_passed`, `blocker_resolved`, `action_started/completed` all projected correctly on aviation events. State progression generalizes without modification. |
| Fleet dashboard (`state/fleet.py`) | Not directly tested here (it reads from `data/normalized/`, a collision-specific file layout), but its aggregation logic already only touches `RepairState`, consistent with this test's findings. |

## What was coupled to collision repair — findings, now fixed

Three real coupling points surfaced. None blocked collision-repair
development, but all three would have blocked a real second domain. All
three are now fixed; the original analysis is kept below for context.

### 1. `insights/engine.py` runs collision rules unconditionally — FIXED

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

**Fix applied**: `insights/engine.py` now has a `DOMAIN_RULE_MODULES` table
mapping domain → the rule modules applicable to it. `material_findings` and
`compliance_findings` only run when `domain == "collision_repair"`.
`build_insight_payload(state, manifest_dict, domain=...)` defaults to
`domain="collision_repair"` so every existing caller is unaffected;
`RepairGraphCompiler.compile_from_state` now threads
`domain_context.domain` through automatically, so callers using the compiler
get correct gating with no code change on their part. Generic rule modules
(QA gates, workflow blockers, milestones, intake readiness) still run for
every domain — gating only applies to material/compliance concerns that are
inherently collision-specific.
Verified with the (since-removed) aviation stress test: the false
positive was gone once the aviation domain was passed through, generic
findings still fired, and collision behavior was unchanged by default.

### 2. `topology/builder.py`'s zone classifier is collision vocabulary, not generic — FIXED

`_classify_zone()` pattern-matches on `stiffener`, `separator`, `gutter`,
`rail`, `pillar`, `sill`, `wheel_arch`, `panel` — all collision body-panel
terms. It falls back to `"unknown"` for anything else rather than crashing,
so aviation zone IDs like `main_gear_strut` would classify as `unknown` /
`unknown` / `unknown` with zero useful structure. This wasn't exercised in
this stress test (the aviation fixture uses `topology=None`, which the
compiler accepts cleanly) — but it means **any domain needing spatial/
structural topology cannot reuse `build_topology_graph`** as-is.

A deeper coupling surfaced while fixing this: `RepairZone.__post_init__`
validated `zone_type`, `vehicle_section`, and `structural_tier` against
closed collision-only enums (`ALLOWED_ZONE_TYPES` etc. in
`topology/schema.py`) — so even a correct custom classifier's output
(`zone_type="landing_gear"`) was rejected outright with a `ValueError`. A
pluggable classifier alone was not sufficient.

**Fix applied**: `build_topology_graph(procedure, structure=None,
zone_classifier=collision_zone_classifier)` now accepts a `ZoneClassifier`
function (`zone_id -> (zone_type, vehicle_section, structural_tier)`).
`_classify_zone` was renamed `collision_zone_classifier` and kept as the
default and as a backward-compatible alias (`_classify_zone =
collision_zone_classifier`) for existing imports. `RepairZone`'s validation
was relaxed from closed-set membership to "non-empty string" — the
`ALLOWED_*` sets in `topology/schema.py` are now documentation of collision
repair's vocabulary, not a validation gate. Verified with the (since-removed) aviation stress test: a custom
classifier produced non-collision zone types end-to-end, and collision
behavior was byte-for-byte unchanged by default.

### 3. `RepairSession` fields are named after collision concepts — FIXED

`RepairSession` has `oem`, `year`, `model`, `operation` — no generic
`primary_identifier` / `secondary_identifier` slots. The aviation adapter's
`from_repair_state` has to reuse `session.oem` to mean "aircraft type" and
`session.model` to mean "registration," which works but is a naming leak:
reading `RepairState` code cold, you'd assume every domain has an OEM and a
vehicle model. This is the most cosmetic of the three findings — it doesn't
block anything — but it's the first thing a second real adapter author would
trip on.

**Fix applied**: rather than rename the stored fields (16 call sites across
the collision product layer read `session.oem`/`.model`/`.operation`
directly — a rename would be pure churn risk for a cosmetic issue),
`RepairSession` gained three read-only properties: `primary_context`
(alias for `oem`), `secondary_context` (alias for `model`), `context_label`
(alias for `operation`). Existing code is completely unaffected — the
underlying fields, their names, and their values are unchanged. The
(since-removed) aviation adapter's `from_repair_state` was updated to read
the session through these domain-neutral properties instead of reusing
`session.oem` to mean "aircraft type," resolving the naming leak at the
point where it was actually felt.

**Why not rename outright**: additive properties get 100% of the risk
reduction (no domain-adapter author needs to read collision-named fields
directly to write correct code) at 0% of the blast radius. A future
domain that needs the session schema to carry meaningfully different data
(not just a differently-named label) is a bigger conversation than a stress
test warrants — this fix closes the immediate finding without pre-committing
to that redesign.

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

All three coupling findings are now fixed, each with zero behavior change
for existing collision-repair callers (verified by the full test suite
passing at the time, including every pre-existing collision test unmodified
except two that pinned the old closed-set topology validation and were
updated to assert the new, intentionally relaxed contract). The cost of
fixing all three together was small — a domain-gating table, a classifier
parameter plus relaxed validation, and three read-only properties —
confirming the original assessment that fixing this now, with one domain's
worth of code depending on the current shape, was cheap. Doing this after a
second real vertical was built on top would not have been.

To be explicit about scope: this was architecture validation, not the start
of a second vertical. Collision repair remains the only product under
development. The point of this exercise was to confirm the core doesn't
quietly assume collision data — so that whenever a real second domain is
brought in later, by a domain expert building that vertical properly, it
inherits a core that was already checked rather than one that's generic in
name only.
