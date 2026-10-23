# -*- coding: utf-8 -*-
"""ROUTE C — re-anchor an existing bookmark tree of a PURE-SCAN PDF using
targeted-crop OCR, compensating the per-page CropBox shift.

Use when: the PDF has no text layer, its outline is structurally good (titles clean,
levels right) but every landing is off by a roughly constant amount -> CropBox
pollution (see SKILL.md hard rule 9).  Do NOT OCR the whole book: only a 130 pt band
around each existing landing (110 bands ~= 40 s).

Stages (run in order; --write is the only mutating step):
    python crop_reanchor.py render            # bands -> WORK/png/page_%04d.png
    <run winocr.ps1 on WORK/png -> WORK/ocr.txt>            (command printed)
    python crop_reanchor.py match             # OCR + ink bands -> WORK/new.tsv
    python crop_reanchor.py audit             # numeric 110/110 landing check
    python crop_reanchor.py sheet             # contact sheets for the risky subset
    python crop_reanchor.py write --write     # set_toc with per-page compensation
    python crop_reanchor.py labels --write    # optional: page labels == printed folio

RE-POINT THESE CONSTANTS PER BOOK: SRC, WORK, K_BODY_START(only for labels), and the
label ranges in do_labels().  Everything else is generic.
"""
import io
import os
import re
import shutil
import subprocess
import sys

import fitz

SRC = (u"F:/大学/数字资源/数学/代数学/高等代数/北大高代/"
       u"高等代数 第六版 (北京大学数学系前代数小组编,王萼芳,石生明,王立中).pdf")
WORK = r"C:/Users/asus/_cropfix"          # png/ ocr.txt meta.txt new.tsv reports
WINOCR = u"F:/大学/数字资源/数学/分析学/_build/winocr.ps1"
DPI = 200.0
SC = 72.0 / DPI
ISC = 4.0                                  # ink measurement dpi = 288
TOP, BOT = 30.0, 100.0                     # band = [land-TOP, land+BOT]
BAK = None                                 # rollback copy, set if you want one

PNG = os.path.join(WORK, "png")
OCR = os.path.join(WORK, "ocr.txt")
METAF = os.path.join(WORK, "meta.tsv")
NEW = os.path.join(WORK, "new.tsv")
TMP = os.path.join(WORK, "tmp.pdf")

CJK = re.compile(u"[\u4e00-\u9fff]")
SEP = re.compile(u"[\\s\u3000．.、,，;；:：\\-–—_·•∙*/§()（）\\[\\]【】{}“”\"'’‘<>《》&]+")


def toks(s):
    out = set()
    for w in SEP.split((s or u"").strip()):
        if not w:
            continue
        if CJK.search(w):
            for ch in w:
                if CJK.match(ch):
                    out.add(ch)
            for x in re.findall(r"[A-Za-z]+|\d+", w):
                out.add(x.lower())
        else:
            out.add(w.lower())
    return out


# ---------------------------------------------------------------- geometry ----
def geo():
    d = fitz.open(SRC)
    n = d.page_count
    shift = [round(d[i].mediabox.y1 - d[i].cropbox.y1, 3) for i in range(n)]
    rots = {d[i].rotation for i in range(n)}
    assert rots == {0}, u"rotated pages: rect coords differ, handle per page"
    return d, n, shift


# ------------------------------------------------------------------ stage 1 ----
def do_render():
    if os.path.isdir(PNG):
        shutil.rmtree(PNG)
    os.makedirs(PNG)
    d, n, shift = geo()
    toc = d.get_toc(simple=False)
    meta = io.open(METAF, "w", encoding="utf-8")
    for i, (lv, t, p, dest) in enumerate(toc, 1):
        y = dest['to'].y
        pg = d[p - 1]
        top = max(0.0, y - TOP)
        bot = min(pg.rect.height, y + BOT)
        pg.get_pixmap(matrix=fitz.Matrix(1 / SC, 1 / SC), colorspace=fitz.csGRAY,
                      clip=fitz.Rect(0, top, pg.rect.width, bot)
                      ).save(os.path.join(PNG, "page_%04d.png" % i))
        meta.write(u"%d\t%d\t%s\t%d\t%.2f\t%.2f\t%.2f\n"
                   % (i, lv, t.replace(u"\t", u" "), p, y, top, bot))
    meta.close()
    d.close()
    print(u"crops=%d" % len(toc))
    print(u"next:  powershell -NoProfile -ExecutionPolicy Bypass -File \"%s\" "
          u"-PngDir \"%s\" -OutFile \"%s\"" % (WINOCR, PNG, OCR))


