# -*- coding: utf-8 -*-
"""Measure, per file, how much set_toc(numeric y) shifts the landing point.

    landing(page-rect coords) = numeric_input + shift(page)
    shift(page)               = mediabox.y1 - cropbox.y1      <-- the empirical law

Usage:  python shift_probe.py <a.pdf> [b.pdf ...]
Writes  shift_probe.txt (utf-8) next to nothing -- it prints ASCII only.
Never touches the originals: each file is copied to a scratch PDF first.
"""
import os
import re
import shutil
import sys

import fitz

TMP = r"C:/Users/asus/_shiftprobe.pdf"
REP = r"C:/Users/asus/_shiftprobe.txt"


def probe(src):
    lines = []
    if not os.path.exists(src):
        return [u"MISSING " + src.encode("utf-8", "replace").decode("ascii", "replace")]
    shutil.copy2(src, TMP)
    d = fitz.open(TMP)
    n = d.page_count
    shifts = sorted({round(d[i].mediabox.y1 - d[i].cropbox.y1, 3) for i in range(n)})
    rots = sorted({d[i].rotation for i in range(n)})
    lines.append(u"pages=%d rotations=%s distinct_shifts=%s" % (n, rots, shifts))
    for pn in (6, max(2, n // 2), n - 1):
        d.set_toc([[1, "probe", pn, 100.0]])
        xr = d.get_toc(simple=False)[0][3]['xref']
        m = re.search(r'/XYZ\s+([-\d.]+)\s+([-\d.]+)', d.xref_object(xr, compressed=True))
        land = d.get_toc(simple=False)[0][3]['to'].y
        pg = d[pn - 1]
        lines.append(u"  p%-5d rect=(%.1f,%.1f) crop.y1=%.2f media.y1=%.2f"
                     u"  input=100 -> land=%.2f (shift %+.2f, formula %+.2f) raw_y=%s"
                     % (pn, pg.rect.width, pg.rect.height, pg.cropbox.y1, pg.mediabox.y1,
                        land, land - 100.0, pg.mediabox.y1 - pg.cropbox.y1,
                        m.group(2) if m else u'?'))
    d.close()
    os.remove(TMP)
    return lines


def main():
    out = []
    for src in sys.argv[1:]:
        out.append(u"== " + src)
        out.extend(probe(src))
    txt = u"\n".join(out) + u"\n"
    with open(REP, "w", encoding="utf-8") as f:
        f.write(txt)
    sys.stdout.write(txt.encode("ascii", "replace").decode("ascii") + "\n")
    sys.stdout.write("full report: %s\n" % REP)


if __name__ == "__main__":
    main()
