# -*- coding: utf-8 -*-
"""ROUTE P-IMG template -- PURE-SCAN Chinese book, NO text layer at all.

Proven on Stein《复分析》中译本 (286 pp, 119 bookmarks, 0 MISS, ink_audit 119/119).

Symptoms that put a book on this route
--------------------------------------
* `page.get_text()` returns 0 characters on every page (not "dirty", ABSENT);
* the printed Contents is itself a scan, so nothing can be parsed mechanically;
* the old bookmark tree (if any) is 100% page-top and mixes in front-matter rows
  the printed Contents does NOT list -- 封面 p1 / 书名 p3 / 版权 p4 / 目录 p10.
  The first three carry the ENGLISH original's arabic folios, so they are
  unanchorable in the Chinese pagination; 目录 is where every bookmark starts
  from anyway.  Drop them, and ADD the entries the old tree missed
  (stein: 译者的话 / 引言) -- 121 - 4 + 2 = 119.

WHY THE OCR DUMP STAYS OUTSIDE THE PDF
--------------------------------------
Phase 1 (inject an invisible layer, then let build_t1 find the Contents) makes
the locator match AGAINST ITS OWN INJECTION -- the Phase 1b defect that ruined
Ahlfors 中译本.  Here the Contents is transcribed BY EYE from renders, so the
OCR text is only ever used to locate body headings, and it never enters the
deliverable.  Keep the dump files; they are the book's evidence.

Pipeline
--------
1. probe the scanner's NATIVE dpi and render the whole book with it
   (see the docstring of references/render_range.py for the probe one-liner):
       python references/render_range.py "<pdf>" <out_dir> 1 286 228   # page_%04d.png
2. OCR with AT MOST 2 workers (6 parallel processes hang the machine); split the
   range so each worker writes its own dump:
       powershell -NoProfile -ExecutionPolicy Bypass -File references/winocr.ps1 \
                  -PngDir <out_dir_part_a> -OutFile ocr_a.txt
       ... -PngDir <out_dir_part_b> -OutFile ocr_b.txt
   dump format: `##### page_0013.png` then `y x0 x1 h text` in IMAGE PIXELS.
3. fill SRC / E / K / OVERRIDE below, then
       python pureimage_build.py            # dry run -> report, read every line
       python pureimage_build.py --write    # only if MISS == 0 and nonmono == 0
4. accept with  references/ink_audit.py <pdf> --x1 <text-block right edge>
   and the three bookkeeping proofs (title hygiene / label == printed folio /
   numbering holes) -- see label_folio_check.py.
"""
import io
import os
import re
import shutil
import sys

import fitz

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

SRC = u"F:/path/to/book.pdf"
OCR = [r"C:/Users/asus/_ocr_a.txt", r"C:/Users/asus/_ocr_b.txt"]
DPI = 228.0                   # NATIVE render dpi of the dump, measured
SC = 72.0 / DPI
REPORT = r"C:/Users/asus/_loc.txt"
TMP = r"C:/Users/asus/_tmp.pdf"
BAKDIR = u"F:/path/_bm_rerun_backup/subdir"
K = 12                        # physical(1-based) = printed + K
TOC_PAGES = (10, 11, 12)      # the printed Contents itself -> never a match target
X_MARGIN = (18.0, 450.0)      # pt: text block, measured -- see rule 1 in the docstring
Y_HEADER = 45.0               # pt: running heads sit above this (measured, not assumed)
WRITE = "--write" in sys.argv

# ---------------------------------------------------------------------------
# 1. Transcribe the printed Contents BY EYE from the Contents-page renders:
#    (level, number, title, printed page or None, forced physical page or None)
#    Keep the printed spacing exactly: this book prints "Goursat 定理", not
#    "Goursat定理" -- a reader checks entries one by one against the page.
# ---------------------------------------------------------------------------
E = [
    (1, '', u'译者的话', None, 5),
    (1, '', u'前言', None, 6),
    (1, '1', u'第 1 章 复分析预备知识', 1, None),
    (2, '1', u'复数和复平面', 1, None),
    (3, '1.1', u'基本性质', 1, None),
    (3, '5.5', u'Runge 近似定理', 42, None),
    (1, 'A', u'附录 A 渐近', 236, None),
]

CJK = re.compile(u"[\u3400-\u4dbf\u4e00-\u9fff]")
LAT = re.compile(r"[A-Za-z]")
DOTS = u"\u2022\u00b7\u2027\u2219\u30fb\u25cf\u3001\uff0e*\uff0c,\u3002."


def norm(s):
    s = re.sub(r"\s+", "", s)
    for c in DOTS:
        s = s.replace(c, ".")
    return re.sub(r"\.{2,}", ".", s).strip(".")


