# OEM Repair Packet Intake Pipeline

RepairGraph includes a repair packet intake pipeline for ingesting unfamiliar
OEM repair documents. The intake layer classifies documents, detects vehicle
metadata, identifies present and missing document roles, and produces intake
manifests and diagnostic reports.

**Important:** RepairGraph processes OEM repair information supplied by
authorized users/subscribers who have acquired the right to use that
information. RepairGraph is not an OEM document distribution platform.
It does not redistribute OEM documentation or grant access to OEM content.

---

## Intake architecture

```
Input files (any OEM, any format)
    ↓
classify_intake_file()          — per-file classification
    ↓
detect_document_role()          — keyword heuristic role detection
detect_oem_metadata()           — OEM/model/year/operation detection
    ↓
classify_intake_packet()        — multi-file aggregation
    ↓
IntakeManifest                  — complete intake result
    ↓
validate_packet_completeness()  — completeness diagnostics
build_intake_diagnostics()      — structured diagnostic report
    ↓
build_intake_html_report()      — portable HTML report
```

### Modules

| Module | Purpose |
|---|---|
| `intake/schema.py` | Dataclasses: IntakeFile, IntakeManifest, IntakePacket, IntakeDiagnostic, etc. |
| `intake/classify.py` | File classification, OEM detection, packet assembly |
| `intake/diagnostics.py` | Completeness validation, missing role reports, diagnostic structuring |
| `intake/report.py` | Self-contained HTML report generation |
| `intake/cli.py` | CLI: ingest files, write manifest JSON + HTML report |
| `api/intake_routes.py` | FastAPI endpoints: POST /internal/intake/classify and /report |

---

## Classification heuristics

The intake classifier uses keyword pattern matching only. It does not call
any external AI service, OCR library, or ML model.

### OEM detection

OEM patterns are searched in the full text of each file. The OEM with the
highest weighted keyword hit count wins. Confidence is proportional to hit
count but capped at 0.85 (no classification is treated as certain).

Supported OEMs (heuristic, not exhaustive):
Honda, Toyota, Ford, GM (Chevrolet/GMC/Buick/Cadillac), Nissan, Subaru,
Volkswagen, BMW, Mercedes-Benz, Stellantis (Chrysler/Dodge/Jeep/Ram),
Hyundai/Kia, Mazda, Mitsubishi, Volvo, Rivian, Tesla.

### Model detection

Model patterns are searched within the detected OEM's model list first,
then across all OEMs if no OEM was detected.

### Year detection

Four-digit years in the range 1980–2039 are matched. The most frequently
occurring plausible year wins.

### Operation detection

Common collision repair operations are detected by phrase matching:
quarter panel replacement, outer panel replacement, roof panel, door
replacement, sectioning, frame repair, etc.

### Document role detection

Files are scored against eight keyword sets:
`repair_procedure`, `sectioning`, `welding`, `corrosion_protection`,
`materials`, `dimensions`, `calibration`, `precautions`.

The role with the highest keyword match score is assigned. Documents
with no matching keywords receive the role `unknown`.

**Limitations of heuristics:**

- A document can genuinely match multiple roles (e.g., a repair procedure
  with extensive gap specs may score high on both `repair_procedure` and
  `dimensions`). The classifier assigns the top-scoring role.
- Unusual formatting, non-English text, or heavily abbreviated content
  may not trigger the expected keywords.
- PDF classification uses raw byte extraction, which is unreliable for
  scanned or image-only PDFs.

---

## PDF handling

RepairGraph does not include an OCR library or PDF text extraction
dependency. PDF classification uses heuristic ASCII run extraction
from raw bytes. This works for text-embedded PDFs but not scanned PDFs.

When text extraction from a PDF yields minimal content, a warning is
added: `"PDF text extraction yielded minimal content."` The file is
still processed and assigned whatever confidence the limited text allows.

For best intake results, provide text-format (`.txt`) documents.

---

## Readiness scoring

Each intake manifest receives one of four readiness levels:

