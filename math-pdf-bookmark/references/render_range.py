# -*- coding: utf-8 -*-
"""render_range.py -- render a page range as `page_%04d.png` for the OCR dump.

    python render_range.py <pdf> <out_dir> <start> <end> [dpi]

Used by ROUTE P-IMG (`pureimage_build.py`) and ROUTE C: `winocr.ps1` sorts
`page_*.png` by NAME, so the 4-digit padded index IS the physical page number --
never renumber it, or every y in the dump lands on the wrong page.

**Probe the native dpi, do not guess.**  The page's embedded image is the scan;
compare its pixel size with the page rect:

    python -c "import fitz;d=fitz.open(r'<pdf>');p=d[0];w,h=p.get_images()[0][2:4];\\
               print(p.rect,w,h, w/p.rect.width*72)"

stein 中译本: rect 485.33 x 720.81 pt, page image 1536 x 2300 px -> 1536/485.33*72
= **228 dpi** (and 2300/720.81*72 = 229.8, the scanner rounds per axis).  Rendering
at 300 instead of the native 228 resamples the scan (blurrier OCR) and, worse, if
you then use SC = 72/300 on boxes measured at 228 every y is off by a factor of
1.31 -- "looks right, whole book is wrong".  Also note `get_images()` may list a
small logo/decoration first; pick the image whose aspect ratio matches the page.
"""
import os
import sys

import fitz


def main():
    if len(sys.argv) < 5:
        sys.exit(__doc__)
    pdf, out_dir = sys.argv[1], sys.argv[2]
    a, b = int(sys.argv[3]), int(sys.argv[4])
    dpi = int(sys.argv[5]) if len(sys.argv) > 5 else 228
    os.makedirs(out_dir, exist_ok=True)
    d = fitz.open(pdf)
    z = dpi / 72.0
    n = 0
    for p in range(max(1, a), min(d.page_count, b) + 1):
        fn = os.path.join(out_dir, "page_%04d.png" % p)
        if os.path.exists(fn):
            continue                      # resumable: rerun after a crash
        d[p - 1].get_pixmap(matrix=fitz.Matrix(z, z)).save(fn)
        n += 1
    d.close()
    print("rendered %d new pages (%d-%d) at %d dpi -> %s" % (n, a, b, dpi, out_dir))


if __name__ == '__main__':
    main()
