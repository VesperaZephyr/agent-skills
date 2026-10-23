# -*- coding: utf-8 -*-
"""Visual + structural acceptance for the rebuilt 王晓光《101复变函数》 bookmarks.

A) structure : count, levels, dest y > 0.5 (never page-top), page range, monotone,
               clean titles (no NUL / dot-leader / escape residue)
B) labels    : reader page number == printed folio (OCR folio audit, all 385 body pp)
C) ink       : per entry, dark pixels in [y+2, y+16] (the heading itself) and
               white in [y-14, y-2] (the gap above it)
D) sheets    : contact sheets of the anchored crops, 12 per page, labelled #idx p/y

Writes C:/Users/asus/_w101_verify.txt and C:/Users/asus/_w101_sheet_NN.png

TEMPLATE (Phase 6 acceptance).  Re-point SRC / OUT / the crop+sheet prefixes, and the
OCR dump used by part B's folio audit.  D is the part you must actually LOOK at:
read every sheet with the Read tool -- crop filenames have to be unique per entry or
PyMuPDF's image cache makes all sheets show the same picture.
"""
import os, re, sys, glob
import fitz
import numpy as np

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
SRC = (r"F:/大学/数字资源/数学/分析学/复分析/"
       r"101复变函数 (王晓光).pdf")
OUT = r"C:/Users/asus/_w101_verify.txt"
DPI = 200
SC = 72.0 / DPI
K = 16
ROMAN = [(1000, 'm'), (900, 'cm'), (500, 'd'), (400, 'cd'), (100, 'c'),
         (90, 'xc'), (50, 'l'), (40, 'xl'), (10, 'x'), (9, 'ix'),
         (5, 'v'), (4, 'iv'), (1, 'i')]


def to_roman(n):
    s = ''
    for v, sym in ROMAN:
        while n >= v:
            s += sym
            n -= v
    return s


def to_alpha(n):
    s = ''
    while True:
        n, r = divmod(n - 1, 26)
        s = chr(ord('a') + r) + s
        if not n:
            return s


def load_folios():
    f, cur = {}, None
    for fn in (r"C:/Users/asus/_w101_ocr_a.txt", r"C:/Users/asus/_w101_ocr_b.txt"):
        for raw in open(fn, encoding='utf-8-sig', errors='ignore'):
            l = raw.rstrip("\n")
            if l.startswith('#####'):
                m = re.search(r'page_(\d+)', l)
                cur = int(m.group(1)) if m else None
                continue
            if cur is None:
                continue
            p = l.split('\t')
            if len(p) < 5:
                continue
            try:
                y, h = int(p[0]) * SC, int(p[3]) * SC
            except ValueError:
                continue
            t = re.sub(r'\s+', '', p[4])
            if y < 60 and h <= 7.6 and re.fullmatch(r'\d{1,3}', t):
                f.setdefault(cur, int(t))
    return f


