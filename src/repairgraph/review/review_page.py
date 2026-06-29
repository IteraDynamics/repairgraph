"""
Review Repair HTML page builder.

Generates a self-contained, vanilla HTML/CSS/JS page from a ReviewPayload.
No CDN. No external JS. No frameworks.

The page answers within ten seconds:
  - Can this repair proceed?           (large hero status)
  - Why or why not?                    (primary problem + executive summary)
  - What to do right now?              (immediate actions, max 3)
  - Who does what?                     (technician + manager callouts)
  - Why was this decision made?        (top findings)
  - What can wait?                     (upcoming work, secondary)
  - What evidence supports this?       (evidence trail, collapsible)
"""
from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any

import re

from repairgraph.review.review_payload import ReviewPayload

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_LABEL_ACRONYMS: frozenset[str] = frozenset({"qa", "oem", "uhss", "hss", "mig", "mag", "vin"})


def _format_display_label(s: str) -> str:
    """Format internal snake_case identifiers for display, handling acronyms."""
    parts = re.split(r"[_\-]", s)
    out = []
    for p in parts:
        if not p:
            continue
        if p.lower() in _LABEL_ACRONYMS:
            out.append(p.upper())
        else:
            out.append(p.title())
    return " ".join(out)


def _strip_ids(text: str) -> str:
    """Remove internal gate/action IDs from user-facing text."""
    text = re.sub(r"\bqa:[a-z_]+:[a-z]+:\d+\b\.?\s*", "", text)
    text = re.sub(r"^QA gate remains open:\s*", "", text)
    text = re.sub(r"^Resolve QA gate [^\s.]+\.\s*(?:Check:\s*)?", "", text)
    return text.strip()


# ---------------------------------------------------------------------------
# Colour palette
# ---------------------------------------------------------------------------

