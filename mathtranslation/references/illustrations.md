# Mathematical illustrations: source fidelity and final-page readability

Use this workflow for a book-wide illustration repair, ordinary geometry,
curves and surfaces, vector fields, level sets, tangent/cotangent bundles,
orientation and boundary diagrams. For commutative arrow-and-node diagrams,
also follow the existing diagram audit skill. Do not recreate a mathematical
figure with image generation: exact mathematical relationships require
deterministic geometry and a published-source comparison.

For a book-wide source-vs-translation figure audit (dual inventories, full-page
pair rendering, reviewer dispatch, scripted repair and re-render verification),
read [figure-audit.md](figure-audit.md).
For executable capture commands, coordinate conventions and TikZ implementation,
read [figure-capture.md](figure-capture.md). For clean-context figure review,
read [independent-review.md](independent-review.md).

## Diagnose before selecting a drawing method

Record six distinct questions for each figure:

1. Identity: is this actually the source figure attached to this number?
2. Completeness: are all panels, labels, axes, level lines and arrows present?
3. Crop: is there foreign prose, a caption fragment, or another figure?
4. Representation: are paths/text retained, or were vectors rasterized?
5. Readability: are principal labels and fine distinctions legible at the final size?
6. Placement: does the actual book page keep the figure, caption and context usable?

Do not solve identity/completeness by increasing DPI. Do not solve a layout
problem by arbitrarily changing the mathematical drawing. When the user wants
redrawn or editable illustrations, retaining a source crop is an intermediate
reference, not fulfillment of that request.

## Independent inventories and an evidence ledger

Inventory the published PDF first, using its page images as authority. Locate
captions with text extraction, but inspect complete pages to distinguish
captions from prose references and to find unnumbered figures. Then inventory
the actual TeX input chain (including macros, appendices, exercises and inline
graphics) and the compiled PDF independently. Reconcile by identity, not count.

Suggested fields:

`id, source_sha256, physical_page_1based, printed_folio, bbox_pdf_points,
source_panels, mathematical_facts, tex_file/line, label, asset,
method, displayed_width, final_pdf_page, crop_review, final_review,
evidence, unresolved`.

Distinguish `pending`, `defect`, `repaired`, `source_issue_retained` and
`verified`. Never automatically initialize `verified` because an export ran.
Record source and output numbering from rendered PDFs/AUX, not guessed file
names. Compare neighboring figures to detect duplicate or displaced crops.
Retain original files or a timestamped backup before changing a batch.

## Build source-to-translation page pairs

For a book-wide comparison, use the reusable page-pair tool after confirming the
source PDF identity and preparing a translation placement manifest:

    python scripts/figure_page_pair_review.py SOURCE.pdf TRANSLATION.pdf --translation-placement-manifest placements.csv --out REPORT_DIR

The manifest is UTF-8 CSV with id,pdf_page; page numbers are physical,
one-based PDF pages, and repeated or continued placements get one row each.
Default caption patterns handle Fig. 2.3 and 图2.3:. Provide custom regular
expressions when the book differs. With a placement manifest, the report pairs
each source caption page with the actual figure-placement pages, including
continued panels. Without it, it uses caption pages and may miss figures that
float elsewhere. The output directory must be empty. The report contains
index.html, summary.json, caption-page-map.csv, input hashes and full-page
pair sheets. Review the sheets manually; a matched status means only that
captions and page mappings were found, not that the artwork is faithful.

Caption extraction depends on searchable PDF text. For scans, OCR or a manually
prepared mapping may be needed. After changing the PDF or manifest, regenerate
the report. Read figure-audit.md for source identity checks, coverage
reconciliation, zoom criteria and repair closure.

## Choose the representation

- **Clean source vector PDF:** faithfully reuse a cropped PDF region if its
  typography and language suit the project. PyMuPDF `show_pdf_page(..., clip=...)`
  preserves paths, glyphs, shading and transparency; render the result to confirm
  what survived. Inspect `get_drawings()`, fonts and embedded images as diagnostics.
  A PDF container can contain a bitmap, so the extension alone proves nothing.
- **Native redraw:** use ordinary TikZ/PGFPlots for editable geometry and plots,
  or `tikzcd` for commutative diagrams. Recover the mathematical specification
  independently from the printed source. Use consistent line weights, arrowheads,
  fonts and palette, but preserve geometric and orientation facts. Curves should
  come from their known functions/parameters where possible, not arbitrary
  approximations. Check front/back occlusion, dashed hidden lines, projections,
  field direction, boundary signs, level spacing and shared scales explicitly.
