"""
HTML report builder for RepairGraph workflow intelligence.

Produces self-contained, portable HTML reports from RepairState data.
Reports include workflow summaries, timeline views, Mermaid diagram sources,
and an interactive replay inspector. All outputs are deterministic and
require no external dependencies or CDN access.

All outputs are advisory workflow intelligence. They do not certify repair
completion, OEM compliance, or repair quality.
"""
from __future__ import annotations

import html
import json
from typing import Any

from repairgraph.state.blockers import get_open_blockers, summarize_blockers
from repairgraph.state.export_mermaid import (
    build_blocker_flow_mermaid,
    build_phase_flow_mermaid,
    build_workflow_timeline_mermaid,
    build_zone_activation_mermaid,
)
from repairgraph.state.next_actions import summarize_next_actions
from repairgraph.state.replay import build_state_diff, replay_repair_state, summarize_state_diff
from repairgraph.state.schema import RepairEvent, RepairState
from repairgraph.state.timeline import (
    build_action_timeline,
    build_event_timeline,
    build_phase_timeline,
    summarize_timeline,
)

_ADVISORY_NOTE = (
    "Advisory: This report is workflow intelligence derived from RepairGraph "
    "procedure data and explicit state events. It does not certify repair "
    "completion, OEM compliance, or repair quality. All workflow guidance "
    "requires OEM procedure verification and qualified technician review "
    "before acting on any recommendation."
)

_GENERATED_BY = "repairgraph.state.html_report"

