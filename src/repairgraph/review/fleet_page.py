"""
Fleet dashboard — self-contained HTML page (no CDN, no external JS, no
frameworks) showing every tracked job grouped by status.

Answers a manager's question — "which jobs need attention right now" —
rather than a technician's "what's next on this job." Each job card links
to its Repair Review and Progress pages.
"""
from __future__ import annotations

import html
from typing import Any

_ADVISORY_FALLBACK = (
    "Fleet summary outputs are advisory workflow intelligence aggregated across "
    "tracked jobs. They do not certify repair completion, OEM compliance, or "
    "repair quality. Each job requires verification by a qualified technician "
    "against its applicable OEM procedures."
)

_STATUS_ORDER = ["blocked", "in_progress", "not_started", "ready", "cancelled"]
_STATUS_LABELS = {
    "blocked": "Blocked",
    "in_progress": "In Progress",
    "not_started": "Not Started",
    "ready": "Ready",
    "cancelled": "Cancelled",
}

_CSS = """
:root { --bg:#f6f7f9; --card:#fff; --ink:#1a1f28; --muted:#5c6470; --line:#e3e6ea;
        --ok:#1a7f4e; --ok-bg:#e8f5ee; --warn:#9a6700; --warn-bg:#fff3d6;
        --bad:#b3251e; --bad-bg:#fdebea; --accent:#2456c4; --accent-bg:#e7edfb; }
* { box-sizing:border-box; margin:0; padding:0; }
body { font:15px/1.5 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
       background:var(--bg); color:var(--ink); padding:24px; max-width:1080px; margin:0 auto; }
h1 { font-size:22px; margin-bottom:4px; }
h2 { font-size:15px; margin:0 0 10px; display:flex; align-items:center; gap:8px; }
.sub { color:var(--muted); font-size:13px; margin-bottom:20px; }
.stat-row { display:flex; gap:14px; flex-wrap:wrap; margin-bottom:26px; }
.stat { background:var(--card); border:1px solid var(--line); border-radius:8px;
        padding:12px 18px; min-width:110px; }
.stat b { display:block; font-size:24px; }
.stat span { font-size:12px; color:var(--muted); }
.stat.blocked b { color:var(--bad); }
.stat.in_progress b { color:var(--accent); }
.stat.ready b { color:var(--ok); }
.bucket { margin-bottom:26px; }
.bucket-empty { color:var(--muted); font-size:13px; padding:10px 0; }
.count-pill { font-size:12px; font-weight:700; padding:1px 8px; border-radius:10px; }
.count-pill.blocked { background:var(--bad-bg); color:var(--bad); }
.count-pill.in_progress { background:var(--accent-bg); color:var(--accent); }
.count-pill.not_started { background:#eee; color:var(--muted); }
.count-pill.ready { background:var(--ok-bg); color:var(--ok); }
.count-pill.cancelled { background:#eee; color:var(--muted); }
.job-grid { display:grid; grid-template-columns:repeat(auto-fill, minmax(260px,1fr)); gap:10px; }
.job-card { background:var(--card); border:1px solid var(--line); border-left-width:4px;
            border-radius:8px; padding:12px 14px; }
.job-card.blocked { border-left-color:var(--bad); }
.job-card.in_progress { border-left-color:var(--accent); }
.job-card.not_started { border-left-color:var(--line); }
.job-card.ready { border-left-color:var(--ok); }
.job-title { font-weight:600; margin-bottom:2px; }
.job-op { color:var(--muted); font-size:12.5px; margin-bottom:8px; }
.job-metrics { display:flex; gap:12px; font-size:12.5px; color:var(--muted); margin-bottom:8px; }
.job-metrics b { color:var(--ink); }
.job-links { display:flex; gap:8px; }
.job-links a { font-size:12.5px; color:var(--accent); text-decoration:none; }
.job-links a:hover { text-decoration:underline; }
.source-badge { font-size:10.5px; text-transform:uppercase; letter-spacing:.3px;
                color:var(--muted); border:1px solid var(--line); border-radius:8px;
                padding:0 6px; margin-left:6px; }
.advisory { margin-top:24px; padding-top:12px; border-top:1px solid var(--line);
            font-size:12px; color:var(--muted); }
.empty-fleet { text-align:center; color:var(--muted); padding:60px 0; }
"""


def _esc(s: Any) -> str:
    return html.escape(str(s), quote=True)


def _job_card(job: dict[str, Any]) -> str:
    status = job["status"]
    title = f"{job['year']} {job['oem']} {job['model']}"
    op = job.get("operation", "").replace("_", " ").title()
    next_action = job.get("next_recommended_action")
    next_label = (
        next_action.replace(":", " — ").replace("_", " ")
        if next_action else "No pending action"
    )
    return f"""<div class="job-card {_esc(status)}">
  <div class="job-title">{_esc(title)}<span class="source-badge">{_esc(job.get("source","?"))}</span></div>
  <div class="job-op">{_esc(op)}</div>
  <div class="job-metrics">
    <span><b>{job['open_qa_gates']}</b> open gates</span>
    <span><b>{job['open_blockers']}</b> blockers</span>
    <span><b>{job['complete_actions']}</b>/{job['total_actions']} actions</span>
  </div>
  <div class="job-op">Next: {_esc(next_label)}</div>
  <div class="job-links">
    <a href="{_esc(job['review_link'])}">Review</a>
    <a href="{_esc(job['progress_link'])}">Progress</a>
  </div>
</div>"""


def _bucket_section(status: str, jobs: list[dict[str, Any]]) -> str:
    label = _STATUS_LABELS[status]
    if not jobs:
        return f"""<div class="bucket">
  <h2>{_esc(label)} <span class="count-pill {_esc(status)}">0</span></h2>
  <div class="bucket-empty">No jobs.</div>
</div>"""
    cards = "".join(_job_card(j) for j in jobs)
    return f"""<div class="bucket">
  <h2>{_esc(label)} <span class="count-pill {_esc(status)}">{len(jobs)}</span></h2>
  <div class="job-grid">{cards}</div>
</div>"""


def build_fleet_page_html(summary: dict[str, Any]) -> str:
    """Render the Fleet Summary dashboard from a build_fleet_summary() dict."""
    counts = summary["counts_by_status"]
    by_status = summary["jobs_by_status"]

    if summary["job_count"] == 0:
        body = (
            '<div class="empty-fleet">No jobs yet. Upload an OEM packet through '
            '<a href="/internal/intake">Intake</a> to start tracking one.</div>'
        )
    else:
        stats = "".join(
            f'<div class="stat {_esc(s)}"><b>{counts.get(s,0)}</b><span>{_esc(_STATUS_LABELS[s])}</span></div>'
            for s in _STATUS_ORDER
        )
        buckets = "".join(
            _bucket_section(s, by_status.get(s, []))
            for s in _STATUS_ORDER
            if by_status.get(s) or s in ("blocked", "in_progress")
        )
        body = f'<div class="stat-row">{stats}</div>{buckets}'

    advisory = summary.get("advisory", _ADVISORY_FALLBACK)

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>Fleet Summary</title>
<style>{_CSS}</style>
</head>
<body>
<h1>Fleet Summary</h1>
<div class="sub">{summary['job_count']} tracked job{'s' if summary['job_count'] != 1 else ''}
  &middot; <a href="/internal/intake">Add a job via Intake</a></div>

{body}

<div class="advisory">{_esc(advisory)}</div>
</body>
</html>"""
