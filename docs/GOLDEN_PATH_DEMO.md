# RepairGraph Golden Path Demo

The golden path demo is the recommended way to demonstrate RepairGraph to MSO executives, OEM representatives, collision shop owners, and strategic partners.

## Access

```
GET /internal/demo
```

Open it in any modern browser. Everything runs in-memory. No data is stored. No login required.

## What It Demonstrates

The demo answers one question without requiring explanation from the presenter:

> **What does RepairGraph actually do?**

The answer: RepairGraph transforms static OEM repair documentation into a live operational model of the repair — complete with spatial topology, a dependency graph, a workflow state machine, QA gate requirements, and a full event audit trail.

Every step in the demo reinforces this message.

## The Flow

### Step 1 — OEM Intake

The user uploads an OEM repair packet or clicks **Use Demo Packet** to load the built-in synthetic fixture. The page accepts any readable format (PDF, TXT, DOCX, HTML).

The demo packet uses existing test fixtures — no OEM PDFs are bundled with RepairGraph.

### Step 2 — Packet Analysis

RepairGraph animates through:

- Reading files
- Detecting OEM
- Classifying documents by role
- Building evidence
- Determining readiness

On completion, a result card shows the detected OEM, model, year, document roles, readiness level, and confidence score. All data comes from `classify_intake_packet()` — the same module used by the `/internal/intake` API.

### Step 3 — Generate Repair Intelligence

RepairGraph animates through:

- Building topology
- Mapping repair zones
- Building workflow
- Creating repair state
- Generating replay
- Preparing visualization

On completion, a summary card confirms the operational model is ready: phase count, action count, QA gate count, zone count, and dependency count.

### Step 4 — Interactive Topology Viewer

The existing topology viewer (`/internal/state/accord/topology-viewer`) is embedded inline as an iframe. The viewer loads lazily when scrolled into view.

Users can click vehicle regions, inspect workflow state, step through the timeline, and apply filters — all within the demo flow.

### Step 5 — Replay

The full event audit trail is rendered as a vertical timeline. Each event shows:

- Event type (color-coded: blue for start events, green for completion, red for blockers)
- Actor and target
- Timestamp
- State diff summary (what changed)

All data comes from `replay_repair_state()` and `build_state_diff()`.

### Step 6 — Repair Intelligence Summary

Large summary cards show everything RepairGraph derived from the OEM documents:

| Card | Data source |
|---|---|
| Procedures | `action_count` from `workflow_summary` |
| Workflow Phases | `phase_count` |
| QA Gates | `qa_gate_count` |
| Dependencies | `blocker_count` |
| Repair Zones | `zone_count` |
| Events | `event_count` in audit trail |

Below the cards, the next recommended action and full phase list (with status badges) are shown.

### Step 7 — Export

Five export links give users portable artifacts:

| Export | Endpoint |
|---|---|
| Workflow Report | `GET /internal/state/accord/report?view=workflow` |
| Replay Report | `GET /internal/state/accord/report?view=replay` |
| Intake Analyzer | `GET /internal/intake` |
| Topology Viewer | `GET /internal/state/accord/topology-viewer` |
| Visualization JSON | `GET /internal/state/accord/visualization` |

All exports are self-contained HTML or JSON — no server needed to view them.

## Right Side Panel

Throughout the experience, a persistent side panel narrates what RepairGraph is doing at each step. It updates as the user scrolls through the demo. Example messages:

> RepairGraph analyzed your OEM documents and identified procedure files, welding specifications, corrosion protection requirements, and material data.

> RepairGraph converted static OEM documentation into a live operational model of the repair.

> RepairGraph maintains a complete audit trail of every workflow event — who did what, when, and what changed as a result.

## Architecture

### `src/repairgraph/demo/orchestrator.py`

Assembles the complete demo payload by calling existing modules:

- `classify_intake_packet()` from `repairgraph.intake.classify`
- `summarize_intake_manifest()` from `repairgraph.intake.classify`
- `build_accord_initial_state()`, `build_accord_demo_events()`, `build_accord_projected_state()` from `repairgraph.state.demo`
- `replay_repair_state()`, `build_state_diff()` from `repairgraph.state.replay`
- `build_event_timeline()`, `build_phase_timeline()`, `build_action_timeline()` from `repairgraph.state.timeline`
- `summarize_blockers()` from `repairgraph.state.blockers`
- `summarize_next_actions()` from `repairgraph.state.next_actions`

**No business logic is duplicated.** The orchestrator is pure coordination.

### `src/repairgraph/demo/demo_page.py`

Generates the self-contained HTML. All data is embedded as a `const DEMO = {...}` JSON constant. The page uses vanilla JavaScript for all interactivity — no frameworks, no CDN.

### `src/repairgraph/api/demo_routes.py`

FastAPI router with two endpoints:

- `GET /internal/demo` — returns the HTML demo page
- `GET /internal/demo/payload` — returns the JSON payload for debugging

## Testing

112 tests across three files in `tests/demo/`:

- `test_orchestrator.py` — intake payload, workflow payload, full combined payload, structural consistency
- `test_demo_page.py` — HTML structure, no external dependencies, all steps present, JS functions, advisory content
- `test_demo_api.py` — HTTP endpoints, determinism, regression against all existing endpoints

Run all tests:

```bash
python3 -m pytest
```

## Manual Validation

Start the server:

```bash
python -m uvicorn repairgraph.api.app:app --reload
```

Open the demo:

```
http://localhost:8000/internal/demo
```

Expected experience:

1. Hero landing with live workflow statistics
2. Upload card — click **Use Demo Packet**, then **Analyze Packet →**
3. Watch the packet analysis animation complete
4. Watch the repair intelligence animation complete
5. Scroll down to the embedded topology viewer — click vehicle regions
6. Review the replay event timeline
7. Read the intelligence summary cards
8. Click an export link to get a portable report

The full experience should take 2–3 minutes and require no explanation from the presenter.

## What RepairGraph Is Not

The demo reinforces this throughout:

- Not a document parser
- Not a viewer
- Not a reporting tool

RepairGraph converts static OEM repair documentation into living workflow intelligence.
