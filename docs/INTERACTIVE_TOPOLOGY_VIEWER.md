# Interactive Topology Viewer

RepairGraph includes a browser-based interactive topology viewer that makes repair workflow state immediately visible. Upload OEM documents, build a repair session, and open the viewer to see exactly what is being repaired, what has happened, what happens next, and what is blocked.

## Access

```
GET /internal/state/accord/topology-viewer
```

Returns a self-contained HTML page. Open it in any modern browser. No server-side rendering, no CDN, no external dependencies.

## What the Viewer Shows

### Vehicle Silhouette

A simplified side-profile SVG of the vehicle divided into major repair regions:

- Hood, front/rear bumpers
- Front and rear quarter panels
- Doors (front and rear)
- Roof, rockers, floor
- Rear body
- Front and rear wheelhouses
- A/B/C pillars

Each region is color-coded by its current workflow state.

### Zone State Colors

| Color | Status | Meaning |
|-------|--------|---------|
| Dark gray | Inactive | Not involved in this repair |
| Blue | Pending | Planned but not started |
| Amber | Active | Work in progress |
| Green | Complete | All actions done |
| Red | Blocked | Cannot proceed — see blockers |

### Click to Inspect

Clicking any region opens the Inspector panel on the right with:

- **Zones** — matched topology zones and their status
- **Workflow Phase** — which repair phase owns this region
- **Procedures** — every action targeting this region, with status badges
- **QA Gates** — open QA checks tied to this region
- **Blockers** — any open blockers and their severity/type
- **Next Actions** — recommended next steps for this region
- **Risk Flags** — material risk flags from zone classification

### Timeline Replay

The bottom of the page shows a horizontal event timeline. Use it to:

- Scrub through the repair event history with the range slider
- Step event-by-event with ◀ / ▶ buttons
- Jump to the initial state (|◀) or latest state (▶|)
- Use arrow keys for keyboard navigation

The vehicle silhouette and inspector panel update live as you move through the timeline.

### Filters

Checkboxes in the filter bar toggle visibility:

- **QA Gates** — show/hide QA gate details in the inspector
- **Blockers** — show/hide blocker details
- **Completed** — show/hide completed regions on the vehicle
- **Dependencies** — show dependency overlay (SVG arrows between zones)

### Export

The **Export** button downloads the current viewer as a self-contained HTML file. The export captures the full embedded payload at the current timeline position.

## Architecture

The viewer is built from three modules:

### `src/repairgraph/viewer/topology_layout.py`

Defines the SVG vehicle silhouette geometry — region shapes, coordinates, label anchors, and the mapping from region IDs to zone_id substrings. Also defines the color palettes for all state types.

### `src/repairgraph/viewer/topology_payload.py`

Assembles the JSON payload consumed by the viewer. Reuses existing RepairGraph modules:

- `replay_repair_state()` / `build_state_diff()` from `state.replay`
- `build_event_timeline()` / `build_phase_timeline()` / `build_action_timeline()` from `state.timeline`
- `summarize_blockers()` from `state.blockers`
- `summarize_next_actions()` from `state.next_actions`

No logic is duplicated. The payload builder maps RepairState zones to viewer regions by matching zone_id substrings against region zone_keys.

### `src/repairgraph/viewer/topology_viewer.py`

Generates the self-contained HTML. Embeds:

- SVG vehicle silhouette with all region elements
- CSS (dark theme, enterprise minimal)
- The complete topology payload as an inline JSON constant
- Vanilla JavaScript for all interactivity (selection, timeline replay, filters, export, tooltips, keyboard navigation)

No React, Vue, CDN, or external references of any kind.

## API Integration

The endpoint is registered in `src/repairgraph/api/state_routes.py`:

```python
GET /internal/state/accord/topology-viewer
```

Returns `text/html`. Uses the same `build_accord_initial_state()` and `build_accord_demo_events()` demo builders as all other state endpoints — no second state model.

## Testing

107 tests cover the viewer across four test files in `tests/viewer/`:

- `test_topology_layout.py` — region definitions, color palette completeness
- `test_topology_payload.py` — region map derivation, inspector payloads, replay snapshots, full payload structure, determinism
- `test_topology_viewer.py` — HTML structure, no external dependencies, SVG presence, embedded JS functions, advisory metadata
- `test_topology_viewer_api.py` — HTTP endpoint, content type, determinism, regression against existing endpoints

Run all tests:

```bash
python3 -m pytest
```

## Manual Validation

Start the server:

```bash
python -m uvicorn repairgraph.api.app:app --reload
```

Open the viewer:

```
http://localhost:8000/internal/state/accord/topology-viewer
```

Expected behavior:

1. Vehicle silhouette renders with color-coded regions
2. Clicking a region opens the inspector with workflow details
3. Timeline scrubber steps through repair events and updates the vehicle live
4. Filter checkboxes hide/show region types
5. Export button downloads the page as a standalone HTML file
6. Keyboard left/right arrows step through events; Escape clears selection