_CSS = """
*{box-sizing:border-box;margin:0;padding:0}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;font-size:14px;background:#f0f2f5;color:#1a1a2e;line-height:1.5}
header{background:#1a2332;color:#e8eaf0;padding:20px 32px;border-bottom:3px solid #2d5a8c}
header .title{font-size:22px;font-weight:700;letter-spacing:.5px}
header .subtitle{font-size:13px;color:#8899bb;margin-top:4px}
header .meta{font-size:12px;color:#667799;margin-top:2px;font-family:monospace}
.advisory-banner{background:#fff3cd;border-left:4px solid #e6a817;color:#5a4000;padding:10px 32px;font-size:13px}
.advisory-banner strong{color:#b8860b}
main{padding:24px 32px;max-width:1400px}
.section{background:#fff;border-radius:6px;border:1px solid #dde1e8;margin-bottom:18px;overflow:hidden}
.section-header{background:#f8f9fc;border-bottom:1px solid #dde1e8;padding:10px 16px;font-weight:600;font-size:12px;color:#333;text-transform:uppercase;letter-spacing:.5px}
.section-body{padding:16px}
.cards{display:flex;flex-wrap:wrap;gap:12px}
.card{background:#fff;border:1px solid #dde1e8;border-radius:6px;padding:14px 16px;min-width:110px;text-align:center;flex:1}
.card-value{font-size:26px;font-weight:700;color:#1a2332}
.card-label{font-size:11px;color:#778;text-transform:uppercase;letter-spacing:.5px;margin-top:3px}
.card.blue .card-value{color:#2d5a8c}
.card.amber .card-value{color:#c87800}
.card.red .card-value{color:#cc3333}
.card.green .card-value{color:#228844}
table{width:100%;border-collapse:collapse;font-size:13px}
th{background:#f0f2f5;text-align:left;padding:7px 10px;font-weight:600;font-size:11px;text-transform:uppercase;letter-spacing:.4px;color:#556;border-bottom:1px solid #dde1e8}
td{padding:7px 10px;border-bottom:1px solid #eef0f3;vertical-align:top}
tr:last-child td{border-bottom:none}
tr:hover td{background:#f8f9fc}
.badge{display:inline-block;padding:2px 7px;border-radius:3px;font-size:11px;font-weight:600;text-transform:uppercase;letter-spacing:.3px;white-space:nowrap}
.s-not_started,.s-pending{background:#eee;color:#555}
.s-in_progress{background:#fff3cd;color:#7a5200}
.s-complete{background:#d4edda;color:#155724}
.s-blocked{background:#f8d7da;color:#721c24}
.s-ready_for_review{background:#cce5ff;color:#004085}
.s-not_applicable{background:#f5f5f5;color:#888}
.s-open{background:#f8d7da;color:#721c24}
.s-passed{background:#d4edda;color:#155724}
.s-failed{background:#f8d7da;color:#721c24}
.s-resolved{background:#d4edda;color:#155724}
.s-low{background:#e8f5e9;color:#1b5e20}
.s-medium{background:#fff3e0;color:#7a3800}
.s-high{background:#fce4ec;color:#880e4f}
.s-critical{background:#c62828;color:#fff}
.ev-session_started,.ev-phase_started,.ev-action_started,.ev-qa_gate_opened{background:#e3f2fd;color:#0d47a1}
.ev-action_completed,.ev-phase_completed,.ev-session_completed,.ev-qa_gate_passed,.ev-blocker_resolved{background:#e8f5e9;color:#1b5e20}
.ev-action_blocked,.ev-qa_gate_failed,.ev-session_cancelled,.ev-blocker_added{background:#fce4ec;color:#880e4f}
.ev-action_marked_not_applicable,.ev-qa_gate_marked_not_applicable{background:#f5f5f5;color:#666}
.mono{font-family:monospace;font-size:12px;color:#334}
.mermaid-block{background:#1e2030;color:#c8d0e7;border-radius:4px;padding:14px 16px;font-family:monospace;font-size:12px;overflow-x:auto;white-space:pre;line-height:1.6;border:1px solid #333}
.mermaid-hint{font-size:11px;color:#888;margin-top:6px;font-style:italic}
.empty{color:#999;font-style:italic;font-size:13px}
.tag{display:inline-block;background:#eef0f5;border-radius:3px;padding:1px 6px;font-size:11px;color:#445;margin:1px;font-family:monospace}
.replay-controls{display:flex;align-items:center;gap:10px;margin-bottom:14px;flex-wrap:wrap}
.replay-btn{background:#1a2332;color:#e8eaf0;border:none;padding:6px 14px;border-radius:4px;cursor:pointer;font-size:13px;font-weight:600}
.replay-btn:hover{background:#2d5a8c}
.replay-btn:disabled{background:#bbb;cursor:not-allowed}
.step-chips{display:flex;flex-wrap:wrap;gap:5px;margin-bottom:14px}
.step-chip{padding:3px 10px;border-radius:10px;border:1px solid #dde1e8;background:#f8f9fc;cursor:pointer;font-size:12px;color:#445}
.step-chip:hover{background:#e0e5f0;border-color:#aaa}
.step-chip.active{background:#1a2332;color:#fff;border-color:#1a2332}
.step-counter{font-size:13px;color:#556;min-width:80px}
.replay-panel{display:none;background:#f8f9fc;border:1px solid #dde1e8;border-radius:4px;padding:16px}
.replay-panel.visible{display:block}
.replay-event-type{font-size:16px;font-weight:700;color:#1a2332;margin-bottom:12px}
.replay-grid{display:grid;grid-template-columns:repeat(auto-fit,minmax(230px,1fr));gap:12px}
.replay-card{background:#fff;border:1px solid #dde1e8;border-radius:4px;padding:12px}
.replay-card-title{font-size:11px;text-transform:uppercase;letter-spacing:.5px;color:#778;margin-bottom:8px;font-weight:600}
.diff-item{font-size:12px;padding:2px 0;font-family:monospace}
.diff-item::before{content:"→ ";color:#2d5a8c}
.kv{display:flex;gap:8px;margin-bottom:4px;font-size:12px}
.kv-key{color:#778;min-width:120px;flex-shrink:0}
.kv-val{color:#1a1a2e;font-family:monospace;word-break:break-all}
footer{margin-top:24px;padding:14px 32px;font-size:11px;color:#aaa;border-top:1px solid #dde1e8;text-align:center}
"""

