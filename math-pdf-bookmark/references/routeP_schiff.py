# -*- coding: utf-8 -*-
"""_sch_build.py -- Schiff, Topics in Complex Analysis: rebuild the bookmark tree
from the PRINTED Contents (p13-16) and anchor every entry on the heading line.

The book ships with 15 chapter-only bookmarks; the printed Contents has ~170
entries in four indented levels, so the skeleton cannot be re-anchored (route R)
-- it must be re-parsed (route P) and each title located in the text layer.

Heading geometry (measured, not guessed):
  chapter   bold, size 15, flush left          ('1 Analytic functions')
  section   bold, size 12, flush left          ('Analytic continuation')
  sub/SS    bold, size 9.5, flush left         ('Laurent series')
  body      NOT bold; first line indented +17; theorem refs are bold but flush
            left AND start with a number ('3.1 Theorem.') -> excluded.

Usage:  python _sch_build.py            dry run -> _sch_build.txt
        python _sch_build.py --write    back up + set_toc
"""
import fitz, os, re, shutil, sys

sys.path.insert(0, r"C:/Users/asus")
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
try:                                   # working copy imports the engine as _reanchor
    from _reanchor import page_lines, clean, nz, score, next_bak, TMP
except ImportError:                    # this references/ copy
    from reanchor import page_lines, clean, nz, score, next_bak, TMP

SRC = r"F:/大学/数字资源/数学/分析学/复分析/Topics in Complex Analysis (Joel L. Schiff).pdf"
REP = r"C:/Users/asus/_sch_build.txt"
TOCP = [13, 14, 15, 16]          # physical pages of the printed Contents
K = 16                          # arabic folio + K = physical page (ch.1 folio 1 -> p17)
WIN_LO, WIN_HI = -1, 3          # search window around the expected page
ACCEPT = 3.0
ROMAN = {'i': 1, 'v': 5, 'x': 10, 'l': 50}
# the text layer flattens superscripts, so two Contents rows read 'h1(U)' and
# 'τ2= 4' where the printed page shows h¹(U) and τ² = 4.  Fix the display title
# only -- the probe (matching text) is left untouched.
TITLE_FIX = {'Positive harmonic functions/class h1(U)':
             'Positive harmonic functions/class h¹(U)',
             'One fixed point (parabolic case: τ2= 4)':
             'One fixed point (parabolic case: τ² = 4)'}


def roman(s):
    s = s.lower().strip()
    if not s or any(c not in ROMAN for c in s):
        return None
    tot, prev = 0, 0
    for c in reversed(s):
        v = ROMAN[c]
        tot += v if v >= prev else -v
        prev = v
    return tot


def rows(page):
    """cluster page_lines() into visual rows (the chapter number and the title of
    one Contents line live in different blocks with the same y)."""
    out = []
    for ln in sorted(page_lines(page)):
        y, x, sz, b, t = ln[0], ln[1], ln[2], ln[3], clean(ln[4])
        if len(t) < 1 or y < 40 or sz < 9.0:      # folio / running head (size 8)
            continue
        if out and abs(out[-1][0] - y) < 3.0:
            r = out[-1]
            r[1] = min(r[1], x)
            r[2] = max(r[2], sz)
            r[3] = r[3] or b
            r[4] += ' ' + t
        else:
            out.append([y, x, sz, b, t])
    return [(r[0], r[1], r[2], r[3], r[4]) for r in out]


def parse_toc(doc):
    ents, dropped = [], []
    for p in TOCP:
        rs = rows(doc[p - 1])
        if not rs:
            continue
        x0 = min(r[1] for r in rs)                # this page's Contents left edge
        for (y, x, sz, b, t) in rs:
            m = re.match(r'^(.*?)\s*\|\s*([0-9]+|[IVXLC]+)\s*$', t)
            if not m:
                dropped.append('p%d y=%.1f %r' % (p, y, t[:60]))
                continue
            title, fol = clean(m.group(1)), m.group(2)
            # on some Contents pages the chapter number is its own span (merged as
            # '1 Analytic functions'), on others it is jammed ('10Analytic ...').
            # Normalise so no bookmark panel shows a glued number.
            title = re.sub(r'^([0-9]+)(?=[A-Za-z])', r'\1 ', title)
            front = not fol.isdigit()
            num = int(fol) if not front else roman(fol)
            if num is None:
                dropped.append('p%d y=%.1f bad folio %r' % (p, y, fol))
                continue
            d = x - x0
            lvl = 1 if d < 20 else (2 if d < 40 else (3 if d < 66 else 4))
            # the chapter number is a separate span: '1 Analytic functions | 1'.
            # Keep it in the TITLE (the printed Contents shows it) but match on
            # the bare words -- and never strip roman numerals, or 'Index'
            # becomes 'ndex'.
            probe = re.sub(r'^[0-9]+[ .、]*\s*', '', title).strip() if lvl == 1 else title
            ents.append([lvl, TITLE_FIX.get(title, title), probe,
                         num if front else num + K, d])
    return ents, dropped


