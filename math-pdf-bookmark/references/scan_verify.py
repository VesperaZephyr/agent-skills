# -*- coding: utf-8 -*-
"""Visual + numeric verification of the Conway GTM 159 bookmarks.

1) ink check (all 84): the rendered page must contain dark pixels inside the
   band [y, y+line-height] and must be white just above it -> the destination
   really sits on the heading line, not on the page top.
2) contact sheets: one strip per bookmark, cropped around its own y, stacked
   with the bookmark title printed next to it -> read them with your eyes.
"""
import sys, fitz
from PIL import Image, ImageDraw

sys.path.insert(0, r"C:/Users/asus")
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
SRC = (r"F:/大学/数字资源/数学/分析学/复分析/Conway/"
       r"GTM159 Functions of One Complex Variable Vol II (J.B.Conway).pdf")

d = fitz.open(SRC)
toc = d.get_toc(simple=False)
print("bookmarks:", len(toc), "pages:", d.page_count)

RANGES = d.get_page_labels()
def to_roman(n):
    vals = [(1000,'m'),(900,'cm'),(500,'d'),(400,'cd'),(100,'c'),(90,'xc'),
            (50,'l'),(40,'xl'),(10,'x'),(9,'ix'),(5,'v'),(4,'iv'),(1,'i')]
    o = ''
    for v, s in vals:
        while n >= v: o += s; n -= v
    return o
def label_of(p1):                       # p1 = 1-based physical page
    cur = None
    for r in RANGES:
        if r['startpage'] <= p1: cur = r
    if cur is None: return str(p1)
    off = p1 - cur['startpage']
    n = cur['firstpagenum'] + off
    st = cur['style']
    if st in ('r', 'R'):
        s = to_roman(n)
        return s.upper() if st == 'R' else s
    if st in ('a', 'A'):
        s = ''
        while n:
            n, r0 = divmod(n - 1, 26); s = chr(97 + r0) + s
        return s.upper() if st == 'A' else s
    return str(n)

bad = []
strips = []
for i, e in enumerate(toc):
    lvl, title, p1, dest = e[0], e[1], e[2], e[3]
    y = dest['to'].y if isinstance(dest, dict) else float(dest)
    pg = d[p1 - 1]
    H, W = pg.rect.height, pg.rect.width
    lab = "L%d p%d (printed %s) y=%.0f  %s" % (lvl, p1, label_of(p1), y, title)
    # band that must contain the heading
    a = pg.get_pixmap(dpi=72, clip=fitz.Rect(0, y, W, y + 60))
    b = pg.get_pixmap(dpi=72, clip=fitz.Rect(0, max(0, y - 55), W, y - 5))
    def dark(pix):
        s = pix.samples
        n = pix.width * pix.height
        g = pix.n
        return sum(1 for j in range(0, n * g, g) if s[j] < 128) / n
    da, db = dark(a), dark(b)
    ok = da > 0.004 and db < 0.02
    if not ok: bad.append((lab, round(da, 4), round(db, 4)))
    clip = fitz.Rect(0, max(0, y - 18), W, min(H, y + 78))
    pix = pg.get_pixmap(dpi=72, clip=clip)
    im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
    im.thumbnail((1300, 10000))
    strips.append((lab, im, ok))

print("ink-check failures: %d" % len(bad))
for x in bad: print("   ", x)

PER = 21
for s in range(0, len(strips), PER):
    grp = strips[s:s + PER]
    w = max(im.width for _, im, _ in grp) + 4
    hh = sum(im.height + 20 for _, im, _ in grp)
    sheet = Image.new('RGB', (w, hh), 'white')
    dr = ImageDraw.Draw(sheet)
    yy = 0
    for lab, im, ok in grp:
        dr.text((4, yy + 2), lab + ('' if ok else '   <<< INK FAIL'),
                fill=(200, 0, 0) if ok else (0, 0, 200))
        sheet.paste(im, (2, yy + 16))
        yy += im.height + 20
    out = r"C:/Users/asus/_cw_vfy_%d.png" % (s // PER + 1)
    sheet.save(out)
    print("sheet", out, sheet.size)

# page-label spot audit
print("\nlabel audit (physical -> reader label):")
for p in (1, 2, 6, 7, 15, 16, 17, 42, 200, 399, 406, 409, 410, 412):
    print("   p%-4d -> %s" % (p, label_of(p)))
