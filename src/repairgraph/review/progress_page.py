"""
Repair Progress page — record work as it happens.

Self-contained HTML page (no CDN, no external JS, no frameworks) that lists
the resolved vehicle's QA gates and actions with controls to record progress
events. Every button POSTs a single event to /internal/review/progress/events
and reloads, so the page always shows the projected state from the journal.

Recording an event documents that a human performed or verified work. All
resulting state remains advisory — nothing on this page certifies repair
completion, OEM compliance, or repair quality.
"""
from __future__ import annotations

import html
import json
from typing import Any

_ADVISORY = (
    "RepairGraph outputs are advisory workflow intelligence. They do not certify "
    "repair completion, OEM compliance, or repair quality. All outputs require "
    "verification by a qualified technician against current OEM procedures."
)

_CSS = """
:root { --bg:#f6f7f9; --card:#fff; --ink:#1a1f28; --muted:#5c6470; --line:#e3e6ea;
        --ok:#1a7f4e; --ok-bg:#e8f5ee; --warn:#9a6700; --warn-bg:#fff3d6;
        --bad:#b3251e; --bad-bg:#fdebea; --accent:#2456c4; }
* { box-sizing:border-box; margin:0; padding:0; }
body { font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
       background:var(--bg); color:var(--ink); padding:24px; max-width:960px; margin:0 auto; }
h1 { font-size:22px; margin-bottom:4px; }
h2 { font-size:16px; margin:24px 0 8px; }
.sub { color:var(--muted); font-size:13px; margin-bottom:16px; }
.card { background:var(--card); border:1px solid var(--line); border-radius:8px;
        padding:14px 16px; margin-bottom:10px; }
.row { display:flex; align-items:center; justify-content:space-between; gap:12px; }
.meta { color:var(--muted); font-size:12.5px; margin-top:2px; }
.badge { display:inline-block; font-size:11px; font-weight:700; letter-spacing:.4px;
         padding:2px 8px; border-radius:10px; text-transform:uppercase; }
.badge.open, .badge.pending, .badge.not_started { background:var(--warn-bg); color:var(--warn); }
.badge.passed, .badge.complete, .badge.resolved, .badge.ready_for_review { background:var(--ok-bg); color:var(--ok); }
.badge.failed, .badge.blocked { background:var(--bad-bg); color:var(--bad); }
.badge.in_progress { background:#e7edfb; color:var(--accent); }
.badge.not_applicable { background:#eee; color:var(--muted); }
button { font:13px inherit; padding:5px 12px; border-radius:6px; border:1px solid var(--line);
         background:#fff; cursor:pointer; }
button:hover { border-color:var(--accent); color:var(--accent); }
button.primary { background:var(--accent); border-color:var(--accent); color:#fff; }
button.primary:hover { opacity:.9; color:#fff; }
button.danger { color:var(--bad); }
.controls { display:flex; gap:6px; flex-shrink:0; }
.topbar { display:flex; justify-content:space-between; align-items:center; margin-bottom:6px; }
.summary { display:flex; gap:18px; flex-wrap:wrap; margin:14px 0 6px; }
.stat { background:var(--card); border:1px solid var(--line); border-radius:8px; padding:10px 16px; }
.stat b { display:block; font-size:20px; }
.stat span { font-size:12px; color:var(--muted); }
.advisory { margin-top:28px; padding-top:12px; border-top:1px solid var(--line);
            font-size:12px; color:var(--muted); }
a { color:var(--accent); }
"""

_JS = """
const QS = window.location.search;
async function record(eventType, targetId) {
  const actor = document.getElementById('actor').value || 'review_ui';
  const res = await fetch('/internal/review/progress/events' + QS, {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({event_type: eventType, target_id: targetId, actor: actor}),
  });
  if (!res.ok) {
    const err = await res.json().catch(() => ({}));
    alert('Could not record event: ' + (err.detail || res.status));
    return;
  }
  window.location.reload();
}
async function resetProgress() {
  if (!confirm('Reset all recorded progress for this repair?')) return;
  await fetch('/internal/review/progress' + QS, {method: 'DELETE'});
  window.location.reload();
}
"""


def _esc(s: Any) -> str:
    return html.escape(str(s), quote=True)


