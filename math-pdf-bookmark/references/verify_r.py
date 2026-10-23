# -*- coding: utf-8 -*-
"""verify_r.py -- acceptance for ROUTE R books (text layer, re-anchored dests).

    python verify_r.py <pdf> [--sample N] [--tag NAME]

A) structure : n, level histogram, page-top dests, out-of-range, monotone,
               dirty titles (NUL / dot-leader / LaTeX)
B) ink       : every entry -- dark pixels just BELOW y (the heading) and clear
               space ABOVE it (the gap), on a 150 dpi render
C) sheets    : contact sheets of the anchored crops, 12 per sheet, labelled
               '#idx L<lvl> p<page> y=<y>  <title>'  -> READ THESE WITH YOUR EYES

Writes C:/Users/asus/_vr_<tag>.txt and C:/Users/asus/_vr_<tag>_NN.png
"""
import fitz, os, re, sys
import numpy as np

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DPI = 150.0
SC = DPI / 72.0
CTRL = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\ufffd]')
LEAD = re.compile(r'[\s.\u2024\u2026\u00b7\u2219]{2,}\s*\d+\s*$')
TEX = re.compile(r'\$\d|\\[a-zA-Z]')


def main():
    src = sys.argv[1]
    tag = re.sub(r'\W+', '', os.path.basename(src))[:20]
    if '--tag' in sys.argv:
        tag = sys.argv[sys.argv.index('--tag') + 1]
    out = []
    d = fitz.open(src)
    toc = d.get_toc(simple=False)
    n = d.page_count
    lv = {}
    top = oor = nonmono = dirty = 0
    prev = (0, 0.0)
    ents = []
    for e in toc:
        lvl, t, p = e[0], str(e[1]), e[2]
        y = e[3].get('to').y if isinstance(e[3], dict) else float(e[3] or 0)
        lv[lvl] = lv.get(lvl, 0) + 1
        if y <= 0.5:
            top += 1
        if p < 1 or p > n:
            oor += 1
        if (p, y) < prev:
            nonmono += 1
        prev = (p, y)
        if CTRL.search(t) or LEAD.search(t) or TEX.search(t):
            dirty += 1
        ents.append((lvl, t, p, y))
    out.append("=== A. structure ===")
    out.append("file=%s pages=%d bookmarks=%d" % (os.path.basename(src), n, len(toc)))
    out.append("levels=%s  page-top=%d  oor=%d  nonmono=%d  dirty-title=%d"
               % (dict(sorted(lv.items())), top, oor, nonmono, dirty))

    out.append("\n=== B. ink check (band below y dark, gap above y clear) ===")
    fails = []
    cache = {}
    for (lvl, t, p, y) in ents:
        if p < 1 or p > n:
            fails.append((lvl, t, p, y, 'oor'))
            continue
        if p not in cache:
            cache[p] = d[p - 1].get_pixmap(matrix=fitz.Matrix(SC, SC), colorspace=fitz.csGRAY)
        pm = cache[p]
        a = np.frombuffer(pm.samples, dtype=np.uint8).reshape(pm.height, pm.width)
        H = a.shape[0]
        y0 = int(max(0, min(H - 1, y * SC)))
        lo = a[min(H - 1, y0 + 3):min(H, y0 + int(16 * SC)), :].mean() / 255.0 if y0 + 3 < H else 1
        hi = a[max(0, y0 - int(14 * SC)):max(0, y0 - int(2 * SC)), :].mean() / 255.0
        dark = 1.0 - lo                      # ink just below y  -> must be > 0
        clear = 1.0 - hi                      # ink in the gap above y -> must be ~0
        if dark < 0.003 or clear > 0.02:
            fails.append((lvl, t, p, y, 'dark=%.4f gapink=%.4f' % (dark, clear)))
    out.append("ink failures: %d / %d" % (len(fails), len(ents)))
    for f in fails[:25]:
        out.append("   FAIL L%d p%d y=%.1f %r  %s" % (f[0], f[2], f[3], f[1][:40], f[4]))

    out.append("\n=== C. contact sheets ===")
    crops = []
    for i, (lvl, t, p, y) in enumerate(ents):
        if p < 1 or p > n:
            continue
        pg = d[p - 1]
        clip = fitz.Rect(0, max(0, y - 20), pg.rect.width, min(pg.rect.height, y + 62))
        pm = pg.get_pixmap(matrix=fitz.Matrix(2.2, 2.2), clip=clip)
        fp = r"C:/Users/asus/_vr_%s_c%04d.png" % (tag, i)
        pm.save(fp)
        crops.append((fp, "L%d p%d y=%.0f  %s" % (lvl, p, y, t[:58])))
    per = 12
    sheets = 0
    for s in range(0, len(crops), per):
        chunk = crops[s:s + per]
        doc = fitz.open()
        w, h = 620, 100
        pg = doc.new_page(width=w, height=per * (h + 14))
        for j, (fp, lab) in enumerate(chunk):
            y0 = j * (h + 14)
            pg.insert_text((6, y0 + 10), "#%d %s" % (s + j + 1, lab), fontsize=7.5,
                           color=(0.75, 0, 0))
            pg.insert_image(fitz.Rect(6, y0 + 13, w - 6, y0 + h + 10), filename=fp)
        sp = r"C:/Users/asus/_vr_%s_%02d.pdf" % (tag, sheets + 1)
        doc.save(sp)
        doc.close()
        q = fitz.open(sp)
        q[0].get_pixmap(matrix=fitz.Matrix(1.6, 1.6)).save(
            r"C:/Users/asus/_vr_%s_%02d.png" % (tag, sheets + 1))
        q.close()
        os.remove(sp)
        sheets += 1
    for fp, _ in crops:
        os.remove(fp)
    out.append("sheets=%d (%d rows each, %d entries) -> C:/Users/asus/_vr_%s_NN.png"
               % (sheets, per, len(crops), tag))
    with open(r"C:/Users/asus/_vr_%s.txt" % tag, 'w', encoding='utf-8') as fh:
        fh.write("\n".join(out) + "\n")
    print("\n".join(out[:6]))
    d.close()


if __name__ == '__main__':
    main()
