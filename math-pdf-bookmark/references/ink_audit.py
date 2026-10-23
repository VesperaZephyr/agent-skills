# -*- coding: utf-8 -*-
"""ink_audit.py -- 100%-coverage ACCEPTANCE test for a bookmark tree, measured
from the page IMAGE, plus contact sheets for the human eye.

    python ink_audit.py <pdf> [--out prefix] [--dpi 200]

Six rules this tool exists to enforce (all learned the hard way):

0. **rule 7 (added on Lax, 218/218): a LARGE-FONT heading's text-layer bbox top sits
   6-15 pt ABOVE its own ink.**  Lax chapter openers print a 47pt numeral and a 23.5pt
   title; their bbox tops are 45.4 / 107.9 while the ink starts at 59.8 / 116.1.
   The anchor is correct (that IS the heading's y in PDF space), but the old
   `0..8 pt below band top` gate called all 45 chapter openers NO-BAND.  Rule 7
   accepts a landing up to `--leadabove` (default 20) pt ABOVE a band that is
   unmistakably big-type (height >= 12 pt, left run >= 15 pt) -- a 9.8pt body line
   can never produce such a band, so the escape hatch cannot mask a real error.
   Verdict `ok-lead`; the tile still goes on the contact sheet.

1. **landing == read-back `to.y`, do NOT add the CropBox shift again.**
   `set_toc` input y is stored raw; `get_toc()['to'].y` reads back as
   `y_in + shift`, and THAT read-back value is already the landing in page
   (CropBox) space -- the same space the text-layer bboxes live in.  Re-adding
   `shift` here double-counts the compensation and every verdict becomes junk.

2. **The ink window must be WIDER than the band you are testing**
   (`landing-40 .. landing+70`).  A tight `landing-20 .. landing+90` clip changes
   the 12th-percentile grey threshold of that clip, which merges all lines of the
   window into one giant band and produces false NO-BAND verdicts.

3. **Set the ink window to the TEXT BLOCK, not the page** (`--x0/--x1`).
   A book that prints its folio in the outer margin (stein 中译本: block ends
   x=457, folio sits at x=461..484) keeps >0.4% dark pixels in every inter-line
   gap row, so the gap never breaks a band and heading+body merge into one
   437 pt / 32 pt "line" -> false BADs on perfectly anchored bookmarks.
   Default 48..505 fits Ahlfors; pass e.g. `--x1 455` for marginal-folio books.

4. **Ignore dust bands when picking the band to judge** (full left-run < 15 pt or
   height < 3 pt).  Scans carry stray specks; one 2.2 x 0.4 pt speck 0.3 pt above
   the 引言 title of stein 中译本 was the "nearest" band and turned a perfect
   anchor into a BAD.

5. **Measure the line width in the band's TOP 11 pt, not over the whole band.**
   A heading and the body line under it merge into one 29 pt tall band whenever
   the scan's inter-line gap still has a dark pixel, so the merged band is full
   text width even though the heading itself is short (stein 中译本 "2.1 例子"
   p67, "4 分割函数" p259).  The top-11pt run is the heading's own line; the
   full-band height is then no longer a usable test -- the real guards are
   gap <= 8 pt (landing is at the band top, not on a body line below) and the
   head-run width <= 265 pt (a body line is wide).  Level-1 openers skip the
   width cap because chapter titles legitimately span the page.

6. **A level-1 anchor may sit INSIDE its title band.**  Chapter openers print
   large, and a scan often keeps 1-4 % dark pixels in the ~14 pt of air above the
   title (stein 中译本 p13: rows 78.6..93.4 at frac .011, the title itself .20-.36),
   so the band top is 15 pt above a perfect anchor and the entry reads NO-BAND.
   Do NOT "fix" this by trimming faint rows against the band's peak density -- a
   short section heading is far less dense than the body line merged under it, and
   the trim then eats the heading (p67 "2.1 例子" went NO-BAND).  Accept a level-1
   landing covered by a band >= 12 pt tall; every level-1 tile is on the contact
   sheet anyway, so the eye still checks it.

8. **rule 8 (added on 孙永生《泛函分析讲义》, 52/54 -> 54/54): the ink grey MUST be capped.**
   `bands_of()` asked "is this row ink?" with an ADAPTIVE threshold
   `a < max(percentile(a, 12), 100)`, while the audit window is `landing-40 .. landing+70`.
   When that 110 pt strip is mostly blank (a section heading right after a page break, a
   习题 title after displayed maths), the clip's 12th percentile IS the paper grey --
   measured pct12 = 254.0 and p50 = 254 on 孙永生 p58/p202 -- so `a < 254` called the whole
   page ink, no inter-line gap ever broke a band, and the heading merged with everything
   above it into a 39 pt "band" whose top sat 12-15 pt ABOVE a perfect anchor => false
   NO-BAND.  Re-measured at an absolute grey (a<190, 300 dpi, full text column x=48..505)
   those two windows contain exactly ONE ink band each (397.28..414.08 / 285.60..305.76),
   i.e. the anchors were right.  Fix: `GREY` (`--grey`, default 200) caps the adaptive
   threshold.  Capping only ever REMOVES pseudo-ink, so it strictly TIGHTENS the gate --
   negative controls on this very book, with anchors forced to page top / running head /
   +15 pt into a body line / shifted one entry backwards, lost oks (23->10, 34->32,
   19->10, 44->41) while true anchors gained (52->54); 王晓光《101复变函数》 went
   241/244 -> 244/244, and 101泛函分析 56/57, Terse 86/89, Lang GTM102 109/125 are
   byte-for-byte unchanged.  150..230 all read 54/54, so the value is not a knife edge;
   `--grey 255` reproduces the pre-rule-8 behaviour exactly.
   NOTE: raising the *row-fraction* instead (`--rowfrac`) is NOT a fix -- it is not
   monotone: 0.012 saved p58 but left p202 NO-BAND, and 0.050 saved both yet collapsed the
   band height of a perfectly anchored `#31 p158 习题三` into `BAD h=3.2`, because the same
   permissive array decides both the band's EXTENT and its TOP/HEIGHT.

Verdict per entry: the landing must sit 0..8 pt BELOW the top of a band that is
   * solid (left-cluster width >= 15 pt, height >= 3 pt -- rule 4),
   * for level >= 2: one line wide (HEAD-window run <= 265 pt -- rule 5),
   * for level 1: big (band height >= 8 pt), width unconstrained; or, failing
     that, inside a >= 12 pt band (rule 6).
Width uses the ink run CONTIGUOUS with the band's left edge, bridging gaps <=40
pt: enough to cross spaces and punctuation inside one line, far too little to
jump to a detached mark.  Never gate on the text layer's x -- third-party OCR
layers truncate x-bboxes (measured up to -174 pt on Ahlfors 中译本) while their
y values stay trustworthy.
"""