_REPLAY_JS = r"""
var REPLAY_DATA = null;
var currentStep = -1;

function initReplay(data) {
    REPLAY_DATA = data;
    if (!data || !data.steps || !data.steps.length) return;
    document.getElementById('replay-total').textContent = data.steps.length;
    buildStepChips();
    showStep(0);
}

function buildStepChips() {
    var container = document.getElementById('step-chips');
    if (!container) return;
    container.innerHTML = '';
    REPLAY_DATA.steps.forEach(function(step, i) {
        var chip = document.createElement('span');
        chip.className = 'step-chip';
        chip.textContent = 'Step ' + step.step;
        chip.onclick = function() { showStep(i); };
        chip.id = 'chip-' + i;
        container.appendChild(chip);
    });
}

function showStep(idx) {
    if (!REPLAY_DATA || idx < 0 || idx >= REPLAY_DATA.steps.length) return;
    currentStep = idx;
    var step = REPLAY_DATA.steps[idx];

    document.querySelectorAll('.step-chip').forEach(function(c, i) {
        c.classList.toggle('active', i === idx);
    });
    document.getElementById('replay-current').textContent = idx + 1;

    document.getElementById('btn-prev').disabled = (idx === 0);
    document.getElementById('btn-next').disabled = (idx === REPLAY_DATA.steps.length - 1);

    var panel = document.getElementById('replay-panel');
    if (panel) {
        panel.classList.add('visible');
        panel.innerHTML = renderStep(step);
    }
}

function renderStep(step) {
    var ev = step.event;
    var ss = step.state_summary;
    var ds = step.diff_summary;

    var evClass = 'ev-' + ev.event_type.replace(/_/g, '_');

    var html = '<div class="replay-event-type">';
    html += '<span class="badge ' + evClass + '">' + esc(ev.event_type) + '</span>';
    html += ' &nbsp; Step ' + step.step + ' of ' + REPLAY_DATA.steps.length;
    html += '</div>';

    html += '<div class="replay-grid">';

    // Event card
    html += '<div class="replay-card">';
    html += '<div class="replay-card-title">Event</div>';
    html += kv('ID', ev.event_id);
    html += kv('Type', ev.event_type);
    html += kv('Actor', ev.actor);
    html += kv('Target', ev.target_type + ':' + ev.target_id);
    html += kv('Timestamp', ev.timestamp);
    if (ev.notes) html += kv('Notes', ev.notes);
    html += '</div>';

    // State Summary card
    html += '<div class="replay-card">';
    html += '<div class="replay-card-title">State After Event</div>';
    html += kv('Session', ss.session_status);
    html += kv('Active Phases', ss.active_phase_ids.join(', ') || '—');
    html += kv('Completed Phases', ss.completed_phase_count);
    html += kv('Completed Actions', ss.completed_action_count);
    html += kv('Open Blockers', ss.open_blocker_count);
    html += kv('Open QA Gates', ss.open_qa_gate_count);
    html += '</div>';

    // Diff card
    html += '<div class="replay-card">';
    html += '<div class="replay-card-title">Changes (' + ds.change_count + ')</div>';
    if (ds.changes && ds.changes.length > 0) {
        ds.changes.forEach(function(c) {
            html += '<div class="diff-item">' + esc(c) + '</div>';
        });
    } else {
        html += '<span class="empty">No state changes</span>';
    }
    html += '</div>';

    // Next Actions card
    if (ss.next_recommended_actions && ss.next_recommended_actions.length > 0) {
        html += '<div class="replay-card">';
        html += '<div class="replay-card-title">Next Actions</div>';
        ss.next_recommended_actions.forEach(function(a) {
            html += '<div class="diff-item">' + esc(a) + '</div>';
        });
        html += '</div>';
    }

    html += '</div>';
    return html;
}

function kv(key, val) {
    return '<div class="kv"><span class="kv-key">' + esc(key) + '</span><span class="kv-val">' + esc(String(val)) + '</span></div>';
}

function esc(s) {
    return String(s).replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}

function prevStep() { if (currentStep > 0) showStep(currentStep - 1); }
function nextStep() { if (REPLAY_DATA && currentStep < REPLAY_DATA.steps.length - 1) showStep(currentStep + 1); }
"""


# ─────────────────────────────────────────────
# Low-level helpers
# ─────────────────────────────────────────────

def _h(text: Any) -> str:
    return html.escape(str(text))


def _badge(status: str, prefix: str = "s") -> str:
    cls = f"{prefix}-{status.replace(' ', '_').replace('/', '_').replace(':', '_')}"
    return f'<span class="badge {_h(cls)}">{_h(status)}</span>'


