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
| `intake/classify.py` | File classification, OEM detection, packet assembly, breadcrumb parsing, multi-role detection |
| `intake/diagnostics.py` | Completeness validation, missing role reports, diagnostic structuring |
| `intake/report.py` | Self-contained HTML report generation |
| `intake/cli.py` | CLI: ingest files, write manifest JSON + HTML report |
| `api/intake_routes.py` | FastAPI endpoints: POST /internal/intake/classify and /report |

---

## Real-world metadata detection hardening

### Two-channel evidence model

The intake classifier uses two evidence channels for OEM, model, year, and
operation detection:

**Filename evidence (high-signal):** OEM, model, year, and operation are
extracted directly from filename tokens. Filenames like
`"2024 Subaru Outback Quarter Panel Replacement.pdf"` carry explicit vehicle
identity and are treated as the strongest available signal. Filename evidence
is not subject to the isolation penalty applied to body text.

**Text evidence (lower-signal):** OEM/model/year extracted from document body
text. Text from noisy sources (scanned PDFs, repair info systems with boilerplate)
may contain unrelated OEM mentions. The classifier applies an isolation penalty
to single-or-double OEM mentions in documents longer than 1000 characters.

**Merge rules:**
- Filename OEM/year/model takes priority when present
- When filename and text agree: confidence is boosted
- When filename and text disagree: filename wins, a `FILENAME_TEXT_DISAGREEMENT`
  diagnostic is generated with both evidence values
- When only text has metadata: text result used with text-derived confidence

### Isolation penalty for weak OEM mentions

