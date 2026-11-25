#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""bm_locate.py — 写回之前的三件事，一个入口。

子命令
------
locate    按「印刷目录条目表」在正文里定位标题行，产出 located.json + items.json
diagnose  给现有书签做错误分型（页顶 / 负坐标 / 页码口径错 / 标题混入页码 / 指向目录页 / 页序倒退）
chunks    两次拼版图逐块哈希比对，只重看变了的块

为什么需要它
------------
2026-11-23 连做三本（严加安《测度论讲义》纯扫描、程其襄《实变函数与泛函分析基础》
扫描+OCR 文字层、Bogachev《Measure Theory》两卷合订 born-digital），每本都临时手写了
一套 locate / folio / 旧树诊断脚本，坑重复踩。这里把三次的规则固定下来：

* **先聚行，再按 x 拼接**：born-digital 常把「2.7.」与题名排成同一行高、y 差 1–2pt 的
  两条 line（规则 28）。只读单条 line 会漏整节，或只拿到题名、匹配不到编号。
* **节号锚必须精确**：`^num\\.\\s+(?!\\d)`，否则「1.8.1. Theorem」会把书签打到定理上
  （Bogachev 实测 9 条误判）；同时排除 Theorem/Definition/Lemma 等词。
* **粗体门槛**：页眉常是同名 9pt 非粗体行，不设门槛就会落到页眉。
* **页码分段**：`物理 = 印刷 folio + offset` 允许按 folio 分段（Bogachev 第一卷在
  References 处从 +16 变 +15）。
* **落点 y = 标题行顶 − dy**（默认 6pt），保证编号与完整标题可见。

输入
----
条目表（JSON 数组，一条一个对象）::

    [
      {"level": 1, "kind": "text",    "title": "Preface",  "page": 5,  "key": "Preface"},
      {"level": 2, "kind": "chapter", "title": "Chapter 1. Constructions ...", "num": 1, "folio": 1},
      {"level": 3, "kind": "section", "title": "1.2. Algebras and σ-algebras",
                                      "num": "1.2", "folio": 3},
      {"level": 1, "kind": "text",    "title": "目录", "page": 1, "y": 145.0}
    ]

字段：level 必填；title 必填；kind 可省（有 num 且含点 → section，num 为整数 → chapter，
否则 text）。定位依据三选一：`page`（物理页，最高优先）> `folio`（印刷页，配合
--offset 换算）> `expect`（同 folio）。`key` 覆盖搜索文本；`y`/`dy` 覆盖落点。

文字来源二选一：
  * `--pdf`            文字层（born-digital 或扫描件带 OCR 层）
  * `--rows all_rows.txt`  `ocr_rows.py --summary` 的行摘要（纯扫描件）

用法
----
    # 1) 定位
    python bm_locate.py locate --pdf book.pdf --entries entries.json \
        --offset 16 --offset 456=15 -o .

    # 2) 旧树分型
    python bm_locate.py diagnose --pdf book.pdf
    python bm_locate.py diagnose --pdf book.pdf --json diag.json --window 12

    # 3) 拼版只重看变了的块
    python bm_locate.py chunks --a sheets_v2 --b sheets_v3 --out chunks_v3 --tile 970

