# RepairGraph Internal State API Contract

## Purpose

The RepairGraph internal state API exposes the state workflow layer and AR
payload intelligence through local FastAPI endpoints. It is a demo/development
convenience surface, not a production API. No authentication is required.
No data is persisted. All responses are deterministic advisory outputs generated
from the Honda 2025 Accord seed dataset.

## Non-goals

- **No authentication or authorization** — endpoints are open and local-only
- **No persistence** — no database, no file writes, no session storage
- **No production claims** — not a stable external API surface
- **No repair certification** — outputs do not certify repair completion or OEM compliance
- **No OEM document redistribution** — outputs are derived intelligence, not OEM document content
- **No AR rendering** — outputs are payload contracts, not rendered overlays
- **No external network calls** — all data is derived from local normalized seed data

## Endpoints

### `GET /internal/state/accord/initial`

Returns the initial (un-projected) RepairState for the Honda 2025 Accord.
No events are applied. Session status is `not_started`.

**Response schema:** `repairgraph.repair_state` v0.1

**Top-level fields:**

| Field | Type | Description |
|---|---|---|
| `schema_name` | string | Always `"repairgraph.repair_state"` |
| `schema_version` | string | Always `"0.1"` |
| `advisory` | boolean | Always `true` |
| `generated_by` | string | Always `"repairgraph.state"` |
| `advisory_note` | string | Advisory disclaimer text |
| `endpoint_advisory` | string | Endpoint-level advisory note |
| `session` | object | Session identity and status |
| `phases` | array | Phase states |
| `actions` | array | Action states |
| `qa_gates` | array | QA gate states |
| `zones` | array | Zone activation states |
| `blockers` | array | Blocker states |
| `events` | array | Applied events (empty for initial) |
| `next_recommended_actions` | array | Advisory next action IDs |
| `interpretation_note` | string | Interpretation advisory |

---

### `GET /internal/state/accord/projected`

Returns the RepairState after applying the deterministic demo event ledger.
Applies: session_started, phase_started, action_started, action_completed,
qa_gate_passed, blocker_resolved. Session status is `in_progress`.

**Response schema:** `repairgraph.repair_state` v0.1

Same fields as `/initial`, plus:

| Field | Notable value |
|---|---|
| `session.status` | `"in_progress"` |
| `events` | Non-empty list with deterministic event IDs |
| `next_recommended_actions` | Advisory next action IDs |

---

### `GET /internal/state/accord/ar-payload`

Returns the AR workflow payload for the projected Accord state. Suitable for
consumption by AR technician interfaces, workflow UIs, or API clients.

**Response schema:** `repairgraph.ar_workflow_payload` v0.1

**Top-level fields:**

| Field | Type | Description |
|---|---|---|
| `schema_name` | string | Always `"repairgraph.ar_workflow_payload"` |
| `schema_version` | string | Always `"0.1"` |
| `advisory` | boolean | Always `true` |
| `generated_by` | string | Always `"repairgraph.state.ar_payload"` |
| `advisory_note` | string | Advisory disclaimer text |
| `endpoint_advisory` | string | Endpoint-level advisory note |
| `session` | object | Session identity and status |
| `workflow_summary` | object | Aggregate counts |
| `active_context` | object | Active/blocked phase and zone IDs; next action IDs |
| `overlays` | object | Zone overlays, action guidance, QA gates, blockers |
| `source_state` | object | Source schema reference |

**`workflow_summary` fields:**

| Field | Type | Description |
|---|---|---|
| `phase_count` | int | Total phase count |
| `action_count` | int | Total action count |
| `qa_gate_count` | int | Total QA gate count |
| `blocker_count` | int | Total blocker count |
| `open_blocker_count` | int | Open (unresolved) blocker count |
| `event_count` | int | Applied event count |
| `next_action_count` | int | Advisory next action count |

**`overlays` structure:**

| Key | Item fields | Role field |
|---|---|---|
| `zones` | `zone_id`, `label`, `status`, `active_phase`, `active_actions`, `material_classification`, `risk_flags` | `overlay_role` |
| `actions` | `action_id`, `action_type`, `target`, `phase`, `status`, `zone_refs`, `requires_qa`, `evidence` | `guidance_role` |
| `qa_gates` | `gate_id`, `category`, `priority`, `status`, `related_phase`, `zone_refs`, `check`, `blocks_completion`, `evidence` | `guidance_role` |
| `blockers` | `blocker_id`, `type`, `severity`, `status`, `blocks`, `reason`, `related_zones`, `related_actions` | `guidance_role` |

**Overlay role values (`zones`):**

| Value | Meaning |
|---|---|
| `active_repair_zone` | Zone is currently active |
| `blocked_zone` | Zone has an unresolved blocker |
| `completed_zone` | Zone's actions are complete |
| `inactive_context_zone` | Zone is inactive or pending |

**Guidance role values (`actions`):**

| Value | Meaning |
|---|---|
| `next_recommended_action` | Action is in `next_recommended_actions` |
| `active_action` | Status is `in_progress` |
| `blocked_action` | Status is `blocked` |
| `completed_action` | Status is `complete` |
| `not_applicable_action` | Status is `not_applicable` |
| `pending_context_action` | All other cases |

**Guidance role values (`qa_gates`):**

| Value | Meaning |
|---|---|
| `blocking_open_qa_gate` | `blocks_completion=true` and status is open/in_review/failed |
| `passed_qa_gate` | Status is `passed` |
| `not_applicable_qa_gate` | Status is `not_applicable` |
| `context_qa_gate` | All other cases |

**Guidance role values (`blockers`):**

| Value | Meaning |
|---|---|
| `critical_open_blocker` | Open blocker with `critical` severity |
| `open_blocker` | Open blocker with non-critical severity |
| `resolved_blocker` | Blocker has been resolved |

---

### `GET /internal/state/accord/summary`

Returns a compact summary of the projected Accord state.

**Response schema:** `repairgraph.repair_state.summary`

| Field | Type | Description |
|---|---|---|
| `schema_name` | string | Always `"repairgraph.repair_state.summary"` |
| `advisory` | boolean | Always `true` |
| `endpoint_advisory` | string | Endpoint-level advisory note |
| `session` | object | Session identity and status |
| `workflow_summary` | object | Aggregate counts |
| `open_blockers` | object | Blocker summary from `summarize_blockers()` |
| `next_actions` | object | Next action summary from `summarize_next_actions()` |
| `advisory_note` | string | Advisory disclaimer text |

---

## Shared demo builder

All four endpoints use `repairgraph.state.demo` — a shared deterministic demo
builder — to ensure consistent, reproducible outputs:

- `build_accord_initial_state()` — loads Accord procedure and initializes state
- `build_accord_demo_events(initial_state)` — builds fixed event ledger
- `build_accord_projected_state()` — initial state + events → projected state
- `build_accord_ar_payload()` — projected state → AR workflow payload

The CLI tools (`state/cli.py`, `state/ar_cli.py`) use the same helpers.

## Advisory

All outputs from these endpoints are **advisory workflow projections** derived
from RepairGraph procedure data and explicit state events. They do not certify
repair completion, OEM compliance, or repair quality. OEM procedure verification
and qualified technician review are required before acting on any recommendation.

These endpoints are local, internal demo endpoints. They are not a production
API surface, not authenticated, and not suitable for use outside development
and internal tooling.
