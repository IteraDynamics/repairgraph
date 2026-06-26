"""
Review Repair HTML page builder.

Generates a self-contained, vanilla HTML/CSS/JS page from a ReviewPayload.
No CDN. No external JS. No frameworks.

The page answers, within 30 seconds:
  - Can this repair proceed?
  - Why or why not?
  - What matters most?
  - What should happen next?
  - What evidence supports those conclusions?
"""
from __future__ import annotations

import json
from typing import Any

from repairgraph.review.review_payload import ReviewPayload

# ---------------------------------------------------------------------------
# Colour palette (status-driven, accessible)
# ---------------------------------------------------------------------------

_DECISION_COLORS: dict[str, dict[str, str]] = {
    "Blocked": {
        "bg": "#fef2f2",
        "border": "#ef4444",
        "badge_bg": "#ef4444",
        "badge_text": "#fff",
        "icon": "⛔",
    },
    "Proceed with Caution": {
        "bg": "#fffbeb",
        "border": "#f59e0b",
        "badge_bg": "#f59e0b",
        "badge_text": "#fff",
        "icon": "⚠️",
    },
    "Ready to Proceed": {
        "bg": "#f0fdf4",
        "border": "#22c55e",
        "badge_bg": "#22c55e",
        "badge_text": "#fff",
        "icon": "✅",
    },
    "Needs Review": {
        "bg": "#f0f9ff",
        "border": "#3b82f6",
        "badge_bg": "#3b82f6",
        "badge_text": "#fff",
        "icon": "🔍",
    },
    "Insufficient Packet": {
        "bg": "#faf5ff",
        "border": "#8b5cf6",
        "badge_bg": "#8b5cf6",
        "badge_text": "#fff",
        "icon": "📋",
    },
}

_SEVERITY_COLORS: dict[str, dict[str, str]] = {
    "critical": {"bg": "#fef2f2", "border": "#ef4444", "badge": "#ef4444", "text": "#991b1b"},
    "high": {"bg": "#fff7ed", "border": "#f97316", "badge": "#f97316", "text": "#9a3412"},
    "medium": {"bg": "#fffbeb", "border": "#f59e0b", "badge": "#f59e0b", "text": "#92400e"},
    "low": {"bg": "#f0fdf4", "border": "#22c55e", "badge": "#22c55e", "text": "#166534"},
    "informational": {"bg": "#f0f9ff", "border": "#3b82f6", "badge": "#3b82f6", "text": "#1e40af"},
}

_CONFIDENCE_BADGE: dict[str, dict[str, str]] = {
    "High": {"bg": "#dcfce7", "text": "#166534"},
    "Medium": {"bg": "#fef9c3", "text": "#854d0e"},
    "Low": {"bg": "#fee2e2", "text": "#991b1b"},
}


def _esc(s: Any) -> str:
    """Minimal HTML escaping."""
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _decision_colors(decision: str) -> dict[str, str]:
    return _DECISION_COLORS.get(decision, _DECISION_COLORS["Needs Review"])


def _severity_colors(severity: str) -> dict[str, str]:
    return _SEVERITY_COLORS.get(severity, _SEVERITY_COLORS["informational"])


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------

def _render_header(h: dict[str, Any]) -> str:
    confidence = h.get("operational_confidence", "Low")
    cb = _CONFIDENCE_BADGE.get(confidence, _CONFIDENCE_BADGE["Low"])
    readiness = _esc(h.get("readiness", ""))
    headline = _esc(h.get("summary_headline", ""))
    return f"""
<div class="rr-header">
  <div class="rr-header-top">
    <div class="rr-header-title">
      <span class="rr-label">REPAIR REVIEW</span>
      <h1>{_esc(h.get("repair_label", "Repair Review"))}</h1>
      <div class="rr-header-meta">
        {f'<span class="rr-meta-chip">{_esc(h.get("oem",""))} {_esc(h.get("year",""))} {_esc(h.get("model",""))}</span>' if h.get("oem") else ""}
        {f'<span class="rr-meta-chip">{_esc(h.get("operation",""))}</span>' if h.get("operation") else ""}
      </div>
    </div>
    <div class="rr-header-badges">
      <div class="rr-confidence-badge" style="background:{cb['bg']};color:{cb['text']};">
        Operational Confidence: <strong>{_esc(confidence)}</strong>
      </div>
      <div class="rr-readiness-chip">{_esc(readiness)}</div>
    </div>
  </div>
  {f'<p class="rr-headline">{headline}</p>' if headline else ""}
  {f'<div class="rr-next-action-bar"><span class="rr-next-label">Next Action:</span> {_esc(h.get("top_recommended_action",""))}</div>' if h.get("top_recommended_action") else ""}
</div>"""


