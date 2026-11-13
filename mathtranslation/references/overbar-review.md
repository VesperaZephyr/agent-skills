# Review overbars and the objects they cover

Use this procedure when source fidelity review involves closure, extension,
conjugation or other overloaded overbar notation. Published page images are
the content authority; OCR and PDF text extraction can omit or shift bars.

1. Work source-first: record every visible bar and exactly what it covers on
   the relevant original page. Determine its meaning from definitions and
   context: topological closure (including the topology), zero extension,
   complex conjugate, average, or another defined operation. Do not infer
   meaning solely from the glyph or TeX command.
2. Map each source occurrence to translation TeX and final PDF, including
   repeated occurrences in derivative identities, integrals, convolution and
   support estimates. Compare entire scope: e.g. closure of a sum versus sum
   of closures, complement of a closure versus complement, and a bar over a
   product or derivative sum versus one factor. Check open/closed balls,
   domains, endpoints and quantifiers independently. A single formula may use
   several meanings of overbar.
3. Optionally run `python scripts/inventory_overbars.py chapters -o overbars.csv`
   (using the skill's script path and a project-specific output path). This
   read-only locator records explicit `\bar`, `\overline`, `\widebar`
   occurrences, their arguments, positions, file hashes and empty fields for
   source evidence, meaning and verdict. Check incomplete arguments manually.
   It is not a TeX interpreter: custom macros, verbatim, commented-out blocks,
   macro expansion and source-PDF bars need separate attention. It cannot find
   a bar entirely absent from the translation, determine meaning, compare page
   images, or certify fidelity. Inventory the original independently.
4. Record source page/region, target file/line and PDF page, exact object,
   meaning, finding, repair status and evidence. Separate source errors from
   translation errors; retain or correct a suspected source error according to
   the skill's source-authority policy and document the reasoning.
5. After repairs, rebuild with the actual project pipeline, inspect the final
   affected PDF pages against the source image, and compare with the previous
   PDF where useful. State the verified scope and unresolved candidates.
