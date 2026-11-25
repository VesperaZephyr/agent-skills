# -*- coding: utf-8 -*-
"""纯扫描件交叉引用：用 OCR 行缓存直接建 /Link，不写文本层。

原理
----
链接 (/Link) 是独立注解对象，不依赖 PDF 文字层。因此零文字层扫描件也能做
交叉引用，只要 OCR 给出「引用文字」与「目标定义点」的页面坐标。

坐标口径
--------
ocr.pkl 存的是 pt 坐标 (x0,y0,x1,y1,text)，由 300dpi 渲染像素换算而来，
等于页面坐标系（左上原点、y 向下），可直接作为 insert_link 的 rect，
以及 to=Point(x,y) 的落点。

行内 x 定位
-----------
OCR 只给行框 + 整行文本。行内某段文字 [a,b) 的 x 用「字符宽度权重」
（全角 1.0 / ASCII 0.55）在行框内线性插值；中文数学书以等宽全角为主，
误差 < 1 字，足以覆盖编号。

子命令
------
  scan   : 输出目标索引 index.json 与引用清单 report.json（不写 PDF）
  build  : 按 report 写链接副本
  audit  : 校验副本中每条链接的 rect 是否压在对应编号上、目标是否一致
"""
import argparse
import collections
import json
import os
import pickle
import re
import sys

import pymupdf as fitz

KINDS = ('例题', '定理', '定义', '引理', '命题', '推论', '例', '习题', '注')
KIND_RE = '|'.join(sorted(KINDS, key=len, reverse=True))
# 本书定义点写作「例题 N.M」，正文引用写作「例 N.M」：统一键为「例」
KIND_NORM = {'例题': '例'}


def knorm(k):
    return KIND_NORM.get(k, k)
# 编号：章.序号（两段），允许 OCR 的点号变体
NUM = r'\d{1,3}\s*[.．∙，,、]\s*\d{1,3}'
NUM_RE = re.compile(NUM)
HEAD_RE = re.compile(r'^(' + KIND_RE + r')\s*(' + NUM + r')')
MENTION_RE = re.compile(r'(' + KIND_RE + r')\s*(' + NUM + r')(?![\d.．∙])')
EQ_TAIL_RE = re.compile(r'[（(](\d{1,3})\s*[.．∙]\s*(\d{1,3})[)）]\s*$')
SEC_RE = re.compile(r'^(\d{1,3})\s*[.．∙]\s*(\d{1,3})\s+(?=[\u4e00-\u9fff])')

CUE = ('参见', '根据', '参考', '利用', '应用', '结合', '回顾', '引进', '注意',
       '如同', '由', '见', '证明', '即', '如', '与', '和', '及', '按')


def norm_num(s):
    m = re.match(r'\s*(\d{1,3})\s*[.．∙，,、]\s*(\d{1,3})', s)
    return '%s.%s' % m.groups() if m else None


def cw(ch):
    """字符宽度权重（全角 1.0 / ASCII 0.55）。"""
    return 1.0 if ord(ch) > 0x2E80 else 0.55


def xspan(text, a, b, x0, x1):
    """行内 [a,b) 字符区间 -> (xa, xb)。"""
    total = sum(cw(c) for c in text) or 1.0
    pre = sum(cw(c) for c in text[:a])
    seg = sum(cw(c) for c in text[a:b])
    W = x1 - x0
    return x0 + W * pre / total, x0 + W * (pre + seg) / total


def load_lines(cache_path):
    with open(cache_path, 'rb') as f:
        cache = pickle.load(f)
    pages = {}
    for pno, items in cache.items():
        rows = []
        for (x0, y0, x1, y1, text) in items:
            t = (text or '').strip()
            if not t or t.startswith('__OCR_ERROR__'):
                continue
            if x1 <= x0 or y1 <= y0:
                continue
            rows.append({'x0': x0, 'y0': y0, 'x1': x1, 'y1': y1, 'text': t})
        rows.sort(key=lambda r: (round(r['y0'], 1), r['x0']))
        pages[pno] = rows
    return pages


