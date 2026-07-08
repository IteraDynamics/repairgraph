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

## Known gap found during evaluation, not fixed here

Testing the evaluator journey with a **Kia** vehicle surfaced a real
classifier bug: Kia isn't in the intake classifier's known-OEM vocabulary,
and the document was misdetected as **Hyundai** with no model — a silent
wrong-brand misclassification, not a graceful "unknown." This is a
classifier-accuracy gap (`intake/classify.py`'s OEM pattern list), separate
from the four trust/UX issues this pass addressed. Worth fixing before an
evaluator who works on Kia, Mazda, or other brands outside the current
pattern list tries this — but out of scope here since it's an accuracy
problem, not a trust/honesty one.

## Verification

- Full test suite: 2313 passed, 1 skipped.
- Real browser (Playwright) click-through of the complete evaluator journey:
  home (no active job) → intake upload (Nissan Rogue) → home (shows active
  job) → review (no demo notice, real content) → progress (clearing a QA
  gate moves 8 open → 7) → fleet (shows the job). Zero JavaScript errors
  across the full journey.