def cjk(s):
    return set(CJK.findall(s))


def letters(s):
    """Lower-case letter set with l/I folded together: WinOCR reads Wiener as
    `WieneI`, Bessel as `BesseI`, Liouville as `LiouviIIe`."""
    return set(c.lower().replace('l', 'i') for c in LAT.findall(s))


def subseq(a, b):
    it = iter(b)
    return all(any(c == w for w in it) for c in a)


def lead_num(n):
    m = re.match(r"^(\d+(?:\.\d+)*)", n)
    return m.group(1) if m else None


def window(printed, phys):
    """Expected page FIRST so a tie is won by the promised page."""
    if phys is not None:
        return [phys]
    return [printed + K, printed + K - 1, printed + K + 1]


# ---------------------------------------------------------------------------
# 2. OCR dump -> visual lines.  Two rules learned the hard way:
#    (a) DROP spans outside the text block.  This book prints its folio in the
#        OUTER margin (x 461..484) and footnote markers in the inner one; the
#        "42" on p54 merged into the heading row and turned `5.5` into `425·5`,
#        which killed the strict pass for that entry.
#    (b) cluster spans into a row only when they are at the same height AND
#        horizontally adjacent (<= 8 pt gap), else a centred heading swallows
#        the right-margin equation number next to it.
# ---------------------------------------------------------------------------
def load_ocr(paths):
    raw, cur = {}, None
    for path in paths:
        for ln in io.open(path, encoding='utf-8-sig').read().splitlines():
            m = re.match(r"^##### page_(\d+)\.png$", ln.strip())
            if m:
                cur = int(m.group(1))
                raw[cur] = []
                continue
            if cur is None or not ln.strip():
                continue
            f = ln.split('\t')
            if len(f) < 5:
                continue
            try:
                y, x0, x1, h = int(f[0]), int(f[1]), int(f[2]), int(f[3])
            except ValueError:
                continue
            x0, x1 = x0 * SC, x1 * SC
            if x1 < X_MARGIN[0] or x0 > X_MARGIN[1]:
                continue
            raw[cur].append({'y': y * SC, 'x0': x0, 'x1': x1, 'h': h * SC,
                             'txt': f[4]})
    pages = {}
    for pno, rows in raw.items():
        rows.sort(key=lambda r: (r['y'], r['x0']))
        out = []
        for r in rows:
            if (out and abs(r['y'] - out[-1]['y']) < 3.5
                    and r['x0'] <= out[-1]['x1'] + 8.0):
                L = out[-1]
                L['sp'].append(r)
                L['y'] = min(L['y'], r['y'])
                L['x0'] = min(L['x0'], r['x0'])
                L['x1'] = max(L['x1'], r['x1'])
                L['h'] = max(L['h'], r['h'])
            else:
                out.append({'y': r['y'], 'x0': r['x0'], 'x1': r['x1'],
                            'h': r['h'], 'sp': [r]})
        for L in out:
            L['sp'].sort(key=lambda t: t['x0'])
            L['txt'] = "".join(t['txt'] for t in L['sp'])
            L['n'] = norm(L['txt'])
        pages[pno] = out
    return pages


try:
    PAGES = load_ocr(OCR)
except (IOError, OSError) as ex:
    sys.exit("OCR dump unreadable (%s) -- run the render + winocr.ps1 steps first" % ex)


def lines_of(pno):
    return PAGES.get(pno, [])


# ---------------------------------------------------------------------------
# 3a. chapter / appendix openers: 第 N 章 / 附录 X, big glyphs
# ---------------------------------------------------------------------------
def chapter_anchor(num, title, pages):
    if num in ('A', 'B'):
        wants = [norm(u"附录 %s" % num), norm(u"附录%s" % num)]
    else:
        wants = [norm(u"第 %s 章" % num)]
    tcjk = cjk(title) - cjk(u'第章附录')
    best = None
    for rank, pno in enumerate(pages):
        if pno in TOC_PAGES:
            continue
        for L in lines_of(pno):
            if L['y'] < Y_HEADER:
                continue
            if not any(w in L['n'] for w in wants):
                continue
            cov = (len(tcjk & cjk(L['txt'])) / float(len(tcjk))) if tcjk else 1.0
            score = (2.0 if rank == 0 else 1.0) + cov + min(L['h'], 20) / 100.0
            if best is None or score > best[0]:
                best = (score, pno, L['y'], 'chap:cjk%.2f' % cov, L['txt'][:34])
    return (best[1], best[2], best[3], best[4]) if best else None


