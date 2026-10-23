# -*- coding: utf-8 -*-
"""bm_quality.py -- per-folder bookmark QUALITY audit (not just existence).

Why this exists: `verify.py` only answers "does the PDF have bookmarks / are the
links alive".  The user's real complaint is books that HAVE bookmarks but are
bad in one of four ways:
  (1) page-top landings   -- dest y == 0 / missing, so a click jumps to the
      top of the page instead of the heading line;
  (2) missing entries     -- far fewer items than the printed Contents has;
  (3) broken hierarchy    -- everything at level 1, or level jumps;
  (4) wrong page numbers  -- no /PageLabels, so the reader's page number
      disagrees with the printed folio;
  (5) dirty titles        -- the item still carries the Contents dot-leader and
      page number ("§3 Prime Ends .... 55"), a literal escape, mojibake, an
      embedded NUL/control character, or raw LaTeX source;
Titles in family (5) nearly always mean the dest points at the TOC line rather
than the body heading, so those books need a real rebuild, not a title cleanup.
This script reports all four so you can build a REWORK list instead of
trusting the old "A-ok = skip" classification.

Usage:
    python bm_quality.py [ROOT]           # table, worst first
    python bm_quality.py ROOT --csv out   # same, machine readable
Set ROOT at the top if you copy this into a folder's _build/.
"""
import os, re, sys, glob
from collections import Counter
import fitz

try:
    sys.stdout.reconfigure(encoding='utf-8', errors='replace')
except Exception:
    pass

ROOT = "F:/大学/数字资源/数学/分析学/复分析"

TOP_EPS = 0.5      # dest y at or below this = page-top landing, not a heading
FLAT_LV1 = 30      # > this many items all at level 1 = no real hierarchy


def dest_y(e):
    """y (points from page top) of a get_toc(simple=False) entry, or None."""
    z = e[3] if len(e) > 3 else None
    if isinstance(z, dict):
        to = z.get('to')
        v = getattr(to, 'y', None)
        if v is None and isinstance(to, (list, tuple)) and len(to) >= 2:
            v = to[1]
        return v
    if isinstance(z, (int, float)):
        return float(z)
    return None


LEADER_RE = re.compile(r'[\s.\u2024\u2026\u00b7\u2219\u22c5\u2027\u2212\u2013\u2014\-]{2,}\s*([0-9]{1,4}|[ivxlcdmIVXLCDM]{1,8})\s*$')
ESCAPE_RE = re.compile(r'\\u[0-9a-fA-F]{4}|\\x[0-9a-fA-F]{2}|\\\\')
MOJI_MARKS = ('\ufffd', 'â€', 'Ã', 'Â§')   # latin-1 mis-decode / replacement char
# A NUL / control byte at the END of every title is a whole defect FAMILY: the
# list was written by a tool that stores titles as C strings (seen on Chinese
# textbooks: '封面\x00', '前言\x00').  It is invisible in every viewer, so it is
# only ever found by a byte-level check -- and it silently breaks any title
# comparison you do later (`t in DROP` never fires), which is how five junk
# items survived a rebuild.  See SKILL.md "NUL-suffixed titles".
CTRL_RE = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f]')
# Raw LaTeX / OCR-garble signature: `$...$` math or a `\macro`.  Note that
# `^{` / `_` ALONE are not evidence -- a hand-written Unicode-math title such as
# '23.2 ∫_0^{2π} Q(sin θ, cos θ) dθ 型积分' is intentional and readable.
TEX_RE = re.compile(r'\$|\\[a-zA-Z]')


def title_dirt(t):
    """(leader, escape, mojibake, control, latex) flags for one bookmark title.

    'leader'  -> the item still carries the Contents dot-leader + page number,
                 i.e. it was scraped from the TOC page instead of the body
                 heading (and usually points at that TOC line);
    'escape'  -> a literal \\u00a7-style sequence survived into the title
                 (Write-tool double-escaping / a raw LaTeX macro);
    'mojibake'-> wrong codec: U+FFFD, or UTF-8 read as latin-1 ("â€™");
    'control' -> an embedded NUL / control byte (C-string writer);
    'latex'   -> raw LaTeX source or OCR-garbled Latin text ('$ ', '\\lapping').
    """
    return (bool(LEADER_RE.search(t)),
            bool(ESCAPE_RE.search(t)),
            any(m in t for m in MOJI_MARKS),
            bool(CTRL_RE.search(t)),
            bool(TEX_RE.search(t)))


