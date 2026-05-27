"""
Intake pipeline CLI for RepairGraph OEM repair packet import.

Accepts local file or folder paths, classifies the intake packet, writes
an intake manifest (JSON) and HTML report, and prints a terminal summary.

Usage:
    python -m repairgraph.intake.cli path/to/files [path/to/more ...]

Outputs are written to data/extracted/intake/ relative to the working directory.

Advisory: RepairGraph processes OEM repair information supplied by authorized
users. It is not an OEM document distribution platform.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from repairgraph.intake.classify import classify_intake_packet, summarize_intake_manifest
from repairgraph.intake.report import build_intake_html_report
from repairgraph.intake.schema import IntakeManifest

_OUTPUT_DIR = Path("data/extracted/intake")

MANIFEST_FILENAME = "intake_manifest.json"
REPORT_FILENAME = "intake_report.html"


def _manifest_to_dict(manifest: IntakeManifest) -> dict:
    """Serialize an IntakeManifest to a JSON-compatible dict."""
    return {
        "schema_name": "repairgraph.intake_manifest",
        "schema_version": "0.1",
        "advisory": manifest.advisory,
        "intake_id": manifest.intake_id,
        "created_at": manifest.created_at,
        "readiness": manifest.readiness,
        "detected_packet": {
            "detected_oem": manifest.detected_packet.detected_oem,
            "detected_model": manifest.detected_packet.detected_model,
            "detected_year": manifest.detected_packet.detected_year,
            "detected_operation": manifest.detected_packet.detected_operation,
            "oem_confidence": manifest.detected_packet.oem_confidence,
            "detected_roles": manifest.detected_packet.detected_roles,
            "file_count": manifest.detected_packet.file_count,
        },
        "files": [
            {
                "file_id": f.file_id,
                "filename": f.filename,
                "extension": f.extension,
                "size_bytes": f.size_bytes,
                "detected_oem": f.detected_oem,
                "detected_model": f.detected_model,
                "detected_year": f.detected_year,
                "detected_operation": f.detected_operation,
                "document_role": f.document_role,
                "confidence": f.confidence,
                "warnings": f.warnings,
                "errors": f.errors,
                "advisory_note": f.advisory_note,
            }
            for f in manifest.files
        ],
        "missing_roles": manifest.missing_roles,
        "diagnostics": [
            {
                "code": d.code,
                "severity": d.severity,
                "message": d.message,
                "file_id": d.file_id,
                "detail": d.detail,
            }
            for d in manifest.diagnostics
        ],
    }


def collect_paths(args: list[str]) -> list[Path]:
    """Expand CLI args to a flat list of file paths."""
    paths: list[Path] = []
    for arg in args:
        p = Path(arg)
        if p.is_dir():
            for f in sorted(p.iterdir()):
                if f.is_file():
                    paths.append(f)
        elif p.exists():
            paths.append(p)
        else:
            print(f"  Warning: path not found: {p}", file=sys.stderr)
    return paths


def run_intake_cli(args: list[str] | None = None) -> None:
    """Run the intake CLI. args defaults to sys.argv[1:] if None."""
    if args is None:
        args = sys.argv[1:]

    print("RepairGraph Intake CLI")
    print("─" * 40)

    if not args:
        print("Usage: python -m repairgraph.intake.cli path/to/files [...]")
        print()
        print("Advisory: Provide paths to OEM repair documents for intake classification.")
        print("          RepairGraph processes OEM repair information supplied by")
        print("          authorized users. It is not an OEM document distribution platform.")
        return

    paths = collect_paths(args)
    if not paths:
        print("No readable files found at the specified paths.")
        return

    print(f"Processing {len(paths)} file(s)...")
    for p in paths:
        print(f"  {p.name}")
    print()

    manifest = classify_intake_packet(paths)
    summary = summarize_intake_manifest(manifest)

    print("Intake Results:")
    print(f"  Files processed:   {summary['file_count']}")
    print(f"  Readable files:    {summary['readable_file_count']}")
    print(f"  OEM detected:      {summary['detected_oem'] or 'Not detected'}")
    print(f"  Model detected:    {summary['detected_model'] or 'Not detected'}")
    print(f"  Year detected:     {summary['detected_year'] or 'Not detected'}")
    print(f"  OEM confidence:    {int(summary['oem_confidence'] * 100)}%")
    print(f"  Roles found:       {', '.join(summary['detected_roles']) or 'None'}")
    print(f"  Missing roles:     {', '.join(summary['missing_roles']) or 'None'}")
    print(f"  Readiness:         {summary['readiness'].upper()}")
    print(f"  Warnings:          {summary['warning_count']}")
    print(f"  Errors:            {summary['error_count']}")
    print()

    _OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    manifest_path = _OUTPUT_DIR / MANIFEST_FILENAME
    report_path = _OUTPUT_DIR / REPORT_FILENAME

    manifest_dict = _manifest_to_dict(manifest)
    manifest_path.write_text(
        json.dumps(manifest_dict, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    report_html = build_intake_html_report(manifest)
    report_path.write_text(report_html, encoding="utf-8")

    print("Outputs written:")
    print(f"  manifest: {manifest_path}")
    print(f"  report:   {report_path}")
    print()
    print("Advisory: RepairGraph processes OEM repair information supplied by authorized users.")
    print("          It is not an OEM document distribution platform.")


if __name__ == "__main__":
    run_intake_cli()