def find(doc, title, exp, npages):
    best = None
    for p in range(max(1, exp + WIN_LO), min(npages, exp + WIN_HI) + 1):
        ls = page_lines(doc[p - 1])
        cand = [l for l in ls if len(clean(l[4])) >= 2]
        if not cand:
            continue
        mx = min(l[1] for l in cand)              # this page's body left edge
        for ln in ls:
            t = clean(ln[4])
            if not ln[3] or len(t) > 62 or ln[1] > mx + 2.5:
                continue                          # not bold / too long / indented
            if re.match(r'^[0-9]+(\.[0-9]+)*\s*[A-Za-z]', t) and ln[2] < 14:
                continue                          # '3.1 Theorem.' style run-in refs
            s = score(title, (ln[0], ln[1], ln[2], ln[3], t), 9.5, mx)
            if s <= 0:
                continue
            s += 1.2 - 0.6 * abs(p - exp)
            if s >= ACCEPT and (best is None or s > best[0]):
                best = (s, p, ln[0], t)
        if best and best[0] >= ACCEPT + 2.0 and best[1] == exp:
            break
    return best


def main():
    write = '--write' in sys.argv
    doc = fitz.open(SRC)
    old = doc.get_toc()
    ents, dropped = parse_toc(doc)
    # the Contents page never lists itself; the old skeleton had it as L1 p13, so
    # splice it in at the right place (after Acknowledgments, before chapter 1).
    ins = next((i for i, e in enumerate(ents) if e[3] >= 15), len(ents))
    ents.insert(ins, [1, 'Contents', 'Contents', 13, 0.0])
    out = ["parsed %d Contents entries from pages %s" % (len(ents), TOCP),
           "old bookmarks: %d" % len(old),
           "",
           "=== rows that did not parse as 'title | folio' ==="]
    out += ["  " + d for d in dropped] or ["  (none)"]
    out.append("")
    fixed, miss = [], []
    for lvl, title, probe, exp, d in ents:
        hit = find(doc, probe, exp, doc.page_count)
        if hit is None:
            miss.append((lvl, title, exp))
            out.append("MISS L%d %r exp_p=%d" % (lvl, title, exp))
            continue
        s, p, y, t = hit
        fixed.append([lvl, title, p, round(y, 1)])
        out.append("  OK L%d p%-4d y=%-6.1f (%+.1f d=%2.0f) %r  <=  %r"
                   % (lvl, p, y, s, d, title[:40], t[:44]))
    mono = all(fixed[i][2] > fixed[i - 1][2] or (fixed[i][2] == fixed[i - 1][2]
               and fixed[i][3] >= fixed[i - 1][3]) for i in range(1, len(fixed)))
    lv = {}
    for e in fixed:
        lv[e[0]] = lv.get(e[0], 0) + 1
    out.append("")
    out.append("located=%d MISS=%d levels=%s monotone=%s" % (len(fixed), len(miss), lv, mono))
    # cross-check the 15 existing chapter bookmarks
    out.append("")
    out.append("=== cross-check vs existing chapter bookmarks ===")
    for (l, t, p) in [(e[0], e[1], e[2]) for e in old]:
        near = [f for f in fixed if f[0] == 1 and abs(f[2] - p) <= 1]
        out.append("  old L%d p%-4d %-42r -> %s" % (l, p, t[:42], near if near else 'NO NEW L1 NEARBY'))
    with open(REP, 'w', encoding='utf-8') as fh:
        fh.write("\n".join(out) + "\n")
    print("report ->", REP, "| located=%d MISS=%d" % (len(fixed), len(miss)))
    if miss:
        print("refusing to write while %d entries are unlocated" % len(miss))
        return 1
    if not write:
        print("dry run only (pass --write)")
        return 0
    bak = next_bak(SRC)
    shutil.copy2(SRC, bak)
    shutil.copy2(SRC, TMP)
    d = fitz.open(TMP)
    d.set_toc(fixed)
    d.saveIncr()
    d.close()
    shutil.move(TMP, SRC)
    v = fitz.open(SRC)
    t2 = v.get_toc(simple=False)
    tops = sum(1 for x in t2 if x[3].get('to').y <= 0.5)
    print("wrote %d bookmarks (backup %s); re-open pages=%d bm=%d page-top=%d"
          % (len(t2), os.path.basename(bak), v.page_count, len(t2), tops))
    v.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