# ------------------------------------------------------------------ stage 2 ----
def load_ocr():
    blocks, cur = {}, None
    for raw in io.open(OCR, encoding="utf-8-sig").read().splitlines():
        if raw.startswith(u"#####"):
            cur = int(re.findall(r"\d+", raw.split()[-1])[0])
            blocks[cur] = []
            continue
        if cur is None or not raw.strip():
            continue
        q = raw.split(u"\t")
        if len(q) >= 5:
            try:
                blocks[cur].append((int(q[0]), int(q[1]), int(q[2]), int(q[3]),
                                    u" ".join(q[4:]).strip()))
            except ValueError:
                pass
    return blocks


def ink_bands(doc, page, xa, xb, ya, yb, thresh=140, minrun=3):
    if yb <= ya:
        return []
    pix = doc[page - 1].get_pixmap(matrix=fitz.Matrix(ISC, ISC), colorspace=fitz.csGRAY,
                                   clip=fitz.Rect(xa, ya, xb, yb))
    w, h, nn = pix.width, pix.height, pix.n
    buf = pix.samples
    dark = [sum(1 for x in range(w) if buf[y * w * nn + x * nn] < thresh) for y in range(h)]
    res, y = [], 0
    while y < h:
        if dark[y] >= minrun:
            y2 = y
            while y2 + 1 < h and dark[y2 + 1] >= 2:
                y2 += 1
            res.append((ya + y / float(ISC), ya + (y2 + 1) / float(ISC)))
            y = y2 + 1
        else:
            y += 1
    return res


def do_match():
    meta = []
    for raw in io.open(METAF, encoding="utf-8").read().splitlines():
        q = raw.split(u"\t")
        if len(q) >= 7:
            meta.append((int(q[0]), int(q[1]), q[2], int(q[3]), float(q[4]),
                         float(q[5], ), float(q[6])))
    blocks = load_ocr()
    d, n, shift = geo()
    PH = [d[i].rect.height for i in range(n)]
    PW = [d[i].rect.width for i in range(n)]
    toc = d.get_toc(simple=False)
    assert len(toc) == len(meta)
    rep = io.open(os.path.join(WORK, "match.txt"), "w", encoding="utf-8")
    new, nink = [], 0
    for (idx, lv, title, page, old_y, top, _bot), e in zip(meta, toc):
        sh = shift[page - 1]
        guess = old_y - sh                 # the outline's own numeric input
        T = toks(title)
        lines = sorted(blocks.get(idx, []))
        tk = [T & toks(l[4]) for l in lines]
        best = None
        for k in range(len(lines)):
            grp = [lines[k]]
            cov = len(tk[k]) / float(len(T)) if T else 0.0
            mh = lines[k][3]
            # a heading may wrap: pair ONLY if both lines carry title tokens
            if k + 1 < len(lines) and tk[k] and tk[k + 1]:
                c2 = len(tk[k] | tk[k + 1]) / float(len(T)) if T else 0.0
                if c2 > cov + 0.05:
                    cov, mh, grp = c2, max(mh, lines[k + 1][3]), [lines[k], lines[k + 1]]
            if cov >= 0.55:
                cand = (-cov, -mh, lines[k][0], lines[k][1], lines[k][2], mh,
                        u" | ".join(g[4] for g in grp))
                if best is None or cand < best:
                    best = cand
        W = PW[page - 1]
        if best is not None:
            cov, _1, y0px, x0px, x1px, hpx, ocr = (-best[0], best[1], best[2], best[3],
                                                   best[4], best[5], best[6])
            y_ocr = top + y0px * SC
            hpt = hpx * SC
            y_new, tag = y_ocr, u"ocr c=%.2f h=%.1f" % (cov, hpt)
            if lv == 1:
                # chapter/appendix openers carry a decorative smudge at the LEFT and a
                # vertical rule at the RIGHT -> window = this line's own span, +40/-55
                xa = max(20.0, x0px * SC - 40)
                xb = min(W - 55.0, x1px * SC + 40)
                up, minh = 32.0, max(12.0, 0.70 * hpt)
            else:
                xa = max(20.0, x0px * SC - 8)
                xb = min(W - 20.0, x1px * SC + 8)
                up, minh = 8.0, 6.0
            for (a, b) in ink_bands(d, page, xa, xb, max(0.0, y_ocr - up), y_ocr + 6.0):
                if b - a >= minh:
                    if abs(a - guess) < 45.0:
                        y_new, tag = a, tag + u" ink"
                    break
        else:
            nink += 1
            y_new, ocr, tag = guess, u"", u"INKONLY"
            if lv == 1:
                xa, xb = 0.60 * W, W - 55.0
                up = 45.0
            else:
                xa, xb = 40.0, W - 40.0
                up = 16.0
            for (a, b) in ink_bands(d, page, xa, xb, max(0.0, y_new - up),
                                    min(PH[page - 1], y_new + 30.0)):
                if b - a >= 12.0:
                    y_new, tag = a, u"INKONLY ink"
                    break
        if title.strip() in (u"封面", u"Cover", u"Title page"):
            y_new, tag = 1.0, u"cover"
        y_new = round(min(max(1.0, y_new), PH[page - 1] - 2.0), 2)
        new.append([lv, title, page, y_new])
        rep.write(u"%3d L%-2d %-38s p%-4d old=%7.2f guess=%7.2f new=%7.2f (%+6.2f) "
                  u"sh=%+7.2f %-18s | %s\n"
                  % (idx, lv, title[:38], page, old_y, guess, y_new, y_new - old_y, sh,
                     tag, ocr[:52]))
    rep.write(u"entries=%d INKONLY=%d\n" % (len(new), nink))
    rep.close()
    io.open(NEW, "w", encoding="utf-8").write(
        u"\n".join(u"%d\t%s\t%d\t%.2f" % (lv, t.replace(u"\t", u" "), p, y)
                   for lv, t, p, y in new) + u"\n")
    d.close()
    print(u"entries=%d INKONLY=%d -> %s" % (len(new), nink, NEW))


