# -*- coding: utf-8 -*-
"""Bookmark writer for Conway GTM 159 (Functions of One Complex Variable II).

Pure-scan PDF (412 pp, FreePic2Pdf, page rect 2242x3857 pt == native pixels of
a ~300 dpi scan).  Route B of the SOP: render at dpi=72 (native px) -> WinRT OCR
-> locate headings in the OCR word-box dump.  Because the render DPI equals the
PDF's own point scale (72), OCR pixel y IS the PDF point y -- no conversion.

Usage:
    python _cw_bm.py            # dry-run: print every located heading
    python _cw_bm.py audit      # running-head folio audit (validates K)
    python _cw_bm.py write      # write bookmarks (+ page labels) into the PDF
"""
import os, re, shutil, sys, difflib
import fitz

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

SRC   = r"F:/大学/数字资源/数学/分析学/复分析/Conway/GTM159 Functions of One Complex Variable Vol II (J.B.Conway).pdf"
OCRA  = r"C:/Users/asus/_cw_ocr_a.txt"
OCRB  = r"C:/Users/asus/_cw_ocr_b.txt"
PNGD  = r"C:/Users/asus/_cw_r72"
K     = 15                      # physical(1-based) = printed + K
DPI   = 72                      # render DPI; px -> pt factor = 72/DPI = 1
SC    = 72.0 / DPI
WRITE = len(sys.argv) > 1 and sys.argv[1] == 'write'
AUDIT = len(sys.argv) > 1 and sys.argv[1] == 'audit'
BACKUP = r"F:/大学/数字资源/数学/_bm_rerun_backup/分析学/复分析/Conway"

sys.path.insert(0, r"C:/Users/asus")
from _cw_toc import build_toc, K as KT
assert K == KT, "K mismatch between _cw_toc.py and this script"


# --------------------------------------------------------------- OCR loading
def load_ocr():
    pages, cur = {}, None
    for fn in (OCRA, OCRB):
        for raw in open(fn, encoding='utf-8-sig', errors='ignore'):
            l = raw.rstrip("\n")
            if l.startswith('#####'):
                m = re.search(r'page_(\d+)', l)
                cur = int(m.group(1)) if m else None
                if cur: pages.setdefault(cur, [])
                continue
            if cur is None: continue
            p = l.split('\t')
            if len(p) < 5: continue
            try:
                y, x0, x1, h = int(p[0]), int(p[1]), int(p[2]), int(p[3])
            except ValueError:
                continue
            t = p[4].strip()
            if t: pages[cur].append((y * SC, x0 * SC, x1 * SC, h * SC, t))
    for v in pages.values():
        v.sort()
    return pages


def nrm(s):
    """lowercase, keep letters+digits only (kills OCR's spurious spaces)."""
    return re.sub(r'[^0-9a-z]', '', s.lower())


def variants(s):
    n = nrm(s)
    out = {n}
    # WinRT reads 'o' as '0' and 'l/I' as '1' inside words fairly often
    out.add(n.replace('0', 'o').replace('1', 'l'))
    out.add(n.replace('0', 'o'))
    return {v for v in out if v}


def sim(cand, goal):
    g = nrm(goal)
    best = 0.0
    for c in variants(cand):
        if not c or not g: continue
        r = difflib.SequenceMatcher(None, c, g).ratio()
        # credit a shared long prefix (body titles can wrap / be truncated)
        if min(len(c), len(g)) >= 10 and (
                c.startswith(g[:14]) or g.startswith(c[:14])):
            r = max(r, 0.9)
        best = max(best, r)
    return best


# ------------------------------------------------------------------ locating
HDR_Y = 200.0          # running heads live above this (page top band)
FOL_Y = 3600.0         # folios, if any, below this


def lines_of(pages, phys, skip_head=True):
    v = pages.get(phys, [])
    if skip_head:
        return [l for l in v if l[0] > HDR_Y]
    return list(v)


