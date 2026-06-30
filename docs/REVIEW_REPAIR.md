# Review Repair

Review Repair is the collision repair product front door in RepairGraph.

A collision center manager can open `/internal/review` and understand
the repair status within 30 seconds — without understanding graphs, JSON,
replay engines, or document classification.

## What it answers

- **Can this repair proceed?** — Blocked / Proceed with Caution / Ready to Proceed / Needs Review
- **Why or why not?** — The primary blocking reason, derived from open blockers and findings
- **What matters most?** — Top findings by severity (QA gates, material risk, compliance)
- **What is missing?** — Required documentation roles not yet supplied
- **What should happen next?** — Next recommended action from the workflow engine
- **What evidence supports those conclusions?** — Evidence trail from state, findings, and QA gates

## Architecture

Review Repair consumes the **OperationalModel** produced by the `RepairGraphCompiler`.
It does not re-derive conclusions from scattered modules.

```
RepairGraphCompiler.compile_demo()
        ↓
  OperationalModel
        ↓
  build_review_payload()   ← src/repairgraph/review/review_payload.py
        ↓
  ReviewPayload (JSON-serializable projection)
        ↓
  build_review_page_html()  ← src/repairgraph/review/review_page.py
        ↓
  Self-contained HTML (vanilla CSS/JS, no CDN, no frameworks)
```

### Module layout

```
src/repairgraph/review/
  __init__.py          Package marker
  review_payload.py    ReviewPayload builder — projection from OperationalModel
  review_page.py       HTML page renderer — vanilla CSS/JS
  routes.py            FastAPI router — GET /internal/review[/payload]
```

## Endpoints

| Endpoint | Response | Description |
|---|---|---|
| `GET /internal/review` | HTML | Self-contained Review Repair page |
| `GET /internal/review/payload` | JSON | ReviewPayload for integration/testing |

## Data boundaries

RepairGraph works with repair information supplied by the shop.
It does not replace OEM procedures or distribute licensed repair data.
All outputs are advisory and require qualified technician review against OEM procedures.

Source documents (OEM repair procedures, sectioning guides, etc.) are
customer-owned content. RepairGraph processes this content but does not
claim ownership or redistribute it. The `ReviewPayload` and HTML outputs
are the RepairGraph operational artifact.

## Page sections

1. **Review Header** — repair label, OEM/year/model, operational confidence, readiness, top action
2. **Decision Panel** — proceed/blocked decision with reason, next action, top risks
3. **Top Findings** — up to 5 findings by severity; expand to show all
4. **Required Documentation** — detected/missing document roles, packet readiness, extraction warnings
5. **Workflow Readiness** — current phase, blockers, next actions, completed actions, QA gates
6. **Material & Structural Risk** — UHSS/HSS zones, joining verification, corrosion protection (collision-specific)
7. **Evidence Trail** — collapsible; evidence items, finding evidence, OEM verification notice
8. **Actions & Exports** — links to Topology Viewer, Workflow Report, Audit Trail, Intake Analysis

## Running

```bash
python -m uvicorn repairgraph.api.app:app --reload
# Open: http://localhost:8000/internal/review
```

## Testing

```bash
python -m pytest tests/test_review_payload.py tests/test_review_api.py -v
```

All existing tests continue to pass without modification.

---

## Operational Planner Integration

The Review Repair page now consumes an `OperationalPlan` produced by the
Operational Planner (`src/repairgraph/review/operational_planner.py`).

The data flow is:

```text
OperationalModel
      ↓
RootCauseAnalysis
      ↓
OperationalPlanner
      ↓
ReviewPayload  +  OperationalPlan
      ↓
Review Repair UI
```

The `GET /internal/review` route builds the OperationalPlan alongside the
ReviewPayload and passes it to `build_review_page_html()`. The page leads with
a **Next Best Action** section that shows:

- The single highest-leverage action
- Why that action is recommended now
- Expected unlocks (phases, QA gates, actions unblocked)
- Critical path (ordered sequence of steps)
- Action queue (Today / Next / Deferred)

Root causes and other secondary content remain on the page but appear below
the planner output.

A separate JSON endpoint is available:

```
GET /internal/review/plan
```

This returns the full `OperationalPlan` as JSON for integration testing and
downstream tooling.