def _render_decision(d: dict[str, Any]) -> str:
    decision = d.get("decision", "Needs Review")
    dc = _decision_colors(decision)
    reason = _esc(d.get("reason", ""))
    next_action = _esc(d.get("next_action", ""))
    top_risks = d.get("top_risks", [])
    confidence = d.get("operational_confidence", "Low")
    cb = _CONFIDENCE_BADGE.get(confidence, _CONFIDENCE_BADGE["Low"])

    risks_html = ""
    if top_risks:
        risk_items = "".join(f"<li>{_esc(r)}</li>" for r in top_risks)
        risks_html = f"<div class='rr-risks'><strong>Top Risks:</strong><ul>{risk_items}</ul></div>"

    return f"""
<section class="rr-section" id="s-decision">
  <div class="rr-decision-card" style="background:{dc['bg']};border-color:{dc['border']};">
    <div class="rr-decision-header">
      <span class="rr-decision-icon">{dc['icon']}</span>
      <div>
        <p class="rr-decision-label">Can this repair proceed?</p>
        <h2 class="rr-decision-value">{_esc(decision)}</h2>
      </div>
      <span class="rr-confidence-badge" style="background:{cb['bg']};color:{cb['text']};">
        Confidence: {_esc(confidence)}
      </span>
    </div>
    {f'<p class="rr-decision-reason"><strong>Reason:</strong> {reason}</p>' if reason else ""}
    {f'<div class="rr-next-action"><strong>Next Action:</strong> {next_action}</div>' if next_action else ""}
    {risks_html}
  </div>
</section>"""


def _render_findings(tf: dict[str, Any]) -> str:
    top = tf.get("top_findings", [])
    all_f = tf.get("all_findings", [])
    counts = tf.get("finding_counts", {})
    total = tf.get("total_count", 0)

    counts_html = ""
    if counts:
        chips = []
        for sev in ("critical", "high", "medium", "low", "informational"):
            n = counts.get(sev, 0)
            if n:
                sc = _severity_colors(sev)
                chips.append(
                    f'<span class="rr-count-chip" style="background:{sc["badge"]};color:#fff;">'
                    f'{_esc(sev.title())}: {n}</span>'
                )
        counts_html = f'<div class="rr-count-chips">{"".join(chips)}</div>'

    def render_finding(f: dict[str, Any], hidden: bool = False) -> str:
        sev = f.get("severity", "informational")
        sc = _severity_colors(sev)
        ev = f.get("supporting_evidence", [])
        ev_html = ""
        if ev:
            ev_items = "".join(f"<li>{_esc(e)}</li>" for e in ev)
            ev_html = f"<div class='rr-finding-evidence'><strong>Evidence:</strong><ul>{ev_items}</ul></div>"
        conf = f.get("confidence", "")
        conf_cb = _CONFIDENCE_BADGE.get(conf.title(), _CONFIDENCE_BADGE["Low"])
        return f"""
<div class="rr-finding-card {'rr-finding-extra' if hidden else ''}"
     style="background:{sc['bg']};border-left:4px solid {sc['border']};">
  <div class="rr-finding-header">
    <span class="rr-sev-badge" style="background:{sc['badge']};color:#fff;">{_esc(sev.upper())}</span>
    <span class="rr-cat-chip">{_esc(f.get("category","").replace("_"," ").title())}</span>
    {f'<span class="rr-conf-chip" style="background:{conf_cb["bg"]};color:{conf_cb["text"]};">Confidence: {_esc(conf.title())}</span>' if conf else ""}
  </div>
  <h4 class="rr-finding-title">{_esc(f.get("title",""))}</h4>
  <p class="rr-finding-explanation">{_esc(f.get("explanation",""))}</p>
  <div class="rr-finding-action"><strong>Recommended Action:</strong> {_esc(f.get("recommended_action",""))}</div>
  {ev_html}
</div>"""

    top_html = "".join(render_finding(f) for f in top)

    extra_html = ""
    extra_findings = all_f[5:]
    if extra_findings:
        extra_items = "".join(render_finding(f, hidden=True) for f in extra_findings)
        extra_html = f"""
<div id="extra-findings" style="display:none;">{extra_items}</div>
<button class="rr-toggle-btn" onclick="toggleFindings()">
  Show all {total} findings
</button>"""

    if not top and total == 0:
        top_html = '<p class="rr-empty">No findings recorded.</p>'

    return f"""
<section class="rr-section" id="s-findings">
  <h3 class="rr-section-title">Top Findings</h3>
  {counts_html}
  {top_html}
  {extra_html}
</section>"""


