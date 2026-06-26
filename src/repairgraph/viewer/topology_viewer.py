"""
Interactive topology viewer HTML generator for RepairGraph.

Produces a self-contained HTML page (no CDN, no React, no Vue, pure vanilla JS)
that renders a vehicle silhouette with color-coded repair zones, a timeline
replay scrubber, and a click-to-inspect panel.

All data is embedded as JSON in the page. The viewer consumes
topology_viewer_payload and renders entirely in the browser.
"""
from __future__ import annotations

import html
import json

from repairgraph.state.schema import RepairEvent, RepairState
from repairgraph.viewer.topology_layout import VEHICLE_REGIONS, ZONE_STATUS_COLORS
from repairgraph.viewer.topology_payload import build_topology_viewer_payload

_GENERATED_BY = "repairgraph.viewer.topology_viewer"


def _svg_vehicle(regions_json_var: str = "REGIONS") -> str:
    """Return the SVG vehicle silhouette with interactive regions."""
    rects = []
    for reg in VEHICLE_REGIONS:
        label = html.escape(reg["label"])
        rid = reg["id"]
        default_fill = ZONE_STATUS_COLORS["inactive"]["fill"]
        default_stroke = ZONE_STATUS_COLORS["inactive"]["stroke"]
        rx = reg.get("rx", 3)
        rects.append(
            f'  <rect id="{rid}" class="vehicle-region" '
            f'x="{reg["x"]}" y="{reg["y"]}" '
            f'width="{reg["width"]}" height="{reg["height"]}" '
            f'rx="{rx}" '
            f'fill="{default_fill}" stroke="{default_stroke}" stroke-width="1.5" '
            f'data-region="{rid}" '
            f'onclick="selectRegion(\'{rid}\')" '
            f'role="button" tabindex="0" aria-label="{label}">'
            f'<title>{label}</title></rect>'
        )
    labels = []
    for reg in VEHICLE_REGIONS:
        label = html.escape(reg["label"])
        w = reg["width"]
        if w >= 60:
            labels.append(
                f'  <text class="region-label" '
                f'x="{reg["cx"]}" y="{reg["cy"]}" '
                f'text-anchor="middle" dominant-baseline="middle" '
                f'pointer-events="none" font-size="9" fill="#94a3b8">'
                f'{label}</text>'
            )

    all_rects = "\n".join(rects)
    all_labels = "\n".join(labels)

    return f"""<svg id="vehicle-svg" viewBox="0 0 790 310" xmlns="http://www.w3.org/2000/svg"
     style="width:100%;max-width:860px;display:block;margin:0 auto;">
  <!-- Ground shadow -->
  <ellipse cx="420" cy="300" rx="368" ry="9" fill="#000" opacity="0.22" pointer-events="none"/>
  <!-- Car body silhouette (sedan profile) -->
  <path d="M 26,254
    C 12,252 8,238 8,218
    L 8,166
    C 8,154 14,144 28,136
    L 48,114
    L 94,86
    L 174,78
    L 200,38
    L 642,38
    C 660,38 672,46 678,58
    L 700,78
    L 754,78
    C 774,78 782,90 782,108
    L 782,178
    C 782,198 774,216 760,228
    L 748,254
    Z"
    fill="#141824" stroke="#2d3a4e" stroke-width="1.5"/>
  <!-- Body character line -->
  <line x1="30" y1="138" x2="752" y2="138"
    stroke="#1e2a3a" stroke-width="1" opacity="0.7" pointer-events="none"/>
  <!-- Windshield glass (angled) -->
  <polygon points="176,78 202,78 202,40 196,40"
    fill="#0c1624" stroke="#182840" stroke-width="1" opacity="0.92" pointer-events="none"/>
  <!-- Front door glass -->
  <rect x="204" y="40" width="148" height="36" rx="3"
    fill="#0c1624" stroke="#182840" stroke-width="1" opacity="0.92" pointer-events="none"/>
  <!-- Rear door glass -->
  <rect x="370" y="40" width="118" height="36" rx="3"
    fill="#0c1624" stroke="#182840" stroke-width="1" opacity="0.92" pointer-events="none"/>
  <!-- Quarter glass -->
  <rect x="506" y="40" width="134" height="36" rx="3"
    fill="#0c1624" stroke="#182840" stroke-width="1" opacity="0.92" pointer-events="none"/>
  <!-- Rear glass (angled) -->
  <polygon points="642,38 648,38 672,60 700,78 692,78 670,62 648,40"
    fill="#0c1624" stroke="#182840" stroke-width="1" opacity="0.92" pointer-events="none"/>
  <!-- Repair regions (interactive) -->
{all_rects}
  <!-- Wheels -->
  <ellipse cx="132" cy="282" rx="40" ry="24" fill="#0e1118" stroke="#374151" stroke-width="1.5"/>
  <ellipse cx="132" cy="282" rx="28" ry="17" fill="#0a0d12" stroke="#4b5563" stroke-width="1"/>
  <ellipse cx="132" cy="282" rx="12" ry="7" fill="#141824" stroke="#6b7280" stroke-width="1"/>
  <ellipse cx="708" cy="282" rx="40" ry="24" fill="#0e1118" stroke="#374151" stroke-width="1.5"/>
  <ellipse cx="708" cy="282" rx="28" ry="17" fill="#0a0d12" stroke="#4b5563" stroke-width="1"/>
  <ellipse cx="708" cy="282" rx="12" ry="7" fill="#141824" stroke="#6b7280" stroke-width="1"/>
  <!-- Region labels -->
{all_labels}
</svg>"""


