# Targeted translation-fidelity checks

Use these candidate checks alongside the source-first unit mapping in
[forensic-review.md](forensic-review.md), not as a replacement for it. Establish
the original edition and compare page images; OCR and extracted text are aids.
Compare by section, statement and content anchors rather than assuming a fixed
page offset. Record unmatched source and translation material separately.

## Structure and navigation

- Compare chapter and section headings and exercise groups with the original
  contents and body; a plausible page count and working references do not show
  that all sections or visible exercise headings exist. Check whether each
  heading present in the original is actually visible and, where required by
  the project, has a correct TOC entry and link destination.
- Inspect untranslated headings independently of body prose. Mathematical
  notation, names, quotations and intentional editorial material may remain in
  a foreign language. Classify each candidate in context.
- Follow [hardref-completeness.md](hardref-completeness.md) for unlinked prose
  references, including mixed lists and front/back matter. The printed number is
  AUX field 1; an anchor in field 4 is not a substitute. Parse nested groups,
  handle `<label>@cref`, and investigate collisions and target type rather than
  inferring a unique target from number shape or a project-specific counter.
- Verify the index file actually read by the final LaTeX run is the file written
  by the index processor. Count indented as well as unindented index items; a
  suspicious zero may be a faulty measurement. Inspect printed pages and links.
  Check missing glyphs including in index display entries, duplicate labels,
  undefined references and font-shape warnings in the final log.

## Captions and generated material

Map each original figure caption to its translation, including all original
sentences, notation and cross-references. Compare meaning and scope; locate and
adjudicate omitted or added claims, including plausible explanatory tails. Do
not demand word-for-word Chinese, remove original sentences merely for length,
or remove an intentional translator addition without considering the user's
policy. Distinguish caption text from nearby legitimate body text; check the
individual caption, not a whole-file search for a phrase. Inspect original and
final page images, enlarging the crop when glyphs are unclear. Audit figure
geometry, labels, size and placement independently of caption wording.

When captions or chapter TeX are generated, identify the authoritative source
and build pipeline first. Apply a confirmed correction at the right source and
regenerate or synchronize the output as the project requires; verify the
generated and rendered caption and prevent a later regeneration reverting it.
Use brace-aware extraction for candidate captions, while checking custom macros,
optional arguments and unlabelled captions manually.

## Symbols, English, and OCR candidates

- Inventory project-defined operators and compare each suspect spelling to the
  original and the project's actual macros. For example, `\operatorname{Fr}` or
  `\operatorname{N}` may be an error in a project using `\Frob` or `\Nm`, but
  these spellings are not universally wrong. Do not rewrite a shared macro or
  impose a specific book's conventions on another project.
- Compare fraktur letters, subscripts, degrees, exponents and number-theoretic
  symbols at corresponding statements. Whole-book counts can locate suspicious
  absences only when source and translation scopes match; a high count mismatch
  is not itself proof, and a singleton OCR hit is not automatically an artifact.
  Check source-page images and local context, including cases where OCR confuses
  `\Re` with a fraktur letter or inserts spaces in command arguments.
- Search residual structural words in headings and body, but distinguish
  bibliographic titles, quotations, translator notes, comments, verbatim and
  math from genuinely untranslated prose. Regex exclusions can hide valid hits
  and disrupt line numbers; validate candidate positions against the file.
- Formula-cluster comparison is a discovery aid only. Normalizing away fonts,
  braces, macros or whitespace can erase mathematically meaningful differences;
  different TeX encodings may also be equivalent. Global or local regex math
  extraction can both fail on nested macros, comments or malformed delimiters.
  Confirm each candidate on the source page and rendered translation; never
  claim formula or sentence coverage from a clean scan.

Preserve the project's encoding and line endings during edits. Keep candidate
results, source-page evidence, disposition, and final build/visual verification
separate. Use the project's actual build commands and report the audited scope.