def _render_documentation(doc: dict[str, Any]) -> str:
    detected = doc.get("detected_roles", [])
    missing = doc.get("missing_roles", [])
    warnings = doc.get("extraction_warnings", [])
    filenames = doc.get("filenames", [])
    readiness = doc.get("readiness", "incomplete")
    notice = _esc(doc.get("customer_owned_content_notice", ""))

    readiness_colors = {
        "ready": "#22c55e",
        "partial": "#f59e0b",
        "incomplete": "#ef4444",
        "unprocessable": "#8b5cf6",
    }
    r_color = readiness_colors.get(readiness, "#6b7280")

    detected_html = ""
    if detected:
        items = "".join(f'<span class="rr-role-chip rr-role-detected">{_esc(r.replace("_"," ").title())}</span>' for r in detected)
        detected_html = f'<div class="rr-role-row"><strong>Detected:</strong> {items}</div>'

    missing_html = ""
    if missing:
        items = "".join(f'<span class="rr-role-chip rr-role-missing">{_esc(r.replace("_"," ").title())}</span>' for r in missing)
        missing_html = f'<div class="rr-role-row"><strong>Missing:</strong> {items}</div>'

    files_html = ""
    if filenames:
        items = "".join(f"<li>{_esc(fn)}</li>" for fn in filenames)
        files_html = f"<div class='rr-doc-files'><strong>Supplied Documents:</strong><ul>{items}</ul></div>"

    warn_html = ""
    if warnings:
        items = "".join(f"<li>{_esc(w)}</li>" for w in warnings)
        warn_html = f"<div class='rr-doc-warnings'><strong>Extraction Warnings:</strong><ul>{items}</ul></div>"

    return f"""
<section class="rr-section" id="s-documentation">
  <h3 class="rr-section-title">Required Documentation</h3>
  <div class="rr-doc-readiness">
    Packet Readiness: <span style="font-weight:700;color:{r_color};">{_esc(readiness.title())}</span>
    &nbsp;·&nbsp; {doc.get("source_count",0)} document(s) supplied
  </div>
  {files_html}
  {detected_html}
  {missing_html}
  {warn_html}
  <p class="rr-notice-text">{notice}</p>
</section>"""