def scan_targets(pages, skip, ymin, x0_min, x0_max, eq_xmin):
    results, sections, equations, exercises = [], [], [], []
    for pno in sorted(pages):
        if pno in skip:
            continue
        for r in pages[pno]:
            if r['y0'] < ymin:
                continue
            t = r['text']
            m = HEAD_RE.match(t)
            if m:
                num = norm_num(m.group(2))
                if num and x0_min <= r['x0'] <= x0_max:
                    results.append({'page': pno + 1, 'y': round(r['y0'], 2),
                                    'x0': round(r['x0'], 2), 'kind': knorm(m.group(1)),
                                    'num': num, 'text': t[:70]})
                    continue
            ms = SEC_RE.match(t)
            if ms and r['x0'] <= x0_max:
                sections.append({'page': pno + 1, 'y': round(r['y0'], 2),
                                 'num': '%s.%s' % (ms.group(1), ms.group(2)),
                                 'text': t[:60]})
                continue
            if t.startswith('习题') and r['x0'] <= x0_max:
                exercises.append({'page': pno + 1, 'y': round(r['y0'], 2),
                                  'num': None, 'text': t[:60]})
            if r['x0'] >= eq_xmin:
                me = EQ_TAIL_RE.search(t)
                if me:
                    equations.append({'page': pno + 1, 'y': round(r['y0'], 2),
                                      'num': '%s.%s' % me.groups(),
                                      'text': t[-30:]})
    return {'results': results, 'sections': sections,
            'equations': equations, 'exercises': exercises}


def build_index(tg):
    idx = collections.defaultdict(list)
    for r in tg['results']:
        idx[('result', r['kind'], r['num'])].append(r)
    for s in tg['sections']:
        idx[('section', '', s['num'])].append(s)
    for q in tg['equations']:
        idx[('equation', '', q['num'])].append(q)
    return idx


def head_score(r):
    """同号多候选时给真标题加分、给正文提及句减分。"""
    t = r['text']
    m = HEAD_RE.match(t)
    if not m:
        return -5
    after = t[m.end():].lstrip()
    s = 0
    if after.startswith(('（', '(', '[')):
        s += 3
    if re.match(r'^(说明|表明|可见|中|的证明|推出|给出|是|有|设|告诉|成立)', after):
        s -= 4
    if len(after) <= 3:
        s += 2
    if 80 <= r.get('x0', 999) <= 112:
        s += 1
    return s


def match_charline(cpage, r):
    """把 xref 的行（ocr.pkl）对应到字符级行（char.pkl）。

    两次 OCR 是独立进程，det 行框应当一致；按 y 最近 + x 次之匹配，
    距离过大视为不匹配（回退到宽度插值）。
    """
    if not cpage:
        return None
    best, bd = None, 1e9
    for cl in cpage:
        bx0, by0, bx1, by1 = cl['box']
        d = abs(by0 - r['y0']) + 0.15 * abs(bx0 - r['x0'])
        if d < bd:
            bd, best = d, cl
    return best if bd < 6.0 else None


def char_rect(cl, a, b):
    """字符区间 [a,b) -> (x0,y0,x1,y1)；越界返回 None。"""
    ch = cl['chars']
    if not ch or b > len(ch) or a >= b:
        return None
    seg = ch[a:b]
    return (min(c[1] for c in seg), min(c[2] for c in seg),
            max(c[3] for c in seg), max(c[4] for c in seg))


