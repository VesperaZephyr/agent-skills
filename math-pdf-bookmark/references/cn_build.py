# -*- coding: utf-8 -*-
"""Rebuild precise bookmarks for 王晓光《101复变函数》 (pure scan, 405 pp).

Entries  : skeleton = the book's existing bookmark list (249 items, titles already
           faithful to the printed Contents), with printed section numbers re-attached.
Locator  : OCR dump (200 dpi, WinRT) + this book's heading signatures
             chapter  -> line whose text is 第X章 (Arabic/Chinese numeral verified),
                         y in the opener band 90..210
             section  -> line with h>=8, x0<=128, leading token = "N.M"/"NLM"/"N·M"
                         (L is this OCR's mis-read of "1."), plus title similarity
             front/back -> biggest glyph line in the upper half of the known page
K        : physical(1-based) = printed + 16   (proved by the folio audit below)

Usage:  python _w101_bm.py            -> dry run, report only
        python _w101_bm.py --write     -> write bookmarks + page labels (needs 0 MISS)

TEMPLATE (Phase 6, 中文教科书扫描本).  Re-point for every new book before running:
  DPI / SC      -- only set SC = 72/DPI; verify page.rect != native pixels first
  SRC / TMP / BAK-- the PDF, an ASCII temp path, and the _pre1 backup (make the backup!)
  OLD           -- dump of the book's EXISTING bookmarks (the skeleton);
                   get it with:  get_toc(simple=False) written as "lvl\\t page\\t y\\t title"
  K             -- physical(1-based) = printed + K; prove it twice (folio audit + one
                   Contents row), never guess
  OCR dump paths in load()  -- the winocr.ps1 output files
  FIXT / DROP / PAREN       -- book-specific: LaTeX-in-title rewrites, publisher junk
                   items to drop, half/full-width paren fixes
Then check the heading signatures (find_section's h/x0/y gates, find_chapter's band)
against THIS book's probe dump before trusting a single MISS=0.
"""
import re, sys, os, shutil, difflib
import fitz

sys.stdout.reconfigure(encoding='utf-8', errors='replace')

DPI = 200
SC = 72.0 / DPI
SRC = (r"F:/大学/数字资源/数学/分析学/复分析/"
       r"101复变函数 (王晓光).pdf")
OLD = r"C:/Users/asus/_w101_oldtoc.txt"
REPORT = r"C:/Users/asus/_w101_locate.txt"
TMP = r"C:/Users/asus/_w101_tmp.pdf"
BAK = (r"F:/大学/数字资源/数学/_bm_rerun_backup/复分析/"
       r"101复变函数 (王晓光)_pre1.pdf")
K = 16

# ----------------------------------------------------------------- OCR dump
def load():
    pages, cur = {}, None
    for fn in (r"C:/Users/asus/_w101_ocr_a.txt", r"C:/Users/asus/_w101_ocr_b.txt"):
        for raw in open(fn, encoding='utf-8-sig', errors='ignore'):
            l = raw.rstrip("\n")
            if l.startswith('#####'):
                m = re.search(r'page_(\d+)', l)
                cur = int(m.group(1)) if m else None
                if cur:
                    pages.setdefault(cur, [])
                continue
            if cur is None:
                continue
            p = l.split('\t')
            if len(p) < 5:
                continue
            try:
                y, x0, x1, h = (int(p[0]) * SC, int(p[1]) * SC,
                                int(p[2]) * SC, int(p[3]) * SC)
            except ValueError:
                continue
            t = p[4].strip()
            if t:
                pages[cur].append((y, x0, x1, h, t))
    for v in pages.values():
        v.sort()
    return pages


PAGES = load()


def sq(s):
    s = re.sub(r'\s+', '', s)
    for c in '，．、·•‧⋅・':
        s = s.replace(c, '.')
    return s


def sim(a, b):
    if not a or not b:
        return 0.0
    r = difflib.SequenceMatcher(None, a, b).ratio()
    if min(len(a), len(b)) >= 10:
        n = 0
        for x, y in zip(a, b):
            if x != y:
                break
            n += 1
        r = min(1.0, r + 0.04 * n / min(len(a), len(b)))
    return r


# ------------------------------------------------- numerals
CN = '零一二三四五六七八九'
DIG = {c: i for i, c in enumerate(CN)}
DIG['〇'] = 0


def cn2int(s):
    s = s.strip()
    if not s:
        return None
    if s.isdigit():
        return int(s)
    # pure chinese numeral, up to 99
    total, cur = 0, 0
    if '十' in s:
        a, _, b = s.partition('十')
        tens = 1 if a == '' else DIG.get(a, None)
        if tens is None:
            return None
        ones = 0 if b == '' else DIG.get(b, None)
        if ones is None:
            return None
        return tens * 10 + ones
    for ch in s:
        if ch not in DIG:
            return None
        cur = cur * 10 + DIG[ch]
    return cur


