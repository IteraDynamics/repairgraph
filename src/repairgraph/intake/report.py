"""
HTML intake report builder for RepairGraph OEM repair packet intake.

Produces self-contained, portable HTML reports from IntakeManifest data.
Reports show detected metadata, file classifications, role coverage,
diagnostics, readiness assessment, and confidence indicators.

No external dependencies, no CDN, no network access required.
Reports open directly in any browser.

All outputs are advisory. They do not certify OEM authenticity, document
completeness, or normalization readiness.
"""
from __future__ import annotations

import html
from typing import Any

from repairgraph.intake.diagnostics import build_intake_diagnostics, build_missing_role_report
from repairgraph.intake.schema import IntakeFile, IntakeManifest

_ADVISORY_NOTE = (
    "Advisory: RepairGraph processes OEM repair information supplied by authorized users. "
    "It is not an OEM document distribution platform. "
    "This intake report is a heuristic classification estimate. It does not certify "
    "document completeness, OEM authenticity, or normalization readiness. "
    "All intake outputs require qualified review before proceeding to normalization "
    "or repair workflow generation."
)

_GENERATED_BY = "repairgraph.intake.report"

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
.r-ready{background:#d4edda;color:#155724}
.r-partial{background:#fff3cd;color:#7a5200}
.r-incomplete{background:#f8d7da;color:#721c24}
.r-unprocessable{background:#f5c6cb;color:#491217}
.r-unknown{background:#eee;color:#555}
.r-repair_procedure,.r-welding,.r-corrosion_protection,.r-materials,.r-precautions,.r-sectioning,.r-dimensions,.r-calibration{background:#eef0f5;color:#334}
.sev-info{background:#e3f2fd;color:#0d47a1}
.sev-warning{background:#fff3cd;color:#7a5200}
.sev-error{background:#f8d7da;color:#721c24}
.conf-high{background:#d4edda;color:#155724}
.conf-med{background:#fff3cd;color:#7a5200}
.conf-low{background:#f8d7da;color:#721c24}
.mono{font-family:monospace;font-size:12px;color:#334}
.empty{color:#999;font-style:italic;font-size:13px}
.kv{display:flex;gap:8px;margin-bottom:5px;font-size:13px}
.kv-key{color:#778;min-width:160px;flex-shrink:0;font-size:12px}
.kv-val{color:#1a1a2e;font-family:monospace;word-break:break-all;font-size:12px}
.progress-outer{background:#e9ecef;border-radius:4px;height:8px;overflow:hidden;width:80px;display:inline-block;vertical-align:middle;margin-left:6px}
.progress-inner{height:100%;border-radius:4px;background:#2d5a8c}
.role-found{background:#d4edda;color:#155724;border-radius:3px;padding:3px 9px;font-size:12px;font-weight:600;margin:2px;display:inline-block}
.role-missing{background:#f8d7da;color:#721c24;border-radius:3px;padding:3px 9px;font-size:12px;font-weight:600;margin:2px;display:inline-block}
footer{margin-top:24px;padding:14px 32px;font-size:11px;color:#aaa;border-top:1px solid #dde1e8;text-align:center}
"""


def _h(text: Any) -> str:
    return html.escape(str(text))


def _badge(css_class: str, label: str) -> str:
    return f'<span class="badge {_h(css_class)}">{_h(label)}</span>'


def _kv(key: str, val: Any) -> str:
    return (
        f'<div class="kv">'
        f'<span class="kv-key">{_h(key)}</span>'
        f'<span class="kv-val">{_h(str(val))}</span>'
        f'</div>'
    )


def _section(title: str, content: str) -> str:
    return (
        f'<div class="section">'
        f'<div class="section-header">{_h(title)}</div>'
        f'<div class="section-body">{content}</div>'
        f'</div>'
    )


def _table(headers: list[str], rows: list[list[str]]) -> str:
    th = "".join(f"<th>{_h(h)}</th>" for h in headers)
    trs = ""
    for row in rows:
        tds = "".join(f"<td>{cell}</td>" for cell in row)
        trs += f"<tr>{tds}</tr>"
    if not rows:
        trs = f'<tr><td colspan="{len(headers)}" class="empty" style="padding:12px 10px">No entries.</td></tr>'
    return f"<table><thead><tr>{th}</tr></thead><tbody>{trs}</tbody></table>"


def _confidence_display(conf: float) -> str:
    pct = int(conf * 100)
    if conf >= 0.65:
        badge_cls = "conf-high"
    elif conf >= 0.35:
        badge_cls = "conf-med"
    else:
        badge_cls = "conf-low"
    bar = (
        f'<div class="progress-outer">'
        f'<div class="progress-inner" style="width:{pct}%"></div>'
        f'</div>'
    )
    return f'<span class="badge {badge_cls}">{pct}%</span>{bar}'


def _readiness_badge(readiness: str) -> str:
    labels = {"ready": "Ready", "partial": "Partial", "incomplete": "Incomplete", "unprocessable": "Unprocessable"}
    return _badge(f"r-{readiness}", labels.get(readiness, readiness))


def _html_shell(title: str, body: str) -> str:
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
        f'<footer>Generated by {_h(_GENERATED_BY)} &bull; RepairGraph OEM intake intelligence</footer>\n'
        f"</body>\n"
        f"</html>"
    )


def build_intake_summary_cards(manifest: IntakeManifest) -> list[dict[str, str]]:
    """Return summary card data for the given IntakeManifest.

    Each dict has keys: value, label, accent.
    """
    error_count = sum(1 for d in manifest.diagnostics if d.severity == "error")
    warning_count = sum(1 for d in manifest.diagnostics if d.severity == "warning")
    readable = [f for f in manifest.files if not f.errors]

    return [
        {"value": str(len(manifest.files)), "label": "Files", "accent": "blue"},
        {"value": str(len(readable)), "label": "Readable", "accent": "green" if len(readable) == len(manifest.files) else "amber"},
        {"value": str(len(manifest.detected_packet.detected_roles)), "label": "Roles Found", "accent": "blue"},
        {"value": str(len(manifest.missing_roles)), "label": "Roles Missing", "accent": "amber" if manifest.missing_roles else "green"},
        {"value": str(error_count), "label": "Errors", "accent": "red" if error_count else "green"},
        {"value": str(warning_count), "label": "Warnings", "accent": "amber" if warning_count else "green"},
    ]


def build_intake_html_report(manifest: IntakeManifest) -> str:
    """Build a self-contained HTML intake report from an IntakeManifest.

    Includes advisory banner, intake summary cards, detected packet metadata,
    document role coverage, per-file classifications, diagnostics, missing role
    report, and readiness assessment. No external dependencies. Deterministic output.
    """
    parts: list[str] = []

    p = manifest.detected_packet
    oem = p.detected_oem or "Unknown OEM"
    model = p.detected_model or "Unknown Model"
    year = str(p.detected_year) if p.detected_year else "Unknown Year"

    # Header
    parts.append(
        f'<header>'
        f'<div class="title">RepairGraph OEM Intake Report</div>'
        f'<div class="subtitle">{_h(year)} {_h(oem)} {_h(model)}</div>'
        f'<div class="meta">'
        f'Intake: {_h(manifest.intake_id)} &bull; '
        f'Readiness: {_readiness_badge(manifest.readiness)} &bull; '
        f'{_h(p.file_count)} file(s) &bull; {_h(manifest.created_at)}'
        f'</div>'
        f'</header>'
    )

    # Advisory banner
    parts.append(
        f'<div class="advisory-banner">'
        f'<strong>Advisory:</strong> {_h(_ADVISORY_NOTE[len("Advisory: ")])}'
        f'{_h(_ADVISORY_NOTE[len("Advisory: A")+1:])}'
        f'</div>'
    )

    parts.append("<main>")

    # Summary cards
    cards = build_intake_summary_cards(manifest)
    cards_html = '<div class="cards">' + "".join(
        f'<div class="card {c["accent"]}">'
        f'<div class="card-value">{_h(c["value"])}</div>'
        f'<div class="card-label">{_h(c["label"])}</div>'
        f'</div>'
        for c in cards
    ) + '</div>'
    parts.append(_section("Intake Summary", cards_html))

    # Packet metadata
    meta_html = (
        _kv("Detected OEM", p.detected_oem or "Not detected")
        + _kv("Detected Model", p.detected_model or "Not detected")
        + _kv("Detected Year", p.detected_year or "Not detected")
        + _kv("Detected Operation", p.detected_operation or "Not detected")
        + f'<div class="kv"><span class="kv-key">OEM Confidence</span>'
        f'<span class="kv-val">{_confidence_display(p.oem_confidence)}</span></div>'
        + _kv("Intake ID", manifest.intake_id)
        + _kv("Created At", manifest.created_at)
        + _kv("Readiness", manifest.readiness)
    )
    parts.append(_section("Detected Packet Metadata", meta_html))

    # Document role coverage
    all_roles = [
        "repair_procedure", "sectioning", "welding", "corrosion_protection",
        "materials", "dimensions", "calibration", "precautions",
    ]
    found_set = set(p.detected_roles)
    role_html = "".join(
        f'<span class="role-found">{_h(r)}</span>'
        if r in found_set else
        f'<span class="role-missing">{_h(r)} ✗</span>'
        for r in all_roles
    )
    unknown_files = [f for f in manifest.files if f.document_role == "unknown" and not f.errors]
    if unknown_files:
        role_html += (
            f'<p style="margin-top:10px;font-size:12px;color:#888;">'
            f'{len(unknown_files)} file(s) classified as unknown role.</p>'
        )
    parts.append(_section("Document Role Coverage", role_html))

    # File classifications
    if manifest.files:
        rows = []
        for f in manifest.files:
            if f.errors:
                status = _badge("sev-error", "Error")
            elif f.warnings:
                status = _badge("sev-warning", "Warning")
            else:
                status = _badge("r-ready", "OK")
            rows.append([
                f'<span class="mono">{_h(f.filename)}</span>',
                _h(f.extension or "—"),
                _badge(f"r-{f.document_role}", f.document_role),
                _h(f.detected_oem or "—"),
                _h(f.detected_model or "—"),
                _h(str(f.detected_year) if f.detected_year else "—"),
                _confidence_display(f.confidence),
                status,
            ])
        parts.append(_section(
            "File Classifications",
            _table(["Filename", "Ext", "Role", "OEM", "Model", "Year", "Confidence", "Status"], rows),
        ))

    # Diagnostics
    diag_data = build_intake_diagnostics(manifest)
    all_diags = diag_data["errors"] + diag_data["warnings"] + diag_data["infos"]
    if all_diags:
        rows = [
            [
                _badge(f'sev-{d["severity"]}', d["severity"]),
                f'<span class="mono">{_h(d["code"])}</span>',
                _h(d["message"]),
                _h(d.get("detail") or "—"),
            ]
            for d in all_diags
        ]
        parts.append(_section(
            f'Diagnostics ({len(all_diags)})',
            _table(["Severity", "Code", "Message", "Detail"], rows),
        ))
    else:
        parts.append(_section("Diagnostics", '<span class="empty">No diagnostics.</span>'))

    # Missing role report
    missing_report = build_missing_role_report(manifest)
    if missing_report["missing_roles"]:
        missing_rows = [
            [
                f'<span class="role-missing">{_h(r)}</span>',
                _badge(
                    "sev-error" if r in missing_report["missing_essential"] else "sev-warning",
                    "essential" if r in missing_report["missing_essential"] else "recommended",
                ),
                _h(missing_report["role_descriptions"].get(r, "—")),
            ]
            for r in missing_report["missing_roles"]
        ]
        parts.append(_section(
            "Missing Document Roles",
            _table(["Role", "Priority", "Description"], missing_rows)
            + f'<p style="margin-top:10px;font-size:12px;color:#666;">'
            f'{_h(missing_report["advisory"])}</p>',
        ))

    # Readiness assessment
    readiness_color = {
        "ready": "#228844", "partial": "#c87800",
        "incomplete": "#cc3333", "unprocessable": "#8b0000",
    }.get(manifest.readiness, "#555")

    readiness_html = (
        f'<p style="font-size:18px;font-weight:700;color:{readiness_color};margin-bottom:12px;">'
        f'{_readiness_badge(manifest.readiness)}'
        f'</p>'
        + _kv("Files processed", len(manifest.files))
        + _kv("Readable files", len([f for f in manifest.files if not f.errors]))
        + _kv("Roles detected", ", ".join(p.detected_roles) or "None")
        + _kv("Roles missing", ", ".join(manifest.missing_roles) or "None")
        + _kv("Errors", diag_data["error_count"])
        + _kv("Warnings", diag_data["warning_count"])
        + f'<p style="margin-top:12px;font-size:12px;color:#666;">{_h(manifest.advisory)}</p>'
    )
    parts.append(_section("Readiness Assessment", readiness_html))

    parts.append("</main>")

    return _html_shell(
        title=f"RepairGraph Intake Report — {year} {oem} {model}",
        body="\n".join(parts),
    )