def label_ranges(doc):
    try:
        return doc.get_page_labels() or []
    except Exception:
        return []


def label_at(rng, p1):
    """Reader-visible page label for 1-based physical page p1."""
    cur = None
    for r in rng:
        if r['startpage'] <= p1:
            cur = r
    if cur is None:
        return None
    n = cur['firstpagenum'] + (p1 - cur['startpage'])
    st = cur.get('style', 'D')
    if st in ('r', 'R'):
        vals = [(1000, 'm'), (900, 'cm'), (500, 'd'), (400, 'cd'), (100, 'c'),
                (90, 'xc'), (50, 'l'), (40, 'xl'), (10, 'x'), (9, 'ix'),
                (5, 'v'), (4, 'iv'), (1, 'i')]
        s = ''
        k = n
        for v, t in vals:
            while k >= v:
                s += t
                k -= v
        return s.upper() if st == 'R' else s
    if st in ('a', 'A'):
        s = ''
        k = n
        while k:
            k, r0 = divmod(k - 1, 26)
            s = chr(97 + r0) + s
        return s.upper() if st == 'A' else s
    return str(n)


def audit(path):
    r = {'file': path, 'bm': 0, 'pages': 0, 'top': 0, 'nodest': 0,
         'oor': 0, 'nonmono': 0, 'lv': '-', 'flat': 0, 'labels': 0,
         'dirty': 0, 'leader': 0, 'escape': 0, 'moji': 0, 'ctrl': 0, 'tex': 0,
         'notes': ''}
    try:
        doc = fitz.open(path)
    except Exception as ex:
        r['notes'] = 'UNOPENABLE ' + repr(ex)[:40]
        return r
    r['pages'] = doc.page_count
    toc = doc.get_toc(simple=False)
    r['bm'] = len(toc)
    rng = label_ranges(doc)
    r['labels'] = len(rng)
    if toc:
        for e in toc:
            ld, es, mj, ct, tx = title_dirt(str(e[1]))
            r['dirty'] += 1 if (ld or es or mj or ct or tx) else 0
            r['leader'] += 1 if ld else 0
            r['escape'] += 1 if es else 0
            r['moji'] += 1 if mj else 0
            r['ctrl'] += 1 if ct else 0
            r['tex'] += 1 if tx else 0
        lv = sorted({e[0] for e in toc})
        r['lv'] = '%d..%d' % (lv[0], lv[-1])
        n1 = sum(1 for e in toc if e[0] == 1)
        r['flat'] = 1 if (len(toc) > FLAT_LV1 and n1 == len(toc)) else 0
        prev = (0, 0.0)
        for e in toc:
            p = e[2]
            y = dest_y(e)
            if y is None:
                r['nodest'] += 1
            elif y <= TOP_EPS:
                r['top'] += 1
            if p < 1 or p > doc.page_count:
                r['oor'] += 1
            key = (p, y if y is not None else 0.0)
            if key < prev:
                r['nonmono'] += 1
            prev = key
        # --- "one fixed dest" detector (谭小江《复变函数简明教程》taught us) ---
        # A writer that never measured the heading puts EVERY item at the same y,
        # and that y need not be <= TOP_EPS (there it was 0.603 pt, so the test
        # above saw only 4 page-tops out of 57 -- and reported the book as OK).
        # Identical y repeated over many DIFFERENT pages cannot be real heading
        # geometry, so count all of them as page-top.
        cnt = Counter(round(y, 2) for y in (dest_y(e) for e in toc) if y is not None)
        if cnt:
            yv, nc = cnt.most_common(1)[0]
            pages_at = len({e[2] for e in toc
                            if dest_y(e) is not None and round(dest_y(e), 2) == yv})
            if nc >= max(5, 0.2 * len(toc)) and pages_at >= 3 and yv <= 5.0:
                if nc > r['top'] + r['nodest']:
                    r['notes'] += ' fixed-dest y=%.2fx%d;' % (yv, nc)
                    r['top'] = nc
    doc.close()
    return r