def find_chapter(pages, cno, title, phys):
    """Chapter opener: huge 'Chapter N' line + big title line(s) below it."""
    for p in (phys, phys + 1, phys - 1):
        v = pages.get(p, [])
        for i, (y, x0, x1, h, t) in enumerate(v):
            if h < 80: continue
            if nrm(t) == ('chapter%d' % cno) or re.match(r'^\s*Ch[a-z]*\s*%d' % cno, nrm(t)) \
               or nrm(t).startswith('chapter%d' % cno):
                return (p, y, h, t, 'chapter-line')
    # fallback: the title itself in big type
    for p in (phys, phys + 1):
        for (y, x0, x1, h, t) in pages.get(p, []):
            if h >= 70 and sim(t, title) >= 0.7:
                return (p, y, h, t, 'chapter-title-big')
    return None


def find_section(pages, cno, sno, title, phys):
    """Section heading: bold '§N  Title' at the left margin, taller than body."""
    cands = []
    for p in (phys, phys + 1, phys - 1, phys + 2):
        for (y, x0, x1, h, t) in lines_of(pages, p):
            if x0 > 260: continue                 # headings sit on the margin
            if h < 40: continue                   # ignore small/odd boxes
            s = sim(t, title)
            if s < 0.6: continue
            has_num = bool(re.match(r'^\W*%s?\s*%d' % ('[\u00a7S5]', sno), nrm(t))) or \
                      bool(re.search(r'%d\s*%d' % (cno, sno), nrm(t)))
            cands.append((s + (0.05 if has_num else 0), p, y, h, t,
                          'sec-text' + ('+num' if has_num else '')))
    if cands:
        cands.sort(key=lambda z: (-z[0], z[1]))
        s, p, y, h, t, how = cands[0]
        return (p, y, h, t, how + ' score=%.2f' % s)
    return None


def find_back(pages, label, phys):
    """Back-matter openers: a big centred heading at the very top of the page
    (References h=66, List of Symbols h=66, Index h=92).  The running heads on
    the following pages are the SAME words at h~41, so gate on height."""
    best = None
    for p in (phys, phys + 1, phys - 1):
        for (y, x0, x1, h, t) in pages.get(p, []):
            if y > 400 or h < 55: continue
            s = sim(t, label)
            if s < 0.75: continue
            if best is None or s > best[0]:
                best = (s, p, y, h, t)
    if best:
        s, p, y, h, t = best
        return (p, y, h, t, 'back score=%.2f' % s)
    return None


def find_front(pages, key, phys):
    want = {'title': "Functions of One Complex Variable II",
            'preface': "Preface", 'toc2': "Contents of Volume II",
            'toc1': "Contents of Volume I"}[key]
    for p in (phys, phys + 1):
        for (y, x0, x1, h, t) in pages.get(p, []):
            if sim(t, want) >= 0.8:
                return (p, y, h, t, 'front')
    return None


# --------------------------------------------------------------------- main
def locate_all():
    pages = load_ocr()
    out, rows, misses = [], [], []
    for lv, label, phys, kind, key in build_toc():
        r = None
        if kind == 'chap':  r = find_chapter(pages, key[0], key[1], phys)
        elif kind == 'sec': r = find_section(pages, key[0], key[1], key[2], phys)
        elif kind == 'back': r = find_back(pages, label, phys)
        elif kind == 'front': r = find_front(pages, key, phys)
        if r is None:
            misses.append((label, phys))
            out.append(None)                      # NEVER fall back to page top
            rows.append((lv, label, phys, None, '', 0, '', 'MISS'))
        else:
            p, y, h, t, how = r
            out.append([lv, label, p, round(y, 1)])
            rows.append((lv, label, phys, p, t, h, how, 'ok'))
    return pages, out, rows, misses


def report(rows, misses):
    print("%-4s %-58s %-6s %-6s %-5s %s" % ("lv", "label", "want", "got", "h", "matched line"))
    for lv, label, phys, p, t, h, how, st in rows:
        flag = '' if st == 'ok' else '   <<<< ' + st
        if p and abs(p - phys) > 1: flag += '   <<<< PAGE OFF BY %d' % (p - phys)
        print("%-4d %-58s %-6s %-6s %-5.0f %-40s %s%s" %
              (lv, label[:58], phys, p or '-', h, t[:38], how, flag))
    print("\nlocated: %d/%d   MISS: %d" % (len(rows) - len(misses), len(rows), len(misses)))


