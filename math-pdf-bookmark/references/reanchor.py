# -*- coding: utf-8 -*-
"""reanchor.py -- ROUTE R: text-layer book whose existing bookmark LIST is
faithful to the printed Contents, but whose DESTS are page-top (y=0 / /Fit).

Instead of re-parsing the printed Contents (Phase 2) or OCR-ing the book
(Phase 5/6), keep the skeleton and re-locate every entry inside the text layer,
then rewrite the tree with real heading y.  Zero OCR, seconds per book.

    python reanchor.py <pdf>                dry run -> report only
    python reanchor.py <pdf> --write        back up + write (needs 0 MISS)
    python reanchor.py <pdf> --report f.txt

Matching is per-LINE (not per-word), scored so that a heading beats a body
sentence that happens to contain the same words:
  +4  probe is a prefix of the line / line equals probe   (else ratio>=0.75 -> +2r)
  -1.5 line is much longer than the probe (that is a sentence, not a heading)
  +1  line's font size >= the book's body size
  +1  page == the old page (window is +-WIN pages; chapters get +-WIN_CH)
accept at score >= 3.0.  A probe list is tried in order:
  full title -> title with the leading number stripped -> first N words.
"""
import fitz, os, re, sys, shutil, difflib, statistics, unicodedata

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

WIN = 2          # page window for sections
WIN_CH = 3       # window for level-1 items
ACCEPT = 3.0
BAKROOT = r"F:/大学/数字资源/数学/_bm_rerun_backup"
TMP = r"C:/Users/asus/_reanchor_tmp.pdf"

CTRL = re.compile(r'[\x00-\x08\x0b\x0c\x0e-\x1f\x7f\ufffd]')
# A leading number is only stripped when it is really a section number:
#  - arabic digits may run into the first word ('Chapter 16Harmonic', '9.1Classiﬁcation');
#  - roman numerals MUST be followed by a separator, otherwise 'Cover' loses its 'C'
#    and 'Index' loses its 'I' (both bit on Alpay / Ahlfors front matter).
LEADNUM = re.compile(r'^\s*(Chapter|CHAPTER|Ch\.|Part|VOL\.|Volume)?\s*'
                     r'([0-9]+([.．][0-9]+)*[.．、:：\) 　]{0,3}'
                     r'|[IVXLCDM]+[.．、:：\) 　]{1,3}'
                     r'|[一二三四五六七八九十]+[.．、]?)')
DOTLEAD = re.compile(r'[\s.\u2024\u2026\u00b7\u2219]{2,}\s*\d+\s*$')
NUMLEAD = re.compile(r'^\s*([0-9]+(?:[.．][0-9]+)*|[IVXLCDM]+)\b')
FRONT = {'cover', 'title', 'title page', 'halftitle', 'half title', 'copyright',
         'dedication', 'epigraph', 'series page', 'also by', 'note to the reader'}


def clean(t):
    t = CTRL.sub('', str(t))
    t = DOTLEAD.sub('', t)
    return re.sub(r'\s+', ' ', t).strip()


LIG = {'\ufb00': 'ff', '\ufb01': 'fi', '\ufb02': 'fl', '\ufb03': 'ffi', '\ufb04': 'ffl',
       '\u2019': "'", '\u2018': "'", '\u201c': '"', '\u201d': '"',
       '\u2013': '-', '\u2014': '-', '\u2212': '-', '\u00a0': ' ',
       # blackboard / script letters used in headings ('ℂ-differentiable') are
       # extracted as themselves by some producers and as plain latin by others
       '\u2102': 'c', '\u211d': 'r', '\u2124': 'z', '\u2115': 'n', '\u210d': 'h',
       '\u2119': 'p', '\u2113': 'l', '\u0127': 'h', '\u0111': 'd'}


def nz(s):
    """normalise for comparing: ligatures, quotes, accents, lowercase, one space.

    Three artefacts of real text layers make naive comparison fail, and all three
    bit in practice:  (a) the PDF stores 'fi' as U+FB01, so 'Classification' never
    equals 'Classiﬁcation';  (b) the section number is glued to the first word
    ('9.1Classiﬁcation'), so split it back off before comparing word by word;
    (c) accented letters arrive in decomposed form (base + combining mark).
    """
    s = clean(s).lower()
    for k, v in LIG.items():
        s = s.replace(k, v)
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(ch for ch in s if not unicodedata.combining(ch))
    s = re.sub(r'^(\d+(?:[.．]\d+)*)[.．]?\s*', r'\1 ', s)
    s = re.sub(r'\s+', ' ', s)
    return s.strip()



