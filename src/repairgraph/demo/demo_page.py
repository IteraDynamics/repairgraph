"""
RepairGraph golden-path demo page generator.

Produces a self-contained HTML page (no CDN, no React, pure vanilla JS/CSS)
that guides a viewer through the complete RepairGraph workflow story in a
linear, step-by-step presentation.

Steps:
  1. OEM Intake         — upload or use demo packet
  2. Packet Analysis    — animated classification results
  3. Repair Intelligence — animated construction of topology + workflow state
  4. Interactive Viewer  — embedded topology viewer iframe
  5. Replay             — event-by-event timeline walkthrough
  6. Intelligence Summary — large cards with workflow metrics
  7. Export             — links to reports and exports

The page embeds all data as JSON. No server round-trips after initial load.
"""
from __future__ import annotations

import html
import json

from repairgraph.demo.orchestrator import build_full_demo_payload

_GENERATED_BY = "repairgraph.demo.demo_page"


def _css() -> str:
    return """
*{box-sizing:border-box;margin:0;padding:0}
:root{
  --bg:#0d1117;--surface:#161b22;--border:#21262d;--border2:#30363d;
  --text:#e6edf3;--text2:#c9d1d9;--muted:#8b949e;--dim:#6e7681;
  --blue:#388bfd;--blue-dim:#1f4280;--green:#3fb950;--amber:#e3b341;
  --red:#f85149;--purple:#bc8cff;--teal:#39d353;
  --accent:#388bfd;--accent-dim:#1a3560;
}
html,body{min-height:100%;background:var(--bg);color:var(--text2);
  font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,ui-monospace,monospace;
  font-size:14px;line-height:1.6;scroll-behavior:smooth}
::-webkit-scrollbar{width:5px;height:5px}
::-webkit-scrollbar-track{background:var(--surface)}
::-webkit-scrollbar-thumb{background:var(--border2);border-radius:3px}

/* ── Shell ── */
#shell{display:grid;grid-template-columns:1fr 300px;min-height:100vh;gap:0}
@media(max-width:900px){#shell{grid-template-columns:1fr}}

/* ── Left: Main flow ── */
#flow{padding:0 0 80px 0;overflow-x:hidden}

/* ── Hero ── */
#hero{
  padding:64px 56px 52px;
  border-bottom:1px solid var(--border);
  background:linear-gradient(180deg,#111827 0%,var(--bg) 100%);
}
#hero-eyebrow{font-size:11px;font-weight:600;color:var(--blue);letter-spacing:1.5px;text-transform:uppercase;margin-bottom:16px}
#hero-title{font-size:40px;font-weight:700;color:var(--text);line-height:1.1;letter-spacing:-.5px;max-width:560px;margin-bottom:16px}
#hero-subtitle{font-size:16px;color:var(--muted);max-width:500px;line-height:1.7;margin-bottom:32px}
.hero-stat-row{display:flex;gap:32px;flex-wrap:wrap}
.hero-stat{text-align:left}
.hero-stat .n{font-size:28px;font-weight:700;color:var(--text);line-height:1}
.hero-stat .l{font-size:11px;color:var(--dim);text-transform:uppercase;letter-spacing:.5px;margin-top:3px}

/* ── Steps ── */
.step{padding:0 56px;border-bottom:1px solid var(--border)}
.step-inner{padding:44px 0;max-width:700px}
.step-eyebrow{font-size:10px;font-weight:700;color:var(--blue);letter-spacing:1.5px;text-transform:uppercase;margin-bottom:10px;display:flex;align-items:center;gap:8px}
.step-num{display:inline-flex;align-items:center;justify-content:center;width:20px;height:20px;border-radius:50%;background:var(--blue);color:#fff;font-size:10px;font-weight:700;flex-shrink:0}
.step-title{font-size:26px;font-weight:700;color:var(--text);line-height:1.2;margin-bottom:10px;letter-spacing:-.3px}
.step-desc{font-size:14px;color:var(--muted);margin-bottom:28px;line-height:1.7;max-width:580px}
.step-connector{display:flex;align-items:center;gap:0;padding:0 56px}
.step-connector-line{width:1px;height:36px;background:linear-gradient(180deg,var(--border) 0%,var(--blue-dim) 100%);margin-left:9px}

/* ── Upload card ── */
#upload-card{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:28px;max-width:560px}
.drop-zone{border:2px dashed var(--border2);border-radius:6px;padding:36px 20px;text-align:center;cursor:pointer;transition:all .15s}
.drop-zone:hover,.drop-zone.drag-over{border-color:var(--blue);background:var(--accent-dim);}
.drop-zone-icon{font-size:28px;margin-bottom:10px;color:var(--dim)}
.drop-zone-label{font-size:14px;color:var(--muted);margin-bottom:4px}
.drop-zone-sub{font-size:12px;color:var(--dim)}
.or-divider{display:flex;align-items:center;gap:12px;margin:18px 0;color:var(--dim);font-size:12px}
.or-divider::before,.or-divider::after{content:'';flex:1;height:1px;background:var(--border)}
.btn{display:inline-flex;align-items:center;gap:6px;padding:9px 18px;border-radius:5px;font-size:13px;font-weight:600;border:none;cursor:pointer;transition:all .12s;letter-spacing:.1px;text-decoration:none}
.btn-primary{background:var(--blue);color:#fff}
.btn-primary:hover{background:#58a6ff}
.btn-ghost{background:var(--surface);color:var(--text2);border:1px solid var(--border2)}
.btn-ghost:hover{background:var(--border);color:var(--text)}
.btn-sm{padding:5px 12px;font-size:12px}
.btn-row{display:flex;gap:10px;flex-wrap:wrap;margin-top:14px}
#file-list{margin-top:12px;font-size:12px;color:var(--muted)}
.file-chip{display:inline-flex;align-items:center;gap:5px;background:var(--border);border-radius:3px;padding:2px 7px;margin:2px;font-size:11px;font-family:monospace;color:var(--text2)}

/* ── Analysis / progress ── */
.progress-stages{margin-bottom:20px}
.stage-row{display:flex;align-items:center;gap:12px;padding:7px 0;font-size:13px;color:var(--muted)}
.stage-dot{width:8px;height:8px;border-radius:50%;background:var(--border2);flex-shrink:0;transition:all .3s}
.stage-dot.done{background:var(--green);box-shadow:0 0 0 3px rgba(63,185,80,.2)}
.stage-dot.active{background:var(--amber);box-shadow:0 0 0 3px rgba(227,179,65,.2);animation:pulse 1.2s infinite}
.stage-label{transition:color .3s}
.stage-label.done{color:var(--text2)}
.stage-label.active{color:var(--amber)}
@keyframes pulse{0%,100%{opacity:1}50%{opacity:.5}}

/* ── Detected packet card ── */
.result-card{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:24px;max-width:560px}
.result-card-title{font-size:11px;font-weight:600;color:var(--dim);text-transform:uppercase;letter-spacing:.6px;margin-bottom:16px}
.kv-grid{display:grid;grid-template-columns:auto 1fr;gap:6px 16px}
.kv-key{font-size:11px;color:var(--muted);font-family:monospace;white-space:nowrap}
.kv-val{font-size:13px;color:var(--text);font-weight:500}
.role-chips{display:flex;flex-wrap:wrap;gap:4px;margin-top:4px}
.role-chip{background:var(--accent-dim);color:var(--blue);border:1px solid var(--blue-dim);border-radius:3px;padding:2px 7px;font-size:10px;font-weight:600;letter-spacing:.2px;text-transform:uppercase}
.conf-bar{height:4px;background:var(--border2);border-radius:2px;margin-top:6px;overflow:hidden;max-width:200px}
.conf-fill{height:100%;border-radius:2px;background:var(--green);transition:width .6s ease}
.badge{display:inline-block;padding:2px 7px;border-radius:3px;font-size:10px;font-weight:700;letter-spacing:.3px;text-transform:uppercase}
.b-green{background:rgba(63,185,80,.15);color:var(--green);border:1px solid rgba(63,185,80,.3)}
.b-amber{background:rgba(227,179,65,.15);color:var(--amber);border:1px solid rgba(227,179,65,.3)}
.b-red{background:rgba(248,81,73,.15);color:var(--red);border:1px solid rgba(248,81,73,.3)}
.b-blue{background:rgba(56,139,253,.15);color:var(--blue);border:1px solid rgba(56,139,253,.3)}
.b-purple{background:rgba(188,140,255,.15);color:var(--purple);border:1px solid rgba(188,140,255,.3)}
.b-muted{background:var(--border);color:var(--muted);border:1px solid var(--border2)}
.warn-item{display:flex;gap:8px;align-items:flex-start;font-size:12px;color:var(--amber);margin-top:5px}
.warn-item::before{content:'⚠';flex-shrink:0}

/* ── Topology viewer iframe ── */
#viewer-frame{width:100%;height:580px;border:none;border-radius:6px;background:var(--bg);display:block}
#viewer-wrap{background:var(--surface);border:1px solid var(--border);border-radius:8px;overflow:hidden;max-width:100%}

/* ── Replay ── */
#replay-list{max-width:560px}
.replay-step{display:flex;gap:14px;padding:10px 0;position:relative}
.replay-step::before{content:'';position:absolute;left:9px;top:28px;bottom:-10px;width:1px;background:var(--border)}
.replay-step:last-child::before{display:none}
.replay-icon{width:20px;height:20px;border-radius:50%;flex-shrink:0;display:flex;align-items:center;justify-content:center;font-size:10px;font-weight:700;margin-top:2px;z-index:1}
.ri-started{background:rgba(56,139,253,.2);color:var(--blue);border:1px solid rgba(56,139,253,.4)}
.ri-completed{background:rgba(63,185,80,.2);color:var(--green);border:1px solid rgba(63,185,80,.4)}
.ri-passed{background:rgba(63,185,80,.2);color:var(--green);border:1px solid rgba(63,185,80,.4)}
.ri-resolved{background:rgba(63,185,80,.2);color:var(--green);border:1px solid rgba(63,185,80,.4)}
.ri-blocked{background:rgba(248,81,73,.2);color:var(--red);border:1px solid rgba(248,81,73,.4)}
.ri-default{background:var(--border);color:var(--muted);border:1px solid var(--border2)}
.replay-body{flex:1;padding-top:1px}
.replay-event-type{font-size:12px;font-weight:600;color:var(--text2);letter-spacing:.1px}
.replay-meta{font-size:11px;color:var(--dim);margin-top:1px;font-family:monospace}
.replay-diff{font-size:11px;color:var(--muted);margin-top:3px}
.replay-step.hidden{display:none}

/* ── Intelligence summary cards ── */
#summary-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;max-width:680px;margin-bottom:24px}
.intel-card{background:var(--surface);border:1px solid var(--border);border-radius:8px;padding:20px 16px}
.intel-card .num{font-size:32px;font-weight:700;color:var(--text);line-height:1;margin-bottom:4px}
.intel-card .lbl{font-size:10px;color:var(--dim);text-transform:uppercase;letter-spacing:.6px}
.intel-card .sub{font-size:11px;color:var(--muted);margin-top:4px}
.intel-card.c-blue .num{color:var(--blue)}
.intel-card.c-green .num{color:var(--green)}
.intel-card.c-amber .num{color:var(--amber)}
.intel-card.c-red .num{color:var(--red)}
.intel-card.c-purple .num{color:var(--purple)}

/* ── Next action ── */
#next-action-box{background:var(--surface);border:1px solid var(--blue-dim);border-left:3px solid var(--blue);border-radius:6px;padding:16px 18px;max-width:560px;margin-top:8px}
#next-action-label{font-size:10px;font-weight:700;color:var(--blue);text-transform:uppercase;letter-spacing:.8px;margin-bottom:6px}
#next-action-text{font-size:15px;color:var(--text);font-weight:500}

/* ── Phase list ── */
.phase-row{display:flex;align-items:center;gap:10px;padding:6px 0;border-bottom:1px solid var(--border);font-size:13px}
.phase-row:last-child{border-bottom:none}
.phase-num{font-size:10px;color:var(--dim);font-family:monospace;min-width:18px}
.phase-label{flex:1;color:var(--text2)}
.phase-status{font-size:10px}

/* ── Export ── */
#export-links{display:flex;flex-wrap:wrap;gap:10px;margin-top:8px;max-width:680px}
.export-link{display:flex;flex-direction:column;background:var(--surface);border:1px solid var(--border);border-radius:6px;padding:16px 18px;min-width:140px;flex:1;text-decoration:none;transition:border-color .12s,background .12s;cursor:pointer}
.export-link:hover{border-color:var(--blue);background:var(--accent-dim)}
.export-link .el-icon{font-size:18px;margin-bottom:6px}
.export-link .el-label{font-size:13px;font-weight:600;color:var(--text2)}
.export-link .el-sub{font-size:11px;color:var(--dim);margin-top:2px}

/* ── Right: Insight panel ── */
#insights{background:var(--surface);border-left:1px solid var(--border);padding:0;position:sticky;top:0;height:100vh;overflow-y:auto;display:flex;flex-direction:column}
@media(max-width:900px){#insights{display:none}}
#insights-header{padding:20px;border-bottom:1px solid var(--border)}
#insights-title{font-size:11px;font-weight:700;color:var(--blue);text-transform:uppercase;letter-spacing:1px;margin-bottom:2px}
#insights-sub{font-size:11px;color:var(--dim)}
#insights-body{padding:16px;flex:1}
.insight-item{border-left:2px solid var(--border);padding:8px 12px;margin-bottom:12px;opacity:.4;transition:opacity .3s,border-color .3s}
.insight-item.active{opacity:1;border-color:var(--blue)}
.insight-step-label{font-size:9px;font-weight:700;color:var(--blue);text-transform:uppercase;letter-spacing:.8px;margin-bottom:4px}
.insight-text{font-size:12px;color:var(--text2);line-height:1.6}
.insight-detail{font-size:11px;color:var(--muted);margin-top:4px;line-height:1.5}

/* ── Advisory ── */
#advisory-bar{padding:8px 56px;font-size:11px;color:var(--dim);border-bottom:1px solid var(--border);background:var(--bg)}
#advisory-bar strong{color:var(--muted)}

/* ── State transitions ── */
.hidden{display:none !important}
.fade-in{animation:fadeIn .4s ease forwards}
@keyframes fadeIn{from{opacity:0;transform:translateY(8px)}to{opacity:1;transform:translateY(0)}}
"""


