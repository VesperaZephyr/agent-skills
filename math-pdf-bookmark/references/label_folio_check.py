# -*- coding: utf-8 -*-
"""label_folio_check.py -- three bookkeeping proofs a bookmark tree must pass
BEFORE anyone is told it is finished.  These are cheap and they catch the two
failure modes the ink audit cannot see: wrong PAGE and dirty TITLE.

    python label_folio_check.py <pdf> [--printed toc.txt]

(0) LABEL SANITY      : a /PageLabels range must be a FOLIO scheme (a/r/D with a
                      firstpagenum), not one range per page whose prefix is the
                      scanner's image filename ('cov001.pdg', '000087.pdg',
                      "Anna\\220s Archive").  Those scans show a filename where the
                      printed page number should be, and `bm_quality.py` only
                      counts labels=246 and still calls the book OK.
(1) TITLE hygiene   : no control chars / PUA glyphs / dot leaders / NBSP /
                      leading-trailing space in any of the titles, AND no
                      trailing scanner-bullet junk -- on 孙永生《泛函分析讲义》's
                      vendor tree 10 of 49 titles ended ' ∙' (U+2219 survived OCR
                      of the dot leader); that is a PRINTABLE glyph, so the
                      control-char check, bm_quality's dirty-title family and
                      LEADER_RE all read it as clean and reported verdict=OK.
                      NOTE the limit of any glyph rule: '积分算子庵' (a stray CJK
                      glyph appended to '积分算子') is invisible to every pattern
                      here -- only the whitelist title-diff (compare each title
                      with the transcribed printed Contents) catches it.
(2) FOLIO agreement : for every entry whose printed Contents page is decimal,
                      the viewer's page LABEL of the target physical page must
                      equal that printed folio.  This is what proves the
                      `/PageLabels` ranges and the K offset together, not just
                      one of them.  (This PyMuPDF build has no get_label_value,
                      so label_of() below resolves the ranges by hand.)
(3) NUMBERING holes : section numbers must be contiguous 1..max inside every
                      chapter and every section -- a Contents entry you dropped
                      while transcribing shows up here as a hole instead of
                      vanishing silently.
"""
import collections
import re
import sys

import fitz

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

SRC = sys.argv[1] if len(sys.argv) > 1 else None
if SRC is None:
    print(__doc__)
    sys.exit(1)

d = fitz.open(SRC)
toc = d.get_toc(simple=False)
labels = d.get_page_labels()
rep = ["%s  pages=%d bookmarks=%d" % (SRC, d.page_count, len(toc)),
       "page labels: %s" % labels]

# (0) PAGE-LABEL SANITY ---------------------------------------------------
# Anna's Archive / dvdpdg scans ship a /PageLabels range PER PAGE whose PREFIX is
# the image filename ('cov001.pdg', '000087.pdg', "Anna\\220s Archive").  Then the
# viewer's page number is a filename, not a folio, so every reader-facing page
# reference in the book is unusable -- and `bm_quality.py` only counts
# labels=246 and still says OK.  Any prefix, or a one-range-per-page structure,
# means the labels were never rebuilt from the printed folio.
bad_lab = []
npref = sum(1 for r in labels if (r.get('prefix') or '').strip())
if npref:
    bad_lab.append("%d/%d ranges carry a filename prefix, e.g. %r"
                   % (npref, len(labels), (labels[0].get('prefix') or '')))
if len(labels) > 12:
    bad_lab.append("%d ranges (= per-page scanner filenames, not folios)" % len(labels))
if bad_lab:
    rep.append("LABELS-BAD  " + "; ".join(bad_lab))
else:
    rep.append("labels ok: %d ranges, no prefix" % len(labels))

ROMAN = [(1000, 'm'), (900, 'cm'), (500, 'd'), (400, 'cd'), (100, 'c'), (90, 'xc'),
         (50, 'l'), (40, 'xl'), (10, 'x'), (9, 'ix'), (5, 'v'), (4, 'iv'), (1, 'i')]


def to_roman(n):
    s = ''
    for v, sym in ROMAN:
        while n >= v:
            s += sym
            n -= v
    return s