def find_mentions(pages, tg, skip, ymin, char_pages=None):
    idx = build_index(tg)
    char_pages = char_pages or {}
    head_rows = collections.defaultdict(set)
    for k in ('results', 'sections', 'equations'):
        for r in tg[k]:
            head_rows[r['page']].add(r['y'])
    links, skipped = [], []
    nchar = 0

    for pno in sorted(pages):
        if pno in skip:
            continue
        cpage = char_pages.get(pno)
        for r in pages[pno]:
            t = r['text']
            if r['y0'] < ymin:
                continue
            is_head = any(abs(r['y0'] - hy) < 3.0
                          for hy in head_rows.get(pno + 1, ()))
            # 对准字符级行：检索在「去空白文本」上做，索引即 chars 索引
            cl = match_charline(cpage, r) if cpage else None
            compact = re.sub(r'\s+', '', t)
            use_chars = cl is not None and ''.join(
                c[0] for c in cl['chars']) == compact
            scan_text = compact if use_chars else t

            def rect_of(a, b):
                nonlocal nchar
                if use_chars:
                    rr = char_rect(cl, a, b)
                    if rr:
                        nchar += 1
                        return fitz.Rect(rr[0] - 0.6, rr[1] - 0.6,
                                         rr[2] + 0.6, rr[3] + 0.6)
                xa, xb = xspan(scan_text, a, b, r['x0'], r['x1'])
                return fitz.Rect(xa, r['y0'], xb, r['y1'])

            for m in MENTION_RE.finditer(scan_text):
                kind, numraw = knorm(m.group(1)), m.group(2)
                num = norm_num(numraw)
                if not num:
                    continue
                # 定义点自身不建链接
                if is_head and m.start() <= 2:
                    continue
                key = ('result', kind, num)
                cand = idx.get(key) or []
                if not cand:
                    skipped.append({'page': pno + 1, 'kind': kind, 'num': num,
                                    'why': 'no-target', 'text': t[:70]})
                    continue
                # 定义点 = 该编号最早出现的行；页内提及句（"定理 8.3的一个推论"）
                # 页码/ y 都更靠后，自然被排除。跨章前向引用不受影响。
                tgt = min(cand, key=lambda c: (c['page'], c['y']))
                rect = rect_of(m.start(), m.end())
                links.append({'page': pno + 1, 'page0': pno,
                              'rect': [round(rect.x0, 2), round(rect.y0, 2),
                                       round(rect.x1, 2), round(rect.y1, 2)],
                              'text': m.group(0), 'kind': kind, 'num': num,
                              'line': t[:80],
                              'target_page': tgt['page'],
                              'target_y': tgt['y'],
                              'target_text': tgt.get('text', '')[:60],
                              'exact': bool(use_chars),
                              'how': 'unique' if len(cand) == 1 else 'scored'})
            # 公式号引用：(N.M) 位于行内
            if not is_head:
                for m in re.finditer(r'[（(](\d{1,3})\s*[.．∙]\s*(\d{1,3})[)）]',
                                     scan_text):
                    num = '%s.%s' % m.groups()
                    cand = idx.get(('equation', '', num)) or []
                    if not cand:
                        continue
                    rect = rect_of(m.start(), m.end())
                    links.append({'page': pno + 1, 'page0': pno,
                                  'rect': [round(rect.x0, 2), round(rect.y0, 2),
                                           round(rect.x1, 2), round(rect.y1, 2)],
                                  'text': m.group(0), 'kind': 'Equation',
                                  'num': num, 'line': t[:80],
                                  'target_page': cand[0]['page'],
                                  'target_y': cand[0]['y'],
                                  'target_text': '',
                                  'exact': bool(use_chars),
                                  'how': 'eq-def'})
            # N.N 节引用
            if not is_head:
                for m in re.finditer(r'(\d{1,3})\s*[.．∙]\s*(\d{1,3})\s*节',
                                     scan_text):
                    num = '%s.%s' % m.groups()
                    cand = idx.get(('section', '', num)) or []
                    if not cand:
                        continue
                    rect = rect_of(m.start(), m.end())
                    links.append({'page': pno + 1, 'page0': pno,
                                  'rect': [round(rect.x0, 2), round(rect.y0, 2),
                                           round(rect.x1, 2), round(rect.y1, 2)],
                                  'text': m.group(0), 'kind': 'Section',
                                  'num': num, 'line': t[:80],
                                  'target_page': cand[0]['page'],
                                  'target_y': cand[0]['y'],
                                  'target_text': cand[0].get('text', '')[:60],
                                  'exact': bool(use_chars),
                                  'how': 'sec'})
    print('char-exact rects: %d' % nchar)
    return links, skipped


def dedup(links):
    seen = set()
    out = []
    for L in links:
        k = (L['page'], tuple(L['rect']), L['kind'], L['num'])
        if k in seen:
            continue
        seen.add(k)
        out.append(L)
    return out