import sys

import fitz
import numpy as np
from PIL import Image, ImageDraw

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

SRC = sys.argv[1] if len(sys.argv) > 1 else None
if SRC is None:
    print(__doc__)
    sys.exit(1)
OUT = (sys.argv[sys.argv.index('--out') + 1]
       if '--out' in sys.argv else r"C:/Users/asus/_ink_audit")
DPI = float(sys.argv[sys.argv.index('--dpi') + 1]) if '--dpi' in sys.argv else 200.0
SC = 72.0 / DPI
X0 = float(sys.argv[sys.argv.index('--x0') + 1]) if '--x0' in sys.argv else 48.0
X1 = float(sys.argv[sys.argv.index('--x1') + 1]) if '--x1' in sys.argv else 505.0
# rule 5 cap.  265 pt is calibrated for Chinese books (headings are short).
# Latin ALL-CAPS headings legitimately reach 320 pt -- pass --maxhead 340 there.
MAXHEAD = float(sys.argv[sys.argv.index('--maxhead') + 1]) if '--maxhead' in sys.argv else 265.0
TILEX1 = float(sys.argv[sys.argv.index('--tilex1') + 1]) if '--tilex1' in sys.argv else 330.0
EVERY = int(float(sys.argv[sys.argv.index('--every') + 1])) if '--every' in sys.argv else 6
#                     ^ contact-sheet sampling: every Nth entry + all L1 + all BAD.
#                     `--every 1` = 逐条看图（书只有几十条时这才是"写完必须看图"的正解）。
#                     ⚠️ 必须 int()：`range(0, n, 4.0)` 会 TypeError，float 参数直接崩。
HEAD = 11.0            # pt of a band's top that is read as "the heading's own line"
# rule 7: how far ABOVE the ink a large-font heading's text-layer bbox top may sit.
# Lax (23.5pt titles / 47pt chapter numerals) measured 6.1-20.7 pt -- the numerals
# of ch.22 (land 39.6 / ink 59.8) and ch.26 (39.1 / 59.8) are the extreme cases.
# 24 pt is slack; a 9.8pt body line can never produce a >=12pt band, so this cannot
# mask a real error.
LEADABOVE = float(sys.argv[sys.argv.index('--leadabove') + 1]) \
    if '--leadabove' in sys.argv else 24.0