def wpref(a, b):
    """share of the SHORTER side's leading words that both agree on, in order.
    This is what lets a heading that wraps onto a second line still match."""
    wa, wb = a.split(), b.split()
    n = 0
    for x, y in zip(wa, wb):
        if x.strip('.,;::()（）') != y.strip('.,;::()（）'):
            break
        n += 1
    return n / float(max(1, min(len(wa), len(wb))))


def probes(t):
    t = clean(t)
    out = [t]
    core = LEADNUM.sub('', t).strip()
    if core and core != t:
        out.append(core)
    m = re.match(r'^(Chapter|Part|Appendix)\s+([0-9IVXLC]+)\s*(.*)$', t, re.I)
    if m and m.group(3):
        out.append(m.group(3).strip())
    w = (core or t).split(' ')
    if len(w) > 4:
        out.append(' '.join(w[:4]))
    seen, res = set(), []
    for p in out:
        if p and len(p) >= 3 and p.lower() not in seen:
            seen.add(p.lower())
            res.append(p)
    return res



def page_lines(page):
    ls = []
    for b in page.get_text("dict")["blocks"]:
        if b.get("type") != 0:
            continue
        for l in b.get("lines", []):
            sp = [s for s in l.get("spans", []) if s.get("text", '').strip()]
            if not sp:
                continue
            t = ''.join(s["text"] for s in sp)
            ls.append((min(s["bbox"][1] for s in sp),
                       min(s["bbox"][0] for s in sp),
                       max(s["size"] for s in sp),
                       any(s["flags"] & 16 for s in sp),
                       t))
    return ls


def body_size(doc):
    sz = []
    n = doc.page_count
    for q in range(9):
        p = min(n - 1, int(n * (q + 1) / 11))
        for (y, x, s, b, t) in page_lines(doc[p]):
            if len(t) > 40:
                sz.append(s)
    if not sz:
        for p in range(min(20, n)):
            for (y, x, s, b, t) in page_lines(doc[p]):
                sz.append(s)
    return statistics.median(sz) if sz else 10.0


def pfr(a, b):
    """fuzzy similarity of a LINE against the START of the title, in both
    directions of truncation: the line may carry the whole title (run-in heading)
    or only its first chunk (a heading that wrapped onto a second line)."""
    if not a or not b:
        return 0.0
    f1 = difflib.SequenceMatcher(None, a, b[:len(a) + 3]).ratio()
    f2 = difflib.SequenceMatcher(None, a[:len(b) + 4], b).ratio()
    return max(f1, f2)


def simw(x, y):
    return difflib.SequenceMatcher(None, x, y).ratio()


def split_num(s):
    m = NUMLEAD.match(s)
    if not m:
        return None, s
    return m.group(1).rstrip('.．'), s[m.end():].strip()


def wov(ra, rb):
    """share of the title's remaining words that the line's first words contain
    (unordered, fuzzy) -- used once both sides carry the same section number."""
    wa = [w for w in ra.split() if len(w) >= 2]
    wb = [w for w in rb.split()[:9]]
    if not wa or not wb:
        return 0.0
    hit = 0
    for x in wa:
        for y in wb:
            if x == y or simw(x, y) >= 0.85:
                hit += 1
                break
    return hit / float(len(wa))


def _score_named(a, b, is_head):
    """Same leading section number + the same leading words.
    Saves headings whose maths the text layer mangled: Ahlfors prints
    '3.2. The Functions t(z) and u(z).' for the Contents entry
    '3.2 The Functions zeta(2) and sigma(z)' -- zeta/sigma survive as junk, but
    the number, 'the functions' and 'and' do not."""
    na, ra = split_num(a)
    nb, rb = split_num(b)
    if not na or na != nb:
        return 0.0
    ov = wov(ra, rb)
    if ov < 0.5:
        return 0.0
    return 3.6 + 0.8 * ov + (0.5 if is_head else 0.0)


def _score_fuzzy(a, b, is_head):
    """Garble-tolerant prefix matching, plus the JAMMED text layer: some
    producers (Springer problem books) extract every line with the word spaces
    removed -- 'Cauchy-RiemannEquationsand' -- so no space-aware comparison can
    ever match; compare the space-stripped forms too."""
    if len(a) < 10 or len(b) < 8:
        return 0.0
    r = pfr(a, b)
    an, bn = a.replace(' ', ''), b.replace(' ', '')
    jam = (an != a or bn != b)
    if jam and len(bn) >= 8:
        r = max(r, pfr(an, bn))
    if r < 0.82:
        return 0.0
    if len(b) >= len(a) - 3:                  # the line carries the whole title
        if is_head:
            return 4.7
        if len(b) > len(a) + 40:              # a body sentence that starts with it
            return 3.4
        return 3.6
    cover = min(len(an), len(bn)) / float(max(1, len(an)))
    if is_head and cover >= 0.40 and len(bn) >= 12:
        return 3.0 + 1.6 * cover              # the line is the first line of a wrapped title
    return 0.0


