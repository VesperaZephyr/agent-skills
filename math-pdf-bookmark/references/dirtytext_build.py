# -*- coding: utf-8 -*-
"""ROUTE P-TXT template -- Chinese book with a DIRTY third-party OCR text layer.

Proven on Ahlfors 中译本《复分析》(267 pp, 171 bookmarks, 0 MISS, 171/171 ink-ok).

Symptoms that put a book on this route
--------------------------------------
* `page.get_text()` is NOT empty, but every line is DOUBLED ("算术运算算术运算");
* section-number separators are randomised: `1.1.1` prints as `1∙1．1` / `1，1，1`
  / `1. 1 ，1`, and single DIGITS get dropped or turned into a look-alike Han
  character (`8.1.4` -> `& 1.4`, `4.4.5` -> `4∙4巧`, `5.2.1` -> `5庵2∙1`,
  `2.3.1` -> `2∙1`);
* decorative centred headings are read as garbage (`前言` -> `目刂目刂`).
=> a strict "leading number == printed number" matcher can NEVER agree, so you
   need the two-pass locator below: strict first, then a loose matcher whose
   only hard requirement is the TITLE's CJK plus the digits that survived.

Usage: fill SRC / E / K / OVERRIDE, then
    python dirtytext_build.py           # dry run -> report, read every line
    python dirtytext_build.py --write   # only if MISS == 0 and nonmono == 0
"""
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
REPORT = r"C:/Users/asus/_loc.txt"
TMP = r"C:/Users/asus/_tmp.pdf"
BAKDIR = u"F:/path/_bm_rerun_backup/subdir"
K = 10                      # physical(1-based) = printed + K
WRITE = "--write" in sys.argv

# ---------------------------------------------------------------------------
# 1. Transcribe the printed Contents BY EYE from the Contents-page renders.
#    (level, number, title, printed page or None, forced physical page or None)
#    Front matter whose heading the OCR mangled beyond recognition gets an
#    explicit physical page + an OVERRIDE entry below.
# ---------------------------------------------------------------------------
E = [
    (1, '', u'译者序', None, 5),
    (1, '', u'前言', None, 7),
    (1, '1', u'第 1 章 复数', 1, None),
    (2, '1.1', u'复数代数', 1, None),
    (3, '1.1.1', u'算术运算', 1, None),
]

CJK = re.compile(u"[\u3400-\u4dbf\u4e00-\u9fff]")
# every separator this OCR uses for a decimal point, mapped to '.'
DOTS = u"\u2022\u00b7\u2027\u2219\u30fb\u25cf\u3001\uff0e*\uff0c,\u3002."


def norm(s):
    s = re.sub(r"\s+", "", s)
    for c in DOTS:
        s = s.replace(c, ".")
    s = re.sub(r"\.{2,}", ".", s)
    return s.strip(".")


def cjk(s):
    return set(CJK.findall(s))


_CACHE = {}


def lines_of(page):
    """Spans clustered into visual lines: y, x0, x1, size, text, normalised text."""
    if page.number + 1 in _CACHE:
        return _CACHE[page.number + 1]
    rows = []
    for b in page.get_text('dict')['blocks']:
        for l in b.get('lines', []):
            for sp in l['spans']:
                if not sp['text'].strip():
                    continue
                rows.append([sp['bbox'][1], sp['bbox'][0], sp['bbox'][2],
                             sp['size'], sp['text']])
    rows.sort()
    out = []
    for r in rows:
        if out and abs(r[0] - out[-1]['y']) < 3.0:
            out[-1]['sp'].append(r)
            out[-1]['x1'] = max(out[-1]['x1'], r[2])
        else:
            out.append({'y': r[0], 'x0': r[1], 'x1': r[2], 'sp': [r]})
    for L in out:
        L['sp'].sort(key=lambda t: t[1])
        L['txt'] = "".join(t[4] for t in L['sp'])
        L['n'] = norm(L['txt'])
        L['maxsz'] = max(t[3] for t in L['sp'])
    _CACHE[page.number + 1] = out
    return out


def lead_num(n):
    m = re.match(r"^(\d+(?:\.\d+)*)", n)
    return m.group(1) if m else None


def window(printed, phys):
    """Exact expected page FIRST, so that a tie is won by the promised page."""
    if phys is not None:
        return [phys]
    return [printed + K, printed + K - 1, printed + K + 1]


# ---------------------------------------------------------------------------
# 2a. strict pass
# ---------------------------------------------------------------------------
def find(doc, lvl, num, title, pages):
    best = None
    tcjk = cjk(title)
    for pno in pages:
        if pno < 1 or pno > doc.page_count:
            continue
        for L in lines_of(doc[pno - 1]):
            if L['y'] < 45:                      # header band / folio
                continue
            n = L['n']
            score, how = 0.0, ''
            if num:
                if lead_num(n) == num:
                    cov = (len(tcjk & cjk(n)) / float(len(tcjk))) if tcjk else 1.0
                    if cov >= 0.55:
                        score, how = 2.0 + cov, 'num+cjk%.2f' % cov
                    elif len(num) >= 5 and n.startswith(num):
                        score, how = 1.5, 'num-only'
            else:
                cov = (len(tcjk & cjk(n)) / float(len(tcjk))) if tcjk else 0.0
                # centred front/back matter, doubled by the OCR -> compare CJK SETS
                if cov >= 0.8 and L['maxsz'] >= 9.0 and L['x0'] < 340:
                    score, how = cov + L['maxsz'] / 100.0, 'title%.1f' % L['maxsz']
            if score and (best is None or score > best[0]):
                best = (score, pno, L['y'], how, L['txt'][:34])
    return best