def int2cn(n):
    if n <= 10:
        return ('十' if n == 10 else CN[n])
    if n < 20:
        return '十' + CN[n % 10]
    return CN[n // 10] + '十' + (CN[n % 10] if n % 10 else '')


CHAP_HEAD = re.compile(r'^[\*＊]?第([' + CN + '十〇' + r'\d]{1,6})章')

# ------------------------------------------------- entry list
DROP = {'封面', '声明', '版权', '101计划信息', '郑重声明'}
FIXPAGE = {'第二十三章': 241}

# titles as the printed book sets them (LaTeX in the old list -> readable math)
FIXT = {
    '22.1': '∞ 作为孤立奇点',
    '23.2': '∫_0^{2π} Q(sin θ, cos θ) dθ 型积分',
    '23.3': '∫_{-∞}^{+∞} f(x) dx 型积分',
    '23.4': '∫_{-∞}^{+∞} e^{iαx} f(x) dx 型积分',
    '24.1': '∫_0^{+∞} f(x) dx 型积分',
    '24.2': '∫_a^b (x-a)^r (b-x)^s f(x) dx 型积分',
    '29.1': 'Arzelà-Ascoli 定理',
    '31.3': '单连通域的双曲度量',   # old list said 非连通域 -- print says 单
}
PAREN = {' (续)': '（续）', ' (一)': '（一）', ' (二)': '（二）', ' (三)': '（三）'}


def norm_punct(t):
    for a, b in PAREN.items():
        t = t.replace(a, b)
    t = re.sub(r'[:：][ ]*(?=[一-鿿])', '：', t)
    return t


def bare(num, t):
    """title text (no number) with the printed book's spelling"""
    if num in FIXT:
        return FIXT[num]
    return norm_punct(re.sub(r'^\d+(\.\d+)*\s*', '', t))


def build_entries():
    raw = []
    for l in open(OLD, encoding='utf-8'):
        m = re.match(r'\s*\d+\s+lv(\d)\s+p(\d+)\s+y=\S+\s+kind=\d\s+(.*?)\s*$', l)
        if m:
            raw.append((int(m.group(1)), int(m.group(2)), m.group(3)))
    ents, ch, sec, sub = [], 0, 0, 0
    for lv, p, title in raw:
        # the old bookmark titles all end with a literal NUL -- strip control junk
        t = re.sub(r'[\x00-\x08\x0b\x0c\x0e-\x1f\ufffd]', '', title).strip()
        t = t.replace('重道复偏导数', '重温复偏导数')
        key = re.sub(r'\s+', '', t)
        if key in DROP:
            continue
        if key.startswith('第二十三章') and p == 41:
            p = 241
        if lv == 1:
            t = norm_punct(t)
            m = CHAP_HEAD.match(key)
            if m:
                ch = cn2int(m.group(1)) or 0
                sec, sub = 0, 0
                ents.append([1, t, p, ch, None])
            else:
                ch, sec, sub = 0, 0, 0
                ents.append([1, t, p, 0, None])
        elif lv == 2:
            if ch:
                sec += 1
                sub = 0
                num = '%d.%d' % (ch, sec)
                ents.append([2, '%s %s' % (num, bare(num, t)), p, ch, num])
            else:
                ents.append([2, t, p, 0, None])
        else:
            if ch:
                sub += 1
                num = '%d.%d.%d' % (ch, sec, sub)
                ents.append([3, '%s %s' % (num, bare(num, t)), p, ch, num])
            else:
                ents.append([3, t, p, 0, None])
    return ents


# ------------------------------------------------- locators
def lines(p):
    return PAGES.get(p, [])


def find_chapter(title, page):
    key = sq(title)
    m = CHAP_HEAD.match(key)
    want = cn2int(m.group(1)) if m else None
    best = None
    for p in range(page - 1, page + 2):
        if p < 1 or p > 405:
            continue
        for (y, x0, x1, h, t) in lines(p):
            s = sq(t)
            mm = CHAP_HEAD.match(s)
            if not mm:
                continue
            if want is not None and cn2int(mm.group(1)) != want:
                continue
            if not (85 <= y <= 215):
                continue
            score = h + (30 if p == page else 0)
            if best is None or score > best[0]:
                best = (score, p, y, s)
    return best


LEAD = re.compile(r'^([0-9lL.]{2,9})(?![0-9lL])')


def lead_digits(lead):
    """all readings of a mis-scanned number token, digits only"""
    outs = ['']
    for ch in lead:
        nxt = []
        for base in outs:
            if ch in '.':
                nxt.append(base)
            elif ch.isdigit():
                nxt.append(base + ch)
            else:                       # l / L  ==  '1' or a lost '1.'
                nxt.append(base + '1')
                nxt.append(base)
        outs = nxt
    return set(outs)


def find_section(num, title, page):
    want = num.replace('.', '')
    tkey = sq(re.sub(r'^[\d.]+\s*', '', title))
    best = None
    for p in range(page - 2, page + 3):
        if p < 1 or p > 405:
            continue
        for (y, x0, x1, h, t) in lines(p):
            if h < 8.0 or x0 > 128.0 or y < 58.0:
                continue
            s = sq(t)
            m = LEAD.match(s)
            if not m:
                continue
            lead, rest = m.group(1), s[m.end():]
            nok = want in lead_digits(lead)
            r = sim(tkey, rest)
            if not nok and r < 0.72:
                continue
            sc = (6.0 if nok else 0.0) + 4.0 * r + (1.0 if p == page else 0.0) \
                 - 0.4 * abs(p - page)
            if best is None or sc > best[0]:
                best = (sc, p, y, s, nok, round(r, 2))
    return best


def find_front(title, page):
    key = sq(title)
    cands = [c for c in lines(page) if c[1] < 500 and c[0] < 320]
    if not cands:
        cands = list(lines(page))
    if not cands:
        return None
    big = max(cands, key=lambda c: c[3])
    r = sim(key, sq(big[4]))
    if big[3] >= 11 or r >= 0.5:
        return (big[3] + 10 * r, page, big[0], sq(big[4]), r)
    first = min(cands, key=lambda c: c[0])
    return (0.5, page, first[0], '<first line> ' + sq(first[4]), 0.0)


# ------------------------------------------------- folio audit
def audit_folios(fh):
    ok = miss = bad = 0
    for p in range(17, 402):
        f = None
        for (y, x0, x1, h, t) in lines(p):
            if y < 60 and h <= 7.6:
                s = sq(t)
                if re.fullmatch(r'\d{1,3}', s):
                    f = int(s)
                    break
        if f is None:
            miss += 1
        elif f == p - K:
            ok += 1
        else:
            bad += 1
            fh.write("  folio mismatch p%d shows %d expect %d\n" % (p, f, p - K))
    fh.write("folio audit pages 17..401: match=%d no-folio=%d (chapter openers) mismatch=%d\n"
             % (ok, miss, bad))
    return bad


# ------------------------------------------------- main
def main():
    write = '--write' in sys.argv
    ents = build_entries()
    fh = open(REPORT, 'w', encoding='utf-8')
    fh.write("entries: %d\n" % len(ents))
    audit_folios(fh)

    out, misses = [], []
    for lv, title, page, ch, num in ents:
        if lv == 1 and ch:
            hit = find_chapter(title, page)
            how = 'chapter'
        elif num:
            hit = find_section(num, title, page)
            how = 'section'
        else:
            hit = find_front(title, page)
            how = 'front'
        if hit is None:
            misses.append((lv, title, page, how))
            fh.write("MISS  %-40s p%-4d (%s)\n" % (title, page, how))
            continue
        p = hit[1]
        y = max(1.0, round(hit[2], 2))
        if p < 1:
            p = 1
        out.append((lv, title, p, y, how, hit))
        fh.write("%-8s %-40s -> p%-4d y=%6.1f  [%s] %s\n" % (
            how, title, p, y,
            'num' if (how == 'section' and hit[4]) else how,
            str(hit[3])[:38]))

    # sanity: page monotone, level sane
    drops = []
    cur = 1
    fixed = []
    for e in out:
        p = max(cur, e[2])
        if p != e[2]:
            drops.append(e[1])
        fixed.append((e[0], e[1], p, e[3]))
        cur = p
    fh.write("\nlocated=%d MISS=%d  page-clamped=%d %s\n" % (
        len(out), len(misses), len(drops), drops[:12]))
    fh.write("levels: %s\n" % sorted(set(x[0] for x in fixed)))

    if misses:
        fh.write("\nREFUSING TO WRITE: %d entries unlocated\n" % len(misses))
        fh.close()
        print("MISS %d -> %s" % (len(misses), REPORT))
        return
    if not write:
        fh.write("\ndry run (pass --write to apply)\n")
        fh.close()
        print("located all %d entries -> %s" % (len(fixed), REPORT))
        return

    if not os.path.exists(BAK):
        os.makedirs(os.path.dirname(BAK), exist_ok=True)
        shutil.copy2(SRC, BAK)
    shutil.copy2(SRC, TMP)
    d = fitz.open(TMP)
    n0 = d.page_count
    d.set_toc([[l, t, p, y] for (l, t, p, y) in fixed])
    d.set_page_labels([
        {'startpage': 1, 'prefix': '', 'style': 'a', 'firstpagenum': 1},
        {'startpage': 9, 'prefix': '', 'style': 'r', 'firstpagenum': 1},
        {'startpage': 17, 'prefix': '', 'style': 'D', 'firstpagenum': 1},
        {'startpage': 402, 'prefix': '', 'style': 'a', 'firstpagenum': 1},
    ])
    d.saveIncr()
    d.close()
    assert fitz.open(TMP).page_count == n0
    shutil.move(TMP, SRC)
    fh.write("\nWROTE %d bookmarks + 4 label ranges\n" % len(fixed))
    fh.close()
    print("wrote", len(fixed), "bookmarks")


if __name__ == '__main__':
    main()