def _js(payload_json: str) -> str:
    return f"""
const DEMO = {payload_json};

// ── Utility ──────────────────────────────────────────────────────────────────
function esc(s){{
  if(s===null||s===undefined)return '';
  return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
}}
function el(id){{return document.getElementById(id)}}
function show(id){{const e=el(id);if(e){{e.classList.remove('hidden');e.classList.add('fade-in')}}}}
function hide(id){{const e=el(id);if(e)e.classList.add('hidden')}}
function delay(ms){{return new Promise(r=>setTimeout(r,ms))}}

// ── Insights panel ───────────────────────────────────────────────────────────
const INSIGHTS = [
  {{
    step:'Step 1 — OEM Intake',
    text:'RepairGraph accepts OEM repair documentation in any digital format.',
    detail:'Files are never stored. All processing happens in-memory. No OEM data leaves your system.'
  }},
  {{
    step:'Step 2 — Packet Analysis',
    text:'RepairGraph analyzed your OEM documents and identified {{}}-level procedures, welding specifications, corrosion protection requirements, and material data.',
    detail:'Document roles are detected using structural heuristics — not keyword matching alone. Confidence scores reflect the strength of evidence found in file names and content.'
  }},
  {{
    step:'Step 3 — Repair Intelligence',
    text:'RepairGraph converted static OEM documentation into a live operational model of the repair.',
    detail:'This includes: spatial topology of every repair zone, a dependency graph of all procedures, a complete workflow state machine, and QA gate requirements derived from OEM specifications.'
  }},
  {{
    step:'Step 4 — Topology Viewer',
    text:'RepairGraph knows exactly which parts of the vehicle are involved, in what order they must be repaired, and what dependencies exist between zones.',
    detail:'Click any region to inspect its workflow state, required procedures, QA gates, and any blockers. Use the timeline to replay the repair event history.'
  }},
  {{
    step:'Step 5 — Replay',
    text:'RepairGraph maintains a complete audit trail of every workflow event — who did what, when, and what changed as a result.',
    detail:'The replay engine can reconstruct the exact state of the repair at any point in time. This is the foundation for certification, insurance documentation, and quality assurance.'
  }},
  {{
    step:'Step 6 — Intelligence Summary',
    text:'RepairGraph generated a complete operational model: procedures, dependencies, QA gates, and the exact next action required.',
    detail:'Every metric shown here was derived automatically from OEM documentation — not manually entered. RepairGraph converts documents into decisions.'
  }},
  {{
    step:'Step 7 — Export',
    text:'RepairGraph can export the complete repair record as a portable, self-contained HTML report — suitable for insurance, OEM compliance, or shop management systems.',
    detail:'All exports are generated on demand. No data is stored. The workflow report, replay log, and intake manifest can each be shared independently.'
  }},
];

function renderInsights(){{
  const body = el('insights-body');
  body.innerHTML = INSIGHTS.map((ins,i)=>`
    <div class="insight-item ${{i===0?'active':''}}" id="insight-${{i}}">
      <div class="insight-step-label">${{esc(ins.step)}}</div>
      <div class="insight-text">${{esc(ins.text)}}</div>
      <div class="insight-detail">${{esc(ins.detail)}}</div>
    </div>
  `).join('');
}}

function activateInsight(index){{
  document.querySelectorAll('.insight-item').forEach((el,i)=>{{
    el.classList.toggle('active', i===index);
  }});
}}

// ── Step 2: Intake analysis animation ────────────────────────────────────────
const INTAKE_STAGES = [
  'Reading files...',
  'Detecting OEM...',
  'Classifying documents...',
  'Building evidence...',
  'Determining readiness...',
];

// ── Step 3: Intelligence animation ───────────────────────────────────────────
const INTEL_STAGES = [
  'Building topology...',
  'Mapping repair zones...',
  'Building workflow...',
  'Creating repair state...',
  'Generating replay...',
  'Preparing visualization...',
];

async function runIntelAnimation(intakeData){{
  activateInsight(2);
  const container = el('intel-stages');
  container.innerHTML = INTEL_STAGES.map((s,i)=>`
    <div class="stage-row" id="istage-${{i}}">
      <div class="stage-dot" id="istage-dot-${{i}}"></div>
      <div class="stage-label" id="istage-lbl-${{i}}">${{esc(s)}}</div>
    </div>
  `).join('');

  for(let i=0;i<INTEL_STAGES.length;i++){{
    const dot=el('istage-dot-'+i), lbl=el('istage-lbl-'+i);
    dot.className='stage-dot active';lbl.className='stage-label active';
    await delay(380);
    dot.className='stage-dot done';lbl.className='stage-label done';
  }}

  await delay(200);

  // Show the intel result card — bridge from their vehicle to the reference workflow
  const dp = (intakeData||{{}}).detected_packet||{{}};
  const detectedLabel = [dp.year, dp.oem, dp.model].filter(Boolean).join(' ') || 'your vehicle';
  const refLabel = 'Honda 2025 Accord';
  const isAccord = (dp.oem||'').toLowerCase().includes('honda') && (dp.model||'').toLowerCase().includes('accord');
  const bridgeNote = isAccord
    ? ''
    : `<div style="margin-top:12px;padding:10px 12px;background:var(--accent-dim);border:1px solid var(--blue-dim);border-radius:5px;font-size:12px;color:var(--blue)">
        <strong>Note:</strong> Intake complete for ${{esc(detectedLabel)}}. Displaying reference workflow using
        <strong>${{refLabel}}</strong> (the RepairGraph seed dataset) to demonstrate the full pipeline.
        When your vehicle's OEM procedure is normalized, it will appear here automatically.
       </div>`;

  el('intel-result').innerHTML = `
    <div class="result-card fade-in">
      <div class="result-card-title">Repair model ready — ${{esc(refLabel)}}</div>
      <div class="kv-grid">
        <span class="kv-key">Operation</span><span class="kv-val">${{esc(DEMO.workflow.session.operation||'—')}}</span>
        <span class="kv-key">Phases</span><span class="kv-val">${{DEMO.workflow.workflow_summary.phase_count}} workflow phases</span>
        <span class="kv-key">Actions</span><span class="kv-val">${{DEMO.workflow.workflow_summary.action_count}} procedures mapped</span>
        <span class="kv-key">QA Gates</span><span class="kv-val">${{DEMO.workflow.workflow_summary.qa_gate_count}} OEM-derived checks</span>
        <span class="kv-key">Zones</span><span class="kv-val">${{DEMO.workflow.workflow_summary.zone_count}} spatial zones</span>
        <span class="kv-key">Dependencies</span><span class="kv-val">${{DEMO.workflow.workflow_summary.blocker_count}} procedural dependencies</span>
      </div>
      ${{bridgeNote}}
    </div>
  `;
  show('intel-result');
  show('step-viewer');
  show('conn-viewer');
  show('step-replay');
  show('conn-replay');
  show('step-summary');
  show('conn-summary');
  show('step-export');
  activateInsight(3);
}}

// ── Step 5: Replay render ─────────────────────────────────────────────────────
function iconForEvent(eventType){{
  if(eventType.includes('started'))return['▶','ri-started'];
  if(eventType.includes('completed'))return['✓','ri-completed'];
  if(eventType.includes('passed'))return['✓','ri-passed'];
  if(eventType.includes('resolved'))return['✓','ri-resolved'];
  if(eventType.includes('blocked'))return['!','ri-blocked'];
  return['·','ri-default'];
}}

function renderReplay(){{
  const steps = DEMO.workflow.replay_steps;
  el('replay-list').innerHTML = steps.map((s,i)=>{{
    const [icon,cls]=iconForEvent(s.event.event_type);
    const diffText = s.diff_summary && s.diff_summary.changes
      ? s.diff_summary.changes.slice(0,2).map(c=>esc(c)).join(' · ')
      : '';
    return `
      <div class="replay-step" id="rs-${{i}}">
        <div class="replay-icon ${{cls}}">${{icon}}</div>
        <div class="replay-body">
          <div class="replay-event-type">${{esc(s.event.event_type.replace(/_/g,' '))}}</div>
          <div class="replay-meta">${{esc(s.event.actor)}} · ${{esc(s.event.target_type)}} · ${{esc(s.event.timestamp.slice(0,19).replace('T',' '))}}</div>
          ${{diffText?`<div class="replay-diff">${{diffText}}</div>`:''}}
        </div>
      </div>
    `;
  }}).join('');
}}

// ── Step 6: Summary cards ─────────────────────────────────────────────────────
function renderSummary(){{
  const ws = DEMO.workflow.workflow_summary;
  const sess = DEMO.workflow.session;
  const nextActs = DEMO.workflow.next_actions || [];
  const phases = DEMO.workflow.phases || [];

  el('summary-grid').innerHTML = [
    {{n:ws.action_count, l:'Procedures', sub:ws.complete_action_count+' complete', c:'c-blue'}},
    {{n:ws.phase_count, l:'Workflow Phases', sub:'sequential', c:''}},
    {{n:ws.qa_gate_count, l:'QA Gates', sub:'OEM-derived', c:'c-amber'}},
    {{n:ws.blocker_count, l:'Dependencies', sub:ws.open_blocker_count+' open', c:ws.open_blocker_count>0?'c-red':'c-green'}},
    {{n:ws.zone_count, l:'Repair Zones', sub:'topology-mapped', c:'c-purple'}},
    {{n:ws.event_count, l:'Events', sub:'in audit trail', c:'c-green'}},
  ].map(c=>`
    <div class="intel-card ${{c.c}}">
      <div class="num">${{c.n}}</div>
      <div class="lbl">${{esc(c.l)}}</div>
      <div class="sub">${{esc(c.sub)}}</div>
    </div>
  `).join('');

  // Next action
  const nextAct = nextActs[0] || sess.current_phase || '—';
  el('next-action-text').textContent = nextAct;

  // Phases
  el('phase-list').innerHTML = phases.map(p=>{{
    const statusMap={{'not_started':'b-muted','in_progress':'b-amber','complete':'b-green','blocked':'b-red','ready_for_review':'b-purple','not_applicable':'b-muted'}};
    const sc=statusMap[p.status]||'b-muted';
    return `<div class="phase-row">
      <span class="phase-num">${{p.phase}}</span>
      <span class="phase-label">${{esc(p.label||p.name)}}</span>
      <span class="badge ${{sc}} phase-status">${{esc(p.status.replace(/_/g,' '))}}</span>
    </div>`;
  }}).join('');
}}

// ── Step 4: viewer iframe ────────────────────────────────────────────────────
function activateViewer(){{
  activateInsight(3);
  const frame = el('viewer-frame');
  if(frame && !frame.src){{
    frame.src = '/internal/state/accord/topology-viewer';
  }}
}}

// ── Scroll-based insight activation ──────────────────────────────────────────
function setupScrollObserver(){{
  const stepMap = {{
    'step-intake': 0,
    'step-analysis': 1,
    'step-intelligence': 2,
    'step-viewer': 3,
    'step-replay': 4,
    'step-summary': 5,
    'step-export': 6,
  }};
  const observer = new IntersectionObserver(entries=>{{
    entries.forEach(e=>{{
      if(e.isIntersecting){{
        const idx = stepMap[e.target.id];
        if(idx!==undefined) activateInsight(idx);
        if(e.target.id==='step-viewer') activateViewer();
      }}
    }});
  }},{{threshold:0.15}});
  Object.keys(stepMap).forEach(id=>{{
    const el2=el(id);if(el2)observer.observe(el2);
  }});
}}

// ── Upload state ─────────────────────────────────────────────────────────────
let _uploadedFiles = [];       // real File objects from the browser
let _usingDemoPacket = false;  // true when user clicked "Use Demo Packet"
let _liveIntakeData = null;    // result from POST /internal/intake/classify

// ── Upload handling ───────────────────────────────────────────────────────────
function setupUpload(){{
  const zone = el('drop-zone');
  const fileInput = el('file-input');

  zone.addEventListener('dragover', e=>{{e.preventDefault();zone.classList.add('drag-over')}});
  zone.addEventListener('dragleave',()=>zone.classList.remove('drag-over'));
  zone.addEventListener('drop',e=>{{
    e.preventDefault();zone.classList.remove('drag-over');
    setFiles(Array.from(e.dataTransfer.files));
  }});
  zone.addEventListener('click',()=>fileInput.click());
  fileInput.addEventListener('change',()=>setFiles(Array.from(fileInput.files)));

  el('btn-demo').addEventListener('click', useDemoPacket);
}}

function setFiles(files){{
  _uploadedFiles = files;
  _usingDemoPacket = false;
  el('demo-packet-note').style.display='none';
  el('file-list').innerHTML = files.map(f=>`<span class="file-chip">📄 ${{esc(f.name)}}</span>`).join('');
  el('btn-analyze').disabled = files.length===0;
}}

function useDemoPacket(){{
  _uploadedFiles = [];
  _usingDemoPacket = true;
  const p = DEMO.intake;
  el('file-list').innerHTML = (p.files||[]).map(f=>`<span class="file-chip">📄 ${{esc(f.filename)}}</span>`).join('');
  el('btn-analyze').disabled = false;
  el('demo-packet-note').style.display='';
}}

// ── Live intake classification ────────────────────────────────────────────────
async function classifyRealFiles(files){{
  const formData = new FormData();
  for(const f of files) formData.append('files', f, f.name);

  const resp = await fetch('/internal/intake/classify', {{
    method:'POST',
    body: formData,
  }});
  if(!resp.ok){{
    const txt = await resp.text();
    throw new Error('Classification failed (' + resp.status + '): ' + txt.slice(0,200));
  }}
  return resp.json();
}}

// ── Map live API response → the shape renderIntakeResult() expects ─────────────
function normalizeLiveIntake(apiData){{
  // POST /internal/intake/classify returns slightly different keys than the
  // embedded DEMO.intake payload — flatten them to a common shape.
  const dp = apiData.detected_packet || {{}};
  return {{
    file_count: (apiData.files||[]).length,
    readiness: apiData.readiness || 'unknown',
    detected_packet: {{
      oem:       dp.detected_oem || null,
      model:     dp.detected_model || null,
      year:      dp.detected_year || null,
      operation: dp.detected_operation || null,
      confidence: dp.oem_confidence || 0,
      detected_roles: dp.detected_roles || [],
    }},
    files: (apiData.files||[]).map(f=>({{
      filename: f.filename,
      document_role: f.document_role,
      supporting_roles: f.supporting_roles||[],
      confidence: f.confidence,
    }})),
    diagnostics: (apiData.diagnostics||[]).map(d=>({{
      code: d.code,
      severity: d.severity,
      message: d.message,
    }})),
  }};
}}

// ── renderIntakeResult — accepts an intake payload object ─────────────────────
function renderIntakeResult(intakeData){{
  const p = intakeData;
  const dp = p.detected_packet;
  const conf = Math.round((dp.confidence||0)*100);
  const readinessBadge = dp.confidence>0.75?'b-green':(dp.confidence>0.4?'b-amber':'b-red');
  const readinessLabel = p.readiness;

  const roles = (dp.detected_roles||[]).map(r=>`<span class="role-chip">${{esc(r)}}</span>`).join('');
  const warnings = (p.diagnostics||[]).filter(d=>d.severity==='warning').slice(0,3)
    .map(d=>`<div class="warn-item">${{esc(d.message)}}</div>`).join('');

  // Per-file classification table
  const fileRows = (p.files||[]).map(f=>{{
    const confPct = Math.round((f.confidence||0)*100);
    const confColor = confPct>75?'var(--green)':confPct>40?'var(--amber)':'var(--red)';
    return `<tr>
      <td style="font-family:monospace;font-size:11px;color:var(--text2)">${{esc(f.filename)}}</td>
      <td><span class="role-chip" style="font-size:9px">${{esc(f.document_role)}}</span></td>
      <td style="font-size:11px;color:${{confColor}}">${{confPct}}%</td>
    </tr>`;
  }}).join('');

  el('intake-result').innerHTML = `
    <div class="result-card fade-in">
      <div class="result-card-title">Packet detected</div>
      <div class="kv-grid">
        <span class="kv-key">OEM</span><span class="kv-val">${{esc(dp.oem||'—')}}</span>
        <span class="kv-key">Model</span><span class="kv-val">${{esc(dp.model||'—')}}</span>
        <span class="kv-key">Year</span><span class="kv-val">${{esc(dp.year||'—')}}</span>
        <span class="kv-key">Operation</span><span class="kv-val">${{esc(dp.operation||'—')}}</span>
        <span class="kv-key">Files</span><span class="kv-val">${{esc(p.file_count)}} files classified</span>
        <span class="kv-key">Readiness</span><span class="kv-val"><span class="badge ${{readinessBadge}}">${{esc(readinessLabel)}}</span></span>
        <span class="kv-key">Confidence</span>
        <span class="kv-val">
          ${{conf}}%
          <div class="conf-bar"><div class="conf-fill" style="width:${{conf}}%;background:${{conf>75?'var(--green)':conf>40?'var(--amber)':'var(--red)'}}"></div></div>
        </span>
        <span class="kv-key">Roles</span>
        <span class="kv-val"><div class="role-chips">${{roles||'<span style="color:var(--muted)">none detected</span>'}}</div></span>
      </div>
      ${{fileRows?`<div style="margin-top:16px">
        <div style="font-size:10px;font-weight:600;color:var(--dim);text-transform:uppercase;letter-spacing:.5px;margin-bottom:8px">Per-file classification</div>
        <table style="width:100%;border-collapse:collapse;font-size:12px">
          <thead><tr>
            <th style="text-align:left;padding:4px 8px;color:var(--dim);font-size:10px;font-weight:600;border-bottom:1px solid var(--border)">File</th>
            <th style="text-align:left;padding:4px 8px;color:var(--dim);font-size:10px;font-weight:600;border-bottom:1px solid var(--border)">Role</th>
            <th style="text-align:left;padding:4px 8px;color:var(--dim);font-size:10px;font-weight:600;border-bottom:1px solid var(--border)">Conf</th>
          </tr></thead>
          <tbody>${{fileRows}}</tbody>
        </table>
      </div>`:''}}
      ${{warnings?'<div style="margin-top:12px">'+warnings+'</div>':''}}
    </div>
  `;
}}

async function startAnalysis(){{
  hide('upload-card');
  show('step-analysis');
  show('conn-analysis');

  // Run animation first, then (for real uploads) fire the API in parallel
  const classifyPromise = (!_usingDemoPacket && _uploadedFiles.length > 0)
    ? classifyRealFiles(_uploadedFiles)
    : Promise.resolve(null);

  await runIntakeAnimationOnly();

  // Now resolve the classification
  let intakeData;
  try {{
    const liveResult = await classifyPromise;
    if(liveResult) {{
      _liveIntakeData = normalizeLiveIntake(liveResult);
      intakeData = _liveIntakeData;
    }} else {{
      intakeData = DEMO.intake;
    }}
  }} catch(err) {{
    // Show error but continue demo with embedded data
    intakeData = DEMO.intake;
    console.error('Live classify failed:', err);
    el('intake-error').textContent = 'Classification API error: ' + err.message + ' — showing demo data.';
    el('intake-error').style.display = '';
  }}

  renderIntakeResult(intakeData);
  show('intake-result');
  activateInsight(1);

  show('step-intelligence');
  show('conn-intelligence');
  await delay(600);
  await runIntelAnimation(intakeData);
  renderReplay();
  renderSummary();
  activateInsight(5);
}}

// Renamed: animation-only, no longer calls renderIntakeResult
async function runIntakeAnimationOnly(){{
  const container = el('intake-stages');
  container.innerHTML = INTAKE_STAGES.map((s,i)=>`
    <div class="stage-row" id="stage-${{i}}">
      <div class="stage-dot" id="stage-dot-${{i}}"></div>
      <div class="stage-label" id="stage-lbl-${{i}}">${{esc(s)}}</div>
    </div>
  `).join('');

  for(let i=0;i<INTAKE_STAGES.length;i++){{
    const dot=el('stage-dot-'+i), lbl=el('stage-lbl-'+i);
    dot.className='stage-dot active';lbl.className='stage-label active';
    await delay(420);
    dot.className='stage-dot done';lbl.className='stage-label done';
  }}
  await delay(200);
}}

// ── Init ──────────────────────────────────────────────────────────────────────
document.addEventListener('DOMContentLoaded',()=>{{
  renderInsights();
  setupUpload();
  setupScrollObserver();
  el('btn-analyze').addEventListener('click', startAnalysis);

  // Hero stats
  const ws = DEMO.workflow.workflow_summary;
  el('hero-stat-actions').textContent = ws.action_count;
  el('hero-stat-zones').textContent = ws.zone_count;
  el('hero-stat-qa').textContent = ws.qa_gate_count;
  el('hero-stat-events').textContent = ws.event_count;
}});
"""