def chapter_anchor(doc, num, title, pages):
    """Chapter openers print 第 N 章 in big spaced type; find that row."""
    want = norm(u"\u7b2c %s \u7ae0" % num)
    for pno in pages:
        for L in lines_of(doc[pno - 1]):
            if want in L['n'] and L['maxsz'] >= 13:
                return (pno, L['y'], 'chap', L['txt'][:34])
    return None


# ---------------------------------------------------------------------------
# 2b. LOOSE pass -- for headings whose printed number is corrupted in the layer.
#     Hard requirements: the line CONTAINS the title's CJK (<=4 extra chars),
#     it is SHORT (title + number only), it sits in the LEFT MARGIN band, and the
#     digits that survived form a SUBSEQUENCE of the printed number (so a body
#     line cannot claim to be §4.6.2 by carrying a stray '4' and '2').
#     `after` bounds the search to reading order: never land before the previous
#     heading, which is what stops a wrong-page match.
# ---------------------------------------------------------------------------
def find_loose(doc, num, title, pages, after=None):
    tcjk = cjk(title)
    if len(tcjk) < 3:
        return None
    want = num.replace(u'.', u'') if num else u''
    best = None
    for pno in pages:
        for L in lines_of(doc[pno - 1]):
            if L['y'] < 45 or L['x0'] > 130 or L['x1'] > 430:
                continue
            lc = cjk(L['txt'])
            if not tcjk <= lc:
                continue
            extra = len(lc - tcjk)
            if extra > 4 or len(L['txt']) > len(title) + extra + 12:
                continue
            fd = u''.join(re.findall(r"\d", L['txt']))
            if after is not None and (pno, L['y']) <= after:
                continue
            if want:
                if not fd:
                    continue
                it = iter(want)
                if not all(any(c == w for w in it) for c in fd):
                    continue
                g = len(fd) / float(len(want))
            else:
                g = 0.0
            key = (g, -extra, -L['y'])
            if best is None or key > best[0]:
                best = (key, pno, L['y'], 'loose:g%.2f-e%d' % (g, extra),
                        L['txt'][:34])
    return (best[1], best[2], best[3], best[4]) if best else None


# ---------------------------------------------------------------------------
# 3. Last resort: decorative headings the layer turned into garbage.
#    Each override MUST state the evidence and the measurement method; the y is
#    taken from the rendered page and re-checked by the ink audit.
# ---------------------------------------------------------------------------
OVERRIDE = {
    # E index: (physical page, y, reason)
    1: (7, 99.7, u'centred 前言 in decorative type; OCR reads it as 目刂目刂 '
                 u'(sz 12.4, x0 232.8). Render confirms the heading directly '
                 u'above the body at y 147.8'),
}


def main():
    doc = fitz.open(SRC)
    # CropBox compensation, measured not assumed:
    shift = [round(doc[i].mediabox.y1 - doc[i].cropbox.y1, 2)
             for i in range(doc.page_count)]
    rep = ["shift distinct: %s" % sorted(set(shift))]
    hits, misses = {}, []
    for idx, (lvl, num, title, printed, phys) in enumerate(E):
        exp = window(printed, phys)
        hit = chapter_anchor(doc, num, title, exp) if (lvl == 1 and num) else None
        if hit is None:
            b = find(doc, lvl, num, title, exp)
            if b:
                hit = (b[1], b[2], b[3], b[4])
        if hit:
            hits[idx] = hit
        else:
            misses.append(idx)
    # loose pass, walking in Contents order so `after` is available
    for idx in misses:
        lvl, num, title, printed, phys = E[idx]
        exp = window(printed, phys)
        prev = None
        for j in range(idx - 1, -1, -1):
            if j in hits:
                prev = (hits[j][0], hits[j][1])
                break
        exp = [p for p in exp] + [p for p in range(max(1, prev[0] if prev else 1),
                                                   doc.page_count + 1)
                                  if p not in exp][:40]
        h = find_loose(doc, num, title, exp, after=prev)
        if h:
            hits[idx] = h
    rows, n_loose, n_ovr = [], 0, 0
    for idx, (lvl, num, title, printed, phys) in enumerate(E):
        if idx in OVERRIDE:
            p, y, why = OVERRIDE[idx]
            rows.append((lvl, title, p, y))
            rep.append("OVR   L%d %-8s %-22s p%-4d y=%7.2f  %s" %
                       (lvl, num, title[:11], p, y, why[:60]))
            n_ovr += 1
            continue
        if idx not in hits:
            rep.append("MISS  L%d %-8s %s printed=%s" % (lvl, num, title, printed))
            continue
        pno, y, how, txt = hits[idx]
        if how.startswith('loose'):
            n_loose += 1
        label = (num + u' ' if num else u'') + title
        rows.append((lvl, label, pno, y))
        rep.append("ok    L%d %-8s %-22s p%-4d y=%7.2f  %-10s | %s"
                   % (lvl, num, title[:11], pno, y, how, txt))
    # monotonic guard on (page, y) -- same-page sections must also advance
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
    # landing = input + shift  =>  write y - shift, then assert read-back == y
    d.set_toc([[lv, t, p, round(y - shift[p - 1], 2)] for lv, t, p, y in rows])
    d.set_page_labels([                       # viewer folio == printed folio
        {'startpage': 0, 'prefix': '', 'style': 'a', 'firstpagenum': 1},
        {'startpage': 2, 'prefix': '', 'style': 'r', 'firstpagenum': 1},
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