def main():
    fh = open(OUT, 'w', encoding='utf-8')
    d = fitz.open(SRC)
    toc = d.get_toc(simple=False)
    n = d.page_count
    fh.write("=== A. structure ===\npages=%d bookmarks=%d\n" % (n, len(toc)))
    bad = []
    cur = 0
    for i, e in enumerate(toc):
        lv, t, p, dest = e[0], e[1], e[2], e[3]
        y = dest.get('to').y if isinstance(dest, dict) and dest.get('to') else None
        if lv not in (1, 2, 3):
            bad.append((i, 'level', t))
        if not (1 <= p <= n):
            bad.append((i, 'range', t))
        if y is None or y <= 0.5:
            bad.append((i, 'page-top', t))
        if p < cur:
            bad.append((i, 'backwards %d<%d' % (p, cur), t))
        cur = max(cur, p)
        if re.search(r'[\x00-\x08\ufffd]|\\u[0-9a-f]{4}|\u2026|\u00b7\u00b7', t):
            bad.append((i, 'dirty title', repr(t)))
        if re.search(r'\.{3,}\s*\d+\s*$', t):
            bad.append((i, 'leader', t))
    lv1 = sum(1 for e in toc if e[0] == 1)
    lv2 = sum(1 for e in toc if e[0] == 2)
    lv3 = sum(1 for e in toc if e[0] == 3)
    tops = sum(1 for e in toc
               if (e[3].get('to').y if isinstance(e[3], dict) else 9) <= 0.5)
    fh.write("levels 1/2/3 = %d/%d/%d   page-top dests = %d   defects = %d\n"
             % (lv1, lv2, lv3, tops, len(bad)))
    for b in bad[:40]:
        fh.write("  BAD %s\n" % (b,))

    fh.write("\n=== B. page labels vs printed folio ===\n")
    rngs = d.get_page_labels()

    def label_of(p):
        sel = None
        for r in rngs:
            if p >= r['startpage']:
                sel = r
        if not sel:
            return '?'
        k = p - sel['startpage'] + sel['firstpagenum']
        st = sel['style']
        if st in ('D', 'd'):
            return str(k)
        if st in ('r', 'R'):
            s = to_roman(k)
            return s.upper() if st == 'R' else s
        if st in ('a', 'A'):
            s = to_alpha(k)
            return s.upper() if st == 'A' else s
        return str(k)

    for p in (1, 2, 8, 9, 16, 17, 18, 107, 241, 400, 401, 402, 405):
        fh.write("  p%-4d -> label %s\n" % (p, label_of(p)))
    fol = load_folios()
    hit = mis = 0
    for p, f in sorted(fol.items()):
        if not (17 <= p <= 401):
            continue
        if label_of(p) == str(f):
            hit += 1
        else:
            mis += 1
            fh.write("  MISMATCH p%d printed folio %s label %s\n"
                     % (p, f, label_of(p)))
    fh.write("  folio agreement: %d match, %d mismatch (of %d pages with a folio)\n"
             % (hit, mis, hit + mis))

    fh.write("\n=== C. ink check (heading band vs gap above) ===\n")
    fails = []
    for i, e in enumerate(toc):
        lv, t, p, dest = e[0], e[1], e[2], e[3]
        y = dest['to'].y
        pg = d[p - 1]
        w = pg.rect.width
        h = pg.rect.height

        def dens(y0, y1):
            y0, y1 = max(0, y0), min(h, y1)
            if y1 - y0 < 1:
                return 0.0
            pix = pg.get_pixmap(matrix=fitz.Matrix(2, 2),
                                clip=fitz.Rect(20, y0, w - 20, y1),
                                colorspace=fitz.csGRAY)
            a = np.frombuffer(pix.samples, dtype=np.uint8)
            return float((a < 128).mean())

        ink = dens(y + 2, y + 16)
        gap = dens(y - 14, y - 2)
        if ink < 0.003 or gap > 0.02:
            fails.append((i + 1, p, round(y, 1), round(ink, 4), round(gap, 4), t))
    fh.write("ink failures: %d / %d\n" % (len(fails), len(toc)))
    for f in fails:
        fh.write("  INK #%d p%d y=%s ink=%s gap=%s | %s\n" % f)

    fh.write("\n=== D. contact sheets ===\n")
    for old in glob.glob(r"C:/Users/asus/_w101_sheet_*.png"):
        os.remove(old)
    rows = 12
    per = 6
    sheet, idx = 0, 0
    tmp = r"C:/Users/asus/_w101_crop.png"
    cur_sheet = None
    sheet_rows = []
    crops = []
    def flush(rows_, num):
        out = fitz.open()
        op = out.new_page(width=612, height=len(rows_) * 66 + 20)
        yy = 10
        for (k, pp, yv, f, _) in rows_:
            op.insert_image(fitz.Rect(70, yy, 600, yy + 60), filename=f,
                            keep_proportion=True)
            op.insert_text((8, yy + 26), "#%d" % k, fontsize=7)
            op.insert_text((8, yy + 36), "p%d" % pp, fontsize=7)
            op.insert_text((8, yy + 46), "%.0f" % yv, fontsize=7)
            yy += 66
        pdfp = r"C:/Users/asus/_w101_sheet_%02d.pdf" % num
        pngp = r"C:/Users/asus/_w101_sheet_%02d.png" % num
        out.save(pdfp)
        out.close()
        s = fitz.open(pdfp)
        s[0].get_pixmap(matrix=fitz.Matrix(2, 2)).save(pngp)
        s.close()
        os.remove(pdfp)

    for i, e in enumerate(toc):
        t, p, y = e[1], e[2], e[3]['to'].y
        pg = d[p - 1]
        r = fitz.Rect(24, max(0, y - 16), pg.rect.width - 24, y + 24)
        pix = pg.get_pixmap(matrix=fitz.Matrix(1.6, 1.6), clip=r)
        f = r"C:/Users/asus/_w101_crop_%04d.png" % (i + 1)
        pix.save(f)
        crops.append(f)
        sheet_rows.append((i + 1, p, round(y, 1), f, 0))
        if len(sheet_rows) == rows:
            idx += 1
            flush(sheet_rows, idx)
            sheet_rows = []
    if sheet_rows:
        idx += 1
        flush(sheet_rows, idx)
    for f in crops:
        os.remove(f)
    fh.write("sheets: %d (%d rows each)\n" % (idx, rows))
    fh.close()
    d.close()
    print("verify ->", OUT)


if __name__ == '__main__':
    main()