def _css() -> str:
    return """
*{box-sizing:border-box;margin:0;padding:0}
html,body{height:100%;background:#0d1117;color:#c9d1d9;font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,monospace;font-size:13px;line-height:1.5}
::-webkit-scrollbar{width:6px;height:6px}
::-webkit-scrollbar-track{background:#161b22}
::-webkit-scrollbar-thumb{background:#30363d;border-radius:3px}

/* Layout */
#app{display:grid;grid-template-rows:auto auto 1fr auto;height:100vh;overflow:hidden}
header{background:#161b22;border-bottom:1px solid #21262d;padding:12px 20px;display:flex;align-items:center;gap:14px;flex-wrap:wrap}
header .logo{font-size:15px;font-weight:700;color:#e6edf3;letter-spacing:.3px}
header .subtitle{font-size:11px;color:#6e7681;margin-left:2px}
header .session-meta{margin-left:auto;font-size:11px;color:#6e7681;font-family:monospace}
.advisory-bar{background:#161b22;border-bottom:1px solid #21262d;padding:6px 20px;font-size:11px;color:#6e7681}
.advisory-bar strong{color:#8b949e}

/* Main content split */
#main-content{display:grid;grid-template-columns:1fr 340px;overflow:hidden}
#left-pane{overflow-y:auto;padding:16px 16px 0 16px;display:flex;flex-direction:column;gap:14px}
#right-pane{background:#161b22;border-left:1px solid #21262d;overflow-y:auto;display:flex;flex-direction:column}

/* Vehicle SVG area */
#vehicle-panel{background:#0d1117;border:1px solid #21262d;border-radius:6px;padding:14px 8px 8px 8px}
#vehicle-title{font-size:11px;font-weight:600;color:#6e7681;text-transform:uppercase;letter-spacing:.5px;margin-bottom:10px;padding:0 6px}

/* Status summary cards */
#status-cards{display:flex;gap:10px;flex-wrap:wrap}
.stat-card{background:#161b22;border:1px solid #21262d;border-radius:5px;padding:10px 14px;min-width:90px;text-align:center;flex:1}
.stat-card .val{font-size:22px;font-weight:700;color:#e6edf3}
.stat-card .lbl{font-size:10px;color:#6e7681;text-transform:uppercase;letter-spacing:.4px;margin-top:2px}
.stat-card.warn .val{color:#e3b341}
.stat-card.danger .val{color:#f85149}
.stat-card.ok .val{color:#3fb950}
.stat-card.info .val{color:#388bfd}

/* Filter bar */
#filter-bar{background:#161b22;border:1px solid #21262d;border-radius:5px;padding:8px 12px;display:flex;gap:16px;flex-wrap:wrap;align-items:center}
#filter-bar label{display:flex;align-items:center;gap:5px;font-size:11px;color:#8b949e;cursor:pointer}
#filter-bar input[type=checkbox]{accent-color:#388bfd;cursor:pointer}
#filter-bar .filter-title{font-size:11px;font-weight:600;color:#6e7681;text-transform:uppercase;letter-spacing:.4px;margin-right:4px}

/* Timeline */
#timeline-panel{background:#161b22;border-top:1px solid #21262d;padding:10px 16px;overflow-x:auto}
#timeline-header{display:flex;align-items:center;gap:10px;margin-bottom:8px}
#timeline-title{font-size:11px;font-weight:600;color:#6e7681;text-transform:uppercase;letter-spacing:.5px}
#timeline-controls{display:flex;gap:6px;align-items:center;margin-left:auto}
#timeline-track{display:flex;gap:4px;align-items:center;min-height:36px;padding-bottom:2px}
.timeline-event{display:flex;flex-direction:column;align-items:center;cursor:pointer;min-width:52px}
.tl-dot{width:10px;height:10px;border-radius:50%;border:2px solid #30363d;background:#21262d;transition:all .15s}
.tl-dot.active{background:#388bfd;border-color:#58a6ff;box-shadow:0 0 0 3px rgba(56,139,253,.25)}
.tl-dot.past{background:#3fb950;border-color:#46d160}
.tl-dot.selected{background:#e3b341;border-color:#f0c040;box-shadow:0 0 0 3px rgba(227,179,65,.3)}
.tl-label{font-size:9px;color:#6e7681;margin-top:3px;text-align:center;white-space:nowrap;max-width:60px;overflow:hidden;text-overflow:ellipsis}
.tl-connector{flex:1;height:2px;background:#21262d;min-width:8px}
.tl-connector.past{background:#3fb950}
.replay-btn{background:#21262d;color:#c9d1d9;border:1px solid #30363d;padding:4px 10px;border-radius:4px;cursor:pointer;font-size:11px;font-weight:600}
.replay-btn:hover{background:#30363d;color:#e6edf3}
.replay-btn:disabled{opacity:.4;cursor:not-allowed}
#replay-step-label{font-size:11px;color:#8b949e;font-family:monospace;min-width:80px;text-align:center}
#timeline-range{accent-color:#388bfd;width:100%;max-width:340px;cursor:pointer}

/* Inspector / Right pane */
#inspector-header{padding:12px 14px;border-bottom:1px solid #21262d;background:#0d1117}
#inspector-title{font-size:13px;font-weight:600;color:#e6edf3}
#inspector-subtitle{font-size:11px;color:#6e7681;margin-top:2px}
#inspector-body{padding:12px 14px;flex:1}
.inspector-empty{color:#4d5966;font-style:italic;font-size:12px;padding:24px 0;text-align:center}
.insp-section{margin-bottom:14px}
.insp-section-title{font-size:10px;font-weight:600;color:#6e7681;text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px;padding-bottom:4px;border-bottom:1px solid #21262d}
.insp-row{padding:5px 0;border-bottom:1px solid #161b22;font-size:12px}
.insp-row:last-child{border-bottom:none}
.insp-row .label{color:#8b949e;font-size:11px}
.insp-row .value{color:#e6edf3;font-family:monospace;font-size:11px;word-break:break-all}
.badge{display:inline-block;padding:1px 6px;border-radius:3px;font-size:10px;font-weight:600;letter-spacing:.3px;white-space:nowrap}
.action-item{background:#161b22;border:1px solid #21262d;border-radius:4px;padding:7px 9px;margin-bottom:5px}
.action-item .action-target{font-size:11px;font-weight:600;color:#e6edf3;margin-bottom:2px}
.action-item .action-type{font-size:10px;color:#6e7681;font-family:monospace}
.zone-chip{display:inline-block;background:#21262d;border:1px solid #30363d;border-radius:3px;padding:2px 6px;font-size:10px;font-family:monospace;color:#8b949e;margin:2px 2px 0 0}
.blocker-item{background:#1a0e0e;border:1px solid #3d1515;border-radius:4px;padding:7px 9px;margin-bottom:5px}
.blocker-item .blocker-reason{font-size:11px;color:#ffa0a0;margin-bottom:3px}
.dep-arrow{display:inline-block;color:#388bfd;font-weight:700;margin:0 4px}

/* Legend */
#legend-panel{background:#161b22;border:1px solid #21262d;border-radius:5px;padding:10px 12px}
#legend-title{font-size:10px;font-weight:600;color:#6e7681;text-transform:uppercase;letter-spacing:.5px;margin-bottom:8px}
.legend-grid{display:flex;flex-wrap:wrap;gap:6px}
.legend-item{display:flex;align-items:center;gap:5px;font-size:11px;color:#8b949e}
.legend-swatch{width:12px;height:12px;border-radius:2px;border:1px solid}

/* Export button */
#export-btn{background:#21262d;color:#c9d1d9;border:1px solid #30363d;padding:5px 12px;border-radius:4px;cursor:pointer;font-size:11px;font-weight:600;letter-spacing:.2px}
#export-btn:hover{background:#30363d;color:#e6edf3}

/* Dep toggle */
#dep-toggle{display:flex;align-items:center;gap:6px;font-size:11px;color:#8b949e;cursor:pointer}
#dep-toggle input{accent-color:#388bfd;cursor:pointer}

/* SVG region hover/select */
.vehicle-region{cursor:pointer;transition:opacity .1s}
.vehicle-region:hover{opacity:.85;stroke-width:2.5 !important}
.vehicle-region.selected{stroke-width:2.5 !important;filter:brightness(1.25)}
.vehicle-region.dimmed{opacity:.35}
.vehicle-region.hidden{opacity:.1}

/* Dep arrows SVG overlay */
#dep-overlay{position:absolute;top:0;left:0;pointer-events:none;width:100%;height:100%}
#vehicle-wrap{position:relative}

/* Tooltip */
#tooltip{position:fixed;background:#21262d;border:1px solid #30363d;border-radius:4px;padding:5px 9px;font-size:11px;color:#e6edf3;pointer-events:none;display:none;z-index:999;box-shadow:0 4px 12px rgba(0,0,0,.5)}
"""