def build_demo_page_html() -> str:
    """Build the complete golden-path demo page as a self-contained HTML string."""
    payload = build_full_demo_payload()
    payload_json = json.dumps(payload, default=str, separators=(",", ":"))
    ws = payload["workflow"]["workflow_summary"]
    sess = payload["workflow"]["session"]

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>RepairGraph · Platform Demo</title>
<style>{_css()}</style>
</head>
<body>
<div id="shell">

<!-- ══ Main flow ══════════════════════════════════════════════════════════════ -->
<div id="flow">

  <div id="advisory-bar">
    <strong>Advisory:</strong> All outputs are workflow intelligence derived from OEM procedure data.
    Requires OEM verification and qualified technician review. Not a certified repair record.
  </div>

  <!-- Hero -->
  <div id="hero">
    <div id="hero-eyebrow">RepairGraph · Platform Demo</div>
    <h1 id="hero-title">OEM repair documents, transformed into workflow intelligence.</h1>
    <p id="hero-subtitle">RepairGraph converts static repair documentation into a live operational model — complete with spatial topology, dependency graphs, workflow state, and QA gates.</p>
    <div class="hero-stat-row">
      <div class="hero-stat">
        <div class="n" id="hero-stat-actions">{ws["action_count"]}</div>
        <div class="l">Procedures</div>
      </div>
      <div class="hero-stat">
        <div class="n" id="hero-stat-zones">{ws["zone_count"]}</div>
        <div class="l">Repair Zones</div>
      </div>
      <div class="hero-stat">
        <div class="n" id="hero-stat-qa">{ws["qa_gate_count"]}</div>
        <div class="l">QA Gates</div>
      </div>
      <div class="hero-stat">
        <div class="n" id="hero-stat-events">{ws["event_count"]}</div>
        <div class="l">Events</div>
      </div>
    </div>
  </div>

  <!-- Step 1: OEM Intake -->
  <div class="step" id="step-intake">
    <div class="step-inner">
      <div class="step-eyebrow"><span class="step-num">1</span> OEM Intake</div>
      <h2 class="step-title">Upload your repair packet</h2>
      <p class="step-desc">Upload OEM repair documents for any vehicle. RepairGraph accepts procedure files, material specs, welding guides, corrosion requirements, and QA checklists. Or use the built-in demo packet to see the full workflow.</p>
      <div id="upload-card">
        <div class="drop-zone" id="drop-zone" role="button" tabindex="0" aria-label="Drop files here or click to browse">
          <div class="drop-zone-icon">📂</div>
          <div class="drop-zone-label">Drop OEM repair files here</div>
          <div class="drop-zone-sub">PDF, TXT, DOCX, HTML — any readable format</div>
        </div>
        <input type="file" id="file-input" multiple accept=".pdf,.txt,.docx,.html,.htm" style="display:none">
        <div class="or-divider">or</div>
        <button class="btn btn-primary" id="btn-demo">Use Demo Packet</button>
        <p id="demo-packet-note" style="display:none;font-size:11px;color:var(--muted);margin-top:8px">
          Using built-in demo packet — synthetic OEM repair documentation for demonstration purposes.
        </p>
        <div id="file-list" style="margin-top:10px"></div>
        <div class="btn-row">
          <button class="btn btn-primary" id="btn-analyze" disabled>Analyze Packet →</button>
        </div>
      </div>
    </div>
  </div>

  <div class="step-connector" id="conn-analysis" style="display:none">
    <div class="step-connector-line"></div>
  </div>

  <!-- Step 2: Packet Analysis -->
  <div class="step hidden" id="step-analysis">
    <div class="step-inner">
      <div class="step-eyebrow"><span class="step-num">2</span> Packet Analysis</div>
      <h2 class="step-title">Reading your documents</h2>
      <p class="step-desc">RepairGraph is analyzing document structure, detecting OEM identity, classifying each file by role, and assessing readiness for normalization.</p>
      <div class="progress-stages" id="intake-stages"></div>
      <div id="intake-error" style="display:none;font-size:12px;color:var(--amber);margin-bottom:10px;padding:8px 12px;background:rgba(227,179,65,.1);border-radius:4px;border:1px solid rgba(227,179,65,.3)"></div>
      <div id="intake-result"></div>
    </div>
  </div>

  <div class="step-connector" id="conn-intelligence" style="display:none">
    <div class="step-connector-line"></div>
  </div>

  <!-- Step 3: Generate Repair Intelligence -->
  <div class="step hidden" id="step-intelligence">
    <div class="step-inner">
      <div class="step-eyebrow"><span class="step-num">3</span> Generate Repair Intelligence</div>
      <h2 class="step-title">Building your operational model</h2>
      <p class="step-desc">RepairGraph is constructing the repair topology, mapping every zone and dependency, initializing the workflow state machine, and generating the event replay engine.</p>
      <div class="progress-stages" id="intel-stages"></div>
      <div id="intel-result" class="hidden"></div>
    </div>
  </div>

  <div class="step-connector" id="conn-viewer" style="display:none">
    <div class="step-connector-line"></div>
  </div>

  <!-- Step 4: Interactive Viewer -->
  <div class="step hidden" id="step-viewer">
    <div class="step-inner" style="max-width:100%">
      <div class="step-eyebrow"><span class="step-num">4</span> Interactive Viewer</div>
      <h2 class="step-title">See every zone, every dependency</h2>
      <p class="step-desc">Click any region on the vehicle to inspect its workflow state, procedures, QA gates, and blockers. Use the timeline to replay the full repair event history.</p>
    </div>
    <div style="padding:0 56px 44px" id="viewer-wrap">
      <iframe id="viewer-frame" title="RepairGraph Topology Viewer" loading="lazy"></iframe>
    </div>
  </div>

  <div class="step-connector" id="conn-replay" style="display:none">
    <div class="step-connector-line"></div>
  </div>

  <!-- Step 5: Replay -->
  <div class="step hidden" id="step-replay">
    <div class="step-inner">
      <div class="step-eyebrow"><span class="step-num">5</span> Replay</div>
      <h2 class="step-title">Complete audit trail</h2>
      <p class="step-desc">RepairGraph maintains a full event ledger. Every action, QA gate, and blocker is recorded with actor, timestamp, and state diff — enabling exact reconstruction of the repair at any point.</p>
      <div id="replay-list"></div>
    </div>
  </div>

  <div class="step-connector" id="conn-summary" style="display:none">
    <div class="step-connector-line"></div>
  </div>

  <!-- Step 6: Intelligence Summary -->
  <div class="step hidden" id="step-summary">
    <div class="step-inner" style="max-width:100%">
      <div class="step-eyebrow"><span class="step-num">6</span> Repair Intelligence</div>
      <h2 class="step-title">Everything RepairGraph knows about this repair</h2>
      <p class="step-desc">All derived automatically from OEM documentation — not manually entered.</p>
      <div id="summary-grid"></div>
      <div id="next-action-box">
        <div id="next-action-label">Next Recommended Action</div>
        <div id="next-action-text">Loading…</div>
      </div>
      <div style="margin-top:24px;max-width:560px">
        <div style="font-size:11px;font-weight:600;color:var(--dim);text-transform:uppercase;letter-spacing:.6px;margin-bottom:10px">Workflow Phases</div>
        <div id="phase-list"></div>
      </div>
    </div>
  </div>

  <div class="step-connector" style="display:flex">
    <div class="step-connector-line"></div>
  </div>

  <!-- Step 7: Export -->
  <div class="step" id="step-export">
    <div class="step-inner" style="max-width:100%">
      <div class="step-eyebrow"><span class="step-num">7</span> Export</div>
      <h2 class="step-title">Take it with you</h2>
      <p class="step-desc">Every RepairGraph output is a self-contained, portable artifact — no login required to view, no data stored on our servers.</p>
      <div id="export-links">
        <a href="/internal/state/accord/report?view=workflow" target="_blank" class="export-link">
          <span class="el-icon">📋</span>
          <span class="el-label">Workflow Report</span>
          <span class="el-sub">Full state, phases, QA gates</span>
        </a>
        <a href="/internal/state/accord/report?view=replay" target="_blank" class="export-link">
          <span class="el-icon">⏱</span>
          <span class="el-label">Replay Report</span>
          <span class="el-sub">Event-by-event state history</span>
        </a>
        <a href="/internal/intake" target="_blank" class="export-link">
          <span class="el-icon">📥</span>
          <span class="el-label">Intake Analyzer</span>
          <span class="el-sub">Upload and classify OEM docs</span>
        </a>
        <a href="/internal/state/accord/topology-viewer" target="_blank" class="export-link">
          <span class="el-icon">🔍</span>
          <span class="el-label">Topology Viewer</span>
          <span class="el-sub">Interactive vehicle visualization</span>
        </a>
        <a href="/internal/state/accord/visualization" target="_blank" class="export-link">
          <span class="el-icon">📊</span>
          <span class="el-label">Visualization JSON</span>
          <span class="el-sub">Machine-readable payload</span>
        </a>
      </div>
    </div>
  </div>

</div><!-- /flow -->

<!-- ══ Right: Insights panel ══════════════════════════════════════════════════ -->
<div id="insights">
  <div id="insights-header">
    <div id="insights-title">What RepairGraph is doing</div>
    <div id="insights-sub">Narrated step-by-step</div>
  </div>
  <div id="insights-body"></div>
</div>

</div><!-- /shell -->

<script>{_js(payload_json)}</script>
</body>
</html>"""
