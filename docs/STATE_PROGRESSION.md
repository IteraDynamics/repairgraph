# State Progression

State progression is what turns the Repair Review from a static snapshot into a
live operational picture. The system already knew everything that *needs* to
happen (phases, actions, QA gates, blockers); this layer records what *has*
happened and rebuilds every review from that record.

## The model

```
initialize_repair_state(procedure, structure)      ← everything starts open/pending
        │
        ▼
data/sessions/<oem>/<year>_<model>/events.json     ← append-only event journal
        │
        ▼
project_repair_state(initial_state, events)        ← deterministic replay
        │
        ▼
RepairGraphCompiler.compile_from_state(...)        ← OperationalModel
        │
        ▼
Review page / payload / plan / narrative / package ← all reflect current state
```

Nothing is mutated in place. The journal is the single source of truth for
progress; the current state is always re-derived by replaying the journal over
the initial projection. Deleting the journal returns the repair to its initial
unstarted state.

No database. Each session journal is a JSON file, following the same storage
pattern as `data/active_vehicle.json` and `data/normalized/`.

## Recording progress

### Endpoints

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/internal/review/progress` | Current projected state: phases, actions, QA gates, blockers, recorded events |
| `POST` | `/internal/review/progress/events` | Record one progress event |
| `DELETE` | `/internal/review/progress` | Reset — clear the journal |
| `GET` | `/internal/review/progress/ui` | Self-contained progress page with record controls |

All four resolve the vehicle the same way as the other review endpoints:
explicit `?oem=&year=&model=` query params, else the active vehicle set by the
intake pipeline. There is no demo fallback for progress — the Honda Accord
demo walkthrough is scripted and does not accept events (use explicit params
to track real progress against the Accord fixture instead).

### Event vocabulary

`POST /internal/review/progress/events` accepts:

```json
{
  "event_type": "qa_gate_passed",
  "target_id": "qa:joining_compliance:high:1",
  "actor": "manager",
  "notes": "verified against OEM joining sheet"
}
```

Supported event types (target type is derived automatically):

| Event | Target | Effect |
| --- | --- | --- |
| `action_started` | action | action → in_progress; phase and session → in_progress |
| `action_completed` | action | action → complete; zone completion recomputed |
| `action_blocked` | action | action, phase, session → blocked |
| `action_marked_not_applicable` | action | counts as finished without being performed |
| `qa_gate_passed` | qa_gate | gate → passed; **derived blocker auto-resolved** |
| `qa_gate_failed` | qa_gate | gate → failed |
| `qa_gate_marked_not_applicable` | qa_gate | gate waived; derived blocker auto-resolved |
| `blocker_resolved` | blocker | blocker → resolved; blocked phases recover |
| `phase_started` / `phase_completed` | phase | explicit phase transitions |
| `session_started` / `session_completed` / `session_cancelled` | session | explicit session transitions |

Every event is validated against the current projected state before it is
journaled. Unknown targets and incompatible event/target combinations are
rejected with `422` and nothing is written.

### Gate → blocker companion resolution

Blocking QA gates create derived blockers (`blocker:<gate_id>`) at
initialization. Passing (or waiving) a gate automatically records a companion
`blocker_resolved` event in the same request, so clearing a gate immediately
unblocks the work it was holding. Both events appear in the journal — the
audit trail shows exactly what was resolved and why.

## What the review shows as state moves

Using the Honda 2025 Accord fixture (`?oem=Honda&year=2025&model=Accord`):

| Repair state | Page hero | Payload decision | Workflow readiness |
| --- | --- | --- | --- |
| Initial (nothing recorded) | BLOCKED | Blocked | blocked |
| All blocking gates passed | PROCEED WITH CAUTION | Proceed with Caution | not_started |
| Actions being completed | PROCEED WITH CAUTION | Proceed with Caution | in_progress |
| Journal cleared (reset) | BLOCKED | Blocked | blocked |

The decision, immediate actions, technician/manager guidance, work package,
and narrative all re-derive from the projected state on every request — the
review answers "what should happen next" based on what has actually happened.

## Projection engine fixes

Two latent dead-end states in `state/project.py` were fixed (they were
unreachable before progression existed, because nothing could ever resolve a
blocker):

1. **Blocked phases now recover.** Previously a phase marked `blocked` was
   skipped by recomputation forever, even after every blocker on it was
   resolved. Phases now re-derive their status from actual action progress
   once nothing blocks them.
2. **Blocked sessions now recover.** A session blocked by a blocked action
   returns to `in_progress` once no phase remains blocked.

## Source manifest readiness

`compile_from_state` now accepts `manifest_overrides`, and the review supplies
them from the normalized procedure's `source` block:

- **Intake-derived vehicles** carry the readiness (`ready`/`partial`) and file
  list recorded at classification time.
- **Authored fixtures** are complete seed packets (`ready`).

Before this, every vehicle-resolved review reported "Insufficient Packet"
regardless of state, because the compiled model had no manifest information.

## Trust semantics

Recording an event documents that a human performed or verified work. It does
not certify that work. All projected state remains advisory workflow
intelligence: it does not certify repair completion, OEM compliance, or repair
quality, and requires verification by a qualified technician against current
OEM procedures. The journal preserves actor, timestamp, and notes for every
recorded event, so every state transition is traceable to who recorded it.