# rule 8: the ink grey must be CAPPED.  `bands_of()` decided "is this row ink" with an
# ADAPTIVE threshold `a < max(percentile(a,12), 100)`, but the audit window is
# `landing-40 .. landing+70`.  When that 110 pt strip is mostly blank (a section heading
# after a page break, a 习题 title after displayed maths), the clip's 12th percentile IS
# the paper grey: measured pct12 = 254.0 (and p50 = 254!) on 孙永生 p58/p202, so
# `a < 254` called the whole page ink, every inter-line gap stayed "on", and the heading
# merged with everything above it into a 39 pt "band" whose top sat 12-15 pt above a
# PERFECT anchor -> false NO-BAND.  Measured at an absolute grey (<190, 300 dpi, full text
# column x=48..505) those regions contain exactly ONE ink band: p58 397.28..414.08 and
# p202 285.60..305.76 -- the anchors were right.
# Capping only ever REMOVES pseudo-ink, so it strictly tightens the gate: negative controls
# (anchors forced to page top / running head / +15 pt into a body line / shifted one entry
# backwards) all got FEWER oks (23->10, 34->32, 19->10, 44->41), while true anchors went
# 52/54 -> 54/54 on 孙永生 and 241/244 -> 244/244 on 王晓光《101复变函数》; 101泛函分析
# (56/57), Terse (86/89) and Lang GTM102 (109/125) are byte-for-byte unchanged.
# 150..230 all give 54/54 on 孙永生 -- 200 is a normal ink cut and survives faint scans.
# Pass `--grey 255` to reproduce the pre-rule-8 behaviour exactly.
GREY = float(sys.argv[sys.argv.index('--grey') + 1]) if '--grey' in sys.argv else 200.0


def left_run(prof):
    """First / last column of the ink run contiguous with the band's left edge,
    bridging gaps <= 40 pt, plus the last inked column of the whole profile."""
    cols = np.where(prof)[0]
    if not len(cols):
        return None
    last = j = cols[0]
    while j < len(prof):
        nxt = np.where(prof[j + 1:])[0]
        if not len(nxt):
            break
        gap = nxt[0] + 1
        if gap * SC > 40.0:
            break
        j += gap
        last = j
    return cols[0], last, cols[-1]