def _render_workflow(wf: dict[str, Any]) -> str:
    readiness = wf.get("workflow_readiness", "unknown")
    current = wf.get("current_phase")
    blocked_phases = wf.get("blocked_phases", [])
    open_blockers = wf.get("open_blockers", [])
    next_actions = wf.get("next_actions", [])
    completed_actions = wf.get("completed_actions", [])
    qa_gates = wf.get("qa_gates", {})
    open_qa = qa_gates.get("open", [])
    passed_qa = qa_gates.get("passed", [])

    progress_pct = 0
    total = wf.get("action_count", 0)
    done = wf.get("complete_action_count", 0)
    if total:
        progress_pct = int(done / total * 100)

    current_html = ""
    if current:
        current_html = f'<div class="rr-wf-current">Current Phase: <strong>{_esc(current.get("label", current.get("name","")))}</strong></div>'

    blocker_html = ""
    if open_blockers:
        items = "".join(
            f"""<div class="rr-blocker-item rr-sev-{_esc(b.get("severity",""))}">
              <span class="rr-sev-dot rr-sev-dot-{_esc(b.get("severity",""))}"></span>
              <div>
                <strong>{_esc(b.get("type",""))}</strong>
                <p>{_esc(b.get("reason",""))}</p>
              </div>
            </div>"""
            for b in open_blockers
        )
        blocker_html = f'<div class="rr-blockers"><h4>Open Blockers ({len(open_blockers)})</h4>{items}</div>'

    next_html = ""
    if next_actions:
        items = "".join(
            f'<div class="rr-action-item rr-action-next">'
            f'<span class="rr-action-icon">→</span>'
            f'<span>{_esc(a.get("action_type",""))} — {_esc(a.get("target",""))}</span>'
            f'</div>'
            for a in next_actions
        )
        next_html = f'<div class="rr-next-actions"><h4>Next Recommended Actions</h4>{items}</div>'

    completed_html = ""
    if completed_actions:
        items = "".join(
            f'<div class="rr-action-item rr-action-done">✓ {_esc(a.get("action_type",""))} — {_esc(a.get("target",""))}</div>'
            for a in completed_actions[:5]
        )
        more = f'<p class="rr-more-text">+ {len(completed_actions)-5} more completed</p>' if len(completed_actions) > 5 else ""
        completed_html = f'<details class="rr-details"><summary>Completed Actions ({len(completed_actions)})</summary>{items}{more}</details>'

    qa_html = ""
    if open_qa or passed_qa:
        open_items = "".join(
            f'<div class="rr-qa-item rr-qa-open">⚠ {_esc(g.get("check",""))} <span class="rr-qa-cat">{_esc(g.get("category",""))}</span></div>'
            for g in open_qa
        )
        passed_items = "".join(
            f'<div class="rr-qa-item rr-qa-passed">✓ {_esc(g.get("check",""))}</div>'
            for g in passed_qa
        )
        qa_html = f"""
<div class="rr-qa-block">
  <h4>QA Gates — {len(open_qa)} open / {len(passed_qa)} passed</h4>
  {open_items}{passed_items}
</div>"""

    return f"""
<section class="rr-section" id="s-workflow">
  <h3 class="rr-section-title">Workflow Readiness</h3>
  <div class="rr-progress-bar-wrap">
    <div class="rr-progress-bar" style="width:{progress_pct}%;"></div>
  </div>
  <p class="rr-progress-label">{done} of {total} actions complete ({progress_pct}%)</p>
  {current_html}
  {blocker_html}
  {next_html}
  {completed_html}
  {qa_html}
</section>"""


def _render_material_risk(mr: dict[str, Any]) -> str:
    if not mr.get("has_material_risk") and not mr.get("joining_verification_required") and not mr.get("corrosion_protection_required") and not mr.get("calibration_check_required"):
        return ""

    uhss = mr.get("uhss_zones", [])
    hss = mr.get("hss_zones", [])
    joining_req = mr.get("joining_requirements", [])
    corrosion_req = mr.get("corrosion_requirements", [])

    uhss_html = ""
    if uhss:
        items = "".join(f'<span class="rr-zone-chip rr-zone-uhss">{_esc(z)}</span>' for z in uhss)
        uhss_html = f'<div class="rr-material-row"><strong>UHSS Zones:</strong> {items}</div>'

    hss_html = ""
    if hss:
        items = "".join(f'<span class="rr-zone-chip rr-zone-hss">{_esc(z)}</span>' for z in hss)
        hss_html = f'<div class="rr-material-row"><strong>HSS Zones:</strong> {items}</div>'

    joining_html = ""
    if mr.get("joining_verification_required"):
        req_items = "".join(f"<li>{_esc(r)}</li>" for r in joining_req) if joining_req else ""
        joining_html = f'<div class="rr-material-flag">⚠ Joining method verification required{f"<ul>{req_items}</ul>" if req_items else ""}</div>'

    corrosion_html = ""
    if mr.get("corrosion_protection_required"):
        req_items = "".join(f"<li>{_esc(r)}</li>" for r in corrosion_req) if corrosion_req else ""
        corrosion_html = f'<div class="rr-material-flag">⚠ Corrosion protection required{f"<ul>{req_items}</ul>" if req_items else ""}</div>'

    calibration_html = ""
    if mr.get("calibration_check_required"):
        calibration_html = '<div class="rr-material-flag">⚠ Calibration assessment required</div>'

    return f"""
<section class="rr-section" id="s-material">
  <h3 class="rr-section-title">Material &amp; Structural Risk</h3>
  {uhss_html}
  {hss_html}
  {joining_html}
  {corrosion_html}
  {calibration_html}
</section>"""