def _tags(items: list[str]) -> str:
    if not items:
        return '<span class="empty">—</span>'
    return " ".join(f'<span class="tag">{_h(item)}</span>' for item in items)


def _kv(key: str, val: Any) -> str:
    return f'<div class="kv"><span class="kv-key">{_h(key)}</span><span class="kv-val">{_h(str(val))}</span></div>'


def _table(headers: list[str], rows: list[list[str]]) -> str:
    th = "".join(f"<th>{_h(h)}</th>" for h in headers)
    trs = ""
    for row in rows:
        tds = "".join(f"<td>{cell}</td>" for cell in row)
        trs += f"<tr>{tds}</tr>"
    if not rows:
        trs = f'<tr><td colspan="{len(headers)}" class="empty" style="padding:12px 10px">No entries.</td></tr>'
    return f"<table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>"


def _section(title: str, content: str) -> str:
    return (
        f'<div class="section">'
        f'<div class="section-header">{_h(title)}</div>'
        f'<div class="section-body">{content}</div>'
        f'</div>'
    )


def _mermaid_block(source: str) -> str:
    return (
        f'<pre class="mermaid-block">{_h(source)}</pre>'
        f'<p class="mermaid-hint">Mermaid diagram source — render with any compatible Mermaid tool.</p>'
    )


def _html_shell(title: str, body: str, extra_js: str = "") -> str:
    return (
        f"<!DOCTYPE html>\n"
        f'<html lang="en">\n'
        f"<head>\n"
        f'<meta charset="UTF-8">\n'
        f'<meta name="viewport" content="width=device-width, initial-scale=1.0">\n'
        f"<title>{_h(title)}</title>\n"
        f"<style>\n{_CSS}\n</style>\n"
        f"</head>\n"
        f"<body>\n"
        f"{body}\n"
        f"<footer>Generated by {_h(_GENERATED_BY)} &bull; RepairGraph advisory workflow intelligence</footer>\n"
        f"<script>\n{extra_js}\n</script>\n"
        f"</body>\n"
        f"</html>"
    )


# ─────────────────────────────────────────────
# Public API
# ─────────────────────────────────────────────

def build_summary_cards(state: RepairState) -> list[dict[str, str]]:
    """Return a list of summary card dicts for the given RepairState.

    Each dict has keys: value, label, accent.
    """
    open_blockers = get_open_blockers(state)
    completed_actions = [a for a in state.actions if a.status == "complete"]
    open_qa = [g for g in state.qa_gates if g.status in {"open", "in_review", "failed"}]

    return [
        {"value": str(len(state.phases)), "label": "Phases", "accent": "blue"},
        {"value": str(len(state.actions)), "label": "Actions", "accent": "blue"},
        {"value": str(len(completed_actions)), "label": "Completed Actions", "accent": "green"},
        {"value": str(len(state.qa_gates)), "label": "QA Gates", "accent": "blue"},
        {"value": str(len(open_qa)), "label": "Open QA", "accent": "amber" if open_qa else "green"},
        {"value": str(len(open_blockers)), "label": "Open Blockers", "accent": "red" if open_blockers else "green"},
        {"value": str(len(state.events)), "label": "Events", "accent": "blue"},
        {"value": str(len(state.next_recommended_actions)), "label": "Next Actions", "accent": "amber"},
    ]


def build_visualization_sections(state: RepairState) -> dict[str, Any]:
    """Return a dict containing Mermaid diagram sources and section metadata.

    Keys: workflow_timeline, phase_flow, blocker_flow, zone_activation.
    Each value is the raw Mermaid source string.
    """
    return {
        "workflow_timeline": build_workflow_timeline_mermaid(state),
        "phase_flow": build_phase_flow_mermaid(state),
        "blocker_flow": build_blocker_flow_mermaid(state),
        "zone_activation": build_zone_activation_mermaid(state),
        "sections": ["workflow_timeline", "phase_flow", "blocker_flow", "zone_activation"],
    }