| Level | Meaning |
|---|---|
| `ready` | All files readable; `repair_procedure` detected; 2+ additional roles detected |
| `partial` | At least one document role detected, but essential or recommended roles are missing |
| `incomplete` | No document roles detected; files may be readable but unclassifiable |
| `unprocessable` | All files have read errors, or no files were provided |

Readiness is a heuristic estimate. It does not guarantee that a "ready"
packet can be successfully normalized or that a "partial" packet cannot be.

---

## Diagnostics philosophy

The intake diagnostics layer is the primary explainability surface of the
pipeline. RepairGraph uses diagnostics to communicate:

- **What it found** — detected roles, OEM, model, year, operation
- **What is missing** — essential and recommended document roles
- **What it cannot classify** — unknown-role files, low-confidence files
- **What went wrong** — unreadable files, format warnings, OEM conflicts
- **What confidence it has** — per-file and aggregate confidence scores

### Diagnostic severities

| Severity | Meaning |
|---|---|
| `error` | Missing essential role, unreadable file, or no files provided |
| `warning` | Missing recommended role, low confidence, OEM conflict, unsupported format |
| `info` | Year not detected, or other advisory information |

### Diagnostic codes

| Code | Description |
|---|---|
| `EMPTY_PACKET` | No files provided |
| `FILE_NOT_FOUND` | A specified path does not exist |
| `FILE_ERROR` | File could not be read |
| `FILE_WARNING` | File warning (empty, PDF heuristic, encoding issue) |
| `MISSING_ESSENTIAL_*` | Essential role not detected (e.g., `repair_procedure`) |
| `MISSING_RECOMMENDED_*` | Recommended role not detected |
| `UNREADABLE_FILES` | One or more files could not be read |
| `LOW_CONFIDENCE_CLASSIFICATIONS` | One or more files classified below 30% confidence |
| `UNKNOWN_ROLE_FILES` | One or more files could not be assigned a role |
| `OEM_NOT_DETECTED` | No OEM detected across all files |
| `OEM_CONFLICT` | Multiple different OEMs detected across files |
| `YEAR_NOT_DETECTED` | Model year could not be detected |
| `UNSUPPORTED_FORMATS` | Files with unsupported extensions supplied |

---

## Missing role report

`build_missing_role_report(manifest)` explains which document roles are
absent and why they matter:

- **Essential** (`repair_procedure`): required for normalization
- **Recommended** (`welding`, `corrosion_protection`, `materials`, `precautions`):
  needed for complete repair intelligence

The report computes missing roles from the detected roles, not just
from the pre-stored list, so it is accurate for any manifest regardless
of how it was constructed.

---

## Non-goals

The intake pipeline is explicitly not:

- An OCR system
- An AI document classifier
- A perfect parser
- An OEM procedure validator
- A document authenticity checker
- A production ingestion system with persistence

The goal is **safe, understandable intake of unfamiliar OEM repair packets**,
not flawless extraction.

---

## OEM and legal boundary

RepairGraph is a transformation and intelligence layer, not an OEM
document distribution platform. The intake pipeline assumes:

1. The user has the legal right to possess and process the supplied documents
2. The documents were obtained through authorized channels (OEM subscriptions,
   authorized repair information systems, etc.)
3. RepairGraph's role is to help structure and reason over that authorized
   information — not to provide OEM content

All intake outputs include this advisory language and preserve the
distinction between RepairGraph's intelligence layer and OEM-owned content.

---

## CLI usage

```bash
python -m repairgraph.intake.cli path/to/repair/packet/
python -m repairgraph.intake.cli file1.txt file2.txt file3.txt
```

Outputs to `data/extracted/intake/`:
- `intake_manifest.json` — JSON manifest
- `intake_report.html` — HTML report

---

## API endpoints

```
POST /internal/intake/classify
POST /internal/intake/report
```

Both accept multipart file uploads (`files` field). No files are retained.
`/classify` returns JSON; `/report` returns `text/html`.

See `src/repairgraph/api/intake_routes.py` for implementation.

---

## Advisory

All intake outputs are advisory heuristic estimates. They do not certify
document completeness, OEM authenticity, or normalization readiness.
RepairGraph processes OEM repair information supplied by authorized users.
It is not an OEM document distribution platform.
