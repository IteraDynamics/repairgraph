# Content Extraction

Deterministic, rule-based extraction of structured procedure facts from
uploaded OEM document text. This is the layer that makes an intake-derived
vehicle produce a *rich* review — actions, topology, materials, work package —
instead of the near-empty classification-only projection.

No OCR, no ML, no LLMs. The extractor pattern-matches the text the intake
classifier already reads (including the PDF text layer via pdftotext) and
records only what the document states. If the text does not say it, the fact
does not exist.

## Pipeline position

```
upload → classify (reads text) ──► extract_document_facts(text)
                                          │
                              IntakeFile.extracted_facts
                                          │
              normalizer merges facts across files, strips title noise
                                          │
        data/normalized/<oem>/<year>_<model>/  (procedure + structure JSON)
                                          │
                 compiler → topology, state, review, work package
```

## What is extracted

| Fact | Example source text | Output |
| --- | --- | --- |
| Components | "the rear pillar gutter" | `rear_pillar_gutter` (→ structure_nodes) |
| Dependencies | "Replace the wheel arch separator." / "inspect X for damage" | `{type: replace_component / inspect_if_damaged, target}` |
| Spatial relationships | "X is adjacent to Y", "X is welded to Y" | `{source, relationship: adjacent_to / joined_to, target}` |
| Sectioning | "make the cut along the quarter panel, 30 mm from the seam" | `{zone, description, dimension_mm}` |
| Joining methods | "8 spot welds", "MIG brazing required" | `{method, count?}` |
| Corrosion | "seam sealer", "cavity wax", "weld-through primer" | canonical requirement IDs |
| Materials | "1470 MPa hot-stamped steel", "0.65 mm sheet, zinc-coated" | `{component, tensile_strength_mpa, classification, thickness_mm, zinc_plated}` |
| Repair notes | sentences with warning / caution / must / do not | verbatim strings |

Material classification thresholds follow the fixture convention:
≥980 MPa → UHSS, ≥340 MPa → HSS, below → mild_steel. A 1470 MPa stiffener in
an uploaded document therefore surfaces as a UHSS zone in the review, with the
same joining-compliance implications as fixture data.

## Component recognition

A component is up to three qualifier words ending in a structural noun
(panel, separator, stiffener, rail, gutter, pillar, sill, flange, ...).
Three guards keep this precise:

- **Stopword/junk filtering** — phrases containing verbs, prepositions,
  units, or brand names are rejected ("inspect the rear pillar" is not a
  component).
- **Retry scanning** — when a greedy match is rejected, scanning re-enters
  the span one word later, so "inspect the rear pillar gutter" still yields
  `rear_pillar_gutter`.
- **Line-wrap joining** — single newlines (PDF hard wraps) are joined before
  sentence splitting so "wheel arch\nseparator" survives.

Names are normalized to snake_case and passed through the taxonomy alias
table, so intake-derived and fixture procedures share a vocabulary.

The normalizer additionally strips **vehicle-title noise**: extracted
"components" containing the detected OEM or model tokens (e.g.
`altima_quarter_panel` from a document heading) are removed along with any
facts referencing them.

## Trust semantics

- Every extracted fact carries an evidence object with the exact source
  snippet (`source_type: "document_text"`, `requires_oem_verification: true`).
- Empty output means the document did not state the fact — nothing is
  inferred from role classification, corpus patterns, or defaults at this
  layer. (Classification evidence phrases remain as a fallback for joining
  and corrosion IDs only, unioned with extracted facts.)
- Extraction failures never break intake: errors collapse to "no facts" and
  classification proceeds.
- Authored fixtures are still never overwritten by intake normalization.

## Known v0 limitations

- English-language pattern rules tuned to collision-repair phrasing.
- Very long compound names (≥4 qualifiers, e.g. "side sill extension end
  flange") split into two components.
- Counts are only captured when the number directly precedes the method
  ("8 spot welds").
- Tables, figures, and callout graphics in PDFs are invisible — only the
  text layer is read.

All outputs are advisory and require verification by a qualified technician
against the applicable OEM procedures.