def cmd_scan(a):
    pages = load_lines(a.cache)
    skip = set()
    if a.skip_pages:
        for part in a.skip_pages.split(','):
            if '-' in part:
                s, e = part.split('-')
                skip.update(range(int(s), int(e) + 1))
            else:
                skip.add(int(part))
    tg = scan_targets(pages, skip, a.ymin, a.x0_min, a.x0_max, a.eq_xmin)
    char_pages = {}
    if a.chars and os.path.exists(a.chars):
        with open(a.chars, 'rb') as f:
            char_pages = pickle.load(f)
        print('char-level pages loaded: %d' % len(char_pages))
    links, skipped = find_mentions(pages, tg, skip, a.ymin, char_pages)
    links = dedup(links)
    print('targets: results %d, sections %d, equations %d' %
          (len(tg['results']), len(tg['sections']), len(tg['equations'])))
    print('links %d, skipped %d' % (len(links), len(skipped)))
    print('by kind', collections.Counter(L['kind'] for L in links).most_common())
    print('by target', collections.Counter(L['target_page'] for L in links).most_common(5))
    json.dump(tg, open(a.index, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    json.dump(links, open(a.report, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    json.dump(skipped, open(a.skipped, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
    print('-> %s %s %s' % (a.index, a.report, a.skipped))


def cmd_build(a):
    links = json.load(open(a.report, encoding='utf-8'))
    doc = fitz.open(a.pdf)
    n = 0
    for L in links:
        pg = doc[L['page0']]
        r = fitz.Rect(*L['rect'])
        if r.is_empty or r.width <= 0:
            continue
        dest = fitz.Point(0, max(L['target_y'] - a.dy, 0))
        pg.insert_link({'kind': fitz.LINK_GOTO, 'from': r,
                        'page': L['target_page'] - 1, 'to': dest,
                        'zoom': 0})
        n += 1
    doc.save(a.out, garbage=0, deflate=True, incremental=False)
    print('inserted %d links -> %s' % (n, a.out))


def cmd_audit(a):
    links = json.load(open(a.report, encoding='utf-8'))
    pages = load_lines(a.cache)
    bad_rect, bad_tgt, ok = [], [], 0
    for L in links:
        r = fitz.Rect(*L['rect'])
        # 1) rect 压住的行文本是否含该引用。同一 y 常有多个 OCR 行
        #    （公式行与正文行 y 仅差 1~2pt），必须在该 y 的全部候选中找，
        #    不能只看第一条。
        rows = pages.get(L['page0'], [])
        cands = [row for row in rows
                 if row['y0'] - 2 <= r.y0 <= row['y1']
                 and row['x0'] - 40 <= r.x0 <= row['x1'] + 10]
        raw = L['num']
        hit = None
        for row in cands:
            tt = (row['text'].replace('．', '.').replace('∙', '.')
                  .replace('，', '.').replace(' ', ''))
            if raw in tt:
                hit = row
                break
        if hit is None:
            bad_rect.append(L)
            continue
        # 2) 目标页/行是否有该编号的定义点
        trow = None
        for row in pages.get(L['target_page'] - 1, []):
            if abs(row['y0'] - L['target_y']) < 3.0:
                trow = row
                break
        if trow is None:
            bad_tgt.append(L)
            continue
        tt = trow['text'].replace('．', '.').replace('∙', '.').replace('，', '.')
        if L['num'] not in tt and L['kind'] != 'Equation' and L['kind'] != 'Section':
            bad_tgt.append(L)
            continue
        ok += 1
    print('audit: ok %d / %d ; bad_rect %d ; bad_target %d' %
          (ok, len(links), len(bad_rect), len(bad_tgt)))
    for L in bad_rect[:8]:
        print('  RECT?', L['page'], L['kind'], L['num'], '|', L['line'][:60])
    for L in bad_tgt[:8]:
        print('  TGT? ', L['page'], L['kind'], L['num'], '->p%d y%.1f' %
              (L['target_page'], L['target_y']), '|', L['target_text'][:40])


def main():
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest='cmd', required=True)

    def common(p):
        p.add_argument('--cache', default='ocr.pkl')
        p.add_argument('--skip-pages', default='0-15')
        p.add_argument('--ymin', type=float, default=55.0)
        p.add_argument('--x0-min', type=float, default=70.0)
        p.add_argument('--x0-max', type=float, default=165.0)
        p.add_argument('--eq-xmin', type=float, default=300.0)

    s = sub.add_parser('scan')
    common(s)
    s.add_argument('--chars', default='char.pkl', help='字符级 OCR 缓存（可选）')
    s.add_argument('--index', default='index.json')
    s.add_argument('--report', default='report.json')
    s.add_argument('--skipped', default='skipped.json')
    s.set_defaults(func=cmd_scan)

    b = sub.add_parser('build')
    b.add_argument('--pdf', required=True)
    b.add_argument('--report', default='report.json')
    b.add_argument('--out', required=True)
    b.add_argument('--dy', type=float, default=8.0)
    b.set_defaults(func=cmd_build)

    au = sub.add_parser('audit')
    au.add_argument('--report', default='report.json')
    au.add_argument('--cache', default='ocr.pkl')
    au.set_defaults(func=cmd_audit)

    a = ap.parse_args()
    a.func(a)


if __name__ == '__main__':
    main()