An OEM detected only 1–2 times in a document longer than 1000 characters
receives a score reduction of 60%. This prevents a single incidental OEM
mention (e.g., in boilerplate listing "compatible OEMs: Toyota, Volkswagen,
Honda…") from dominating the classification result.

This penalty does not apply to short texts or to OEMs with 3+ hits.
It does not apply to filename tokens.

### Packet-level filename voting

At the packet level (multiple files):

- Filename OEM is extracted for each readable file
- If ≥50% of readable files agree on the same filename OEM, that OEM is
  selected as the packet OEM with high confidence (0.55–0.85 based on
  agreement ratio)
- If no filename majority exists, a combined weighted vote is used
- When filename evidence determines the OEM, an `OEM_DETECTED_BY_FILENAME`
  info diagnostic explains the evidence source

### Canonical model names

Model detection now returns canonical display names (e.g., "Outback",
"Camry", "F-150", "CR-V") rather than raw regex pattern strings. All
16 supported OEMs have canonical name mappings.

---

## Classification heuristics

The intake classifier uses keyword pattern matching only. It does not call
any external AI service, OCR library, or ML model.

### OEM detection

OEM patterns are searched in the full text of each file with isolation penalty
for weak isolated mentions (see above). The OEM with the highest weighted
keyword hit count wins. Confidence is proportional to hit count but capped
at 0.85. Filename evidence is merged separately and takes priority.

Supported OEMs (heuristic, not exhaustive):
Honda, Toyota, Ford, GM (Chevrolet/GMC/Buick/Cadillac), Nissan, Subaru,
Volkswagen, BMW, Mercedes-Benz, Stellantis (Chrysler/Dodge/Jeep/Ram),
Hyundai/Kia, Mazda, Mitsubishi, Volvo, Rivian, Tesla.

### Model detection

Model patterns are searched within the detected OEM's model list first,
then across all OEMs if no OEM was detected. Returns canonical model name
(e.g., "Outback", not the raw pattern). Filename model takes priority
over text model when both are detected.

### Year detection

Four-digit years in the range 1980–2039 are matched. Filename year takes
priority at both per-file and packet level. Text year is the most frequently
occurring plausible year.

### Operation detection

Common collision repair operations are detected by phrase matching:
quarter panel replacement, outer panel replacement, roof panel, door
replacement, sectioning, frame repair, etc.

### Document role detection

Files are scored against eight role categories:
`repair_procedure`, `sectioning`, `welding`, `corrosion_protection`,
`materials`, `dimensions`, `calibration`, `precautions`.

Role scoring uses three evidence channels:

**Keyword patterns (1× weight):** Each role has an expanded set of
keyword patterns matched against the lowercased document text.

**Ontology phrases (3× weight):** Compound phrases strongly associated
with a specific role (e.g., `"removal and replacement"`, `"weld points"`,
`"corrosion protection"`, `"material specification"`). These are matched as
exact substrings and carry three times the weight of a keyword hit.

**Breadcrumb navigation (5× weight):** ALLDATA and similar repair
information systems embed navigation breadcrumbs in documents, such as:
```
Elantra > Body and Frame > Quarter Panel > Service and Repair > Weld Points
```
The `detect_breadcrumbs()` function extracts segments from lines with 3+
separator-joined parts. Specific document-type segments (e.g., "weld points",
"removal and replacement", "corrosion protection") are matched against
`_BREADCRUMB_ROLE_MAP` and contribute the strongest per-hit signal.

**Primary and supporting roles:** Each file receives a `primary_role`
(highest-scoring role) and a `supporting_roles` list of other roles that
score at least 30% of the top score. A repair procedure that also references
weld specifications would have `repair_procedure` as primary and `welding`
as a supporting role. Supporting roles are recorded on `IntakeFile` but do
not affect packet-level `detected_roles` (which reflects primary roles only).

**Role evidence:** `role_evidence` on `IntakeFile` records the top phrases
(ontology matches, breadcrumb segments) that triggered the classification.
This provides an explainability trail for human review.

**Limitations of heuristics:**

- Unusual formatting, non-English text, or heavily abbreviated content
  may not trigger the expected keywords.
- PDF classification uses raw byte extraction, which is unreliable for
  scanned or image-only PDFs.
- Breadcrumb parsing requires separator characters (`>`, `»`, `→`, `/`, `::`)
  and at least 3 segments per line. Documents without structural navigation
  rely on keyword and ontology scoring only.

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
| `OEM_DETECTED_BY_FILENAME` | OEM determined from filename evidence (majority of files agree) |
| `FILENAME_TEXT_DISAGREEMENT` | Filename OEM/year conflicts with extracted text OEM/year |
| `WEAK_METADATA_CONFIDENCE` | Packet OEM confidence below 40% |
| `NO_STRONG_PACKET_CONSENSUS` | No single OEM achieved majority across files |
| `YEAR_CONFLICT` | Filename year differs from predominant document text year |
| `MODEL_CONFLICT` | Multiple model signals detected across files |

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

## Browser upload workflow

RepairGraph includes a local browser-based upload page for the intake pipeline.

**Start the server:**

```bash
python -m uvicorn repairgraph.api.app:app --reload
```

**Open the intake UI:**

```
http://localhost:8000/internal/intake
```

**Workflow:**

1. Select or drag-and-drop one or more OEM repair documents into the upload zone
2. Click **Analyze Packet** — the page calls `POST /internal/intake/classify`,
   then renders summary cards, detected packet metadata, role coverage, per-file
   classification table, and diagnostics inline
3. Click **View Full Report** — the page calls `POST /internal/intake/report`
   and opens the portable HTML intake report in a new browser tab

**UI limitations:**

- Files are sent on every request — the UI does not cache or store prior results
- Classification is heuristic; low-confidence or unknown-role results are surfaced
  as warnings, not errors
- PDF handling is raw ASCII extraction only; scanned PDFs will produce minimal results
- There is no session persistence; closing or refreshing the page resets the UI

**No persistence, no auth, no document storage:**

The upload page is local/internal only. No files are stored on the server. No
authentication is required. No database is involved. All processing is in-memory
per request and discarded after the response. This is not a production SaaS surface.

---

## API endpoints

```
GET  /internal/intake
POST /internal/intake/classify
POST /internal/intake/report
```

`GET /internal/intake` returns the self-contained HTML upload page.
`POST /classify` and `/report` accept multipart file uploads (`files` field).
No files are retained. `/classify` returns JSON; `/report` returns `text/html`.

See `src/repairgraph/api/intake_routes.py` for implementation.

---

## Advisory

All intake outputs are advisory heuristic estimates. They do not certify
document completeness, OEM authenticity, or normalization readiness.
RepairGraph processes OEM repair information supplied by authorized users.
It is not an OEM document distribution platform.