# ---------------------------------------------------------------------------
# 3b. strict pass.  THE LETTER GATE IS THE POINT OF THIS TEMPLATE:
#     CJK-set coverage alone let the body line
#        "1 / 以 s ） 是 （ 最 简 单 的 ） 整 函 数 ..."
#     steal the heading "1 Gamma 函数" (shared CJK: only 函 and 数).  Requiring
#     the title's LATIN letters to be present too costs nothing (OCR's I/l
#     confusion is folded by letters()) and kills the false match.
# ---------------------------------------------------------------------------
def find(lvl, num, title, pages):
    best, tcjk, tlat = None, cjk(title), letters(title)
    for rank, pno in enumerate(pages):
        if pno in TOC_PAGES:
            continue
        for L in lines_of(pno):
            if L['y'] < Y_HEADER or L['x0'] > 340:
                continue
            n = L['n']
            score, how = 0.0, ''
            if num:
                if lead_num(n) == num:
                    cov = (len(tcjk & cjk(n)) / float(len(tcjk))) if tcjk else 1.0
                    lat = (len(tlat & letters(L['txt'])) / float(len(tlat))
                           if len(tlat) >= 2 else 1.0)
                    if cov >= 0.55 and lat >= 0.6:
                        score, how = 2.0 + cov, 'num+cjk%.2f' % cov
                    elif len(num) >= 4 and n.startswith(num):
                        score, how = 1.5, 'num-only'
            else:
                cov = (len(tcjk & cjk(n)) / float(len(tcjk))) if tcjk else 0.0
                if cov >= 0.8 and L['h'] >= 12 and L['x0'] < 340:
                    score, how = cov + L['h'] / 100.0, 'title h%.1f' % L['h']
            if score:
                score += 1.0 if rank == 0 else 0.0
                if best is None or score > best[0]:
                    best = (score, pno, L['y'], how, L['txt'][:34])
    return best


# ---------------------------------------------------------------------------
# 3c. loose pass.  Digit test must be SYMMETRIC: OCR both drops digits
#     (`2.3.1` -> `2·1`) and invents them (`1.1 1/ζ(s) 的估计` -> `1 · 1 1 卜`,
#     surviving digits `111`).  Allow either, but never let a body line claim a
#     number it does not carry.  `after` keeps the walk in reading order.
# ---------------------------------------------------------------------------
def find_loose(num, title, pages, after=None):
    tcjk = cjk(title)
    if len(tcjk) < 2:
        return None
    want = num.replace(u'.', u'') if num else u''
    best = None
    for rank, pno in enumerate(pages):
        if pno in TOC_PAGES:
            continue
        for L in lines_of(pno):
            if L['y'] < Y_HEADER or L['x0'] > 200 or L['x1'] > 440:
                continue
            lc = cjk(L['txt'])
            if not tcjk <= lc:
                continue
            extra = len(lc - tcjk)
            if extra > 4 or len(L['txt']) > len(title) + extra + 14:
                continue
            if after is not None and (pno, L['y']) <= after:
                continue
            fd = u''.join(re.findall(r"\d", L['txt']))
            if want:
                if not fd:
                    continue
                if not (subseq(fd, want)
                        or (len(fd) <= len(want) + 2 and subseq(want, fd))):
                    continue
                g = min(len(fd), len(want)) / float(len(want))
            else:
                g = 0.0
            key = (1.0 if rank == 0 else 0.0, g, -extra, -L['y'])
            if best is None or key > best[0]:
                best = (key, pno, L['y'], 'loose:g%.2f-e%d' % (g, extra),
                        L['txt'][:34])
    return (best[1], best[2], best[3], best[4]) if best else None


# ---------------------------------------------------------------------------
# 4. Last resort: decorative centred headings WinOCR cannot see at all.
#    Measure y from a 300 dpi ink-band probe and state the evidence here.
# ---------------------------------------------------------------------------
OVERRIDE = {
    # E index: (physical page, y, reason incl. measurement)
    1: (6, 107.20, u'前言: WinOCR 读不出该标题；300dpi 墨迹带 top=107.20 h=21.1 '
                   u'x=202..294（居中，正文首行在 162.2）'),
}


def label(lvl, num, title):
    """Level >= 2 lines read "1.1 基本性质" in the printed Contents, so the number
    belongs to the title; chapter/appendix openers already carry theirs inside
    the title text ("第 1 章 ...", "附录 A ...") -- prefixing those gives the
    Ahlfors-style stutter "1 第 1 章 复数"."""
    return (num + u' ' + title) if (lvl >= 2 and num) else title


