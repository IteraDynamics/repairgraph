"""
Home page — the single entry point tying the product experience together.

Before this existed, evaluating this tool meant already knowing four
separate URLs (/internal/intake, /internal/review, /internal/review/
progress/ui, /internal/fleet/ui) with no page linking them. This is the
front door: upload → see your job's review → track its progress → see the
shop-wide fleet view, in one obvious path.

Self-contained HTML. No CDN, no external JS, no frameworks.
"""
from __future__ import annotations

import html
from typing import Any

_CSS = """
:root { --bg:#f6f7f9; --card:#fff; --ink:#1a1f28; --muted:#5c6470; --line:#e3e6ea; --accent:#2456c4; --accent-bg:#e7edfb; }
* { box-sizing:border-box; margin:0; padding:0; }
body { font:15px/1.6 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,Helvetica,Arial,sans-serif;
       background:var(--bg); color:var(--ink); padding:32px 24px; max-width:840px; margin:0 auto; }
h1 { font-size:26px; margin-bottom:6px; }
.tagline { color:var(--muted); font-size:15px; margin-bottom:28px; max-width:600px; }
.steps { display:flex; flex-direction:column; gap:14px; margin-bottom:32px; }
.step { display:flex; gap:16px; align-items:flex-start; background:var(--card);
        border:1px solid var(--line); border-radius:10px; padding:18px 20px; text-decoration:none; color:inherit; }
.step:hover { border-color:var(--accent); }
.step-num { flex-shrink:0; width:30px; height:30px; border-radius:50%; background:var(--accent-bg);
            color:var(--accent); font-weight:700; font-size:14px; display:flex; align-items:center; justify-content:center; }
.step-body h2 { font-size:16px; margin-bottom:3px; }
.step-body p { color:var(--muted); font-size:13.5px; }
.status-row { display:flex; gap:14px; flex-wrap:wrap; margin-bottom:28px; }
.status-card { background:var(--card); border:1px solid var(--line); border-radius:8px; padding:10px 16px; font-size:13.5px; }
.status-card b { display:block; font-size:20px; }
.status-card.active b { color:var(--accent); }
.footer-note { color:var(--muted); font-size:12px; padding-top:16px; border-top:1px solid var(--line); }
a.plain { color:var(--accent); }
"""


def _esc(s: Any) -> str:
    return html.escape(str(s), quote=True)


def build_home_page_html(active_vehicle: dict[str, Any] | None, job_count: int) -> str:
    """Render the home page. active_vehicle and job_count come from the
    same sources the review and fleet pages already use (vehicle_store,
    fleet summary), so the home page never claims something the rest of
    the product doesn't back up.
    """
    if active_vehicle:
        label = f"{active_vehicle.get('year','')} {active_vehicle.get('oem','')} {active_vehicle.get('model','')}".strip()
        status_html = f"""
<div class="status-row">
  <div class="status-card active"><b>{_esc(label)}</b>Currently active job</div>
  <div class="status-card"><b>{job_count}</b>tracked job{'s' if job_count != 1 else ''}</div>
</div>"""
    else:
        status_html = f"""
<div class="status-row">
  <div class="status-card"><b>No active job</b>Upload a document to begin</div>
  <div class="status-card"><b>{job_count}</b>tracked job{'s' if job_count != 1 else ''}</div>
</div>"""

    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>RepairGraph — Repair Review</title>
<style>{_CSS}</style>
</head>
<body>
<h1>RepairGraph</h1>
<div class="tagline">Upload OEM repair documentation and get an advisory workflow review:
what's blocking a repair, what evidence supports it, and what should happen next.
All outputs require verification by a qualified technician.</div>

{status_html}

<div class="steps">
  <a class="step" href="/internal/intake">
    <div class="step-num">1</div>
    <div class="step-body"><h2>Upload a repair packet</h2>
      <p>Add OEM repair procedure, welding, and corrosion protection documents for a vehicle.</p></div>
  </a>
  <a class="step" href="/internal/review">
    <div class="step-num">2</div>
    <div class="step-body"><h2>Review the repair</h2>
      <p>See the decision, blockers, evidence, and recommended work package for the active job.</p></div>
  </a>
  <a class="step" href="/internal/review/progress/ui">
    <div class="step-num">3</div>
    <div class="step-body"><h2>Track progress</h2>
      <p>Record QA gates cleared and work completed as the repair proceeds.</p></div>
  </a>
  <a class="step" href="/internal/fleet/ui">
    <div class="step-num">4</div>
    <div class="step-body"><h2>See the shop floor</h2>
      <p>Every tracked job grouped by status — blocked, in progress, ready.</p></div>
  </a>
</div>

<div class="footer-note">
  RepairGraph outputs are advisory workflow intelligence. They do not certify repair
  completion, OEM compliance, or repair quality. All outputs require verification by a
  qualified technician against applicable OEM procedures.
</div>
</body>
</html>"""