# ------------------------------------------------------------------ stage 3 ----
def rowmax(doc, page, xa, xb, ya, yb, thresh=140):
    if yb <= ya:
        return 0
    pix = doc[page - 1].get_pixmap(matrix=fitz.Matrix(ISC, ISC), colorspace=fitz.csGRAY,
                                   clip=fitz.Rect(xa, ya, xb, yb))
    w, h, nn = pix.width, pix.height, pix.n
    buf = pix.samples
    best = 0
    for y in range(h):
        c, base = 0, y * w * nn
        for x in range(w):
            if buf[base + x * nn] < thresh:
                c += 1
        best = max(best, c)
    return best


def do_audit():
    """Numeric 100% check: an anchor on a heading's ink top has ink below, blank above."""
    d, n, shift = geo()
    toc = d.get_toc(simple=False)
    out = io.open(os.path.join(WORK, "audit.txt"), "w", encoding="utf-8")
    bad = []
    for i, (lv, t, p, dest) in enumerate(toc, 1):
        y = dest['to'].y
        W = d[p - 1].rect.width
        below = rowmax(d, p, 50.0, W - 50.0, y + 1, y + 6)
        above = rowmax(d, p, 50.0, W - 50.0, max(0.0, y - 6), y - 1)
        ok = below >= 8 and above <= 4
        if not ok:
            bad.append(i)
        out.write(u"%s %3d L%-2d %-40s p%-4d y=%7.2f above=%4d below=%4d\n"
                  % (u"OK " if ok else u"-- ", i, lv, t[:40], p, y, above, below))
    out.write(u"total=%d flagged=%s\n" % (len(toc), bad))
    out.close()
    d.close()
    print(u"flagged %d / %d (lvl1 openers with page decoration are expected) "
          u"-> eyeball them: python crop_reanchor.py sheet" % (len(bad), len(toc)))
    io.open(os.path.join(WORK, "flag.txt"), "w").write(
        "\n".join(str(i) for i in bad) + "\n")