def _render_evidence(ev: dict[str, Any]) -> str:
    items = ev.get("evidence_items", [])
    finding_ev = ev.get("finding_evidence", [])
    conf = ev.get("confidence_by_category", {})
    total = ev.get("total_evidence_count", 0)
    oem_req = ev.get("requires_oem_verification", True)
    filenames = ev.get("source_filenames", [])

    conf_html = ""
    if conf:
        chips = "".join(
            f'<span class="rr-ev-conf-chip">{_esc(cat)}: {int(v*100)}%</span>'
            for cat, v in conf.items()
        )
        conf_html = f'<div class="rr-ev-conf">{chips}</div>'

    finding_html = ""
    if finding_ev:
        sections = []
        for fe in finding_ev:
            ev_list = "".join(f"<li>{_esc(e)}</li>" for e in fe.get("evidence", []))
            sections.append(f'<div class="rr-ev-finding"><strong>{_esc(fe.get("title",""))}</strong><ul>{ev_list}</ul></div>')
        finding_html = f'<div class="rr-ev-findings">{"".join(sections)}</div>'

    files_html = ""
    if filenames:
        items_html = "".join(f"<li>{_esc(fn)}</li>" for fn in filenames)
        files_html = f"<div class='rr-ev-files'><strong>Source Documents:</strong><ul>{items_html}</ul></div>"

    oem_html = ""
    if oem_req:
        oem_html = '<p class="rr-ev-oem-notice">⚠ OEM procedure verification required before proceeding.</p>'

    return f"""
<details class="rr-section rr-ev-section" id="s-evidence">
  <summary><h3 class="rr-section-title rr-inline-title">Evidence Trail ({total} items)</h3></summary>
  {conf_html}
  {finding_html}
  {files_html}
  {oem_html}
</details>"""


def _render_actions(links: dict[str, str]) -> str:
    button_defs = [
        ("operational_model", "Open Operational Model"),
        ("topology_viewer", "Open Topology Viewer"),
        ("repair_audit_trail", "Open Repair Audit Trail"),
        ("technician_workflow", "Open Technician Workflow"),
        ("oem_intake", "Open OEM Intake Analysis"),
        ("executive_summary", "Export Executive Summary"),
    ]
    buttons = ""
    for key, label in button_defs:
        href = links.get(key, "#")
        buttons += f'<a class="rr-action-btn" href="{_esc(href)}" target="_blank">{_esc(label)}</a>\n'

    return f"""
<section class="rr-section rr-actions-section" id="s-actions">
  <h3 class="rr-section-title">Actions &amp; Exports</h3>
  <div class="rr-action-buttons">{buttons}</div>
</section>"""


def _render_legal() -> str:
    return """
<footer class="rr-footer">
  <p class="rr-legal">
    RepairGraph works with repair information supplied by the shop.
    It does not replace OEM procedures or distribute licensed repair data.
    All outputs are advisory and require qualified technician review against OEM procedures.
  </p>
</footer>"""


# ---------------------------------------------------------------------------
# CSS
# ---------------------------------------------------------------------------