def bands_of(pg, y0, y1, x0=X0, x1=X1):
    """Ink bands as (top_pt, height_pt, left_pt, right_pt, left_cluster_pt,
    left_cluster_pt_measured_in_the_top_HEAD_pt)."""
    pix = pg.get_pixmap(matrix=fitz.Matrix(1 / SC, 1 / SC),
                        clip=fitz.Rect(x0, y0, x1, y1), colorspace=fitz.csGRAY)
    a = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.stride)
    a = a[:, :pix.width]
    dark = a < min(max(float(np.percentile(a, 12)), 100.0), GREY)
    on = dark.mean(axis=1) > 0.004
    n_head = max(1, int(round(HEAD / SC)))
    res, y = [], 0
    while y < len(on):
        if on[y]:
            y2 = y
            while y2 + 1 < len(on) and on[y2 + 1]:
                y2 += 1
            lr = left_run(dark[y:y2 + 1].any(axis=0))
            lh = left_run(dark[y:min(y2 + 1, y + n_head)].any(axis=0))
            res.append((y0 + y * SC, (y2 - y + 1) * SC, x0 + lr[0] * SC,
                        x0 + lr[2] * SC, (lr[1] - lr[0]) * SC,
                        (lh[1] - lh[0]) * SC if lh else 0.0))
            y = y2 + 2
        else:
            y += 1
    return res


d = fitz.open(SRC)
toc = d.get_toc(simple=False)
PROPOSED = False
if '--items' in sys.argv:                    # 审"打算写入"的树，而不是已写入的树
    PROPOSED = True
    toc = []
    for line in open(sys.argv[sys.argv.index('--items') + 1], encoding='utf-8'):
        if not line.strip():
            continue
        p, y, lvl, title = line.rstrip('\n').split('\t', 3)
        p, y, lvl = int(p), float(y), int(lvl)
        toc.append([lvl, title, p, {'kind': 1, 'page': p - 1,
                                    'to': fitz.Point(72.0, y)}])
out = ["%s  pages=%d bookmarks=%d%s  crop=%s media=%s"
       % (SRC, d.page_count, len(toc), " (PROPOSED tree, not yet written)" if PROPOSED else "",
          d[0].cropbox, d[0].mediabox),
       "params: dpi=%.0f x=%.0f..%.0f tilex1=%.0f maxhead=%.0f grey=%.0f leadabove=%.0f every=%d"
       % (DPI, X0, X1, TILEX1, MAXHEAD, GREY, LEADABOVE, EVERY)]
recs = []
for i, e in enumerate(toc):
    lvl, title, p, landing = e[0], e[1], e[2], round(e[3]['to'].y, 2)
    pg = d[p - 1]
    bs = bands_of(pg, max(4.0, landing - 40), landing + 70)
    cand = [b for b in bs if -4.0 <= landing - b[0] <= 8.0]
    solid = [b for b in cand if b[4] >= 15.0 and b[1] >= 3.0]      # dust filter
    near = solid if solid else cand
    pick = min(near, key=lambda b: abs(landing - b[0])) if near else None
    inband = False
    if pick is None and lvl == 1:              # rule 6: chapter title haze
        inb = [b for b in bs if b[0] <= landing <= b[0] + b[1] and b[1] >= 12.0]
        pick = max(inb, key=lambda b: b[1]) if inb else None
        inband = pick is not None
    lead = False
    if pick is None:                           # rule 7: large-font leading
        ld = [b for b in bs if landing <= b[0] <= landing + LEADABOVE
              and b[1] >= 12.0 and b[4] >= 15.0]
        if ld:
            pick = min(ld, key=lambda b: b[0] - landing)
            lead = True
    if pick is None:
        cov = [b for b in bs if b[0] <= landing <= b[0] + b[1]]
        verdict = "NO-BAND cover=%s tops=%s" % (
            ["%.1f/%.1f" % (b[0], b[1]) for b in cov], [round(b[0], 1) for b in bs[:5]])
    else:
        hpt, wpt, gapt, whead = pick[1], pick[4], landing - pick[0], pick[5]
        if lvl == 1 or lead:               # big title, may span the page
            ok = hpt >= 8.0
        else:                              # one short line, not a body line
            ok = hpt >= 5.0 and whead <= MAXHEAD
        verdict = ("ok-lead" if lead else
                   "ok-inband" if inband else "ok") if ok else \
                  "BAD w=%.0f wh=%.0f h=%.1f gap=%+.1f" % (wpt, whead, hpt, gapt)
    recs.append((i, lvl, title, p, landing, pick, verdict))
    out.append("#%-4d L%d p%-4d land=%7.2f gap=%+5.1f x=%5.1f w=%5.1f wh=%5.1f h=%4.1f %-30s %s"
               % (i, lvl, p, landing,
                  (landing - pick[0]) if pick else 999,
                  pick[2] if pick else 999, pick[4] if pick else 999,
                  pick[5] if pick else 999,
                  pick[1] if pick else 999, verdict, title[:30]))