- **Original raster/scan:** retain the source resolution or redraw when a reliable
  specification exists. Do not upsample and claim recovered detail. If a raster
  must be used, calculate effective PPI from pixels and displayed width; increasing
  render DPI cannot recover information absent from an embedded source bitmap.
- **Mixed diagrams:** preserve vectors while keeping unavoidable embedded images;
  record the exception instead of claiming the entire image is vector.

Translation inside the figure is a separate task: do not replace mathematical
symbols when changing English labels. For vector overlays, ensure the original
text is actually removed, no line is covered, glyphs are embedded and searchable,
and the Chinese labels fit at final size. For outlined source text, native redraw
may be safer than opaque boxes. If source labels remain, disclose that scope.

## Crop candidates are not truth

Create a manifest of physical pages and manually reviewable PDF-point bounds.
Automated caption bands, graphics boxes, image boxes and white-margin trimming
are candidate generators only. Typical failure modes:

- A text block merges spatially separated labels; using its width as a prose
  classifier discards an entire left panel or a remote formula.
- The largest graphic near a caption belongs to the next figure, particularly
  with side captions, stacked figures or captions broken across math spans.
- An axis or filled rectangle extends far beyond the few text labels used to
  seed the crop. A tangent-bundle diagram can shrink to one horizontal strip.
- Cropping to the main paths omits axes, negative ticks, isolated subpanels,
  panel letters, arrow tips, superscripts or long explanatory labels.
- A caption can start with raised math above the baseline of `Fig.`; subtracting
  a fixed amount from that baseline can still retain a formula fragment.
- Bézier path boxes may include distant control points, transformed paths or
  internal clipping. A path crossing a crop boundary is a warning, not proof
  of missing visible ink. Inspect the rendered original.
- White-margin sampling can miss fine or pale strokes. Keep a small physical
  safety margin and inspect every edge at high magnification.
- Cropped PDF pages can contain text or paths outside their visible page box.
  When placing a crop in TeX, request clipping (`\includegraphics[...,clip]{...}`)
  and verify the final page; a crop that looks clean when rendered alone may leak
  out-of-box content in the compiled book.

For a side caption, isolate the correct horizontal region; expanding to a
full-page horizontal band reintroduces the caption. For two figures on one
page, compare top/bottom or left/right source regions separately. Store manual
overrides in the same manifest as the export source so a later script cannot
silently overwrite a repaired crop.

## Size from the content, not a universal percentage

### Reusable size-review tool

Run the tool against a UTF-8 CSV manifest and the *final compiled PDF*:

```text
python <mathtranslation-skill>/scripts/figure_size_review.py MANIFEST.csv --book BOOK.pdf --out REPORT_DIR --label-threshold-pt 8 --height-limit-mm 195
```

The manifest uses `id,asset,width_mm` and optional `pdf_page,asset_page`; asset
paths are relative to the manifest. `width_mm` is the declared or expected size.
When a top-level or nested PDF vector form can be matched by its asset bounds and
page content, the report measures rendered width and height in the final PDF and
scales extracted-text estimates to that measured width. If placement is unmatched
or has multiple possible sizes, it flags manual review and uses the declared
width for text estimates. `pdf_page` is the physical PDF page, starting at 1;
omit it when uncertain. One row describes one occurrence or panel.

The output directory must be new or empty. It contains `index.html`,
`summary.json`, measurements in CSV/JSON, per-asset previews and per-page previews.
With `--book`, it also creates numbered `all-pages-*.png` sheets for every unique
figure-bearing physical page and `focus-pages-*.png` sheets for pages with at
least one specific review signal. A generic “manual review required” row or a
missing page number does not by itself put a page on a focus sheet. Start with
the all-page sheets to scan page flow, then use focus sheets to prioritize closer
inspection, and open the individual full-page previews for decisions. Several
figures may share one page; a page or row can carry multiple overlapping signals.
The HTML report links both sheet groups and the individual asset/page evidence.

`summary.json` records SHA256 hashes of the exact manifest and book, the active
screening thresholds, counts, page numbers, signal totals and generated sheet
names. If either input PDF or manifest changes, rerun the report so its previews
and measurements cannot be mistaken for evidence from the new input. Optional
`--label-threshold-pt` and `--height-limit-mm` only create review candidates; do
not read them as universal pass limits. The tool never changes the book, assigns
pass status or judges visual crowding; image height excludes caption and prose.
Extracted text spans may not be principal labels. Direct raster files get an
effective PPI estimate; embedded raster regions inside PDFs are not assessed.
Confirm the actual page, caption, crop, labels and local page space manually. An
input error gives exit status 1; invalid setup gives 2. Requires Python and
PyMuPDF.