def _score_raw(a, b, is_head, bs, ln, margin=40.0):
    if not a:
        return 0.0
    s = 0.0
    if b.startswith(a) and len(a.split()) >= 2:
        # Ahlfors prints its subsection headings RUN-IN: '1.2. Analytic
        # Functions. The class of ...' -- same size as the body, same left
        # margin, and the title is only the FIRST part of the line.  A length
        # penalty would throw those away, so recognise the sentence boundary.
        rest = b[len(a):].strip()
        if not rest:
            return 5.0 + (0.5 if is_head else 0.0)
        if rest[0] in '.:,' and ln[1] <= margin + 12:
            return 4.5
        return max(3.2, _score_fuzzy(a, b, is_head), _score_named(a, b, is_head))
    elif b == a:
        return 4.5 + (0.5 if is_head else 0.0)
    r = difflib.SequenceMatcher(None, a, b).ratio()
    if a in b:
        s = max(s, 2.0 + 2.0 * r)
    elif r >= 0.75:
        s = max(s, 2.0 * r)
    elif is_head and wpref(a, b) >= 0.7:
        s = max(s, 3.0 + wpref(a, b))          # wrapped heading
    if s:
        if len(b) > len(a) + 14:
            s -= 1.5
        if len(b) > len(a) + 40:
            s -= 2.0
        if not is_head:
            s -= 1.0
        elif bs and ln[2] > bs + 0.5:
            s += 0.5
    return max(s, _score_fuzzy(a, b, is_head), _score_named(a, b, is_head))


def score(pr, ln, bs, margin=40.0):
    """pr = probe string; ln = (y0, x0, size, bold, text) from page_lines().

    A visible section number that DISAGREES with the entry's own number is
    decisive counter-evidence: on Ahlfors p58 the fuzzy rules happily read
    '3.1 The Exponential' as the chapter opener '3. THE EXPONENTIAL AND
    TRIGONOMETRIC FUNCTIONS' four lines above the real heading, so veto it.
    """
    a, b = nz(pr), nz(ln[4])
    s = _score_raw(a, b, bool(ln[3]) or (bs and ln[2] >= bs + 0.5), bs, ln, margin)
    if s > 0:
        na, nb = split_num(a)[0], split_num(b)[0]
        if na and nb and na != nb:
            s -= 3.0
    return s




CHAPWORD = re.compile(r'^(chapter|part|book|volume|appendix|section|appendice|prologue|epilogue)')


def snap_head_block(lines, y):
    """A heading can wrap ('... Contour Integral' / 'Techniques'), and a chapter
    opener prints 'Chapter 16' above the title.  Walk up over heading-sized
    lines so the jump lands on the TOP of the block: a normal wrapped line sits
    within one line-gap (22 pt), a display chapter/part line is allowed a real
    gap because it is set 40-50 pt above the title it belongs to."""
    ls = sorted(lines)
    idx = min(range(len(ls)), key=lambda i: abs(ls[i][0] - y))
    top = ls[idx][0]
    for i in range(idx - 1, -1, -1):
        y0, x0, sz, bold, t = ls[i]
        if y0 < 30 or sz < 11.0 or not bold:
            break
        jam = re.sub(r'\s+', '', nz(t))
        lim = 90.0 if CHAPWORD.match(jam) else 22.0
        if top - y0 > lim:                     # a real gap, not a wrapped line
            break
        top = y0
    return top


def locate_front(doc, bs, p):
    """Front matter ('Cover', 'Title', 'Copyright') prints no heading at all, so
    the honest anchor is the top of that page's content: the highest large line,
    or the first line of anything."""
    lines = [ln for ln in page_lines(doc[p - 1]) if len(clean(ln[4])) >= 2]
    if not lines:
        return None
    big = [ln for ln in lines if ln[2] >= max(2 * (bs or 10), 14)]
    ln = min(big or lines, key=lambda l: l[0])
    return ACCEPT + 0.5, p, ln[0], ln[4]