n_ok = len([1 for r in recs if r[6].startswith('ok')])
gaps = [r[4] - r[5][0] for r in recs if r[5]]
out.insert(1, "TOTAL=%d ok=%d bad=%d | landing below band-top: min=%+.1f max=%+.1f pt"
           % (len(recs), n_ok, len(recs) - n_ok, min(gaps), max(gaps)))
open(OUT + ".txt", 'w', encoding='utf-8').write("\n".join(out))

if '--nosheet' in sys.argv:                  # 只要数字结论（dry-run 闸门用）
    d.close()
    print("ok=%d/%d bad=%d (no sheets) -> %s.txt" % (n_ok, len(recs), len(recs) - n_ok, OUT))
    raise SystemExit(0)

# ---- contact sheets: red line drawn exactly at each landing (ASCII captions:
# PIL's default font cannot render CJK and silently prints boxes)
sel = sorted(set([r[0] for r in recs if not r[6].startswith('ok')] +
                 [r[0] for r in recs if r[1] == 1] +
                 [r[0] for r in recs if r[0] % EVERY == 0]))
COLS, ROWS, CAP, PAD = 2, 8, 16, 8
tiles = []
for i in sel:
    lvl, title, p, landing = recs[i][1], recs[i][2], recs[i][3], recs[i][4]
    top = max(4.0, landing - 18)
    pix = d[p - 1].get_pixmap(matrix=fitz.Matrix(1 / SC, 1 / SC),
                              clip=fitz.Rect(X0 + 2, top, TILEX1, top + 70))
    im = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
    dr = ImageDraw.Draw(im)
    ln = max(2, int((landing - top) / SC))
    dr.line([(0, ln), (im.width, ln)], fill=(220, 30, 30), width=2)
    tiles.append((im, "#%d L%d p%d land=%.1f" % (i, lvl, p, landing)))
d.close()
per = ROWS * COLS
ns = (len(tiles) + per - 1) // per
for s in range(ns):
    w = COLS * (tiles[0][0].width + PAD) + PAD
    hp = CAP + tiles[0][0].height + PAD
    sheet = Image.new("RGB", (w, ROWS * hp + 22), "white")
    dr = ImageDraw.Draw(sheet)
    dr.text((PAD, 6), "ink audit %d/%d  red line = bookmark landing" % (s + 1, ns),
            fill=(0, 0, 90))
    for k in range(per):
        idx = s * per + k
        if idx >= len(tiles):
            break
        im, cap = tiles[idx]
        cx = PAD + (k % COLS) * (im.width + PAD)
        cy = 22 + (k // COLS) * hp
        dr.text((cx + 2, cy), cap, fill=(0, 0, 140))
        sheet.paste(im, (cx, cy + CAP))
    sheet.save("%s_sheet_%d.png" % (OUT, s + 1))
print("ok=%d/%d bad=%d tiles=%d sheets=%d -> %s.txt" %
      (n_ok, len(recs), len(recs) - n_ok, len(tiles), ns, OUT))