In this Fortney project, the final pass mapped 261 image placements for 256
numbered figures to 211 physical pages (figure 11.34 has three panels; figures
3.16, 5.15 and 5.16 were each divided into two continued panels). Reviewing the
full-page contact sheets and 66 flagged pages exposed two different cases:
figures 2.26, 7.5 and 11.23 had extracted-text medians below 8 pt but occupied
nearly the full text width and remained legible on enlarged page renders; by
contrast, the stacked panels in 3.16, 5.15 and 5.16 were being made uncomfortably
small by the page-height limit. Splitting those independent upper/lower panels
onto continued pages let each use 1.12 `\linewidth`, with measured widths near
179.2 mm and estimated medians of 8.53, 8.42 and 9.26 pt. Figure 5.15's lower
PDF crop contained a stray axis label outside its page box; that text and its
vector stroke were removed, and TeX placement uses explicit clipping. Every crop
edge still needs a rendered-page check. The extra pages were a deliberate
readability tradeoff, not a generic rule to split tall art.

Other verified size decisions in the same book: figure 10.3 occupied only 0.436
line width beside a larger figure despite ample float-page space, and figure
11.14 occupied 0.402 line width within prose; increasing them to 0.68 and 0.60
kept each on its page. Figure 3.11 used unused margins on a standalone float page
to reach 1.12 line width. Figure 5.29's three independent panels were recomposed
as two above and one below, while figure 11.34 changed from a horizontal strip to
two rows. Decide from the source relationships, actual rendered scale, caption
height, neighboring content and resulting page flow. The size script reports
rendered dimensions for matched vector forms and scales extracted-label estimates
to the measured placement; unmatched cases use the declared width and are flagged.
It does not score crowding or readability; inspect full pages at normal reading
scale and enlarge questionable regions manually.


Measure the final principal-label size and the available figure plus caption
height. Prefer `width=<fraction>\linewidth` so nested minipages behave correctly.
Also inspect the artwork's own content bounds: a full-width asset can still look
small when it contains large internal whitespace, while a naturally narrow plot
may already be readable. Do not prescribe 0.40–0.80 for every figure or clamp
narrow/tall plots to one minimum. PDF-point coordinates and native drawing
coordinates can use physical units; those are distinct from choosing the figure's
displayed width.

Aim for principal labels near the book's small-text size; about 8–9 pt is a
useful starting point in an 11-pt book, not a universal pass criterion. Inspect
subscripts separately. A median over extracted spans can be dominated by
subscripts or omit outlined labels; use it to flag candidates, not certify
legibility. A crisp vector label can still be much too small.

Preserve aspect ratio. If width and height are both maximum constraints, use
`keepaspectratio`. Never stretch width and height independently. Reserve room
for the actual caption, including long translations.

For independent panels, reflow a very wide strip into two rows, or stack two
panels when it substantially improves label size. Preserve panel order and
identifiers. Never split a mapping diagram across an essential connecting arrow,
change common scales independently or drop connecting annotations. If a dense
figure cannot fit legibly, use a properly continued figure or justified larger
page layout instead of shrinking indefinitely. Preserve figure numbering and
cross-reference targets when introducing continued panels.

Use `\centering` within figures. Keep `\caption` before `\label`; preserve
existing labels and counters. Avoid wrapfigure where Chinese prose, display
math and theorem environments collide; choose standalone floats or a deliberate
minipage composition and inspect the resulting page flow.

### Size and placement regression example

A size estimate is a prompt to inspect the final page, not a verdict. Compare the
figure and caption with local white space, nearby prose and other figures. If a
page has room, use it; if page height or surrounding text forces an image too
small, move it to a suitable float page, reflow independent panels, or use a
continued figure. Split only where the mathematics remains clear without a shared
frame; preserve panel labels, order, common scales, connecting annotations and
references. For one connected diagram, try a justified larger page or a faithful
redraw before accepting cramped labels. Check the added-page and whitespace cost.

In the Fortney book below, figures 2.15, 2.16 and 5.20 had generous margins on
standalone pages, so their widths increased from 0.96 to 1.12 `\linewidth`.
Figures 3.11, 10.3 and 11.14 also used available page space: 0.88 to 1.12,
0.436 to 0.68, and 0.402 to 0.60 `\linewidth`, respectively. They remained on
their pages without adding overfull boxes. Figures 2.26, 7.5 and 11.23 were
expanded to 1.12 `\linewidth`; their extracted-text medians remained below 8 pt,
but enlarged full-page renders showed the drawings and key labels were readable,
so no further resizing was warranted.