_CSS = """
*, *::before, *::after { box-sizing: border-box; margin: 0; padding: 0; }
body {
  font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif;
  background: #f8fafc;
  color: #1e293b;
  line-height: 1.5;
}
.rr-page { max-width: 900px; margin: 0 auto; padding: 24px 16px 48px; }

/* Header */
.rr-header { background: #1e293b; color: #fff; border-radius: 12px; padding: 28px 32px; margin-bottom: 20px; }
.rr-header-top { display: flex; justify-content: space-between; align-items: flex-start; gap: 20px; flex-wrap: wrap; }
.rr-label { font-size: 11px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; color: #94a3b8; }
.rr-header h1 { font-size: 26px; font-weight: 700; margin: 6px 0 8px; color: #f1f5f9; }
.rr-header-meta { display: flex; gap: 8px; flex-wrap: wrap; }
.rr-meta-chip { background: #334155; color: #cbd5e1; font-size: 13px; padding: 3px 10px; border-radius: 20px; }
.rr-header-badges { display: flex; flex-direction: column; gap: 8px; align-items: flex-end; }
.rr-confidence-badge { font-size: 13px; padding: 6px 14px; border-radius: 20px; white-space: nowrap; }
.rr-readiness-chip { font-size: 13px; color: #94a3b8; white-space: nowrap; }
.rr-headline { color: #94a3b8; font-size: 14px; margin-top: 14px; }
.rr-next-action-bar { margin-top: 14px; background: #0f172a; border-left: 3px solid #3b82f6; padding: 10px 16px; border-radius: 0 8px 8px 0; font-size: 14px; color: #e2e8f0; }
.rr-next-label { font-weight: 700; color: #60a5fa; margin-right: 6px; }

/* Nav */
.rr-nav { display: flex; gap: 8px; margin-bottom: 20px; flex-wrap: wrap; }
.rr-nav a { font-size: 13px; padding: 6px 14px; background: #fff; border: 1px solid #e2e8f0; border-radius: 20px; text-decoration: none; color: #475569; transition: all .15s; }
.rr-nav a:hover { background: #1e293b; color: #fff; border-color: #1e293b; }

/* Sections */
.rr-section { background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 24px 28px; margin-bottom: 16px; }
.rr-section-title { font-size: 16px; font-weight: 700; color: #1e293b; margin-bottom: 16px; }
.rr-inline-title { display: inline; font-size: 15px; }
.rr-empty { color: #94a3b8; font-size: 14px; }

/* Decision card */
.rr-decision-card { border: 2px solid; border-radius: 12px; padding: 24px; }
.rr-decision-header { display: flex; align-items: center; gap: 16px; margin-bottom: 16px; flex-wrap: wrap; }
.rr-decision-icon { font-size: 36px; }
.rr-decision-label { font-size: 12px; font-weight: 600; text-transform: uppercase; letter-spacing: 1px; color: #64748b; }
.rr-decision-value { font-size: 28px; font-weight: 800; color: #1e293b; }
.rr-decision-reason { font-size: 15px; color: #374151; margin-bottom: 12px; }
.rr-next-action { background: #f0f9ff; border-left: 3px solid #3b82f6; padding: 10px 14px; border-radius: 0 8px 8px 0; font-size: 14px; margin-bottom: 12px; }
.rr-risks { font-size: 14px; }
.rr-risks ul { padding-left: 20px; margin-top: 6px; }
.rr-risks li { margin-bottom: 4px; color: #374151; }

/* Count chips */
.rr-count-chips { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 16px; }
.rr-count-chip { font-size: 12px; padding: 3px 10px; border-radius: 20px; font-weight: 600; }

/* Finding cards */
.rr-finding-card { border-radius: 8px; padding: 16px; margin-bottom: 12px; }
.rr-finding-header { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; flex-wrap: wrap; }
.rr-sev-badge { font-size: 11px; font-weight: 700; padding: 2px 8px; border-radius: 4px; }
.rr-cat-chip { font-size: 12px; color: #64748b; background: rgba(0,0,0,.06); padding: 2px 8px; border-radius: 4px; }
.rr-conf-chip { font-size: 12px; padding: 2px 8px; border-radius: 4px; }
.rr-finding-title { font-size: 15px; font-weight: 700; margin-bottom: 6px; }
.rr-finding-explanation { font-size: 14px; color: #374151; margin-bottom: 8px; }
.rr-finding-action { font-size: 13px; color: #1e40af; background: #eff6ff; padding: 8px 12px; border-radius: 6px; margin-bottom: 8px; }
.rr-finding-evidence { font-size: 13px; color: #475569; }
.rr-finding-evidence ul { padding-left: 18px; margin-top: 4px; }
.rr-toggle-btn { margin-top: 8px; padding: 8px 18px; border: 1px solid #3b82f6; color: #3b82f6; background: #fff; border-radius: 8px; cursor: pointer; font-size: 14px; }
.rr-toggle-btn:hover { background: #eff6ff; }

/* Documentation */
.rr-doc-readiness { font-size: 14px; margin-bottom: 12px; }
.rr-role-row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 10px; font-size: 14px; }
.rr-role-chip { font-size: 12px; padding: 3px 10px; border-radius: 20px; }
.rr-role-detected { background: #dcfce7; color: #166534; }
.rr-role-missing { background: #fee2e2; color: #991b1b; }
.rr-doc-files ul, .rr-doc-warnings ul { padding-left: 18px; margin-top: 4px; font-size: 13px; }
.rr-doc-files { font-size: 14px; margin-bottom: 10px; }
.rr-doc-warnings { font-size: 13px; color: #92400e; background: #fffbeb; padding: 10px 14px; border-radius: 6px; margin-bottom: 10px; }
.rr-notice-text { font-size: 12px; color: #64748b; margin-top: 10px; font-style: italic; }

/* Workflow */
.rr-progress-bar-wrap { height: 8px; background: #e2e8f0; border-radius: 99px; overflow: hidden; margin-bottom: 6px; }
.rr-progress-bar { height: 100%; background: #22c55e; border-radius: 99px; transition: width .3s; }
.rr-progress-label { font-size: 13px; color: #64748b; margin-bottom: 16px; }
.rr-wf-current { font-size: 14px; margin-bottom: 12px; }
.rr-blockers h4, .rr-next-actions h4, .rr-qa-block h4 { font-size: 14px; font-weight: 700; margin-bottom: 10px; }
.rr-blocker-item { display: flex; gap: 12px; align-items: flex-start; padding: 10px 12px; background: #fef2f2; border-radius: 8px; margin-bottom: 8px; font-size: 14px; }
.rr-blocker-item p { color: #374151; margin-top: 2px; font-size: 13px; }
.rr-sev-dot { width: 10px; height: 10px; border-radius: 50%; flex-shrink: 0; margin-top: 5px; }
.rr-sev-dot-critical { background: #ef4444; }
.rr-sev-dot-high { background: #f97316; }
.rr-sev-dot-medium { background: #f59e0b; }
.rr-sev-dot-low { background: #22c55e; }
.rr-action-item { font-size: 14px; padding: 8px 12px; border-radius: 6px; margin-bottom: 6px; }
.rr-action-next { background: #eff6ff; color: #1e40af; }
.rr-action-done { background: #f0fdf4; color: #166534; }
.rr-action-icon { margin-right: 8px; font-weight: 700; }
.rr-details summary { cursor: pointer; font-size: 14px; font-weight: 600; padding: 8px 0; color: #475569; }
.rr-more-text { font-size: 13px; color: #64748b; padding: 4px 12px; }
.rr-qa-item { font-size: 13px; padding: 6px 10px; border-radius: 6px; margin-bottom: 4px; }
.rr-qa-open { background: #fffbeb; color: #92400e; }
.rr-qa-passed { background: #f0fdf4; color: #166534; }
.rr-qa-cat { font-size: 11px; color: #64748b; margin-left: 8px; }
.rr-qa-block { margin-top: 14px; }
.rr-blockers { margin-bottom: 14px; }
.rr-next-actions { margin-bottom: 14px; }

/* Material risk */
.rr-material-row { display: flex; gap: 8px; align-items: center; flex-wrap: wrap; margin-bottom: 10px; font-size: 14px; }
.rr-zone-chip { font-size: 12px; padding: 3px 10px; border-radius: 20px; }
.rr-zone-uhss { background: #fef2f2; color: #991b1b; border: 1px solid #fca5a5; }
.rr-zone-hss { background: #fff7ed; color: #9a3412; border: 1px solid #fdba74; }
.rr-material-flag { font-size: 14px; color: #92400e; background: #fffbeb; padding: 10px 14px; border-radius: 6px; margin-bottom: 8px; }
.rr-material-flag ul { padding-left: 18px; margin-top: 4px; font-size: 13px; }

/* Evidence */
.rr-ev-section summary { cursor: pointer; list-style: none; }
.rr-ev-section summary::-webkit-details-marker { display: none; }
.rr-ev-section[open] summary { margin-bottom: 16px; }
.rr-ev-conf { display: flex; gap: 8px; flex-wrap: wrap; margin-bottom: 14px; }
.rr-ev-conf-chip { font-size: 12px; background: #f1f5f9; color: #475569; padding: 3px 10px; border-radius: 20px; }
.rr-ev-finding { font-size: 14px; margin-bottom: 10px; }
.rr-ev-finding ul { padding-left: 18px; margin-top: 4px; font-size: 13px; color: #475569; }
.rr-ev-findings { margin-bottom: 14px; }
.rr-ev-files { font-size: 13px; margin-bottom: 10px; }
.rr-ev-files ul { padding-left: 18px; margin-top: 4px; }
.rr-ev-oem-notice { font-size: 13px; color: #92400e; background: #fffbeb; padding: 8px 12px; border-radius: 6px; }

/* Actions */
.rr-actions-section { background: #f8fafc; }
.rr-action-buttons { display: flex; gap: 10px; flex-wrap: wrap; }
.rr-action-btn { display: inline-block; padding: 10px 18px; background: #1e293b; color: #fff; border-radius: 8px; text-decoration: none; font-size: 14px; font-weight: 500; transition: background .15s; }
.rr-action-btn:hover { background: #0f172a; }

/* Footer */
.rr-footer { margin-top: 32px; padding: 20px 0; border-top: 1px solid #e2e8f0; }
.rr-legal { font-size: 12px; color: #94a3b8; text-align: center; max-width: 700px; margin: 0 auto; }
"""