def _js(payload_json: str) -> str:
    return f"""
const PAYLOAD = {payload_json};

// State
let currentStep = PAYLOAD.replay_snapshots.length; // 0 = initial, n = after n events
let selectedRegion = null;
let showQA = true, showBlockers = true, showCompleted = true, showDeps = false;

const REGIONS_META = PAYLOAD.regions_meta;
const REPLAY = PAYLOAD.replay_snapshots;
const INITIAL_REGION_MAP = PAYLOAD.initial_region_map;

function getRegionMap(step) {{
  if (step === 0) return INITIAL_REGION_MAP;
  return REPLAY[step - 1].region_map;
}}

function getStateSummary(step) {{
  if (step === 0) {{
    return {{
      session_status: 'not_started',
      active_phase_ids: [],
      completed_action_count: 0,
      open_blocker_count: PAYLOAD.replay_snapshots.length > 0 ? 0 : 0,
      open_qa_count: 0,
      next_recommended_actions: [],
    }};
  }}
  return REPLAY[step - 1].state_summary;
}}

// ---- Region coloring ----
function applyRegionMap(regionMap) {{
  const lookup = {{}};
  for (const r of regionMap) lookup[r.id] = r;
  for (const reg of REGIONS_META) {{
    const el = document.getElementById(reg.id);
    if (!el) continue;
    const data = lookup[reg.id];
    if (!data) continue;
    el.setAttribute('fill', data.fill);
    el.setAttribute('stroke', data.stroke);
    // Filter visibility
    const isBlocked = data.status === 'blocked';
    const isComplete = data.status === 'complete';
    const hasQA = data.matched_zones && data.matched_zones.some(z => z.risk_flags && z.risk_flags.length > 0);
    let hidden = false;
    if (!showCompleted && isComplete) hidden = true;
    if (!showBlockers && isBlocked) hidden = true;
    el.classList.toggle('hidden', hidden);
  }}
}}

// ---- Status cards ----
function updateStatusCards(step) {{
  const summary = getStateSummary(step);
  const ws = PAYLOAD.workflow_summary;
  document.getElementById('card-actions').textContent = summary.completed_action_count + '/' + ws.action_count;
  document.getElementById('card-blockers').textContent = summary.open_blocker_count;
  document.getElementById('card-qa').textContent = summary.open_qa_count;
  document.getElementById('card-status').textContent = summary.session_status.replace(/_/g, ' ');
  const phaseEl = document.getElementById('card-phase');
  phaseEl.textContent = summary.active_phase_ids.length > 0 ? summary.active_phase_ids.join(', ') : '—';
}}

// ---- Timeline ----
function buildTimeline() {{
  const track = document.getElementById('timeline-track');
  track.innerHTML = '';

  // Step 0 = initial
  const initialDot = makeDot(0, 'INITIAL', 'initial');
  track.appendChild(initialDot);

  for (let i = 0; i < REPLAY.length; i++) {{
    const snap = REPLAY[i];
    const conn = document.createElement('div');
    conn.className = 'tl-connector' + (i < currentStep ? ' past' : '');
    conn.id = 'tl-conn-' + i;
    track.appendChild(conn);
    const label = snap.event.event_type.replace(/_/g, ' ');
    const dot = makeDot(i + 1, label, snap.event.event_type);
    track.appendChild(dot);
  }}
  updateTimelineDots();

  const range = document.getElementById('timeline-range');
  range.max = REPLAY.length;
  range.value = currentStep;
}}

function makeDot(step, label, eventType) {{
  const wrap = document.createElement('div');
  wrap.className = 'timeline-event';
  wrap.id = 'tl-step-' + step;
  wrap.onclick = () => setStep(step);
  wrap.title = label;

  const dot = document.createElement('div');
  dot.className = 'tl-dot';
  dot.id = 'tl-dot-' + step;

  const lbl = document.createElement('div');
  lbl.className = 'tl-label';
  lbl.textContent = step === 0 ? 'initial' : label.split(' ').slice(-1)[0];

  wrap.appendChild(dot);
  wrap.appendChild(lbl);
  return wrap;
}}

function updateTimelineDots() {{
  for (let i = 0; i <= REPLAY.length; i++) {{
    const dot = document.getElementById('tl-dot-' + i);
    if (!dot) continue;
    dot.className = 'tl-dot';
    if (i === currentStep) dot.classList.add('selected');
    else if (i < currentStep) dot.classList.add('past');
    const conn = document.getElementById('tl-conn-' + (i - 1));
    if (conn) {{
      conn.className = 'tl-connector' + (i <= currentStep ? ' past' : '');
    }}
  }}
  const label = document.getElementById('replay-step-label');
  if (currentStep === 0) label.textContent = 'Initial state';
  else {{
    const snap = REPLAY[currentStep - 1];
    label.textContent = 'Step ' + currentStep + '/' + REPLAY.length + ' · ' + snap.event.event_type.replace(/_/g, ' ');
  }}
}}

// ---- Step navigation ----
function setStep(step) {{
  currentStep = Math.max(0, Math.min(step, REPLAY.length));
  const regionMap = getRegionMap(currentStep);
  applyRegionMap(regionMap);
  updateStatusCards(currentStep);
  updateTimelineDots();
  document.getElementById('timeline-range').value = currentStep;
  if (selectedRegion) updateInspector(selectedRegion);
  updateNavButtons();
}}

function stepBack() {{ setStep(currentStep - 1); }}
function stepForward() {{ setStep(currentStep + 1); }}
function stepLatest() {{ setStep(REPLAY.length); }}
function stepInitial() {{ setStep(0); }}

function updateNavButtons() {{
  document.getElementById('btn-prev').disabled = currentStep <= 0;
  document.getElementById('btn-next').disabled = currentStep >= REPLAY.length;
  document.getElementById('btn-latest').disabled = currentStep >= REPLAY.length;
  document.getElementById('btn-initial').disabled = currentStep <= 0;
}}

// ---- Region selection ----
function selectRegion(regionId) {{
  selectedRegion = regionId;
  // Highlight
  for (const reg of REGIONS_META) {{
    const el = document.getElementById(reg.id);
    if (!el) continue;
    el.classList.toggle('selected', reg.id === regionId);
    el.classList.toggle('dimmed', reg.id !== regionId);
  }}
  updateInspector(regionId);
}}

function clearSelection() {{
  selectedRegion = null;
  for (const reg of REGIONS_META) {{
    const el = document.getElementById(reg.id);
    if (!el) continue;
    el.classList.remove('selected', 'dimmed');
  }}
  document.getElementById('inspector-title').textContent = 'Inspector';
  document.getElementById('inspector-subtitle').textContent = 'Click a region to inspect';
  document.getElementById('inspector-body').innerHTML = '<p class="inspector-empty">Select a vehicle region to view workflow details.</p>';
}}

// ---- Inspector ----
function updateInspector(regionId) {{
  const payload = PAYLOAD.inspector_payloads[regionId];
  if (!payload) return;
  // Get live region status from current step
  const regionMap = getRegionMap(currentStep);
  const regionData = regionMap.find(r => r.id === regionId);
  const status = regionData ? regionData.status : 'inactive';

  document.getElementById('inspector-title').textContent = payload.region_label;
  document.getElementById('inspector-subtitle').textContent =
    payload.zone_count + ' zone(s) · ' + payload.action_count + ' action(s) · status: ' + status;

  let html = '';

  // Zones
  if (payload.zones.length > 0) {{
    html += '<div class="insp-section">';
    html += '<div class="insp-section-title">Zones</div>';
    for (const z of payload.zones) {{
      html += '<div class="insp-row"><span class="label">zone</span> ';
      html += '<span class="value">' + esc(z.zone_id) + '</span> ';
      html += badge(z.status) + '</div>';
    }}
    html += '</div>';
  }}

  // Phases
  if (payload.phases.length > 0) {{
    html += '<div class="insp-section">';
    html += '<div class="insp-section-title">Workflow Phase</div>';
    for (const p of payload.phases) {{
      html += '<div class="insp-row"><span class="label">phase ' + p.phase + '</span> ';
      html += '<span class="value">' + esc(p.label) + '</span> ' + badge(p.status) + '</div>';
    }}
    html += '</div>';
  }}

  // Actions / Procedures
  if (payload.procedures.length > 0) {{
    html += '<div class="insp-section">';
    html += '<div class="insp-section-title">Procedures (' + payload.procedures.length + ')</div>';
    for (const a of payload.procedures) {{
      html += '<div class="action-item">';
      html += '<div class="action-target">' + esc(a.target) + ' ' + badge(a.status) + '</div>';
      html += '<div class="action-type">' + esc(a.action_type) + '</div>';
      if (a.zone_refs.length > 0) {{
        html += '<div style="margin-top:3px">';
        for (const z of a.zone_refs) html += '<span class="zone-chip">' + esc(z) + '</span>';
        html += '</div>';
      }}
      if (a.requires_qa) html += '<div style="margin-top:3px">' + badge('qa_required', '#7c3aed') + '</div>';
      html += '</div>';
    }}
    html += '</div>';
  }}

  // QA Gates
  if (showQA && payload.qa_gates.length > 0) {{
    html += '<div class="insp-section">';
    html += '<div class="insp-section-title">QA Gates (' + payload.qa_gates.length + ')</div>';
    for (const g of payload.qa_gates) {{
      html += '<div class="insp-row">';
      html += badge(g.status) + ' ';
      html += '<span class="value">' + esc(g.check || g.gate_id) + '</span></div>';
    }}
    html += '</div>';
  }}

  // Blockers
  if (showBlockers && payload.blockers.length > 0) {{
    html += '<div class="insp-section">';
    html += '<div class="insp-section-title">Blockers (' + payload.blockers.length + ')</div>';
    for (const b of payload.blockers) {{
      if (b.status === 'resolved') continue;
      html += '<div class="blocker-item">';
      html += '<div class="blocker-reason">' + esc(b.reason) + '</div>';
      html += badge(b.severity) + ' ' + badge(b.type) + ' ' + badge(b.status);
      html += '</div>';
    }}
    html += '</div>';
  }}

  // Next actions
  if (payload.next_actions.length > 0) {{
    html += '<div class="insp-section">';
    html += '<div class="insp-section-title">Next Actions</div>';
    for (const nxt of payload.next_actions) {{
      html += '<div class="insp-row"><span style="color:#388bfd">▶</span> <span class="value">' + esc(nxt) + '</span></div>';
    }}
    html += '</div>';
  }}

  // Required documents (from zone risk flags)
  const docs = [];
  for (const z of payload.zones) {{
    for (const rf of (z.risk_flags || [])) docs.push(rf);
  }}
  if (docs.length > 0) {{
    html += '<div class="insp-section">';
    html += '<div class="insp-section-title">Risk Flags / Required Docs</div>';
    for (const d of docs) {{
      html += '<div class="insp-row"><span class="value">' + esc(d) + '</span></div>';
    }}
    html += '</div>';
  }}

  if (html === '') html = '<p class="inspector-empty">No workflow data for this region.</p>';

  document.getElementById('inspector-body').innerHTML = html;
}}

function badge(status, color) {{
  const statusColors = {{
    'complete': '#3fb950', 'passed': '#3fb950', 'resolved': '#3fb950',
    'in_progress': '#e3b341',
    'blocked': '#f85149', 'open': '#f85149', 'failed': '#f85149',
    'pending': '#6e7681', 'not_started': '#6e7681', 'inactive': '#6e7681',
    'not_applicable': '#4d5966',
    'needs_review': '#bc8cff', 'ready_for_review': '#bc8cff',
    'qa_required': '#7c3aed',
    'critical': '#f85149', 'high': '#db6d28', 'medium': '#e3b341', 'low': '#3fb950',
  }};
  const c = color || statusColors[status] || '#6e7681';
  return '<span class="badge" style="background:' + c + '22;color:' + c + ';border:1px solid ' + c + '44">' + esc(status) + '</span>';
}}

function esc(s) {{
  if (!s && s !== 0) return '';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}}

// ---- Filters ----
function applyFilters() {{
  showQA = document.getElementById('filter-qa').checked;
  showBlockers = document.getElementById('filter-blockers').checked;
  showCompleted = document.getElementById('filter-completed').checked;
  showDeps = document.getElementById('filter-deps').checked;
  applyRegionMap(getRegionMap(currentStep));
  if (selectedRegion) updateInspector(selectedRegion);
  toggleDepOverlay();
}}

// ---- Dep arrows ----
function toggleDepOverlay() {{
  const overlay = document.getElementById('dep-overlay');
  if (!overlay) return;
  overlay.style.display = showDeps ? '' : 'none';
}}

// ---- Export ----
function exportViewer() {{
  const blob = new Blob([document.documentElement.outerHTML], {{type: 'text/html'}});
  const url = URL.createObjectURL(blob);
  const a = document.createElement('a');
  a.href = url;
  a.download = 'repairgraph-topology-viewer.html';
  a.click();
  URL.revokeObjectURL(url);
}}

// ---- Init ----
document.addEventListener('DOMContentLoaded', function() {{
  buildTimeline();
  applyRegionMap(getRegionMap(currentStep));
  updateStatusCards(currentStep);
  updateNavButtons();

  document.getElementById('timeline-range').addEventListener('input', function() {{
    setStep(parseInt(this.value));
  }});
  document.getElementById('filter-qa').addEventListener('change', applyFilters);
  document.getElementById('filter-blockers').addEventListener('change', applyFilters);
  document.getElementById('filter-completed').addEventListener('change', applyFilters);
  document.getElementById('filter-deps').addEventListener('change', applyFilters);
  document.getElementById('btn-prev').addEventListener('click', stepBack);
  document.getElementById('btn-next').addEventListener('click', stepForward);
  document.getElementById('btn-latest').addEventListener('click', stepLatest);
  document.getElementById('btn-initial').addEventListener('click', stepInitial);
  document.getElementById('export-btn').addEventListener('click', exportViewer);

  // Keyboard nav
  document.addEventListener('keydown', function(e) {{
    if (e.key === 'ArrowLeft') stepBack();
    else if (e.key === 'ArrowRight') stepForward();
    else if (e.key === 'Escape') clearSelection();
  }});

  // Click background to deselect
  document.getElementById('vehicle-svg').addEventListener('click', function(e) {{
    if (e.target.id === 'vehicle-svg' || e.target.tagName === 'svg') clearSelection();
  }});

  // Tooltip
  const tooltip = document.getElementById('tooltip');
  document.querySelectorAll('.vehicle-region').forEach(el => {{
    el.addEventListener('mouseenter', function(e) {{
      const rid = this.dataset.region;
      const regionMap = getRegionMap(currentStep);
      const rd = regionMap.find(r => r.id === rid);
      if (!rd) return;
      tooltip.textContent = rd.id.replace('region_', '').replace(/_/g,' ') + ' · ' + rd.status + ' · ' + rd.zone_count + ' zones';
      tooltip.style.display = 'block';
    }});
    el.addEventListener('mousemove', function(e) {{
      tooltip.style.left = (e.clientX + 14) + 'px';
      tooltip.style.top = (e.clientY - 24) + 'px';
    }});
    el.addEventListener('mouseleave', function() {{
      tooltip.style.display = 'none';
    }});
  }});
}});
"""