def label_of(pno):
    """Viewer label of 1-based physical page -> (display, number, style)."""
    cur = {'startpage': 0, 'prefix': '', 'style': 'a', 'firstpagenum': 1}
    for L in labels:
        if L['startpage'] <= pno - 1:
            cur = L
    n = cur.get('firstpagenum', 1) + (pno - 1) - cur['startpage']
    st = cur.get('style', 'a')
    body = to_roman(n) if st in ('r', 'R') else (
        chr(ord('a') + n - 1) if st in ('a', 'A') else str(n))
    if st not in ('D', 'r', 'R', 'a', 'A'):
        body = str(n)
    return cur.get('prefix', '') + body, n, st


# (1) + (2) ---------------------------------------------------------------
BAD_CH = re.compile(u"[\x00-\x08\x0b-\x1f\x7f\uE000-\uF8FF]")
# SCANNER-BULLET junk (found on 孙永生《泛函分析讲义》's vendor tree): a scanned
# TOC's dot-leader survives OCR as a stray '\u2219'/'\u00b7' glued to the end of the
# title ('2 完备性 ∙'), and it is a PRINTABLE math glyph, so BAD_CH / dirty-title /
# LEADER_RE all read it as clean -- three separate checkers called that tree OK.
# A real heading never ends in a bullet-family glyph, so require the last char to be
# a letter/digit/CJK or a closing bracket/quote/punct.
JUNK_END = re.compile(u"[\u2022\u00b7\u2219\u22c5\u2027\u2026\u2212\u2013\u2014"
                      u"\u00b0\u00a0\\s]\\s*$")
n_bad = n_folio = 0
for i, (lv, t, p, dest) in enumerate(toc):
    lab, num, st = label_of(p)
    dirty = (bool(BAD_CH.search(t)) or (u'...' in t) or (u'\xa0' in t)
             or t != t.strip() or bool(JUNK_END.search(t)))
    if dirty:
        n_bad += 1
        rep.append("TITLE#%d %r" % (i, t))
    # the printed folio, if the title's own text or a transcription supplies one
    m = re.search(r"\[(\d+)\]", t)
    if m and st == 'D' and num != int(m.group(1)):
        n_folio += 1
        rep.append("FOLIO#%d %s target p%d label=%s printed=%s"
                   % (i, t[:24], p, lab, m.group(1)))
rep.append("bad_title=%d  (note: folio check needs the printed page per entry -- "
           "run it from your transcription table, see dirtytext_build.py E)" % n_bad)

# (3) ---------------------------------------------------------------------
# 两种编号要分开查，否则 Bogachev《TVS》这类"N.M(i)." 的 Complements 小节会被
# 当成节号 -> 父组里 12 重复出现 -> 假 HOLE(dup=True)，白白误导下一轮。
RV = {'i': 1, 'v': 5, 'x': 10, 'l': 50, 'c': 100, 'd': 500, 'm': 1000}


def roman_val(s):
    tot, prev = 0, 0
    for ch in reversed(s):
        v = RV[ch]
        tot += v if v >= prev else -v
        prev = v
    return tot


kids = collections.defaultdict(list)
subs = collections.defaultdict(list)
for lv, t, p, dest in toc:
    m = re.match(r"^[*＊]?\s*(\d+(?:\.\d+)*)(?:\.?\(([ivxlcdm]+)\))?", t.strip())   # *9.1 选学节星号前缀
    if not m:
        continue
    num, sub = m.group(1), m.group(2)
    if sub:                                     # 1.12(i). -> 组 '1.12' 的罗马号
        subs[num].append(roman_val(sub.lower()))
        continue
    parts = num.split('.')
    if lv >= 2 and len(parts) >= 2:
        kids['.'.join(parts[:-1])].append(int(parts[-1]))
holes = 0
for k in sorted(kids, key=lambda s: [int(x) for x in s.split('.')]):
    seq = sorted(kids[k])
    want = set(range(1, max(seq) + 1))
    missing = sorted(want - set(seq))
    dup = len(seq) != len(set(seq))
    if missing or dup:
        holes += 1
        rep.append("HOLE %-10s got=%s missing=%s dup=%s" % (k, seq, missing, dup))
for k in sorted(subs, key=lambda s: [int(x) for x in s.split('.')]):
    seq = sorted(subs[k])
    if seq != list(range(1, len(seq) + 1)):
        holes += 1
        rep.append("HOLE %-10s(罗马) got=%s" % (k, seq))
rep.append("numbering groups=%d(+%d 罗马组) with_holes=%d"
           % (len(kids), len(subs), holes))
d.close()
print("\n".join(rep))