退出码：0 = 无问题；2 = 有 MISS / 有硬分型（.locate / diagnose）；1 = 用法或读取失败。
"""
import argparse
import difflib
import hashlib
import json
import os
import re
import sys
import unicodedata

try:
    import pymupdf
except ImportError:  # pragma: no cover
    pymupdf = None

# 节标题后面允许出现的排除词：这些是正文里的编号对象，不是节标题
OBJ_WORDS = (r'Theorem|Definition|Lemma|Proposition|Corollary|Example|Remark|'
             r'Exercise|Problem|Proof|Corollary|Notation|Conjecture')
XYZ_RE = re.compile(r"/XYZ\s+(-?[\d.]+|-?null)\s+(-?[\d.]+|-?null)")
LEADER_RE = re.compile(r'(?:[.．·]\s*){4,}|…{2,}')
CN_NUM = '零一二三四五六七八九十'


# --------------------------------------------------------------------------- #
# 文本规范化与相似度
# --------------------------------------------------------------------------- #
def norm(s):
    """折掉重音/连字，只留字母数字与汉字，用于子序列匹配。"""
    s = unicodedata.normalize('NFKD', s)
    s = ''.join(c for c in s if not unicodedata.combining(c))
    for a, b in (('\ufb01', 'fi'), ('\ufb02', 'fl'), ('\ufb00', 'ff'),
                 ('\ufb03', 'ffi'), ('\ufb04', 'ffl')):
        s = s.replace(a, b)
    s = s.lower()
    return re.sub(r'[^0-9a-z\u4e00-\u9fff]+', '', s)


def cn_num(n):
    if n < 10:
        return CN_NUM[n]
    if n == 10:
        return '十'
    if n < 20:
        return '十' + CN_NUM[n - 10]
    return CN_NUM[n // 10] + '十' + (CN_NUM[n % 10] if n % 10 else '')


def title_key(t):
    """从题名里剥掉编号与尾部页码，得到可用于正文比对的键。"""
    t = re.sub(r'^\s*(?:Chapter|CHAPTER|Section)\s+[0-9IVXLCivxlc]+\.?\s*', '', t)
    t = re.sub(r'^\s*[0-9]+(?:\.[0-9]+)*\.?\s+', '', t)
    t = re.sub(r'^\s*第[%s0-9]+[章节篇部分]\s*' % CN_NUM, '', t)
    t = re.sub(r'[\s,，.．、·:：;；()（）\[\]【】]+([0-9]{1,4})\s*$', '', t)
    return re.sub(r'\s+', ' ', t).strip()


def subseq_score(needle, hay):
    """needle 的字符按序出现在 hay 里的比例；抗 OCR 掉字与空格差异。"""
    n = norm(needle)
    h = norm(hay)
    if not n:
        return 0.0
    i = 0
    for ch in h:
        if i < len(n) and ch == n[i]:
            i += 1
    return i / len(n)


# --------------------------------------------------------------------------- #
# 文本来源：文字层 或 OCR 行摘要
# --------------------------------------------------------------------------- #
class Source:
    """统一的「视觉行」接口。line = dict(y, x0, size, bold, text)。"""

    def __init__(self, pdf=None, rows=None, cluster=3.0, verbose=False):
        self.pdf = pdf
        self.rows = rows
        self.cluster = cluster
        self.verbose = verbose
        self._cache = {}
        self._doc = None
        self.folio = {}          # page -> 页脚 folio（数字）
        if pdf:
            self._doc = pymupdf.open(pdf)
            self.page_count = self._doc.page_count
        else:
            self.page_count = max(self._rows_by_page().keys()) if self._rows_by_page() else 0

    # -- OCR 行摘要 -------------------------------------------------------- #
    def _rows_by_page(self):
        if hasattr(self, '_rows_cache'):
            return self._rows_cache
        by = {}
        if self.rows:
            pat = re.compile(r'^p(\d+)\s+y=([\d.]+)\|x=([\d.]+)\t(.*)$')
            with open(self.rows, encoding='utf-8', errors='replace') as fh:
                for line in fh:
                    m = pat.match(line.rstrip('\n'))
                    if not m:
                        continue
                    pg = int(m.group(1))
                    by.setdefault(pg, []).append(
                        dict(y=float(m.group(2)), x0=float(m.group(3)),
                             size=0.0, bold=False, text=m.group(4).replace(' | ', ' ').strip()))
        self._rows_cache = by
        return by

    # -- 行读取 ------------------------------------------------------------ #
    def lines(self, page):
        if page in self._cache:
            return self._cache[page]
        if self.rows:
            raw = self._rows_by_page().get(page, [])
        else:
            raw = self._pdf_lines(page)
        out = self._merge(raw)
        self._cache[page] = out
        return out

    def _pdf_lines(self, page):
        pg = self._doc[page - 1]
        raw = []
        for blk in pg.get_text('dict')['blocks']:
            for ln in blk.get('lines', []):
                txt = ''.join(s['text'] for s in ln['spans']).strip()
                if not txt:
                    continue
                bold = any(('BX' in s['font'] or 'BO' in s['font'] or
                            'Bold' in s['font'] or 'Black' in s['font'] or
                            (s['flags'] & 16)) for s in ln['spans'])
                size = max(s['size'] for s in ln['spans'])
                raw.append(dict(y=ln['bbox'][1], x0=ln['bbox'][0], x1=ln['bbox'][2],
                                size=size, bold=bold, text=txt))
        return raw

    def _merge(self, raw):
        """按 y 聚类（born-digital 拆行），组内按 x 排序拼接（编号在前）。"""
        if not raw:
            return []
        raw = sorted(raw, key=lambda r: (r['y'], r['x0']))
        groups = []
        for r in raw:
            if groups and abs(r['y'] - groups[-1][0]['y']) < self.cluster:
                groups[-1].append(r)
            else:
                groups.append([r])
        out = []
        for g in groups:
            g.sort(key=lambda r: r['x0'])
            out.append(dict(y=min(r['y'] for r in g), x0=min(r['x0'] for r in g),
                            size=max(r['size'] for r in g),
                            bold=any(r['bold'] for r in g),
                            text=' '.join(r['text'] for r in g).strip()))
        return out

    # -- 页脚 folio -------------------------------------------------------- #
    def page_folio(self, page, band=0.90):
        """取页面底部 band 以下的纯数字行首尾 token，作印刷页码。"""
        if page in self.folio:
            return self.folio[page]
        val = None
        if self._doc is not None:
            pg = self._doc[page - 1]
            h = pg.rect.height
            cand = []
            for ln in self.lines(page):
                if ln['y'] >= h * band:
                    toks = ln['text'].split()
                    if len(toks) <= 2 and toks and re.fullmatch(r'\d{1,4}', toks[-1]):
                        cand.append(int(toks[-1]))
            val = cand[-1] if cand else None
        else:
            # OCR 行：取最后一行纯数字
            rows = [r for r in self._rows_by_page().get(page, [])
                    if re.fullmatch(r'\d{1,4}', r['text'].strip())]
            val = int(rows[-1]['text']) if rows else None
        self.folio[page] = val
        return val

    def close(self):
        if self._doc is not None:
            self._doc.close()


# --------------------------------------------------------------------------- #
# 偏移（印刷 folio -> 物理页），支持分段
# --------------------------------------------------------------------------- #
class Offset:
    """--offset 16 --offset 456=15 之后，folio>=456 的页用 +15，其余 +16。"""

    def __init__(self, specs):
        self.rules = []          # [(from_folio, off)]
        self.default = None
        for s in specs or []:
            if '=' in s or ':' in s:
                a, b = re.split(r'[=:]', s, maxsplit=1)
                self.rules.append((int(a), int(b)))
            else:
                self.default = int(s)
        self.rules.sort(reverse=True)

    def __call__(self, folio):
        for frm, off in self.rules:
            if folio >= frm:
                return off
        if self.default is None:
            raise SystemExit('条目给出的是 folio，但没有 --offset；请补 --offset N 或改用 page')
        return self.default

    def __bool__(self):
        return self.default is not None or bool(self.rules)


# --------------------------------------------------------------------------- #
# locate
# --------------------------------------------------------------------------- #
def load_entries(path):
    with open(path, encoding='utf-8') as fh:
        data = json.load(fh)
    if isinstance(data, dict) and 'entries' in data:
        data = data['entries']
    out = []
    for i, e in enumerate(data, 1):
        if 'title' not in e:
            raise SystemExit(f'第 {i} 条缺 title')
        e.setdefault('level', 1)
        out.append(e)
    return out


def infer_kind(e):
    if e.get('kind'):
        return e['kind']
    num = e.get('num')
    if num is None:
        return 'text'
    s = str(num)
    if re.fullmatch(r'\d+\.\d+(\.\d+)*', s):
        return 'section'
    if re.fullmatch(r'\d+', s):
        return 'chapter'
    return 'text'


def match_line(e, kind, ln, ymin, ymax, size_min):
    """返回 (score_tuple, note) 或 None。"""
    txt = ln['text']
    if not (ymin <= ln['y'] <= ymax):
        return None
    if kind == 'section':
        num = str(e['num'])
        # 精确节号锚：允许「1.8.」后跟空格/题名，绝不允许「1.8.1.」
        if not re.match(r'^\s*' + re.escape(num) + r'\.\s*(?!\d)', txt):
            return None
        if re.search(r'\b(?:%s)\b' % OBJ_WORDS, txt):
            return None
        if ln['size'] and ln['size'] < size_min:
            return None
        hit = subseq_score(title_key(e['title']), txt) >= 0.7
        if not (ln['bold'] or hit):
            return None
        return (2 if hit else 0, 2 if ln['bold'] else 0, -ln['y']), ('bold' if ln['bold'] else 'size')
    if kind == 'chapter':
        num = e['num']
        pats = [r'^CHAPTER\s+%s\b' % re.escape(str(num)),
                r'^\s*第\s*%s\s*章' % re.escape(cn_num(int(num)) if str(num).isdigit() else str(num))]
        if not any(re.search(p, txt, re.I) for p in pats):
            return None
        if ln['size'] and ln['size'] < size_min:
            return None
        return (2 if ln['bold'] else 0, -abs(ln['y'] - 200)), 'chapter'
    # text
    if e.get('key'):
        key = e['key']
    elif re.match(r'^\s*(?:第[%s0-9]+章|Chapter\s+\d+)' % CN_NUM, e['title']):
        key = e['title']          # 章标题保留「第N章」，OCR 的「第 3 章」去掉空格后即命中
    else:
        key = title_key(e['title'])
    nk, nt = norm(key), norm(txt)
    if len(nk) < 2:
        return None
    # 非粗体行的长度必须贴近题名（+6）：否则正文里含有该短语的整句也会命中，
    # 实测会把「7.3 正则条件概率」定到下一段定义文字上。
    if nk in nt and len(nt) <= len(nk) + (24 if ln['bold'] else 6):
        pass
    elif (len(nk) >= 3 and 0.6 * len(nk) <= len(nt) <= len(nk) + 6
          and (nk.startswith(nt) or nt.startswith(nk))):
        # 折行，或 OCR 把 `L^p`、`Hausdorff` 尾部读丢。
        # 上界 len+6 是关键：否则以题名开头的正文长句（「正则条件概率的第一个应用…」）
        # 会被当成标题。
        pass
    elif len(nk) >= 6 and len(nt) <= len(nk) * 1.3 and subseq_score(key, txt) >= 0.8:
        pass          # OCR 掉字/换形（Hilbert -> Hilbe, Hausdorff -> HausdorfF）
    elif (len(nk) >= 6 and 0.7 <= len(nt) / len(nk) <= 1.3
          and difflib.SequenceMatcher(None, nk, nt).ratio() >= 0.85):
        pass          # OCR 少一两个字符（Choquet -> Choque, Hilbert -> Hilbe）
    else:
        return None
    return (1 if ln['bold'] else 0, -abs(ln['y'] - 200)), 'text'


def do_locate(args):
    src = Source(pdf=args.pdf, rows=args.rows, cluster=args.cluster, verbose=args.verbose)
    off = Offset(args.offset)
    entries = load_entries(args.entries)
    located, items = [], []
    miss = 0
    tocpages = toc_pages(src) if args.skip_toc else set()

    for e in entries:
        kind = infer_kind(e)
        title = e['title']
        if 'page' in e:
            page, basis = int(e['page']), 'page'
        elif 'folio' in e:
            if 'offset' in e:          # 合订本：各卷 folio 各自从 1 开始，必须逐条带偏移
                page, basis = int(e['folio']) + int(e['offset']), 'folio+entry'
            else:
                page, basis = int(e['folio']) + off(int(e['folio'])), 'folio'
        elif 'expect' in e:
            page, basis = int(e['expect']), 'expect'
        else:
            raise SystemExit(f'{title}: 需要 page 或 folio')

        # 显式 y：跳过定位（书前内容无标题行时用）
        if 'y' in e:
            y = float(e['y'])
            located.append(dict(e, page=page, y=y, hit='(explicit)', score=0, basis=basis))
            items.append(dict(level=e['level'], page=page, title=title, y=y))
            print(f'=   L{e["level"]} {title[:56]:58s} p{page:<5d} y={y:7.1f}  显式')
            continue

        cands = []
        for p in range(page - args.span, page + args.span + 1):
            if not 1 <= p <= src.page_count or p in tocpages:
                continue
            for ln in src.lines(p):
                got = match_line(e, kind, ln, args.ymin, args.ymax, args.size_min)
                if not got:
                    continue
                sco, note = got
                cands.append((sco + (2 if p == page else 0,), p, ln, note))
        if not cands:
            miss += 1
            located.append(dict(e, page=None, y=None, hit=None, score=0, basis=basis))
            print(f'MISS L{e["level"]} {title[:56]:58s} 期望 p{page}  (kind={kind})')
            continue

        cands.sort(key=lambda c: (c[0], -c[1]), reverse=True)
        sc, p, ln, note = cands[0]
        dy = float(e.get('dy', args.dy))
        y = round(ln['y'] - dy, 2)
        located.append(dict(e, page=p, y=y, hit=ln['text'][:90], score=list(sc),
                            basis=basis, note=note))
        items.append(dict(level=e['level'], page=p, title=title, y=y))
        flag = '' if p == page else f'  Δ{p - page:+d}'
        print(f'OK  L{e["level"]} {title[:56]:58s} p{p:<5d} y={y:7.1f} {note}{flag}')

    # 结构检查
    prev = 0
    bad = []
    for i, it in enumerate(items, 1):
        if not 1 <= it['level'] <= prev + 1:
            bad.append(f'第 {i} 条层级跳级: L{prev} -> L{it["level"]}')
        prev = it['level']
    back = [(a['title'], a['page'], b['title'], b['page'])
            for a, b in zip(items, items[1:]) if b['page'] < a['page']]

    print(f'\n条目 {len(items)}  层级 ' +
          ' '.join(f'L{lv}={sum(1 for x in items if x["level"] == lv)}'
                   for lv in sorted({x['level'] for x in items})))
    print(f'MISS {miss}   层级异常 {len(bad)}   页序倒退 {len(back)}')
    for b in bad:
        print('  ! ' + b)
    for t, p1, t2, p2 in back:
        print(f'  ~ 页序 {t[:28]!r} p{p1} -> {t2[:28]!r} p{p2}')

    if args.out:
        os.makedirs(args.out, exist_ok=True)
        json.dump(located, open(os.path.join(args.out, 'located.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        json.dump(items, open(os.path.join(args.out, 'items.json'), 'w', encoding='utf-8'),
                  ensure_ascii=False, indent=1)
        print(f'写出 {os.path.join(args.out, "located.json")} 与 items.json')
    src.close()
    return 0 if miss == 0 and not bad else 2


# --------------------------------------------------------------------------- #
# 页码分段
# --------------------------------------------------------------------------- #
def folio_runs(src, lo=1, hi=None):
    """返回 [(起页, 止页, offset)]；offset = 物理页 - 印刷 folio。"""
    hi = hi or src.page_count
    runs = []
    for pg in range(lo, hi + 1):
        f = src.page_folio(pg)
        if f is None:
            continue
        o = pg - f
        if runs and runs[-1][1] == pg - 1 and runs[-1][2] == o:
            runs[-1][1] = pg
        else:
            runs.append([pg, pg, o])
    return [tuple(r) for r in runs]


# --------------------------------------------------------------------------- #
# diagnose：旧树错误分型
# --------------------------------------------------------------------------- #
def raw_dest_top(doc, item_xref):
    if not item_xref:
        return None
    for key in ('A', 'Dest'):
        kind, val = doc.xref_get_key(item_xref, key)
        if kind != 'null' and '/XYZ' in (val or ''):
            m = XYZ_RE.search(val)
            if m and m.group(2) not in ('null', None):
                return float(m.group(2))
    return None


def toc_pages(src, probe=None):
    """识别目录页：≥3 行带引导点，或整行只有 Contents / 目 录。

    必须扫全书：合订本的第二卷目录常在 500 页之后（Bogachev p521–523），
    只扫前 40 页会漏掉，于是"指向目录页"这类错误反而查不出来。
    门槛取"≥3 行且引导点 ≥8 字符"：正文里的省略号（`…`、`· · ·`）单行出现，
    不会让整页被判成目录页。
    """
    out = set()
    probe = probe or src.page_count
    leader = re.compile(r'(?:[.．·]\s*){8,}|…{3,}')
    for pg in range(1, probe + 1):
        hits = 0
        for ln in src.lines(pg):
            t = ln['text']
            if re.fullmatch(r'\s*(Contents|CONTENTS|Table of Contents|目\s*录)\s*', t):
                out.add(pg)
                break
            if leader.search(t):
                hits += 1
                if hits >= 3:
                    out.add(pg)
                    break
    return out


def toc_like(src, page, cache={}):
    """行尾紧跟裸页码的行占比高 -> 印刷目录页。

    比"引导点"稳：中文扫描本的目录常用间隔点或干脆没有引导线，
    但每行都以页码结尾（严加安 p9: 61 行里 30 行如此；正文页为 0–1 行）。
    """
    key = (id(src), page)
    if key in cache:
        return cache[key]
    ls = src.lines(page)
    if not ls:
        cache[key] = False
        return False
    endnum = sum(1 for ln in ls
                 if len(norm(ln['text'])) > 6 and re.search(r'\d{1,4}\s*$', ln['text']))
    cache[key] = endnum >= 5 and endnum / len(ls) >= 0.3
    return cache[key]


def build_index(src, ymin=62.0):
    """全书行索引 [(page, y, norm(text), bold, text)]，供跨页远距查找。

    ymin 要压过页眉：严加安 p232 的页眉「· 222 · 第 10 章 Choquet 积分与离散集函数」
    落在 y=50.4，阈值取 50 就会把它当成章标题。
    """
    if hasattr(src, '_index'):
        return src._index
    idx = []
    for pg in range(1, src.page_count + 1):
        for ln in src.lines(pg):
            if ln['y'] < ymin:
                continue
            idx.append((pg, ln['y'], norm(ln['text']), ln['bold'], ln['text']))
    src._index = idx
    return idx


def find_title_page(src, key, near, window, tp=None, allow_toclike=False):
    """先 near±window，找不到再全书搜；返回 (page, y, text, far) 或 None。

    `far` 为 True 表示真实页远在窗口之外（旧树页码可能整体错段），这比
    只报"未找到"有用得多：能直接看出 Δ 的量级与方向。
    """
    nk = norm(key)
    if len(nk) < 4:
        return None
    tp = tp or set()

    def scan(rows):
        best = None
        for p, y, nt, bold, txt in rows:
            if p in tp or not nt:
                continue
            if not allow_toclike and toc_like(src, p):
                continue
            if nk not in nt:
                # 标题可能折行：「Connections between the integral and」+
                # 「derivative」，单行里只有前缀。
                if not (len(nt) >= 0.6 * len(nk) and nk.startswith(nt)):
                    continue
            elif not bold and len(nt) > len(nk) + 8:
                continue          # 正文长句
            if LEADER_RE.search(txt):
                continue
            score = (-abs(p - near), 1 if bold else 0, -abs(y - 200))
            if best is None or score > best[0]:
                best = (score, p, y, txt)
        return best

    near_rows = [(p, y, nt, b, t) for (p, y, nt, b, t) in build_index(src)
                 if abs(p - near) <= window]
    best = scan(near_rows)
    if best:
        return best[1], best[2], best[3], False
    best = scan(build_index(src))
    if best:
        return best[1], best[2], best[3], True
    return None


def do_diagnose(args):
    doc = pymupdf.open(args.pdf)
    src = Source(pdf=args.pdf, rows=args.rows)
    toc = doc.get_toc(simple=False)
    # 纯扫描件没有文字层：页码核对必然全 MISS，那是假信号，直接说明并跳过。
    has_text = any(len(ln['text']) > 20 for ln in src.lines(min(5, src.page_count)))
    check_pages = bool(args.rows) or has_text
    if not toc:
        print('该书签为空：需从印刷目录重建。')
        return 2
    tp = toc_pages(src)
    print(f'书签 {len(toc)} 条；疑似目录页 {sorted(tp) if tp else "无"}')

    flags = {k: [] for k in ('top', 'neg', 'oor', 'title_digits', 'in_toc',
                             'page_off', 'far', 'nofind', 'unverified')}
    for idx, (lv, title, page, dest) in enumerate(toc, 1):
        pg = doc[page - 1]
        top = raw_dest_top(doc, dest.get('xref')) if isinstance(dest, dict) else None
        if pg.rotation:
            flags['unverified'].append((idx, lv, title, page, 'rotation≠0'))
            view_top = None
        elif top is None:
            flags['unverified'].append((idx, lv, title, page, '无 /XYZ'))
            view_top = None
        else:
            view_top = pg.cropbox.y1 - top
            if view_top < 0:
                flags['neg'].append((idx, lv, title, page, round(view_top, 1)))
            elif view_top < args.top_band:
                flags['top'].append((idx, lv, title, page, round(view_top, 1)))
            if not (0 <= view_top <= pg.rect.height):
                flags['oor'].append((idx, lv, title, page, round(view_top, 1)))
        if (re.search(r'[\s,，.．、:：]\s*\d{1,4}\s*$', title) and len(title) > 5
                and not re.search(r'(?:Volume|Vol\.?|Part|Book|第)\s*[IVXLC0-9]+$', title)):
            flags['title_digits'].append((idx, lv, title, page, title[-18:]))
        if page in tp:
            if re.search(r'Contents|CONTENTS|Table of Contents|目\s*录', title):
                pass                      # 书签本身就叫「目录」，指向目录页是对的
            else:
                flags['in_toc'].append((idx, lv, title, page, '落在目录页'))
            continue                      # 已在目录页，再比页码无意义
        if not check_pages:
            continue
        key = title_key(title)
        got = find_title_page(src, key, page, args.window, tp)
        if got is None:
            alt = find_title_page(src, key, page, args.window, tp, allow_toclike=True)
            note = '正文未找到题名'
            if alt and alt[0] != page:
                note = f'未找到；p{alt[0]} 有同名行（该页像目录/索引，需目视）'
            flags['nofind'].append((idx, lv, title, page, note))
        elif got[0] != page:
            d = got[0] - page
            item = (idx, lv, title, page, f'实际 p{got[0]} (Δ{d:+d})')
            flags['far' if abs(d) > args.window else 'page_off'].append(item)

    # 页序
    back = [(i + 1, toc[i][1], toc[i][2], toc[i + 1][1], toc[i + 1][2])
            for i in range(len(toc) - 1) if toc[i + 1][2] < toc[i][2]]

    label = {
        'top': '落点在页顶（无标题级定位）',
        'neg': '落点为负（跳转后标题在视口上方）',
        'oor': '落点越出页面',
        'title_digits': '标题混入页码/杂字符',
        'in_toc': '目标指向目录页（把目录当正文）',
        'page_off': '页码口径错（与实际标题页差 ≤ 检索窗）',
        'far': '页码差一个量级（旧树整体错段或缺页）',
        'nofind': '正文未找到题名（需目视或换 key）',
        'unverified': '口径未验证（旋转页/无 /XYZ）',
    }
    print('（下列是待核查信号，不是判决；每条须回到目录顺序与实际页面确认）')
    print()
    for k in ('neg', 'oor', 'in_toc', 'title_digits', 'far', 'page_off',
              'top', 'nofind', 'unverified'):
        rows = sorted(flags[k], key=lambda r: -abs(int(re.search(r'Δ([+-]\d+)', str(r[4])).group(1)))
                      if re.search(r'Δ([+-]\d+)', str(r[4])) else 0)
        if not rows:
            continue
        print(f'[{k}] {label[k]} —— {len(rows)} 条')
        for r in rows[:args.show]:
            print(f'   #{r[0]:<4d} L{r[1]} p{r[3]:<5d} {r[2][:50]:52s} | {r[4]}')
        if len(rows) > args.show:
            print(f'   ... 另 {len(rows) - args.show} 条')
        print()
    if back:
        print(f'[order] 页序倒退 —— {len(back)} 处')
        for i, t1, p1, t2, p2 in back[:args.show]:
            print(f'   #{i} {t1[:34]!r} p{p1} -> {t2[:34]!r} p{p2}')
        print()

    hard = sum(len(flags[k]) for k in ('neg', 'oor', 'in_toc', 'page_off', 'far'))
    print('分型合计: ' + '  '.join(f'{k}={len(flags[k])}' for k in flags) + f'  order={len(back)}')
    if hard:
        print('结论: 旧树有硬缺陷，建议按印刷目录重建（不是逐条微调）。')
    elif flags['top'] or back:
        print('结论: 结构可能可用但落点/顺序需核查；先看页顶条目是否真的没有标题级定位。')
    else:
        print('结论: 未发现硬缺陷；仍须对照印刷目录核对覆盖与层级。')
    if not check_pages:
        print('注意: 本 PDF 无可用文字层，页码核对未做（nofind 一栏不适用）；'
              '扫描件请加 --rows <ocr_rows.py --summary 输出> 再跑一次。')

    if args.json:
        json.dump({'toc': len(toc), 'flags': {k: v for k, v in flags.items()},
                   'order_back': back, 'toc_pages': sorted(tp)},
                  open(args.json, 'w', encoding='utf-8'), ensure_ascii=False, indent=1)
        print(f'写出 {args.json}')
    src.close()
    doc.close()
    return 0 if not hard else 2


# --------------------------------------------------------------------------- #
# chunks：拼版逐块比对
# --------------------------------------------------------------------------- #
def do_chunks(args):
    from PIL import Image

    def digest(path):
        return hashlib.sha256(open(path, 'rb').read()).hexdigest()[:16]

    def sheet_files(d):
        return sorted(f for f in os.listdir(d) if f.lower().endswith('.png'))

    os.makedirs(args.out, exist_ok=True)
    a_files = sheet_files(args.a) if args.a else []
    b_files = sheet_files(args.b)
    only = set(a_files) if a_files else set(b_files)
    diff = []
    for name in b_files:
        im = Image.open(os.path.join(args.b, name))
        stem = os.path.splitext(name)[0]
        for k, top in enumerate(range(0, im.height, args.tile)):
            tile = im.crop((0, top, im.width, min(im.height, top + args.tile)))
            outp = os.path.join(args.out, f'{stem}_{k}.png')
            tile.save(outp)
            if name in only:
                ref = os.path.join(args.a, name)
                ref_k = k
                # 同名列同序号块比较；块数不同则整张对比后定位
                refp = os.path.join(args.a, name)
                if os.path.exists(refp):
                    rim = Image.open(refp)
                    rt = rim.crop((0, top, rim.width, min(rim.height, top + args.tile)))
                    rp = os.path.join(args.out, f'.ref_{stem}_{k}.png')
                    rt.save(rp)
                    same = digest(rp) == digest(outp)
                    os.remove(rp)
                    if not same:
                        diff.append(f'{stem}_{k}')
                else:
                    diff.append(f'{stem}_{k} (新增图)')
    total = sum(len(range(0, Image.open(os.path.join(args.b, f)).height, args.tile))
                for f in b_files)
    print(f'块数 {total}；与 --a 比对后差异 {len(diff)} 块')
    if diff:
        print('需重看: ' + ' '.join(diff[:40]) + (' ...' if len(diff) > 40 else ''))
    else:
        print('全部一致：只需看新增部分，未变的块不必重看。')
    print(f'切片写出 {args.out}')
    return 0


# --------------------------------------------------------------------------- #
def main():
    ap = argparse.ArgumentParser(description='书签写回前的定位 / 旧树分型 / 拼版比对')
    sub = ap.add_subparsers(dest='cmd', required=True)

    p = sub.add_parser('locate', help='按目录条目表定位标题行')
    p.add_argument('--pdf')
    p.add_argument('--rows', help='ocr_rows.py --summary 的行摘要（纯扫描件）')
    p.add_argument('--entries', required=True)
    p.add_argument('--offset', action='append', default=[],
                   help='N（全书）或 FROM=N（folio>=FROM 用 N），可重复')
    p.add_argument('--span', type=int, default=1, help='搜索页范围 ±N（默认 1）')
    p.add_argument('--cluster', type=float, default=3.0, help='同行 y 聚类容差（默认 3.0）')
    p.add_argument('--ymin', type=float, default=70.0)
    p.add_argument('--ymax', type=float, default=800.0)
    p.add_argument('--size-min', type=float, default=0.0, help='标题最小字号（0=不设）')
    p.add_argument('--dy', type=float, default=6.0, help='落点 = 行顶 - dy（默认 6）')
    p.add_argument('--skip-toc', action='store_true', default=True,
                   help='跳过目录页（默认开）')
    p.add_argument('--out', '-o')
    p.add_argument('--verbose', action='store_true')
    p.set_defaults(func=do_locate)

    p = sub.add_parser('diagnose', help='给现有书签做错误分型')
    p.add_argument('--pdf', required=True)
    p.add_argument('--rows', help='OCR 行摘要；纯扫描件必给，否则页码核对无依据')
    p.add_argument('--window', type=int, default=12, help='题名检索页范围 ±N')
    p.add_argument('--top-band', type=float, default=40.0, help='落点小于此值算页顶')
    p.add_argument('--show', type=int, default=5)
    p.add_argument('--json')
    p.set_defaults(func=do_diagnose)

    p = sub.add_parser('chunks', help='拼版切块并与旧版逐块比对')
    p.add_argument('--a', help='旧拼版目录（省略则只切片）')
    p.add_argument('--b', required=True, help='新拼版目录')
    p.add_argument('--out', required=True)
    p.add_argument('--tile', type=int, default=970)
    p.set_defaults(func=do_chunks)

    args = ap.parse_args()
    if args.cmd == 'locate' and not (args.pdf or args.rows):
        raise SystemExit('locate 需要 --pdf 或 --rows')
    sys.exit(args.func(args))


if __name__ == '__main__':
    main()