def _gate_card(g: dict[str, Any]) -> str:
    gid = _esc(g["gate_id"])
    controls = ""
    if g["status"] == "open":
        controls = (
            f'<div class="controls">'
            f'<button class="primary" onclick="record(\'qa_gate_passed\',{json.dumps(g["gate_id"])})">Mark Passed</button>'
            f'<button onclick="record(\'qa_gate_failed\',{json.dumps(g["gate_id"])})">Mark Failed</button>'
            f'<button onclick="record(\'qa_gate_marked_not_applicable\',{json.dumps(g["gate_id"])})">N/A</button>'
            f'</div>'
        )
    blocking = " · blocks completion" if g.get("blocks_completion") else ""
    return (
        f'<div class="card"><div class="row">'
        f'<div><strong>{_esc(g.get("check") or gid)}</strong>'
        f'<div class="meta">{_esc(g.get("category",""))} · {_esc(g.get("priority",""))} priority{blocking}</div></div>'
        f'<div class="controls"><span class="badge {_esc(g["status"])}">{_esc(g["status"])}</span>{controls}</div>'
        f'</div></div>'
    )


def _action_card(a: dict[str, Any]) -> str:
    aid = json.dumps(a["action_id"])
    controls = ""
    if a["status"] == "pending":
        controls = (
            f'<button class="primary" onclick="record(\'action_started\',{aid})">Start</button>'
            f'<button onclick="record(\'action_completed\',{aid})">Complete</button>'
        )
    elif a["status"] == "in_progress":
        controls = (
            f'<button class="primary" onclick="record(\'action_completed\',{aid})">Complete</button>'
            f'<button onclick="record(\'action_blocked\',{aid})">Blocked</button>'
        )
    label = a["action_id"].replace(":", " — ").replace("_", " ")
    return (
        f'<div class="card"><div class="row">'
        f'<div><strong>{_esc(label)}</strong>'
        f'<div class="meta">phase {_esc(a.get("phase",""))} · {_esc(a.get("action_type",""))}</div></div>'
        f'<div class="controls"><span class="badge {_esc(a["status"])}">{_esc(a["status"])}</span>{controls}</div>'
        f'</div></div>'
    )


def build_progress_page_html(summary: dict[str, Any]) -> str:
    """Render the Repair Progress page from a progress summary dict."""
    v = summary["vehicle"]
    session = summary["session"]
    counts = summary["counts"]
    title = f"Repair Progress — {v['year']} {v['oem']} {v['model']}"

    gates = summary.get("qa_gates", [])
    actions = summary.get("actions", [])
    open_gates = [g for g in gates if g["status"] == "open"]
    other_gates = [g for g in gates if g["status"] != "open"]
    todo_actions = [a for a in actions if a["status"] in ("pending", "in_progress")]
    done_actions = [a for a in actions if a["status"] not in ("pending", "in_progress")]

    gates_html = "".join(_gate_card(g) for g in open_gates + other_gates) or (
        '<div class="card meta">No QA gates derived for this procedure.</div>'
    )
    actions_html = "".join(_action_card(a) for a in todo_actions + done_actions) or (
        '<div class="card meta">No actions derived for this procedure. '
        "Intake-derived packets without dependency data produce no action queue.</div>"
    )

    phases_html = " ".join(
        f'<span class="badge {_esc(p["status"])}">{_esc(p["label"] or p["name"])}</span>'
        for p in summary.get("phases", [])
    )

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{_esc(title)}</title>
<style>{_CSS}</style>
</head>
<body>
<div class="topbar">
  <div>
    <h1>{_esc(title)}</h1>
    <div class="sub">Session <span class="badge {_esc(session["status"])}">{_esc(session["status"])}</span>
      · {counts["events_recorded"]} events recorded
      · <a href="/internal/review{'' if not summary.get('_qs') else _esc(summary['_qs'])}">Open Repair Review</a></div>
  </div>
  <div class="controls">
    <label class="meta">Actor <input id="actor" value="review_ui" style="font:13px inherit;padding:4px 6px;border:1px solid var(--line);border-radius:6px;width:110px"></label>
    <button class="danger" onclick="resetProgress()">Reset Progress</button>
  </div>
</div>

<div class="summary">
  <div class="stat"><b>{counts["open_qa_gates"]}</b><span>open QA gates</span></div>
  <div class="stat"><b>{counts["open_blockers"]}</b><span>open blockers</span></div>
  <div class="stat"><b>{counts["pending_actions"]}</b><span>pending actions</span></div>
  <div class="stat"><b>{counts["complete_actions"]}</b><span>completed actions</span></div>
</div>

<h2>Phases</h2>
<div class="card">{phases_html or '<span class="meta">No phases.</span>'}</div>

<h2>QA Gates</h2>
{gates_html}

<h2>Work Actions</h2>
{actions_html}

<div class="advisory">{_esc(_ADVISORY)} Recording an event documents that a
human performed or verified work; it does not certify that work.</div>

<script>{_JS}</script>
</body>
</html>"""