def locate(doc, bs, margin, title, oldp, win):
    best = None
    ps = sorted(range(max(1, oldp - win), min(doc.page_count, oldp + win) + 1),
                key=lambda p: abs(p - oldp))
    for p in ps:
        lines = page_lines(doc[p - 1])
        for ln in lines:
            # Do NOT filter by y alone: a chapter opener can sit at y=8 (Ahlfors).
            # Running heads are caught by being SMALLER than the body text.
            if ln[0] < 50 and bs and ln[2] < bs - 0.5:
                continue
            for k, pr in enumerate(probes(title)):
                s = score(pr, ln, bs, margin)
                if s <= 0:
                    continue
                s -= 0.5 * k
                if p == oldp:
                    s += 1.0
                s -= 0.3 * abs(p - oldp)
                cand = (s, p, ln[0], ln[4])
                if best is None or cand[0] > best[0]:
                    best = cand
        if best and best[0] >= ACCEPT + 1.5 and p == oldp:
            break                               # confident on the expected page
    if best and best[0] >= ACCEPT:
        y = snap_head_block(page_lines(doc[best[1] - 1]), best[2])
        return best[0], best[1], y, best[3]
    return None


def left_margin(doc):
    xs = []
    n = doc.page_count
    for q in range(9):
        p = min(n - 1, int(n * (q + 1) / 11))
        for (y, x, s, b, t) in page_lines(doc[p]):
            if len(t) > 60:
                xs.append(x)
    return statistics.median(xs) if xs else 40.0



def next_bak(path):
    rel = os.path.relpath(path, r"F:/大学/数字资源/数学")
    d = os.path.join(BAKROOT, os.path.dirname(rel))
    os.makedirs(d, exist_ok=True)
    stem = os.path.splitext(os.path.basename(rel))[0]
    k = 1
    while os.path.exists(os.path.join(d, "%s_pre%d.pdf" % (stem, k))):
        k += 1
    return os.path.join(d, "%s_pre%d.pdf" % (stem, k))


def main():
    args = [a for a in sys.argv[1:] if not a.startswith('--')]
    src = args[0]
    write = '--write' in sys.argv
    rep = r"C:/Users/asus/_reanchor_%s.txt" % re.sub(r'\W+', '', os.path.basename(src))[:24]
    if '--report' in sys.argv:
        rep = sys.argv[sys.argv.index('--report') + 1]
    doc = fitz.open(src)
    toc = doc.get_toc(simple=False)
    bs = body_size(doc)
    margin = left_margin(doc)
    out = ["file   : %s" % os.path.basename(src),
           "pages  : %d   bookmarks: %d   body size: %.2f pt" % (doc.page_count, len(toc), bs)]
    fixed, miss = [], []
    for e in toc:
        lvl, title, p = e[0], str(e[1]), e[2]
        oldy = e[3].get('to').y if isinstance(e[3], dict) else (e[3] or 0)
        win = WIN_CH if lvl == 1 else WIN
        hit = locate(doc, bs, margin, title, p, win)
        if hit is None and nz(title) in FRONT:
            hit = locate_front(doc, bs, p)
            if hit:
                out.append("FRONT L%d p%-4d %r -> top of page content" % (lvl, p, clean(title)[:40]))
        if hit is None:
            miss.append((lvl, title, p, oldy))
            out.append("MISS L%d p%-4d y=%-6.1f %r" % (lvl, p, oldy, clean(title)[:70]))
            continue
        s, np_, y, txt = hit
        t = clean(title)
        fixed.append([lvl, t, np_, round(y, 1)])
        out.append("  OK L%d p%-4d y=%-6.1f (%+.1f) %r  <=  %r"
                   % (lvl, np_, y, s, t[:44], txt[:44]))
    mono = all(fixed[i][2] > fixed[i - 1][2] or
               (fixed[i][2] == fixed[i - 1][2] and fixed[i][3] >= fixed[i - 1][3])
               for i in range(1, len(fixed)))
    out.append("located=%d MISS=%d page-monotone=%s" % (len(fixed), len(miss), mono))
    with open(rep, 'w', encoding='utf-8') as fh:
        fh.write("\n".join(out) + "\n")
    print("report ->", rep, "| located=%d MISS=%d" % (len(fixed), len(miss)))
    if miss:
        print("refusing to write while %d entries are unlocated" % len(miss))
        doc.close()
        return 1
    if not write:
        print("dry run only (pass --write)")
        doc.close()
        return 0
    bak = next_bak(src)
    shutil.copy2(src, bak)
    shutil.copy2(src, TMP)
    d = fitz.open(TMP)
    d.set_toc(fixed)
    d.saveIncr()
    d.close()
    shutil.move(TMP, src)
    v = fitz.open(src)
    t2 = v.get_toc(simple=False)
    tops = sum(1 for x in t2 if x[3].get('to').y <= 0.5)
    print("wrote %d bookmarks (backup %s); re-open pages=%d bm=%d page-top=%d"
          % (len(t2), os.path.basename(bak), v.page_count, len(t2), tops))
    v.close()
    doc.close()
    return 0


if __name__ == '__main__':
    sys.exit(main())