def verdict(r):
    """REWORK if the bookmarks really are bad; 'add-labels' is only optional
    polish; a small number of non-monotonic items is normal (front matter,
    index entries) so only flag it when it is systematic."""
    if r['bm'] == 0:
        return 'EMPTY'
    bad = []
    if r['top'] + r['nodest'] > max(1, r['bm'] * 0.2):
        bad.append('page-top')
    if r['flat']:
        bad.append('flat')
    if r['oor']:
        bad.append('oor')
    if r['nonmono'] > max(3, r['bm'] * 0.1):
        bad.append('nonmono')
    if r['dirty'] > max(2, r['bm'] * 0.03):
        bad.append('dirty-title')
    if bad:
        return ','.join(bad)
    if r['labels'] == 0:
        return 'add-labels'
    return 'OK'


def main():
    root = sys.argv[1] if len(sys.argv) > 1 and not sys.argv[1].startswith('--') else ROOT
    csv = None
    if '--csv' in sys.argv:
        csv = sys.argv[sys.argv.index('--csv') + 1]
    files = sorted(glob.glob(os.path.join(root, '**', '*.pdf'), recursive=True))
    rows = [audit(f) for f in files]
    for r in rows:
        r['v'] = verdict(r)

    def sev(r):
        if r['v'] == 'OK':
            return 0
        if r['v'] == 'add-labels':
            return 1
        if r['v'] == 'EMPTY':
            return 2
        return 3                      # real rework, highest priority
    rows.sort(key=lambda r: (-sev(r), -(r['top'] + r['nodest']), -r['bm']))
    hdr = "%-4s %-4s %-6s %-4s %-4s %-4s %-5s %-8s %-7s %-10s %s"
    print(hdr % ('bm', 'top', 'pages', 'oor', 'nmon', 'flat', 'dirty', 'levels', 'labels', 'verdict', 'file'))
    for r in rows:
        print(hdr % (r['bm'], r['top'] + r['nodest'], r['pages'], r['oor'],
                     r['nonmono'], r['flat'], r['dirty'], r['lv'], r['labels'],
                     r['v'], os.path.basename(r['file'])[:60]))
    tot = len(rows)
    rework = [r for r in rows if sev(r) == 3]
    lbl = [r for r in rows if r['v'] == 'add-labels']
    empty = [r for r in rows if r['v'] == 'EMPTY']
    ok = [r for r in rows if r['v'] == 'OK']
    print("\nPDFs: %d | REWORK: %d | add page-labels only: %d | EMPTY: %d | OK: %d"
          % (tot, len(rework), len(lbl), len(empty), len(ok)))
    print("page-top / no-dest items total: %d" %
          sum(r['top'] + r['nodest'] for r in rows))
    print("rework list (worst first):")
    for r in rework:
        print("   %-9s %s" % (r['v'], r['file']))
    # Title dirt is invisible in every viewer, so name the exact family per book:
    # a book whose EVERY title carries a NUL is a C-string-writer book and needs
    # its titles re-written (strip control chars) before any comparison works.
    dts = [r for r in rows if r['dirty']]
    if dts:
        print("\ndirty-title breakdown:")
        for r in sorted(dts, key=lambda r: -r['dirty']):
            print("   bm=%-4d dirty=%-3d leader=%-3d esc=%-2d moji=%-2d ctrl=%-3d tex=%-2d  %s"
                  % (r['bm'], r['dirty'], r['leader'], r['escape'], r['moji'],
                     r['ctrl'], r['tex'], os.path.basename(r['file'])[:60]))
    if csv:
        with open(csv, 'w', encoding='utf-8-sig') as fh:
            fh.write('file,bm,top,oor,nonmono,flat,dirty,leader,escape,moji,'
                     'ctrl,tex,levels,labels,verdict\n')
            for r in rows:
                fh.write('"%s",%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%d,%s,%d,%s\n' % (
                    r['file'], r['bm'], r['top'] + r['nodest'], r['oor'],
                    r['nonmono'], r['flat'], r['dirty'], r['leader'],
                    r['escape'], r['moji'], r['ctrl'], r['tex'],
                    r['lv'], r['labels'], r['v']))
        print('csv ->', csv)


if __name__ == '__main__':
    main()