def audit_folios(pages):
    """Every body page carries its printed folio in the running head."""
    doc = fitz.open(SRC)
    bad, good, none = [], 0, []
    for p in range(16, doc.page_count + 1):
        want = p - K
        nums = []
        for (y, x0, x1, h, t) in pages.get(p, []):
            if y > HDR_Y: continue
            n = nrm(t)
            if re.fullmatch(r'\d{1,3}', n): nums.append(int(n))
        if not nums: none.append(p)
        elif want in nums: good += 1
        else: bad.append((p, want, nums))
    print("body pages checked: %d  folio-ok: %d  no-folio: %d  MISMATCH: %d"
          % (doc.page_count - 15, good, len(none), len(bad)))
    print("mismatches (phys, expected, found):")
    for b in bad[:40]: print("  ", b)
    print("no-folio pages:", none[:40], '...' if len(none) > 40 else '')


def main():
    pages, out, rows, misses = locate_all()
    if AUDIT:
        audit_folios(pages); return
    report(rows, misses)
    # monotonicity
    prev, warn = (0, 0.0), []
    for e in out:
        if e is None: continue
        _, _, p, y = e
        if (p, y) < prev: warn.append((e, prev))
        prev = (p, y)
    print("monotonic:", not warn, " warnings:", len(warn))
    for w in warn[:10]: print("   ", w)
    if misses:
        print("\n!! refusing to write while %d entries are unlocated" % len(misses))
        return
    if not WRITE:
        print("\n(dry-run; pass 'write' to apply)")
        return
    apply_bookmarks(out)


def apply_bookmarks(out):
    toc = [e for e in out]
    if not os.path.isdir(BACKUP): os.makedirs(BACKUP)
    base = os.path.basename(SRC).replace('.pdf', '_pre1.pdf')
    bk = os.path.join(BACKUP, base)
    if not os.path.exists(bk): shutil.copy2(SRC, bk)
    tmp = r"C:/Users/asus/_cw_tmp.pdf"
    shutil.copy2(SRC, tmp)
    doc = fitz.open(tmp)
    doc.set_toc(toc)
    set_page_labels(doc)
    doc.saveIncr(); doc.close()
    shutil.move(tmp, SRC)
    d = fitz.open(SRC)
    t = d.get_toc(simple=False)
    def dest_y(e):
        z = e[3]
        if isinstance(z, dict):
            p = z.get('to')
            return getattr(p, 'y', p if isinstance(p, (int, float)) else None)
        return z
    ys = [dest_y(e) for e in t]
    print("WROTE %d bookmarks; pages=%d; y>0 all=%s" %
          (len(t), d.page_count, all(v is not None and v > 0 for v in ys)))
    labs = d.get_page_labels()
    print("page-label ranges:", len(labs))
    for l in labs: print("   ", l)
    d.close()


def set_page_labels(doc):
    """Make the reader's page number equal the book's printed folio.

    Evidence from the scan itself:
      p6 = vii (Preface, matches the Contents entry "Preface vii"),
      p7 = viii, p8 = ix, p11 = xii, p15 = xvi   ->  roman = physical + 1
      p16 = printed 1 (Chapter 13), p42 = 27, p399 = 384 (References),
      p406 = 391 (Index), p409 = 394             ->  arabic = physical - 15
    So the cover starts at "ii"; the last numbered page is 394 (p409).
    p410-411 are the unnumbered GTM series list, p412 the back cover:
    they get letters so a reader never mistakes them for book pagination.
    """
    doc.set_page_labels([
        {'startpage': 1,   'prefix': '', 'style': 'r', 'firstpagenum': 2},
        {'startpage': 16,  'prefix': '', 'style': 'D', 'firstpagenum': 1},
        {'startpage': 410, 'prefix': '', 'style': 'a', 'firstpagenum': 1},
    ])


if __name__ == '__main__':
    main()