def build_workflow_html_report(state: RepairState) -> str:
    """Build a self-contained HTML workflow report from a RepairState.

    The report includes a header, advisory banner, summary cards, active phases,
    next actions, blockers, QA gates, event timeline, phase and action tables,
    and Mermaid diagram source blocks. No external resources are loaded.
    Output is deterministic given the same input state.
    """
    s = state.session
    parts: list[str] = []

    # Header
    parts.append(
        f'<header>'
        f'<div class="title">RepairGraph Workflow Intelligence</div>'
        f'<div class="subtitle">'
        f'{_h(s.year)} {_h(s.oem)} {_h(s.model)} &mdash; {_h(s.operation)}'
        f'</div>'
        f'<div class="meta">'
        f'Session: {_h(s.session_id)} &bull; Status: {_badge(s.status)}'
        f'</div>'
        f'</header>'
    )

    # Advisory banner
    parts.append(
        f'<div class="advisory-banner">'
        f'<strong>Advisory:</strong> '
        f'{_h(_ADVISORY_NOTE[len("Advisory: "):])}'
        f'</div>'
    )

    parts.append("<main>")

    # Summary cards
    cards = build_summary_cards(state)
    cards_html = '<div class="cards">' + "".join(
        f'<div class="card {c["accent"]}">'
        f'<div class="card-value">{_h(c["value"])}</div>'
        f'<div class="card-label">{_h(c["label"])}</div>'
        f'</div>'
        for c in cards
    ) + '</div>'
    parts.append(_section("Workflow Summary", cards_html))

    # Session overview
    overview_html = (
        _kv("Session ID", s.session_id)
        + _kv("OEM", s.oem)
        + _kv("Year", s.year)
        + _kv("Model", s.model)
        + _kv("Operation", s.operation)
        + _kv("Status", s.status)
        + _kv("Current Phase", s.current_phase or "—")
    )
    parts.append(_section("Session Overview", overview_html))

    # Active phases
    active_phases = [p for p in state.phases if p.status == "in_progress"]
    blocked_phases = [p for p in state.phases if p.status == "blocked"]
    notable_phases = active_phases + blocked_phases
    if notable_phases:
        rows = [
            [
                _h(p.name),
                _badge(p.status),
                _tags(p.active_zones),
                _tags(p.pending_actions),
                _tags(p.blocked_by),
            ]
            for p in notable_phases
        ]
        parts.append(_section(
            "Active / Blocked Phases",
            _table(["Phase Name", "Status", "Active Zones", "Pending Actions", "Blocked By"], rows),
        ))

    # Next recommended actions
    next_acts = state.next_recommended_actions
    if next_acts:
        action_map = {a.action_id: a for a in state.actions}
        rows = []
        for aid in next_acts:
            act = action_map.get(aid)
            rows.append([
                f'<span class="mono">{_h(aid)}</span>',
                _h(act.action_type if act else "—"),
                _h(act.target if act else "—"),
                _badge(act.status if act else "—"),
                _tags(act.zone_refs if act else []),
            ])
        parts.append(_section(
            "Next Recommended Actions",
            _table(["Action ID", "Type", "Target", "Status", "Zones"], rows),
        ))
    else:
        parts.append(_section("Next Recommended Actions", '<span class="empty">No next actions pending.</span>'))

    # Open blockers
    open_blockers = get_open_blockers(state)
    if open_blockers:
        rows = [
            [
                f'<span class="mono">{_h(b.blocker_id)}</span>',
                _badge(b.type),
                _badge(b.severity, "s"),
                _badge(b.status),
                _h(b.reason or "—"),
                _tags(b.blocks),
            ]
            for b in open_blockers
        ]
        parts.append(_section(
            f"Open Blockers ({len(open_blockers)})",
            _table(["Blocker ID", "Type", "Severity", "Status", "Reason", "Blocks"], rows),
        ))
    else:
        parts.append(_section("Open Blockers", '<span class="empty">No open blockers.</span>'))

    # QA gates
    open_qa = [g for g in state.qa_gates if g.status in {"open", "in_review", "failed"}]
    if open_qa:
        rows = [
            [
                f'<span class="mono">{_h(g.gate_id)}</span>',
                _h(g.category),
                _badge(g.priority, "s"),
                _badge(g.status),
                "Yes" if g.blocks_completion else "No",
                _h(g.check or "—"),
            ]
            for g in open_qa
        ]
        parts.append(_section(
            f"Open QA Gates ({len(open_qa)})",
            _table(["Gate ID", "Category", "Priority", "Status", "Blocks Completion", "Check"], rows),
        ))

    # Event timeline
    ev_timeline = build_event_timeline(state)
    if ev_timeline:
        rows = [
            [
                _h(e["seq"]),
                f'<span class="mono">{_h(e["event_id"])}</span>',
                _badge(e["event_type"], "ev"),
                _h(e["actor"]),
                _h(e["target_type"]),
                f'<span class="mono">{_h(e["target_id"])}</span>',
                _h(e["timestamp"]),
            ]
            for e in ev_timeline
        ]
        parts.append(_section(
            "Event Timeline",
            _table(["#", "Event ID", "Type", "Actor", "Target Type", "Target ID", "Timestamp"], rows),
        ))
    else:
        parts.append(_section("Event Timeline", '<span class="empty">No events recorded.</span>'))

    # Phase timeline
    phase_tl = build_phase_timeline(state)
    if phase_tl:
        rows = [
            [
                _h(p["phase"]),
                _h(p["name"]),
                _h(p["label"]),
                _badge(p["status"]),
                _tags(p["active_zones"]),
                _h(len(p["completed_actions"])),
                _h(len(p["pending_actions"])),
            ]
            for p in phase_tl
        ]
        parts.append(_section(
            "Phase Overview",
            _table(["#", "Name", "Label", "Status", "Active Zones", "Completed", "Pending"], rows),
        ))

    # Action timeline
    act_tl = build_action_timeline(state)
    if act_tl:
        rows = [
            [
                f'<span class="mono">{_h(a["action_id"])}</span>',
                _h(a["phase"]),
                _h(a["action_type"]),
                _h(a["target"]),
                _badge(a["status"]),
                _tags(a["zone_refs"]),
            ]
            for a in act_tl
        ]
        parts.append(_section(
            "Action Details",
            _table(["Action ID", "Phase", "Type", "Target", "Status", "Zones"], rows),
        ))

    # Mermaid diagrams
    vis = build_visualization_sections(state)
    mermaid_sections = [
        ("Workflow Timeline Diagram", "workflow_timeline"),
        ("Phase Flow Diagram", "phase_flow"),
        ("Blocker Flow Diagram", "blocker_flow"),
        ("Zone Activation Diagram", "zone_activation"),
    ]
    for label, key in mermaid_sections:
        parts.append(_section(label, _mermaid_block(vis[key])))

    parts.append("</main>")
    return _html_shell(
        title=f"RepairGraph Workflow Report — {s.year} {s.oem} {s.model}",
        body="\n".join(parts),
    )