def _legend_html(payload: dict) -> str:
    legend = payload.get("legend", {})
    zone_states = legend.get("zone_states", [])
    items = "".join(
        f'<div class="legend-item">'
        f'<div class="legend-swatch" style="background:{s["color"]};border-color:{s["border"]}"></div>'
        f'{html.escape(s["label"])}'
        f'</div>'
        for s in zone_states
    )
    return f'<div id="legend-panel"><div id="legend-title">Zone State Legend</div><div class="legend-grid">{items}</div></div>'


def build_topology_viewer_html(initial: RepairState, events: list[RepairEvent]) -> str:
    """Build the complete self-contained interactive topology viewer HTML."""
    payload = build_topology_viewer_payload(initial, events)
    payload_json = json.dumps(payload, default=str, separators=(",", ":"))

    session = payload["session"]
    session_meta = f'{session["oem"]} {session["year"]} {session["model"]} · {session["operation"]} · {session["status"]}'
    ws = payload["workflow_summary"]

    svg_html = _svg_vehicle()
    legend_html = _legend_html(payload)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>RepairGraph · Topology Viewer · {html.escape(session["model"])}</title>
<style>{_css()}</style>
</head>
<body>
<div id="app">
  <header>
    <div>
      <div class="logo">RepairGraph</div>
      <div class="subtitle">Interactive Topology Viewer</div>
    </div>
    <div class="session-meta">{html.escape(session_meta)}</div>
    <button id="export-btn">Export</button>
  </header>

  <div class="advisory-bar">
    <strong>Advisory:</strong> Workflow intelligence derived from OEM procedure data.
    Requires OEM verification and qualified technician review. Not a certified repair record.
  </div>

  <div id="main-content">
    <!-- Left pane: vehicle + controls -->
    <div id="left-pane">
      <!-- Status cards -->
      <div id="status-cards">
        <div class="stat-card info">
          <div class="val" id="card-actions">{ws["complete_action_count"]}/{ws["action_count"]}</div>
          <div class="lbl">Actions</div>
        </div>
        <div class="stat-card danger">
          <div class="val" id="card-blockers">{ws["open_blocker_count"]}</div>
          <div class="lbl">Blockers</div>
        </div>
        <div class="stat-card warn">
          <div class="val" id="card-qa">{ws["qa_gate_count"]}</div>
          <div class="lbl">QA Gates</div>
        </div>
        <div class="stat-card ok">
          <div class="val" id="card-status">{html.escape(session["status"].replace("_", " "))}</div>
          <div class="lbl">Session</div>
        </div>
        <div class="stat-card">
          <div class="val" id="card-phase" style="font-size:13px;padding-top:4px">{html.escape(session["current_phase"] or "—")}</div>
          <div class="lbl">Phase</div>
        </div>
      </div>

      <!-- Vehicle SVG -->
      <div id="vehicle-panel">
        <div id="vehicle-title">Vehicle · {html.escape(f'{session["year"]} {session["oem"]} {session["model"]}')}</div>
        <div id="vehicle-wrap">
          {svg_html}
        </div>
      </div>

      <!-- Filter bar -->
      <div id="filter-bar">
        <span class="filter-title">Filters</span>
        <label><input type="checkbox" id="filter-qa" checked> QA Gates</label>
        <label><input type="checkbox" id="filter-blockers" checked> Blockers</label>
        <label><input type="checkbox" id="filter-completed" checked> Completed</label>
        <label><input type="checkbox" id="filter-deps"> Dependencies</label>
      </div>

      <!-- Legend -->
      {legend_html}
    </div>

    <!-- Right pane: inspector -->
    <div id="right-pane">
      <div id="inspector-header">
        <div id="inspector-title">Inspector</div>
        <div id="inspector-subtitle">Click a region to inspect</div>
      </div>
      <div id="inspector-body">
        <p class="inspector-empty">Select a vehicle region to view workflow details, procedures, QA gates, and blockers.</p>
      </div>
    </div>
  </div>

  <!-- Timeline panel -->
  <div id="timeline-panel">
    <div id="timeline-header">
      <span id="timeline-title">Repair Timeline · {ws["event_count"]} events</span>
      <div id="timeline-controls">
        <button class="replay-btn" id="btn-initial" title="Go to initial state">|◀</button>
        <button class="replay-btn" id="btn-prev" title="Previous event">◀</button>
        <span id="replay-step-label">Latest state</span>
        <button class="replay-btn" id="btn-next" title="Next event">▶</button>
        <button class="replay-btn" id="btn-latest" title="Jump to latest">▶|</button>
        <input type="range" id="timeline-range" min="0" max="{ws["event_count"]}" value="{ws["event_count"]}" style="width:140px">
      </div>
    </div>
    <div id="timeline-track"></div>
  </div>
</div>

<div id="tooltip"></div>

<script>{_js(payload_json)}</script>
</body>
</html>"""