Figure 5.29 had three independent vector panels. Recompose them as two above and
one below at 1.12 `\linewidth`, preserving all source labels and panel order;
this improved the estimated median label size to 9.69 pt, but required a separate
float page. Figure 11.34 similarly changed from a horizontal strip to a two-row
layout. Both figures needed nearby prose updated to match panel positions. In
11.34, a local float barrier restored reading order but left figures 11.33 and
11.34 on separate float pages. Compare this whitespace and pagination cost with
the readability gain. Forcing an enlarged figure with `[H]` in this document let
the caption extend beyond the page even though compilation succeeded.

The final page-pressure report mapped 261 placements to 211 physical pages; 66
pages had at least one automated size, extractability or height flag (48 low
text-size medians, 23 without extractable text and 2 over 195 mm high; categories
overlap). The flags are review candidates, not defects. In contrast to the earlier
height-only decision, inspection of figures 3.16, 5.15 and 5.16 showed that each
contained two vertically stacked panels that could be understood separately.
They were continued across pages at 1.12 `\linewidth`, rather than compressed to
fit one page; the first panel retains the numbered caption and label, and the
second has a continuation caption without incrementing the counter. Figure 5.15
also needed careful seam masking because its source panels overlap. Figure 2.26
is a dense connected diagram and stays intact. Figures 2.26, 7.5 and 11.23 show
why a low extracted-text median alone must not trigger another size change: their
final full-width page renders remain readable. Figure 8.3 is 199.4 mm high, yet
its five stacked panels remain comfortably legible on the complete page. The
report median is scaled to measured final width only when the vector placement
matches; subscripts, outlined text and non-label spans can skew it. Unmatched
placements use declared width and are flagged. None of these estimates judges
crowding or certifies legibility; inspect the complete page and neighbors at
realistic reading scale.

### Wrapping regression probes

Before applying a wrap layout to an actual book, use the actual document class,
font setup, figure, caption and neighboring content in controlled test builds.
Test uninterrupted prose; displays (including numbered and wide formulas);
theorem/proof and question environments; short and nested lists; section
boundaries; and natural page breaks as well as explicit page breaks. A small
passing example does not prove a class of environments is safe.

In this Fortney project, a short paragraph let the wrap continue into the next
section, and an explicit page break left subsequent text in a narrow column
on the next page after the figure had ended. Both compiled successfully and
reported no wrap-specific warning. Several other short probes, including one
display, a theorem and a list, rendered without collision; that observation
does not certify more complex or naturally paginated examples. Inspect every
affected complete page and its neighbors, not just the crop or TeX log.

For a candidate in the real book, compare the baseline and final PDF: relation
to the discussed paragraph, image and caption bounds, label sizes at print size,
line width after the wrap, page breaks and section/theorem indentation, figure
number/anchor and actual cross-reference targets. Compare diagnostics to a
clean baseline and preserve earlier unrelated warnings. A 2026 example moved
figure 10.1 next to its paragraph at 0.41 line width, retaining the original
vector asset and caption; this is one verified case, not a global width rule.


## Verification that separates its claims

1. Compare the full source page with each crop, including every independent
   panel. Numbered contact sheets help cover a large inventory but cannot resolve
   tiny labels or subtle arrow styles; enlarge questionable regions.
2. Render each exported asset and compare it with the designated original region.
   For composed panels, compare each panel with its own original clip. Pixel
   differences detect export damage, but cannot validate a wrong input clip.
3. Compile the actual book until references and page positions stabilize. Inspect
   errors, missing glyphs, missing/duplicate references, oversized floats and
   overfull boxes. Compare pre-existing warnings with a saved baseline.
4. Map every figure label to its actual page and region in the final PDF. Verify
   asset inclusion/transforms and rendered content; do not assume the page from
   a previous build. Inspect each final figure/caption region, plus complete pages
   for dense, tall, reflowed and repaired figures and chapter boundaries.
5. Reconcile source identity, asset identity, rendered numbering, caption and
   reference target. Retain unresolved items with their exact figure/page.

Export completed, mathematical comparison completed and final-page visual review
completed are separate statuses. A successful compile or a high image similarity
score is not a substitute for any of the other checks.

## Demonstrated book-wide failure case

In Fortney's *A Visual Introduction to Differential Forms and Calculus on
Manifolds*, the existing translated project had 256 captions, 256 files and
no missing file paths, yet source comparison found severe defects: 1.8 retained
only the lower region, 2.17 retained a narrow strip of a tangent bundle, 7.3
used the region of 7.4, 9.9 used the next field diagram, 11.12 duplicated 11.11,
and 11.14 used the horizontal 11.15 instead of its vertical boundary diagram.
Other crops dropped negative level lines and isolated panels or included prose.
This case motivates identity/panel checks and final-size verification; it does
not justify reusing this book's crop coordinates or assuming every PDF has the
same failures.
