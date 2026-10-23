# -*- coding: utf-8 -*-
"""_sheet.py -- contact sheets for a CHOSEN subset of bookmarks.

    python _sheet.py <pdf> <tag> <idxfile>          # idxfile: 1-based bm index per line

Crops y-24 .. y+64 around every chosen destination, 12 per sheet, labelled with
the bookmark title, so the eye can decide whether the jump lands on the heading.
"""
import fitz, os, re, sys

sys.stdout.reconfigure(encoding='utf-8', errors='replace')
src, tag, idxf = sys.argv[1], sys.argv[2], sys.argv[3]
idxs = [int(x) for x in re.findall(r'\d+', open(idxf).read())]
d = fitz.open(src)
toc = d.get_toc(simple=False)
crops = []
for i in idxs:
    e = toc[i - 1]
    lvl, t, p = e[0], str(e[1]), e[2]
    y = e[3].get('to').y if isinstance(e[3], dict) else float(e[3] or 0)
    pg = d[p - 1]
    clip = fitz.Rect(0, max(0, y - 24), pg.rect.width, min(pg.rect.height, y + 66))
    fp = r"C:/Users/asus/_sh_%s_%04d.png" % (tag, i)
    pg.get_pixmap(matrix=fitz.Matrix(2.2, 2.2), clip=clip).save(fp)
    crops.append((fp, "#%d L%d p%d y=%.1f  %s" % (i, lvl, p, y, t[:56])))
per, sheets = 12, 0
for s in range(0, len(crops), per):
    chunk = crops[s:s + per]
    doc = fitz.open()
    w, h = 640, 104
    pg = doc.new_page(width=w, height=per * (h + 14))
    for j, (fp, lab) in enumerate(chunk):
        y0 = j * (h + 14)
        pg.insert_text((6, y0 + 10), lab, fontsize=7.5, color=(0.75, 0, 0))
        pg.insert_image(fitz.Rect(6, y0 + 13, w - 6, y0 + h + 10), filename=fp)
    sp = r"C:/Users/asus/_sh_%s_%02d.pdf" % (tag, sheets + 1)
    doc.save(sp)
    doc.close()
    q = fitz.open(sp)
    q[0].get_pixmap(matrix=fitz.Matrix(1.6, 1.6)).save(r"C:/Users/asus/_sh_%s_%02d.png" % (tag, sheets + 1))
    q.close()
    os.remove(sp)
    sheets += 1
for fp, _ in crops:
    os.remove(fp)
print("entries=%d sheets=%d -> C:/Users/asus/_sh_%s_NN.png" % (len(crops), sheets, tag))
d.close()
