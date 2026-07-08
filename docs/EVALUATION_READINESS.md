# Evaluation Readiness

Four fixes made ahead of putting this in front of a real evaluator (a shop
manager or technician, cold, without the internals explained first). Ordered
by how much trust damage each risked.

## 1. The demo fallback is now honest, never silent

Previously: if a real vehicle couldn't be resolved (nothing uploaded yet, an
explicit request for a vehicle that doesn't exist, or an active-vehicle
reference pointing at a procedure that was never written), `/internal/review`
silently rendered the built-in Honda Accord demo with no indication it
wasn't the viewer's data. An evaluator uploading their own document and
being shown unrelated Honda Accord results would reasonably conclude the
tool is broken or faking results.

Now the review page shows a clearly visible banner whenever it's displaying
demo data instead of a resolved vehicle:

- **First-time state** (nothing uploaded yet): a blue notice — "Viewing the
  built-in demo... not data you uploaded."
- **Requested vehicle not found** (explicit params or an active vehicle set,
  but no matching procedure on disk): an amber warning notice naming the
  vehicle that was requested and stating plainly that the demo is being
  shown instead.

JSON endpoints (`/internal/review/payload`, etc.) keep the existing silent
fallback — they're integration surfaces, not something an evaluator reads
directly.

See `src/repairgraph/review/routes.py::_build_model_with_context` and
`review_page.py::_render_demo_notice`. Tests: `tests/test_demo_notice.py`.

## 2. Failure modes verified, not just assumed

Tested against real uploads:

| Input | Result |
| --- | --- |
| Empty file | `readiness: incomplete`, warned "File is empty." |
| Image-only PDF (no text layer) | No crash, `confidence: 0.0`, role `unknown` |
| Unrelated document (a recipe) | No OEM falsely detected, role `unknown`, no active vehicle set |
| Random binary bytes as `.txt` | Returns 200, no crash |
| Control characters / zero-width unicode mixed with real content | Still detects the real content correctly |

No code changes were needed — these were already handled correctly, just
untested. Coverage added in `tests/test_intake_failure_modes.py`, including
an end-to-end test confirming the unrelated-document case combines correctly
with fix #1 (uploading a recipe and then viewing `/internal/review` shows the
honest demo notice, not silent garbage).

## 3. A landing page ties the product together

Previously the experience was four separate URLs an evaluator had to already
know: `/internal/intake`, `/internal/review`, `/internal/review/progress/ui`,
`/internal/fleet/ui`. Nothing linked them.

`GET /` is now the front door: upload → review → track progress → fleet,
with the current active job (if any) and job count shown using the same
data sources the rest of the product reads from — the home page never
claims something the rest of the app doesn't back up.

See `src/repairgraph/review/home_page.py`, `api/home_routes.py`. Tests:
`tests/test_home_page.py`.

## 4. Internal jargon removed from primary surfaces

Three concrete leaks found and fixed:

- **Progress page status badges** showed raw enums (`not_started`, `pending`,
  `open`) as visible text. Now humanized ("Not Started", "Pending", "Open")
  — the fleet dashboard already did this correctly; the progress page didn't.
- **Review page blocker narrative** read "...is preventing progress on:
  session_completion, phase:4" — raw internal tokens in a sentence a reader
  is meant to understand. Now reads "...session completion, Phase 4."
  (The structured evidence list below it, `class="rr-finding-evidence"`,
  intentionally keeps raw tokens — that's a labeled technical/audit area,
  not narrative prose.)
- **Fixture vehicles' "Supplied Documents"** showed the literal internal
  storage filename `repair_procedure_quarter_panel.json`. Now shows a
  readable label: `"2025 Honda Accord — Rear Side Outer Panel Replacement
  (OEM Reference)"`.

Tests: `tests/test_surface_language.py`.

## 5. Fixed: Kia was misdetected as Hyundai

Testing the evaluator journey with a Kia document surfaced a real
classifier bug: Kia wasn't in the intake classifier's OEM vocabulary at
all — it was bucketed under the "Hyundai" pattern group (`_OEM_PATTERNS`
in `intake/classify.py`, following the same badge-consolidation pattern
used for Acura→Honda, Lexus→Toyota, Infiniti→Nissan, etc.). Since no Kia
model names were registered either, a Kia repair document was silently
mislabeled `detected_oem: "Hyundai"` with `detected_model: null` — not a
graceful "unknown," an actively wrong brand.

Fixed by giving Kia its own OEM entry and a model vocabulary (Sportage,
Sorento, Telluride, Forte, Optima, K5, Soul, Niro, Seltos, Rio, Stinger,
Carnival), matching the structure every other independently-badged brand
uses. Hyundai and Genesis detection are unchanged — Genesis remains
bucketed under Hyundai, as it was before.

The same consolidation pattern still exists for other sub-brands (Acura,
Lexus, Scion, Infiniti, Lincoln, GMC/Buick/Cadillac, Audi/Porsche, Mini,
Chrysler/Dodge/Jeep/Ram) — none of those were reported as wrong during
evaluation prep, so they weren't touched here. If an evaluator works with
one of those brands and gets an unexpected OEM label, the fix is the same
shape as this one: give it its own `_OEM_PATTERNS` entry and a
`_MODEL_PATTERNS`/`_MODEL_CANONICAL` list.

Tests: `tests/test_kia_oem_detection.py`.

## Verification

- Full test suite: 2323 passed, 1 skipped.
- Real browser (Playwright) click-through of the complete evaluator journey:
  home (no active job) → intake upload (Nissan Rogue) → home (shows active
  job) → review (no demo notice, real content) → progress (clearing a QA
  gate moves 8 open → 7) → fleet (shows the job). Zero JavaScript errors
  across the full journey.
- Kia fix verified end-to-end the same way: upload → `detected_oem: "Kia"`,
  `detected_model: "Sportage"` → review shows Kia Sportage with no demo
  notice → fleet dashboard shows the job.