_JS = """
function toggleFindings() {
  var el = document.getElementById('extra-findings');
  var btn = event.target;
  if (el.style.display === 'none') {
    el.style.display = 'block';
    btn.textContent = 'Show fewer findings';
  } else {
    el.style.display = 'none';
    btn.textContent = btn.dataset.originalText;
  }
}
document.addEventListener('DOMContentLoaded', function() {
  var btn = document.querySelector('.rr-toggle-btn');
  if (btn) btn.dataset.originalText = btn.textContent;
});
"""


# ---------------------------------------------------------------------------
# Main page builder
# ---------------------------------------------------------------------------

def build_review_page_html(payload: ReviewPayload) -> str:
    """Return a self-contained HTML page for the Review Repair experience."""
    p = payload.to_dict()
    h = p.get("header", {})
    decision = p.get("decision", {})

    nav_links = [
        ("#s-decision", "Decision"),
        ("#s-findings", "Findings"),
        ("#s-documentation", "Documentation"),
        ("#s-workflow", "Workflow"),
        ("#s-material", "Material Risk"),
        ("#s-evidence", "Evidence"),
        ("#s-actions", "Actions"),
    ]
    nav_html = '<nav class="rr-nav">' + "".join(
        f'<a href="{_esc(href)}">{_esc(label)}</a>' for href, label in nav_links
    ) + "</nav>"

    mat_html = _render_material_risk(p.get("material_risk", {}))

    # Embed payload as JSON for future JS use (optional, no external requests needed)
    payload_json = json.dumps(p, ensure_ascii=False, indent=None)

    title = _esc(h.get("repair_label", "Repair Review"))
    return f"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<title>Repair Review — {title}</title>
<style>{_CSS}</style>
</head>
<body>
<div class="rr-page">
  {_render_header(h)}
  {nav_html}
  {_render_decision(decision)}
  {_render_findings(p.get("top_findings", {}))}
  {_render_documentation(p.get("documentation", {}))}
  {_render_workflow(p.get("workflow_readiness", {}))}
  {mat_html if mat_html.strip() else ""}
  {_render_evidence(p.get("evidence_trail", {}))}
  {_render_actions(p.get("export_links", {}))}
  {_render_legal()}
</div>
<script type="application/json" id="rr-payload">{payload_json}</script>
<script>{_JS}</script>
</body>
</html>"""