def do_sheet(zoom=1.5, per=8):
    """Contact sheets for lvl1 + a lvl2 spread + every flagged/INKONLY entry."""
    from PIL import Image, ImageDraw
    flag = set()
    fp = os.path.join(WORK, "flag.txt")
    if os.path.exists(fp):
        flag = set(int(x) for x in io.open(fp).read().split())
    for raw in io.open(os.path.join(WORK, "match.txt"), encoding="utf-8").read().splitlines():
        if u"INKONLY" in raw:
            m = re.match(r"\s*(\d+)", raw)
            if m:
                flag.add(int(m.group(1)))
    d, n, shift = geo()
    toc = d.get_toc(simple=False)
    pick = sorted(set([i + 1 for i, e in enumerate(toc) if e[0] == 1]
                      + [i + 1 for i, e in enumerate(toc) if e[0] == 2][::5]
                      + list(flag)))
    strips, legend = [], []
    for k, i in enumerate(pick, 1):
        lv, t, p, dest = toc[i - 1]
        y = dest['to'].y
        pg = d[p - 1]
        r = fitz.Rect(0, max(0, y - 18), pg.rect.width, y + 54)
        fn = os.path.join(WORK, "s%03d.png" % k)
        pg.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=r).save(fn)
        im = Image.open(fn).convert('RGB')
        ImageDraw.Draw(im).line([(0, 18 * zoom), (im.width, 18 * zoom)],
                                fill=(220, 0, 0), width=2)
        strips.append(im)
        legend.append(u"%2d #%3d L%d p%-4d y=%6.1f shift=%+6.1f %s"
                      % (k, i, lv, p, y, shift[p - 1], t))
        os.remove(fn)
    W = max(s.width for s in strips)
    for k in range(0, len(strips), per):
        grp = strips[k:k + per]
        c = Image.new('RGB', (W, sum(s.height + 6 for s in grp)), 'white')
        yy = 0
        for s in grp:
            c.paste(s, (0, yy))
            yy += s.height + 6
        fn = os.path.join(WORK, "sheet%d.jpg" % (k // per + 1))
        c.save(fn, quality=85)
        print(fn)
    io.open(os.path.join(WORK, "legend.txt"), "w", encoding="utf-8-sig").write(
        u"\n".join(legend) + u"\n")
    d.close()


# ------------------------------------------------------------------ stage 4 ----
def do_write():
    rows = []
    for raw in io.open(NEW, encoding="utf-8").read().splitlines():
        q = raw.split(u"\t")
        if len(q) == 4:
            rows.append((int(q[0]), q[1], int(q[2]), float(q[3])))
    d, n, shift = geo()
    old = d.get_toc()
    d.close()
    assert len(rows) == len(old), u"new.tsv does not match the outline -- rerun match"
    for i, (lv, t, p, y) in enumerate(rows):
        assert old[i][0] == lv and old[i][1] == t and old[i][2] == p, (i, t)
    if "--write" not in sys.argv:
        print(u"dry run: %d rows consistent" % len(rows))
        return
    if BAK:
        shutil.copy2(SRC, BAK)
    shutil.copy2(SRC, TMP)
    d = fitz.open(TMP)
    d.set_toc([[lv, t, p, round(y - shift[p - 1], 2)] for lv, t, p, y in rows])
    d.saveIncr()
    d.close()
    chk = fitz.open(TMP)
    t2 = chk.get_toc(simple=False)
    errs = [abs(t2[i][3]['to'].y - rows[i][3]) for i in range(len(rows))]
    print(u"recheck n=%d max_err=%.3f pages=%d" % (len(t2), max(errs), chk.page_count))
    assert len(t2) == len(rows) and max(errs) < 0.05 and chk.page_count == n
    chk.close()
    shutil.move(TMP, SRC)
    print(u"WROTE")


def do_labels():
    """Optional: page labels == printed folio.  Determine the body start page and the
    printed number there first (bottom-strip OCR + eyeball, see SKILL.md ROUTE C 7)."""
    BODY_START = 6        # 1-based physical page that carries printed page 1
    BODY_FIRST = 1
    if "--write" not in sys.argv:
        d, n, shift = geo()
        print(u"before: %s" % d.get_page_labels())
        d.close()
        print(u"set BODY_START/BODY_FIRST then re-run with --write")
        return
    shutil.copy2(SRC, TMP)
    d = fitz.open(TMP)
    d.set_page_labels([
        {u'startpage': 0, u'prefix': u'', u'style': u'r', u'firstpagenum': 1},
        {u'startpage': BODY_START - 1, u'prefix': u'', u'style': u'D',
         u'firstpagenum': BODY_FIRST},
    ])
    d.saveIncr()
    d.close()
    chk = fitz.open(TMP)
    print(u"after: %s" % chk.get_page_labels())
    print(u"p%d -> %s ; p%d -> %s" % (1, chk[0].get_label(), BODY_START,
                                      chk[BODY_START - 1].get_label()))
    chk.close()
    shutil.move(TMP, SRC)
    print(u"LABELS WRITTEN")


STAGES = {"render": do_render, "match": do_match, "audit": do_audit,
          "sheet": do_sheet, "write": do_write, "labels": do_labels}

if __name__ == "__main__":
    stage = sys.argv[1] if len(sys.argv) > 1 else "render"
    STAGES[stage]()