_HERO_COLORS: dict[str, dict[str, str]] = {
    "BLOCKED": {
        "bg": "#fef2f2",
        "border": "#ef4444",
        "hero_bg": "#ef4444",
        "hero_text": "#fff",
        "icon": "⛔",
        "print_color": "#dc2626",
    },
    "PROCEED WITH CAUTION": {
        "bg": "#fffbeb",
        "border": "#f59e0b",
        "hero_bg": "#f59e0b",
        "hero_text": "#fff",
        "icon": "⚠",
        "print_color": "#d97706",
    },
    "READY": {
        "bg": "#f0fdf4",
        "border": "#22c55e",
        "hero_bg": "#22c55e",
        "hero_text": "#fff",
        "icon": "✓",
        "print_color": "#16a34a",
    },
    "INSUFFICIENT INFORMATION": {
        "bg": "#faf5ff",
        "border": "#8b5cf6",
        "hero_bg": "#8b5cf6",
        "hero_text": "#fff",
        "icon": "?",
        "print_color": "#7c3aed",
    },
    "NEEDS REVIEW": {
        "bg": "#f0f9ff",
        "border": "#3b82f6",
        "hero_bg": "#3b82f6",
        "hero_text": "#fff",
        "icon": "🔍",
        "print_color": "#2563eb",
    },
    # Legacy decision values (ReviewPayload.decision.decision) kept for nav/data
    "Blocked": {
        "bg": "#fef2f2",
        "border": "#ef4444",
        "hero_bg": "#ef4444",
        "hero_text": "#fff",
        "icon": "⛔",
        "print_color": "#dc2626",
    },
    "Proceed with Caution": {
        "bg": "#fffbeb",
        "border": "#f59e0b",
        "hero_bg": "#f59e0b",
        "hero_text": "#fff",
        "icon": "⚠",
        "print_color": "#d97706",
    },
    "Ready to Proceed": {
        "bg": "#f0fdf4",
        "border": "#22c55e",
        "hero_bg": "#22c55e",
        "hero_text": "#fff",
        "icon": "✓",
        "print_color": "#16a34a",
    },
    "Needs Review": {
        "bg": "#f0f9ff",
        "border": "#3b82f6",
        "hero_bg": "#3b82f6",
        "hero_text": "#fff",
        "icon": "🔍",
        "print_color": "#2563eb",
    },
    "Insufficient Packet": {
        "bg": "#faf5ff",
        "border": "#8b5cf6",
        "hero_bg": "#8b5cf6",
        "hero_text": "#fff",
        "icon": "?",
        "print_color": "#7c3aed",
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
    return str(s).replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


def _hero_colors(decision: str) -> dict[str, str]:
    return _HERO_COLORS.get(decision, _HERO_COLORS["Needs Review"])


def _severity_colors(severity: str) -> dict[str, str]:
    return _SEVERITY_COLORS.get(severity, _SEVERITY_COLORS["informational"])


# ---------------------------------------------------------------------------
# Section renderers
# ---------------------------------------------------------------------------

def _render_page_header(h: dict[str, Any], er: dict[str, Any]) -> str:
    """Top header bar — vehicle, operation, print button."""
    oem_chip = ""
    if h.get("oem"):
        oem_chip = (
            f'<span class="rr-meta-chip">'
            f'{_esc(h.get("oem",""))} {_esc(h.get("year",""))} {_esc(h.get("model",""))}'
            f'</span>'
        )
    op_chip = ""
    if h.get("operation"):
        op_chip = f'<span class="rr-meta-chip">{_esc(h.get("operation",""))}</span>'

    return f"""
<div class="rr-header">
  <div class="rr-header-top">
    <div class="rr-header-title">
      <span class="rr-label">REPAIR REVIEW</span>
      <h1>{_esc(h.get("repair_label", "Repair Review"))}</h1>
      <div class="rr-header-meta">{oem_chip}{op_chip}</div>
    </div>
    <div class="rr-header-actions">
      <button class="rr-print-btn" onclick="window.print()">Print Review Summary</button>
    </div>
  </div>
</div>"""


def _render_hero(er: dict[str, Any]) -> str:
    """Large visual status — the first thing a production manager sees."""
    decision = er.get("overall_decision", "INSUFFICIENT INFORMATION")
    dc = _hero_colors(decision)
    primary_problem = _esc(er.get("primary_problem", ""))

    return f"""
<section class="rr-hero" id="s-status" style="background:{dc['bg']};border-color:{dc['border']};">
  <div class="rr-hero-badge" style="background:{dc['hero_bg']};color:{dc['hero_text']};">
    <span class="rr-hero-icon">{dc['icon']}</span>
    <span class="rr-hero-label">{_esc(decision)}</span>
  </div>
  {f'<p class="rr-hero-problem">{primary_problem}</p>' if primary_problem else ""}
</section>"""


def _render_executive_summary(er: dict[str, Any]) -> str:
    summary = _esc(er.get("executive_summary", ""))
    if not summary:
        return ""
    return f"""
<section class="rr-section" id="s-summary">
  <h3 class="rr-section-title">Summary</h3>
  <p class="rr-exec-summary">{summary}</p>
</section>"""


def _render_immediate_actions(er: dict[str, Any]) -> str:
    actions = er.get("immediate_actions", [])
    if not actions:
        return ""

    items = ""
    for i, action in enumerate(actions, 1):
        items += f"""
<div class="rr-action-immediate">
  <span class="rr-action-num">{i}</span>
  <span class="rr-action-text">{_esc(action)}</span>
</div>"""

    deferred = er.get("deferred_actions", [])
    deferred_html = ""
    if deferred:
        deferred_items = "".join(
            f'<div class="rr-deferred-item">→ {_esc(a)}</div>' for a in deferred[:8]
        )
        more = f'<p class="rr-more-text">+ {len(deferred)-8} more items</p>' if len(deferred) > 8 else ""
        deferred_html = f"""
<details class="rr-upcoming-detail">
  <summary class="rr-upcoming-summary">Upcoming Work ({len(deferred)} items)</summary>
  <div class="rr-deferred-list">{deferred_items}{more}</div>
</details>"""

    return f"""
<section class="rr-section" id="s-actions">
  <h3 class="rr-section-title">Immediate Actions</h3>
  <div class="rr-actions-list">{items}</div>
  {deferred_html}
</section>"""


def _render_people_callouts(er: dict[str, Any]) -> str:
    tech = _esc(er.get("technician_message", ""))
    mgr = _esc(er.get("manager_message", ""))
    if not tech and not mgr:
        return ""

    tech_html = ""
    if tech:
        tech_html = f"""
<div class="rr-callout rr-callout-tech">
  <div class="rr-callout-label">Technician</div>
  <p class="rr-callout-q">What should I do next?</p>
  <p class="rr-callout-msg">{tech}</p>
</div>"""

    mgr_html = ""
    if mgr:
        mgr_html = f"""
<div class="rr-callout rr-callout-mgr">
  <div class="rr-callout-label">Manager</div>
  <p class="rr-callout-q">What should I verify before releasing this job?</p>
  <p class="rr-callout-msg">{mgr}</p>
</div>"""

    return f"""
<section class="rr-section" id="s-people">
  <h3 class="rr-section-title">For Your Team</h3>
  <div class="rr-callout-row">{tech_html}{mgr_html}</div>
</section>"""


def _render_confidence(er: dict[str, Any]) -> str:
    conf = er.get("confidence", {})
    ev_conf = conf.get("evidence_confidence", "Low")
    ev_reason = _esc(conf.get("evidence_confidence_reason", ""))
    dec_conf = conf.get("decision_confidence", "Low")
    dec_reason = _esc(conf.get("decision_confidence_reason", ""))

    ev_cb = _CONFIDENCE_BADGE.get(ev_conf, _CONFIDENCE_BADGE["Low"])
    dec_cb = _CONFIDENCE_BADGE.get(dec_conf, _CONFIDENCE_BADGE["Low"])

    return f"""
<section class="rr-section" id="s-confidence">
  <h3 class="rr-section-title">Confidence</h3>
  <div class="rr-conf-row">
    <div class="rr-conf-block">
      <div class="rr-conf-pill" style="background:{ev_cb['bg']};color:{ev_cb['text']};">
        Evidence Confidence: <strong>{_esc(ev_conf)}</strong>
      </div>
      <p class="rr-conf-reason">{ev_reason}</p>
    </div>
    <div class="rr-conf-block">
      <div class="rr-conf-pill" style="background:{dec_cb['bg']};color:{dec_cb['text']};">
        Decision Confidence: <strong>{_esc(dec_conf)}</strong>
      </div>
      <p class="rr-conf-reason">{dec_reason}</p>
    </div>
  </div>
</section>"""


def _render_decision_rationale(er: dict[str, Any]) -> str:
    """Why This Decision Was Made — max 5 findings, rest collapsed."""
    top = er.get("decision_rationale", [])
    extra = er.get("decision_rationale_extra", [])

    if not top and not extra:
        return ""

    def _finding_card(f: dict[str, Any]) -> str:
        sev = f.get("severity", "informational")
        sc = _severity_colors(sev)
        ev = f.get("supporting_evidence", [])
        ev_html = ""
        if ev:
            _id_pat = re.compile(r"qa:[a-z_]+:[a-z]+:\d+")
            clean_ev = [e for e in ev if not _id_pat.search(str(e)) and not str(e).startswith("gate_id=") and not str(e).startswith("status=") and not str(e).startswith("category=")]
            if clean_ev:
                ev_items = "".join(f"<li>{_esc(e)}</li>" for e in clean_ev)
                ev_html = f"<div class='rr-finding-evidence'><ul>{ev_items}</ul></div>"
        return f"""
<div class="rr-finding-card" style="background:{sc['bg']};border-left:4px solid {sc['border']};">
  <div class="rr-finding-header">
    <span class="rr-sev-badge" style="background:{sc['badge']};color:#fff;">{_esc(sev.upper())}</span>
    <span class="rr-cat-chip">{_esc(_format_display_label(f.get("category","")))}</span>
  </div>
  <h4 class="rr-finding-title">{_esc(f.get("title",""))}</h4>
  <p class="rr-finding-explanation">{_esc(_strip_ids(f.get("explanation","")))}</p>
  <div class="rr-finding-action">{_esc(_strip_ids(f.get("recommended_action","")))}</div>
  {ev_html}
</div>"""

    top_html = "".join(_finding_card(f) for f in top)

    extra_html = ""
    if extra:
        extra_cards = "".join(_finding_card(f) for f in extra)
        extra_html = f"""
<details class="rr-extra-findings">
  <summary>More observations ({len(extra)})</summary>
  {extra_cards}
</details>"""

    return f"""
<section class="rr-section" id="s-rationale">
  <h3 class="rr-section-title">Why This Decision Was Made</h3>
  {top_html}
  {extra_html}
</section>"""


def _render_structural_considerations(mr: dict[str, Any]) -> str:
    """Structural Considerations — renamed from Material & Structural Risk."""
    if (
        not mr.get("has_material_risk")
        and not mr.get("joining_verification_required")
        and not mr.get("corrosion_protection_required")
        and not mr.get("calibration_check_required")
    ):
        return ""

    uhss = mr.get("uhss_zones", [])
    hss = mr.get("hss_zones", [])
    joining_req = mr.get("joining_requirements", [])
    corrosion_req = mr.get("corrosion_requirements", [])

    uhss_html = ""
    if uhss:
        items = "".join(f'<span class="rr-zone-chip rr-zone-uhss">{_esc(z)}</span>' for z in uhss)
        uhss_html = f'<div class="rr-material-row"><strong>Ultra-High-Strength Steel Zones:</strong> {items}</div>'

    hss_html = ""
    if hss:
        items = "".join(f'<span class="rr-zone-chip rr-zone-hss">{_esc(z)}</span>' for z in hss)
        hss_html = f'<div class="rr-material-row"><strong>High-Strength Steel Zones:</strong> {items}</div>'

    joining_html = ""
    if mr.get("joining_verification_required"):
        req_items = "".join(f"<li>{_esc(r)}</li>" for r in joining_req) if joining_req else ""
        joining_html = (
            f'<div class="rr-material-flag">OEM joining method verification is required'
            f'{f"<ul>{req_items}</ul>" if req_items else ""}'
            f'</div>'
        )

    corrosion_html = ""
    if mr.get("corrosion_protection_required"):
        req_items = "".join(f"<li>{_esc(r)}</li>" for r in corrosion_req) if corrosion_req else ""
        corrosion_html = (
            f'<div class="rr-material-flag">Corrosion protection is required'
            f'{f"<ul>{req_items}</ul>" if req_items else ""}'
            f'</div>'
        )

    calibration_html = ""
    if mr.get("calibration_check_required"):
        calibration_html = '<div class="rr-material-flag">Post-repair calibration assessment is required</div>'

    return f"""
<section class="rr-section" id="s-structural">
  <h3 class="rr-section-title">Structural Considerations</h3>
  {uhss_html}
  {hss_html}
  {joining_html}
  {corrosion_html}
  {calibration_html}
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
        items = "".join(
            f'<span class="rr-role-chip rr-role-detected">{_esc(_format_display_label(r))}</span>'
            for r in detected
        )
        detected_html = f'<div class="rr-role-row"><strong>Supplied:</strong> {items}</div>'

    missing_html = ""
    if missing:
        items = "".join(
            f'<span class="rr-role-chip rr-role-missing">{_esc(_format_display_label(r))}</span>'
            for r in missing
        )
        missing_html = f'<div class="rr-role-row"><strong>Missing:</strong> {items}</div>'

    files_html = ""
    if filenames:
        items = "".join(f"<li>{_esc(fn)}</li>" for fn in filenames)
        files_html = f"<div class='rr-doc-files'><strong>Supplied Documents:</strong><ul>{items}</ul></div>"

    warn_html = ""
    if warnings:
        items = "".join(f"<li>{_esc(w)}</li>" for w in warnings)
        warn_html = f"<div class='rr-doc-warnings'><strong>Warnings:</strong><ul>{items}</ul></div>"

    return f"""
<section class="rr-section" id="s-documentation">
  <h3 class="rr-section-title">Repair Packet</h3>
  <div class="rr-doc-readiness">
    Packet status: <span style="font-weight:700;color:{r_color};">{_esc(readiness.title())}</span>
    &nbsp;·&nbsp; {doc.get("source_count",0)} document(s)
  </div>
  {files_html}
  {detected_html}
  {missing_html}
  {warn_html}
  <p class="rr-notice-text">{notice}</p>
</section>"""


def _render_evidence(ev: dict[str, Any]) -> str:
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

    files_html = ""
    if filenames:
        items_html = "".join(f"<li>{_esc(fn)}</li>" for fn in filenames)
        files_html = f"<div class='rr-ev-files'><strong>Source Documents:</strong><ul>{items_html}</ul></div>"

    oem_html = ""
    if oem_req:
        oem_html = '<p class="rr-ev-oem-notice">OEM procedure verification is required before proceeding.</p>'

    return f"""
<details class="rr-section rr-ev-section" id="s-evidence">
  <summary><h3 class="rr-section-title rr-inline-title">Evidence Trail ({total} items)</h3></summary>
  {conf_html}
  {files_html}
  {oem_html}
</details>"""


def _render_workflow_secondary(wf: dict[str, Any]) -> str:
    """Secondary workflow section — collapsible, for completeness."""
    readiness = wf.get("workflow_readiness", "unknown")
    done = wf.get("complete_action_count", 0)
    total = wf.get("action_count", 0)
    progress_pct = int(done / total * 100) if total else 0
    open_blockers = wf.get("open_blockers", [])
    qa_gates = wf.get("qa_gates", {})
    open_qa = qa_gates.get("open", [])
    passed_qa = qa_gates.get("passed", [])
    completed_actions = wf.get("completed_actions", [])

    blocker_html = ""
    if open_blockers:
        items = "".join(
            f'<div class="rr-blocker-item">'
            f'<span class="rr-sev-dot rr-sev-dot-{_esc(b.get("severity",""))}"></span>'
            f'<span>{_esc(_strip_ids(b.get("reason","")))}</span>'
            f'</div>'
            for b in open_blockers
        )
        blocker_html = f'<div class="rr-blockers"><strong>Open Issues ({len(open_blockers)}):</strong>{items}</div>'

    qa_html = ""
    if open_qa or passed_qa:
        open_items = "".join(
            f'<div class="rr-qa-item rr-qa-open">⚠ {_esc(_strip_ids(g.get("check","")))} '
            f'<span class="rr-qa-cat">{_esc(_format_display_label(g.get("category","")))}</span></div>'
            for g in open_qa
        )
        passed_items = "".join(
            f'<div class="rr-qa-item rr-qa-passed">✓ {_esc(g.get("check",""))}</div>'
            for g in passed_qa
        )
        qa_html = f'<div class="rr-qa-block"><strong>QA Gates — {len(open_qa)} open / {len(passed_qa)} passed</strong>{open_items}{passed_items}</div>'

    completed_html = ""
    if completed_actions:
        items = "".join(
            f'<div class="rr-action-item rr-action-done">✓ {_esc(a.get("action_type",""))} — {_esc(a.get("target",""))}</div>'
            for a in completed_actions[:5]
        )
        more = f'<p class="rr-more-text">+ {len(completed_actions)-5} more</p>' if len(completed_actions) > 5 else ""
        completed_html = f'<details class="rr-details"><summary>Completed Actions ({len(completed_actions)})</summary>{items}{more}</details>'

    return f"""
<details class="rr-section" id="s-workflow">
  <summary><h3 class="rr-section-title rr-inline-title">What Happens Next — Workflow Overview</h3></summary>
  <div class="rr-progress-bar-wrap"><div class="rr-progress-bar" style="width:{progress_pct}%;"></div></div>
  <p class="rr-progress-label">{done} of {total} actions complete ({progress_pct}%)</p>
  {blocker_html}
  {qa_html}
  {completed_html}
</details>"""


def _render_exports(links: dict[str, str]) -> str:
    button_defs = [
        ("operational_model", "Open Operational Model"),
        ("topology_viewer", "Open Topology Viewer"),
        ("repair_audit_trail", "Open Repair Audit Trail"),
        ("technician_workflow", "Open Technician Workflow"),
        ("oem_intake", "Open OEM Intake Analysis"),
    ]
    buttons = ""
    for key, label in button_defs:
        href = links.get(key, "#")
        buttons += f'<a class="rr-action-btn" href="{_esc(href)}" target="_blank">{_esc(label)}</a>\n'
    return f"""
<section class="rr-section rr-exports-section" id="s-exports">
  <h3 class="rr-section-title">Tools &amp; Exports</h3>
  <div class="rr-action-buttons">{buttons}</div>
</section>"""


def _render_print_summary(
    h: dict[str, Any],
    er: dict[str, Any],
    doc: dict[str, Any],
    generated_at: str,
) -> str:
    """Hidden print-only summary — one page."""
    decision = er.get("overall_decision", "")
    dc = _hero_colors(decision)
    oem_line = f'{h.get("oem","")} {h.get("year","")} {h.get("model","")}'.strip()
    operation = h.get("operation", "")
    primary = _esc(er.get("primary_problem", ""))
    summary = _esc(er.get("executive_summary", ""))
    tech = _esc(er.get("technician_message", ""))
    mgr = _esc(er.get("manager_message", ""))
    actions = er.get("immediate_actions", [])
    risks = er.get("business_risks", [])

    action_items = "".join(f"<li>{_esc(a)}</li>" for a in actions) if actions else "<li>None</li>"
    risk_items = "".join(f"<li>{_esc(r)}</li>" for r in risks) if risks else "<li>None identified</li>"

    ts = generated_at or datetime.now(tz=timezone.utc).isoformat()

    return f"""
<div class="rr-print-summary">
  <div class="rr-print-header">
    <h2>Repair Review Summary</h2>
    <p class="rr-print-meta">{_esc(h.get("repair_label",""))} &nbsp;|&nbsp; {_esc(oem_line)} &nbsp;|&nbsp; {_esc(operation)}</p>
  </div>

  <div class="rr-print-decision" style="border-color:{dc['border']};">
    <span class="rr-print-decision-label" style="background:{dc['hero_bg']};color:{dc['hero_text']};">
      {_esc(decision)}
    </span>
    <p class="rr-print-primary">{primary}</p>
  </div>

  <p class="rr-print-summary-text">{summary}</p>

  <div class="rr-print-two-col">
    <div>
      <h4>Immediate Actions</h4>
      <ol>{action_items}</ol>
    </div>
    <div>
      <h4>Critical Risks</h4>
      <ul>{risk_items}</ul>
    </div>
  </div>

  <div class="rr-print-people">
    <div class="rr-print-callout">
      <strong>Technician</strong>
      <p>{tech}</p>
    </div>
    <div class="rr-print-callout">
      <strong>Manager</strong>
      <p>{mgr}</p>
    </div>
  </div>

  <p class="rr-print-ts">Generated: {_esc(ts)}</p>
  <p class="rr-print-legal">
    RepairGraph outputs are advisory workflow intelligence. They do not certify repair completion,
    OEM compliance, or repair quality. All outputs require verification by a qualified technician
    against current OEM procedures.
  </p>
</div>"""


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
.rr-page { max-width: 920px; margin: 0 auto; padding: 24px 16px 48px; }

/* Header */
.rr-header { background: #1e293b; color: #fff; border-radius: 12px; padding: 24px 28px; margin-bottom: 16px; }
.rr-header-top { display: flex; justify-content: space-between; align-items: flex-start; gap: 16px; flex-wrap: wrap; }
.rr-label { font-size: 11px; font-weight: 700; letter-spacing: 2px; text-transform: uppercase; color: #94a3b8; }
.rr-header h1 { font-size: 24px; font-weight: 700; margin: 4px 0 8px; color: #f1f5f9; }
.rr-header-meta { display: flex; gap: 8px; flex-wrap: wrap; }
.rr-meta-chip { background: #334155; color: #cbd5e1; font-size: 12px; padding: 3px 10px; border-radius: 20px; }
.rr-header-actions { display: flex; align-items: flex-start; }
.rr-print-btn {
  padding: 8px 16px; background: #334155; color: #e2e8f0; border: none;
  border-radius: 8px; cursor: pointer; font-size: 13px; font-weight: 500; white-space: nowrap;
}
.rr-print-btn:hover { background: #475569; }

/* Nav */
.rr-nav { display: flex; gap: 8px; margin-bottom: 16px; flex-wrap: wrap; }
.rr-nav a { font-size: 12px; padding: 5px 12px; background: #fff; border: 1px solid #e2e8f0; border-radius: 20px; text-decoration: none; color: #475569; transition: all .15s; }
.rr-nav a:hover { background: #1e293b; color: #fff; border-color: #1e293b; }

/* Hero */
.rr-hero { border: 2px solid; border-radius: 12px; padding: 28px 32px; margin-bottom: 16px; }
.rr-hero-badge { display: inline-flex; align-items: center; gap: 12px; border-radius: 8px; padding: 12px 24px; margin-bottom: 16px; }
.rr-hero-icon { font-size: 28px; line-height: 1; }
.rr-hero-label { font-size: 28px; font-weight: 900; letter-spacing: 1px; }
.rr-hero-problem { font-size: 17px; color: #374151; font-weight: 500; line-height: 1.5; }

/* Sections */
.rr-section { background: #fff; border: 1px solid #e2e8f0; border-radius: 12px; padding: 24px 28px; margin-bottom: 16px; }
.rr-section-title { font-size: 15px; font-weight: 700; color: #1e293b; margin-bottom: 16px; }
.rr-inline-title { display: inline; font-size: 14px; }
.rr-empty { color: #94a3b8; font-size: 14px; }

/* Executive summary */
.rr-exec-summary { font-size: 15px; color: #374151; line-height: 1.7; }

/* Immediate actions */
.rr-actions-list { display: flex; flex-direction: column; gap: 10px; margin-bottom: 16px; }
.rr-action-immediate { display: flex; align-items: flex-start; gap: 14px; padding: 14px 16px; background: #eff6ff; border-radius: 8px; }
.rr-action-num { font-size: 18px; font-weight: 900; color: #1d4ed8; min-width: 24px; line-height: 1.4; }
.rr-action-text { font-size: 15px; color: #1e293b; line-height: 1.5; }
.rr-upcoming-detail { margin-top: 8px; }
.rr-upcoming-detail summary { cursor: pointer; font-size: 14px; font-weight: 600; color: #475569; padding: 8px 0; }
.rr-deferred-list { margin-top: 10px; }
.rr-deferred-item { font-size: 13px; color: #475569; padding: 6px 10px; border-radius: 6px; background: #f8fafc; margin-bottom: 4px; }

/* People callouts */
.rr-callout-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
@media (max-width: 600px) { .rr-callout-row { grid-template-columns: 1fr; } }
.rr-callout { border-radius: 10px; padding: 18px 20px; }
.rr-callout-tech { background: #eff6ff; border-left: 4px solid #3b82f6; }
.rr-callout-mgr { background: #faf5ff; border-left: 4px solid #8b5cf6; }
.rr-callout-label { font-size: 10px; font-weight: 800; letter-spacing: 2px; text-transform: uppercase; color: #64748b; margin-bottom: 6px; }
.rr-callout-q { font-size: 13px; color: #64748b; margin-bottom: 8px; font-style: italic; }
.rr-callout-msg { font-size: 14px; color: #1e293b; font-weight: 500; line-height: 1.5; }

/* Confidence */
.rr-conf-row { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; }
@media (max-width: 600px) { .rr-conf-row { grid-template-columns: 1fr; } }
.rr-conf-block { }
.rr-conf-pill { font-size: 13px; padding: 6px 14px; border-radius: 20px; margin-bottom: 8px; display: inline-block; }
.rr-conf-reason { font-size: 13px; color: #475569; }

/* Finding cards */
.rr-finding-card { border-radius: 8px; padding: 16px; margin-bottom: 12px; }
.rr-finding-header { display: flex; gap: 8px; align-items: center; margin-bottom: 8px; flex-wrap: wrap; }
.rr-sev-badge { font-size: 10px; font-weight: 700; padding: 2px 8px; border-radius: 4px; }
.rr-cat-chip { font-size: 12px; color: #64748b; background: rgba(0,0,0,.06); padding: 2px 8px; border-radius: 4px; }
.rr-finding-title { font-size: 14px; font-weight: 700; margin-bottom: 6px; }
.rr-finding-explanation { font-size: 13px; color: #374151; margin-bottom: 8px; }
.rr-finding-action { font-size: 13px; color: #1e40af; background: #eff6ff; padding: 8px 12px; border-radius: 6px; margin-bottom: 8px; }
.rr-finding-evidence { font-size: 12px; color: #475569; }
.rr-finding-evidence ul { padding-left: 18px; margin-top: 4px; }
.rr-extra-findings { margin-top: 8px; }
.rr-extra-findings summary { cursor: pointer; font-size: 14px; font-weight: 600; color: #475569; padding: 8px 0; }
.rr-extra-findings[open] summary { margin-bottom: 8px; }

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

/* Workflow (secondary) */
details.rr-section > summary { cursor: pointer; list-style: none; }
details.rr-section > summary::-webkit-details-marker { display: none; }
details.rr-section[open] > summary { margin-bottom: 16px; }
.rr-progress-bar-wrap { height: 8px; background: #e2e8f0; border-radius: 99px; overflow: hidden; margin-bottom: 6px; margin-top: 16px; }
.rr-progress-bar { height: 100%; background: #22c55e; border-radius: 99px; }
.rr-progress-label { font-size: 13px; color: #64748b; margin-bottom: 12px; }
.rr-blockers { margin-bottom: 12px; }
.rr-blocker-item { display: flex; gap: 10px; align-items: flex-start; font-size: 13px; padding: 6px 0; }
.rr-sev-dot { width: 8px; height: 8px; border-radius: 50%; flex-shrink: 0; margin-top: 5px; }
.rr-sev-dot-critical { background: #ef4444; }
.rr-sev-dot-high { background: #f97316; }
.rr-sev-dot-medium { background: #f59e0b; }
.rr-sev-dot-low { background: #22c55e; }
.rr-action-item { font-size: 13px; padding: 6px 10px; border-radius: 6px; margin-bottom: 4px; }
.rr-action-done { background: #f0fdf4; color: #166534; }
.rr-details summary { cursor: pointer; font-size: 13px; font-weight: 600; padding: 8px 0; color: #475569; }
.rr-more-text { font-size: 12px; color: #64748b; padding: 4px 0; }
.rr-qa-item { font-size: 13px; padding: 6px 10px; border-radius: 6px; margin-bottom: 4px; }
.rr-qa-open { background: #fffbeb; color: #92400e; }
.rr-qa-passed { background: #f0fdf4; color: #166534; }
.rr-qa-cat { font-size: 11px; color: #64748b; margin-left: 8px; }
.rr-qa-block { margin-top: 12px; }

/* Structural */
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
.rr-ev-files { font-size: 13px; margin-bottom: 10px; }
.rr-ev-files ul { padding-left: 18px; margin-top: 4px; }
.rr-ev-oem-notice { font-size: 13px; color: #92400e; background: #fffbeb; padding: 8px 12px; border-radius: 6px; }

/* Exports */
.rr-exports-section { background: #f8fafc; }
.rr-action-buttons { display: flex; gap: 10px; flex-wrap: wrap; }
.rr-action-btn { display: inline-block; padding: 10px 18px; background: #1e293b; color: #fff; border-radius: 8px; text-decoration: none; font-size: 13px; font-weight: 500; transition: background .15s; }
.rr-action-btn:hover { background: #0f172a; }

/* Footer */
.rr-footer { margin-top: 32px; padding: 20px 0; border-top: 1px solid #e2e8f0; }
.rr-legal { font-size: 12px; color: #94a3b8; text-align: center; max-width: 700px; margin: 0 auto; }

/* Print */
.rr-print-summary { display: none; }

@media print {
  body { background: #fff; }
  .rr-page > *:not(.rr-print-summary) { display: none !important; }
  .rr-print-summary { display: block !important; font-family: -apple-system, BlinkMacSystemFont, "Segoe UI", sans-serif; color: #1e293b; }
  .rr-print-header { margin-bottom: 16px; border-bottom: 2px solid #1e293b; padding-bottom: 10px; }
  .rr-print-header h2 { font-size: 20px; font-weight: 800; }
  .rr-print-meta { font-size: 12px; color: #64748b; margin-top: 4px; }
  .rr-print-decision { border: 2px solid; border-radius: 8px; padding: 14px 16px; margin: 14px 0; display: flex; align-items: center; gap: 14px; }
  .rr-print-decision-label { font-size: 15px; font-weight: 900; padding: 6px 16px; border-radius: 6px; white-space: nowrap; }
  .rr-print-primary { font-size: 14px; font-weight: 500; }
  .rr-print-summary-text { font-size: 13px; color: #374151; line-height: 1.6; margin: 12px 0; }
  .rr-print-two-col { display: grid; grid-template-columns: 1fr 1fr; gap: 16px; margin: 14px 0; }
  .rr-print-two-col h4 { font-size: 13px; font-weight: 700; margin-bottom: 6px; border-bottom: 1px solid #e2e8f0; padding-bottom: 4px; }
  .rr-print-two-col ol, .rr-print-two-col ul { padding-left: 18px; font-size: 12px; }
  .rr-print-two-col li { margin-bottom: 4px; }
  .rr-print-people { display: grid; grid-template-columns: 1fr 1fr; gap: 14px; margin: 14px 0; }
  .rr-print-callout { background: #f8fafc; border-radius: 6px; padding: 12px 14px; }
  .rr-print-callout strong { font-size: 11px; text-transform: uppercase; letter-spacing: 1px; color: #64748b; }
  .rr-print-callout p { font-size: 12px; margin-top: 6px; color: #1e293b; }
  .rr-print-ts { font-size: 11px; color: #94a3b8; margin-top: 14px; }
  .rr-print-legal { font-size: 10px; color: #94a3b8; margin-top: 8px; line-height: 1.5; border-top: 1px solid #e2e8f0; padding-top: 8px; }
}
"""

_JS = """
document.addEventListener('DOMContentLoaded', function() {
  // restore toggle button state on page load if any
});
"""


# ---------------------------------------------------------------------------
# Main page builder
# ---------------------------------------------------------------------------

def build_review_page_html(payload: ReviewPayload) -> str:
    """Return a self-contained HTML page for the Review Repair experience."""
    p = payload.to_dict()
    h = p.get("header", {})
    er = p.get("executive_review", {})
    doc = p.get("documentation", {})
    wf = p.get("workflow_readiness", {})
    mr = p.get("material_risk", {})
    ev = p.get("evidence_trail", {})
    links = p.get("export_links", {})

    decision = er.get("overall_decision", "INSUFFICIENT INFORMATION")

    nav_links = [
        ("#s-status", "Status"),
        ("#s-summary", "Summary"),
        ("#s-actions", "Actions"),
        ("#s-people", "For Your Team"),
        ("#s-rationale", "Why This Decision"),
        ("#s-structural", "Structural"),
        ("#s-documentation", "Documentation"),
        ("#s-evidence", "Evidence"),
        ("#s-exports", "Tools"),
    ]
    nav_html = '<nav class="rr-nav">' + "".join(
        f'<a href="{_esc(href)}">{_esc(label)}</a>' for href, label in nav_links
    ) + "</nav>"

    structural_html = _render_structural_considerations(mr)

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
  {_render_page_header(h, er)}
  {nav_html}
  {_render_hero(er)}
  {_render_executive_summary(er)}
  {_render_immediate_actions(er)}
  {_render_people_callouts(er)}
  {_render_confidence(er)}
  {_render_decision_rationale(er)}
  {structural_html if structural_html.strip() else ""}
  {_render_workflow_secondary(wf)}
  {_render_documentation(doc)}
  {_render_evidence(ev)}
  {_render_exports(links)}
  {_render_legal()}
  {_render_print_summary(h, er, doc, p.get("generated_at",""))}
</div>
<script type="application/json" id="rr-payload">{payload_json}</script>
<script>{_JS}</script>
</body>
</html>"""