def main():
    doc = fitz.open(SRC)
    shift = [round(doc[i].mediabox.y1 - doc[i].cropbox.y1, 2)
             for i in range(doc.page_count)]
    rep = ["pages=%d shift distinct: %s" % (doc.page_count, sorted(set(shift)))]
    hits, misses = {}, []
    for idx, (lvl, num, title, printed, phys) in enumerate(E):
        if idx in OVERRIDE:
            continue
        exp = window(printed, phys)
        hit = chapter_anchor(num, title, exp) if (lvl == 1 and num) else None
        if hit is None:
            b = find(lvl, num, title, exp)
            if b:
                hit = (b[1], b[2], b[3], b[4])
        if hit:
            hits[idx] = hit
        else:
            misses.append(idx)
    for idx in misses:
        lvl, num, title, printed, phys = E[idx]
        exp = list(window(printed, phys))
        prev = None
        for j in range(idx - 1, -1, -1):
            if j in hits:
                prev = (hits[j][0], hits[j][1])
                break
        base = prev[0] if prev else (printed + K if printed else 1)
        exp += [p for p in range(max(1, base - 2), min(doc.page_count, base + 4))
                if p not in exp]
        h = find_loose(num, title, exp, after=prev)
        if h:
            hits[idx] = h
    rows, n_loose, n_ovr = [], 0, 0
    for idx, (lvl, num, title, printed, phys) in enumerate(E):
        if idx in OVERRIDE:
            p, y, why = OVERRIDE[idx]
            rows.append((lvl, label(lvl, num, title), p, y))
            rep.append("OVR   L%d %-6s %-24s p%-4d y=%7.2f  %s"
                       % (lvl, num, title[:12], p, y, why[:70]))
            n_ovr += 1
            continue
        if idx not in hits:
            rep.append("MISS  L%d %-6s %-24s printed=%s" % (lvl, num, title, printed))
            continue
        pno, y, how, txt = hits[idx]
        if how.startswith('loose'):
            n_loose += 1
        exp_p = phys if phys is not None else printed + K
        flag = '' if pno == exp_p else '  <<PAGE exp %d' % exp_p
        rows.append((lvl, label(lvl, num, title), pno, y))
        rep.append("ok    L%d %-6s %-24s p%-4d y=%7.2f  %-12s | %s%s"
                   % (lvl, num, title[:12], pno, y, how, txt, flag))
    bad, cur = [], (0, 0.0)
    for i, r in enumerate(rows):
        if (r[2], r[3]) <= cur:
            bad.append((i, r))
        cur = max(cur, (r[2], r[3]))
    rep.append("entries=%d located=%d MISS=%d nonmono=%d loose=%d override=%d"
               % (len(E), len(rows), len(E) - len(rows), len(bad), n_loose, n_ovr))
    for i, r in bad:
        rep.append("NONMONO #%d %s p%d y%.1f" % (i, r[1], r[2], r[3]))
    open(REPORT, 'w', encoding='utf-8').write("\n".join(rep))
    print("located %d/%d  MISS %d  nonmono %d  loose %d -> %s"
          % (len(rows), len(E), len(E) - len(rows), len(bad), n_loose, REPORT))
    doc.close()
    if not WRITE:
        return
    if len(rows) != len(E) or bad:
        print("REFUSE: MISS or non-monotonic entries present")
        sys.exit(1)
    if not os.path.isdir(BAKDIR):
        os.makedirs(BAKDIR)
    bak = os.path.join(BAKDIR, os.path.basename(SRC) + ".pre1.pdf")
    if not os.path.exists(bak):
        shutil.copy2(SRC, bak)
    shutil.copy2(SRC, TMP)
    d = fitz.open(TMP)
    # landing = input + shift  =>  compensate EXACTLY ONCE, here, at write time
    d.set_toc([[lv, t, p, round(y - shift[p - 1], 2)] for lv, t, p, y in rows])
    d.set_page_labels([
        # read the front-matter folios off the renders BEFORE choosing the case:
        # stein prints CAPITAL romans (p3=I ... p12=X) -> style 'R', not 'r'
        {'startpage': 0, 'prefix': '', 'style': 'a', 'firstpagenum': 1},
        {'startpage': 2, 'prefix': '', 'style': 'R', 'firstpagenum': 1},
        {'startpage': K, 'prefix': '', 'style': 'D', 'firstpagenum': 1}])
    d.saveIncr()
    d.close()
    shutil.move(TMP, SRC)
    chk = fitz.open(SRC)
    t2 = chk.get_toc(simple=False)
    errs = [abs(t2[i][3]['to'].y - rows[i][3]) for i in range(len(rows))]
    print("recheck n=%d max_err=%.3f pages=%d labels=%s"
          % (len(t2), max(errs), chk.page_count, chk.get_page_labels()))
    chk.close()


if __name__ == '__main__':
    main()