def build_replay_html_report(
    initial_state: RepairState,
    events: list[RepairEvent],
) -> str:
    """Build a self-contained HTML replay inspector report.

    Generates an interactive step-by-step replay navigator that shows the event,
    state summary, and diff at each replay step. Uses vanilla JS only — no frameworks
    or external dependencies. Output is deterministic given the same inputs.
    """
    s = initial_state.session
    snapshots = replay_repair_state(initial_state, events)

    # Build replay data for JS
    steps_data: list[dict[str, Any]] = []
    prev = initial_state
    for i, (event, snap) in enumerate(zip(events, snapshots)):
        diff = build_state_diff(prev, snap)
        diff_summary = summarize_state_diff(diff)
        steps_data.append({
            "step": i + 1,
            "event": {
                "event_id": event.event_id,
                "event_type": event.event_type,
                "timestamp": event.timestamp,
                "actor": event.actor,
                "target_type": event.target_type,
                "target_id": event.target_id,
                "notes": event.notes or "",
            },
            "state_summary": {
                "session_status": snap.session.status,
                "active_phase_ids": [p.name for p in snap.phases if p.status == "in_progress"],
                "completed_phase_count": sum(1 for p in snap.phases if p.status == "complete"),
                "completed_action_count": sum(1 for a in snap.actions if a.status == "complete"),
                "open_blocker_count": sum(1 for b in snap.blockers if b.status == "open"),
                "open_qa_gate_count": sum(1 for g in snap.qa_gates if g.status in {"open", "in_review"}),
                "next_recommended_actions": list(snap.next_recommended_actions),
            },
            "diff_summary": {
                "change_count": diff_summary["change_count"],
                "changes": diff_summary["changes"],
                "changed_entities": diff_summary["changed_entities"],
            },
        })
        prev = snap

    replay_json = json.dumps({"steps": steps_data}, ensure_ascii=False)

    parts: list[str] = []

    # Header
    parts.append(
        f'<header>'
        f'<div class="title">RepairGraph Replay Inspector</div>'
        f'<div class="subtitle">'
        f'{_h(s.year)} {_h(s.oem)} {_h(s.model)} &mdash; {_h(s.operation)}'
        f'</div>'
        f'<div class="meta">'
        f'Session: {_h(s.session_id)} &bull; '
        f'{_h(len(events))} events &bull; {_h(len(snapshots))} snapshots'
        f'</div>'
        f'</header>'
    )

    # Advisory banner
    parts.append(
        f'<div class="advisory-banner">'
        f'<strong>Advisory:</strong> '
        f'{_h(_ADVISORY_NOTE[len("Advisory: "):])}'
        f'</div>'
    )

    parts.append("<main>")

    # Session overview
    overview_html = (
        _kv("Session ID", s.session_id)
        + _kv("OEM", s.oem)
        + _kv("Year", s.year)
        + _kv("Model", s.model)
        + _kv("Operation", s.operation)
        + _kv("Initial Status", initial_state.session.status)
        + _kv("Event Count", len(events))
        + _kv("Snapshot Count", len(snapshots))
    )
    parts.append(_section("Session Overview", overview_html))

    # Summary cards for final projected state
    if snapshots:
        final = snapshots[-1]
        cards = build_summary_cards(final)
        cards_html = '<div class="cards">' + "".join(
            f'<div class="card {c["accent"]}">'
            f'<div class="card-value">{_h(c["value"])}</div>'
            f'<div class="card-label">{_h(c["label"])}</div>'
            f'</div>'
            for c in cards
        ) + '</div>'
        parts.append(_section("Final State Summary", cards_html))

    # Replay inspector
    if events:
        inspector_html = (
            f'<div class="replay-controls">'
            f'<button class="replay-btn" id="btn-prev" onclick="prevStep()" disabled>&#8592; Prev</button>'
            f'<button class="replay-btn" id="btn-next" onclick="nextStep()">Next &#8594;</button>'
            f'<span class="step-counter">Step <span id="replay-current">—</span> of <span id="replay-total">—</span></span>'
            f'</div>'
            f'<div class="step-chips" id="step-chips"></div>'
            f'<div class="replay-panel" id="replay-panel"></div>'
        )
        parts.append(_section("Replay Inspector", inspector_html))
    else:
        parts.append(_section("Replay Inspector", '<span class="empty">No events to replay.</span>'))

    # Replay diff summary table (all steps)
    if steps_data:
        rows = [
            [
                _h(step["step"]),
                _badge(step["event"]["event_type"], "ev"),
                _h(step["event"]["actor"]),
                _h(step["event"]["target_type"] + ":" + step["event"]["target_id"]),
                _badge(step["state_summary"]["session_status"]),
                _h(step["diff_summary"]["change_count"]),
                _h(step["event"]["timestamp"]),
            ]
            for step in steps_data
        ]
        parts.append(_section(
            "Replay Step Summary",
            _table(
                ["Step", "Event Type", "Actor", "Target", "Session Status", "Changes", "Timestamp"],
                rows,
            ),
        ))

    # Mermaid diagrams from final projected state
    if snapshots:
        final = snapshots[-1]
        vis = build_visualization_sections(final)
        mermaid_sections = [
            ("Phase Flow (Final State)", "phase_flow"),
            ("Blocker Flow (Final State)", "blocker_flow"),
            ("Workflow Timeline Diagram", "workflow_timeline"),
        ]
        for label, key in mermaid_sections:
            parts.append(_section(label, _mermaid_block(vis[key])))

    parts.append("</main>")

    init_js = f"var _replayData = {replay_json};\n" + _REPLAY_JS + "\ninitReplay(_replayData);\n"

    return _html_shell(
        title=f"RepairGraph Replay Report — {s.year} {s.oem} {s.model}",
        body="\n".join(parts),
        extra_js=init_js,
    )
