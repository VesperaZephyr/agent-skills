#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""xref_links.py — 给正文里的交叉引用加可点击跳转（不写回原件，只产副本）。

子命令
------
scan    扫描全书，清点可作为跳转目标的标题行（章 / 节 / 习题 / 定理类），出 JSON
build   发现正文中的交叉引用，生成带 /Link 注解的副本；--dry-run 只出报告
audit   回读副本，逐条核验目标页 / 落点 / 落点下方标题文字；--marks 另出带框验证副本

为什么需要它
------------
数学书的正文里大量写着 ``cf. 14.4``、``by th. 12``、``see exercise 3.5``，
PDF 里却往往没有跳转。2026-11-24 在 Serre《Linear Representations of Finite Groups》
(GTM 42, 178 页, 扫描 + Adobe OCR 文字层) 上实测，把工序固化在这里。

关键经验（都踩过坑）：

* **判定"哪一行是标题"不能靠字体 / 字号 / 行距**。OCR 文字层给的是假字体
  （全书同一个 Times-Roman），bbox 互相重叠，相邻行 y0 之差实测可为 −12.5pt。
  唯一稳的是**排版形式**：标题写 ``Theorem 12.``（类型词 + 编号 + 紧随句点），
  正文句子式引用写 ``Theorem 12 shows...``（无句点）。这条规则单独就干净地选出
  全部标题行。第二道闸门是左边距 x0 与页眉剔除（y < --ymin）。
* **必须先测编号作用域**。Serre 的 Theorem / Proposition / Lemma 全书连续唯一，
  但 Corollary 只有 1..3 却出现 29 次（按命题重编号）。``cor. 2 to prop. 5``
  可以靠宿主命题精确配对；孤立的 ``cor. 2`` 在校准的节里若唯一才敢连。
* **目录 / 索引页是最大假阳性源**：目录行 ``8.4 Sylow's theorem 65`` 会被读成
  "theorem 65"（65 是页码）。必须先用 --skip-pages 排除。
* **OCR 纠形要成体系且保守**：I/l→1、O→0、S→5（仅限紧跟类型词的单字母位），
  粘连 ``th.12``、变体 ``tho``（OCR 把句点读成 o）。判不准就跳过，不猜。
* **写入用 /Link + /XYZ**：pymupdf 的 ``to=Point(x, y)`` 与书签同口径（距页顶磅数），
  ``saveIncr()`` 增量保存，不重排页面内容。回读必须用 get_links() 逐条对目标页和 to.y。
* **中文劣质 OCR 是另一套规则**（``--lang zh``）：标题必须逐原始 OCR 行判定（聚合行
  会把标题和同物理行正文倒序拼接），触发只看词尾类型词，编号清洗要先纠形再把未知
  字符换成空格，最多三段；《101 泛函分析》实测 74→151 条、audit 151/151。
  详见 SKILL.md 的中文小节与 references/detailed-rules.md 规则 31。

典型流程
--------
::

    python xref_links.py scan  --pdf book.pdf --skip-pages 0-12 --json heads.json
    python xref_links.py build --pdf book.pdf --out linked.pdf --skip-pages 0-12 \
                               --report links.json --dry-run
    python xref_links.py build --pdf book.pdf --out linked.pdf --skip-pages 0-12 \
                               --report links.json --apply
    python xref_links.py audit --pdf linked.pdf --report links.json --marks marked.pdf

--dry-run 与 --apply 的报告格式一致，便于先看清将写什么再落笔。
"""
import argparse
import collections
import json
import re
import shutil
import sys

try:
    import pymupdf as fitz
except ImportError:
    import fitz

# OCR 常把数字读成同形字母，仅在"紧跟类型词"的位置做有限纠形
OCR_DIGITS = str.maketrans({'I': '1', 'l': '1', 'O': '0', '|': '1'})
SINGLE_DIGIT = {'S': '5', 's': '5', 'B': '8', 'I': '1', 'l': '1', 'O': '0'}

# 结果类：标题行 "Theorem 12." 与正文提及 "th. 12" 的类型词映射
RESULT_KINDS = ('Theorem', 'Proposition', 'Corollary', 'Lemma', 'Definition', 'Remark')
KIND_ALIAS = {
    'th': 'Theorem', 'theo': 'Theorem', 'theorem': 'Theorem',
    'prop': 'Proposition', 'pro': 'Proposition', 'proposition': 'Proposition',
    'cor': 'Corollary', 'corollary': 'Corollary',
    'lem': 'Lemma', 'lemma': 'Lemma',
    'def': 'Definition', 'definition': 'Definition',
    'rem': 'Remark', 'remark': 'Remark',
    'ex': 'Exercise', 'exercise': 'Exercise',
}
# 复数/普通词不是引用触发词：OCR 常把 "EXERCISES"/"Remarks" 后的页码读成编号
NOT_MENTION = {'exercises', 'remarks', 'definitions', 'theorems',
               'propositions', 'lemmas', 'corollaries', 'problems'}

HEAD_RE = re.compile(
    r'^(Theorem|Proposition|Corollary|Lemma|Definition|Remark|Exercise|Problem|Claim)\s+'
    r'([0-9IlO|SB]{1,4})'
    r'(?:\s*\.|$|\s*\(|\s+[A-Z\u00c0-\u024f])'
)
SEC_RE = re.compile(r'^(\d{1,2})\.(\d{1,2})\b(.*)$')
CHAP_RE = re.compile(r'^(?:CHAPTER|Chapter)\s+(\d{1,2})\b')
EXER_RE = re.compile(r'^(\d{1,2})\.(\d{1,2})\.\s*(.*)$')

# ---------------------------------------------------------------------------
# 中文模式（--lang zh）：劣质 OCR 扫描件。2026-11-24 在《101 泛函分析》
# （Epson 扫描 + 劣质 OCR，254 页）上实测。与英文模式的关键差异：
#   * 编号是 章.节.序号 三段式，天然全书唯一，无需按节消歧；
#   * OCR 把点号读成 . ． ∙ • ， , 、 : ： 甚至空格，把 1 读成 I/l/i/|/工，
#     0 读成 O/o，5 读成 S/s，8 读成 B；
#   * 标题靠"行首类型词 + 左边距缩进 x0∈[74,150]"判定；字体全是假的
#     （MicrosoftYaHei），字号 7~8pt 也不可用；
#   * 正文提及靠引导词（见/由/根据/利用/证明…）+ 类型词 + 编号；裸 N.N
#     多为公式号（印在右边缘 x≈441）或节号，必须分开处理。
#   * 公式号/节号几乎总被 OCR 拆词：（+4+．+17+） / 1+．+4+节；
#     右边缘定义点还会把 1.4 整体读成 L4（L 兼含点号）。
# ---------------------------------------------------------------------------
ZH_KINDS = ('定理', '定义', '引理', '命题', '推论', '例', '习题', '注')
ZH_CUES = ('参见', '根据', '参考', '利用', '应用', '结合', '回顾', '提及',
           '引进', '如同', '注意', '定义见', '见', '由', '证明', '即')
# 中文 OCR 数字纠形。除常见的 I/l→1、O→0 外，下列映射是从
# 《101 泛函分析》真实扫描页的标题行逐条比对得出的（只作用于编号位置）：
#   L→1, 詵/上/生→4, &/}/該→3, 之/刀→2, G→6, 与→5
# 典型：定理 1 詵 10 = 1.4.10；例 2 ∙ L10 = 2.1.10；定理生 5 刁 = 4.5.4
ZH_DIGITS = str.maketrans({'I': '1', 'l': '1', 'i': '1', '|': '1', '工': '1',
                           'O': '0', 'o': '0', 'S': '5', 's': '5', 'B': '8',
                           'L': '1', '詵': '4', '上': '4', '生': '4',
                           '&': '3', '}': '3', '該': '3',
                           '之': '2', '刀': '2', 'G': '6', '与': '5',
                           # OCR 把末位 1 读成右括号，仅在数字位纠形
                           ']': '1', '」': '1', '』': '1'})
ZH_SEPS = '.．∙•，,、:：;；“” '
ZH_DIGIT_EXTRA = 'IilLoOL|工SsB]」』詵上生}&該之刀G与'
ZH_DIGIT_CLASS = r'[0-9' + re.escape(ZH_DIGIT_EXTRA) + r']'
# 编号捕获：1.2.3 / I.I.IO / 1 工 7 / 1 詵 10 / 4.5」 —— 2 或 3 段
ZH_NUMCAP = re.compile(
    r'(' + ZH_DIGIT_CLASS + r'{1,3}(?:\s*[' + re.escape(ZH_SEPS) + r']\s*' +
    ZH_DIGIT_CLASS + r'{1,3}){1,2})'
)
ZH_HEAD_RE = re.compile(r'^(' + '|'.join(ZH_KINDS) + r')\s*')
ZH_CUE_RE = re.compile(
    '(' + '|'.join(ZH_CUES) + r')\s*(' + '|'.join(ZH_KINDS) + r')\s*'
)
ZH_SEC_RE = re.compile(r'^(\d{1,2})\s*[.．∙•，,]\s*(\d{1,2})\s+([\u4e00-\u9fffA-Za-z].*)$')
ZH_EXER_RE = re.compile(r'^(习题)\s*(\d{1,2})\s*[.．∙•，,]\s*(\d{1,2})\s*$')
# 公式号：(1.2) / （1．4) / (L4)；L 也是 1 的 OCR 变体
ZH_EQ_REF = re.compile(r'[（(]\s*([0-9IilOoL]{1,2})\s*[.．∙•，,]\s*([0-9IilOoSsB]{1,3})\s*[)）]')
ZH_EQ_DEF = re.compile(r'^[（(]\s*([0-9IilOoL]{1,2})\s*[.．∙•，,]\s*([0-9IilOoSsB]{1,3})\s*[)）]$')
# 节号引用：1.4 节 / 2 ． 5 节中
ZH_SEC_REF = re.compile(r'(\d{1,2})\s*[.．∙•，,]\s*(\d{1,2})\s*节')


def zh_eq_num(raw):
    """公式号归一。扫描件把 '1.4' 整体读成 'L4'（L 兼含点号），需特判。"""
    s = raw.strip()
    m = re.match(r'^[（(]\s*[Ll]\s*(' + ZH_DIGIT_CLASS + r'{1,3})\s*[)）]$', s)
    if m:
        d = m.group(1).translate(ZH_DIGITS)
        if d.isdigit():
            return '1.' + d
    m = ZH_EQ_DEF.match(s)
    if m:
        return zh_num('%s.%s' % m.groups())
    return None


NBSP = '\xa0'


def norm_zh(s):
    """中文 OCR 行归一：NBSP->空格、压缩空白。"""
    return re.sub(r'\s+', ' ', s.replace(NBSP, ' ')).strip()


def zh_num(raw):
    """把 OCR 的 'I.I.IO' / '1 工 7' / '1.1.6)' 归一成 '1.1.10' / '1.1.6'。

    关键：先做字形纠形，再把**所有非数字非分隔符字符（含尾随括号、乱码）换成空格**。
    旧版把未知字符原样留下，导致 ``'1.1.6)'`` 的最后一段变成 ``'6)'`` 而整号失效，
    这是《101 泛函分析》初版只写出 74 条链接的最大漏检源。
    """
    s = raw.translate(ZH_DIGITS)
    s = ''.join(ch if ch.isdigit() or ch in ZH_SEPS else ' ' for ch in s)
    parts = [p for p in re.split(r'[' + re.escape(ZH_SEPS) + r']+', s) if p]
    if not (2 <= len(parts) <= 3) or not all(p.isdigit() for p in parts):
        return None
    return '.'.join(parts)


def zh_cap_num_end(text, start):
    """从 text[start:] 抓编号，返回 (归一编号, 结束绝对位置)；失败 (None, start)。

    前置分隔符（OCR 常把 ``定理 1.2`` 读成 ``定理 ： }.3``）先剥掉，
    否则 ``ZH_NUMCAP`` 要求首字符是数字-like，会把整行误判成非标题。
    """
    seg = text[start:]
    lead = len(seg) - len(seg.lstrip())
    seg2 = seg[lead:]
    lead2 = len(seg2) - len(seg2.lstrip(ZH_SEPS))
    p = start + lead + lead2
    m = ZH_NUMCAP.match(text[p:])
    if not m:
        return None, start
    return zh_num(m.group(1)), p + m.end(1)


def zh_cap_num(text, start):
    """从 text[start:] 起抓连续编号（允许点号间夹空白），返回归一号。"""
    n, _ = zh_cap_num_end(text, start)
    return n


def zh_spans(page):
    """原始 span [(y0, x0, text)]，不聚行（公式号定义点用）。"""
    out = []
    for b in page.get_text('dict')['blocks']:
        if b['type'] != 0:
            continue
        for l in b['lines']:
            for s in l['spans']:
                t = norm_zh(s['text'])
                if t:
                    out.append((s['bbox'][1], s['bbox'][0], t))
    return out


def zh_vlines(page, tol=2.5):
    """中文 OCR 视觉行 [(y0, x0, text)]，按 y 容差聚行并归一。"""
    raw = []
    for b in page.get_text('dict')['blocks']:
        if b['type'] != 0:
            continue
        for l in b['lines']:
            sp = [s for s in l['spans'] if s['text'].strip()]
            if not sp:
                continue
            sp.sort(key=lambda s: s['bbox'][0])
            t = norm_zh(''.join(s['text'] for s in sp))
            if t:
                raw.append((min(s['bbox'][1] for s in sp), sp[0]['bbox'][0], t))
    raw.sort()
    out = []
    for y, x, t in raw:
        if out and abs(y - out[-1][0]) < tol:
            out[-1][2] += ' ' + t
        else:
            out.append([y, x, t])
    return [(y, x, norm_zh(t)) for y, x, t in out]


def zh_raw_lines(page):
    """未聚行的 OCR 原始行 [(y0, x0, text)]。

    标题检测**必须**用这个函数而不是 ``zh_vlines``：劣质 OCR 会把同一物理行的
    标题与后续正文拆成两个 y 相差 <1pt 的 line，``zh_vlines`` 按 y 合并后
    出现 ``'对内积空间 H 中两个元 定理 1.2.2 ...'`` 这种顺序错乱的行，
    ``^定理`` 判定便会漏掉标题。原始行里标题自己仍是一行的开头。
    """
    out = []
    for b in page.get_text('dict')['blocks']:
        if b['type'] != 0:
            continue
        for l in b['lines']:
            sp = [s for s in l['spans'] if s['text'].strip()]
            if not sp:
                continue
            sp.sort(key=lambda s: s['bbox'][0])
            t = norm_zh(''.join(s['text'] for s in sp))
            if t:
                out.append((min(s['bbox'][1] for s in sp), sp[0]['bbox'][0], t))
    out.sort()
    return out


def parse_pages(spec):
    """'0-12,20,30-31' -> set of 0-based page indices."""
    if not spec:
        return set()
    out = set()
    for part in spec.split(','):
        part = part.strip()
        if not part:
            continue
        if '-' in part:
            a, b = part.split('-', 1)
            out.update(range(int(a), int(b) + 1))
        else:
            out.add(int(part))
    return out


def ocr_num(tok):
    """OCR 数字纠形；非数字单字母按字形回读。失败抛 ValueError。"""
    t = tok.translate(OCR_DIGITS)
    if not t.isdigit() and len(tok) == 1:
        t = SINGLE_DIGIT.get(tok, t)
    if not t.isdigit():
        raise ValueError('not a number: %r' % tok)
    return int(t)


def vis_lines(page):
    """视觉行 [(y0, y1, x0, size, font, text)]，按 y 容差 2pt 聚行。"""
    rows = []
    for b in page.get_text('dict')['blocks']:
        if b['type'] != 0:
            continue
        for l in b['lines']:
            sp = [s for s in l['spans'] if s['text'].strip()]
            if not sp:
                continue
            sp.sort(key=lambda s: s['bbox'][0])
            rows.append([min(s['bbox'][1] for s in sp), max(s['bbox'][3] for s in sp),
                         sp[0]['bbox'][0], max(s['size'] for s in sp),
                         sp[0]['font'], ''.join(s['text'] for s in sp)])
    rows.sort(key=lambda r: (r[0], r[2]))
    merged = []
    for r in rows:
        if merged and abs(r[0] - merged[-1][0]) < 2.0:
            m = merged[-1]
            m[1] = max(m[1], r[1])
            m[5] += ' ' + r[5]
        else:
            merged.append(list(r))
    return [(m[0], m[1], m[2], m[3], m[4], re.sub(r'\s+', ' ', m[5]).strip())
            for m in merged]


def word_lines(page, ytol=3.0):
    """按 y 聚词，返回 [(y, [(word, x0, y0, x1, y1), ...])]。"""
    words = page.get_text('words')
    words.sort(key=lambda w: (round(w[1], 1), w[0]))
    lines = []
    for w in words:
        if lines and abs(w[1] - lines[-1][0]) < ytol:
            lines[-1][1].append(w)
        else:
            lines.append([w[1], [w]])
    return [(y, sorted(ws, key=lambda w: w[0])) for y, ws in lines]


def scan_targets(doc, args):
    """扫描全书，返回各类目标标题与编号作用域统计。"""
    n = doc.page_count
    skip = parse_pages(args.skip_pages)
    chapters, sections, exercises, results = [], [], [], []
    for i in range(n):
        if i in skip:
            continue
        for y0, y1, x0, sz, font, text in vis_lines(doc[i]):
            if y0 < args.ymin:          # 页眉
                continue
            m = CHAP_RE.match(text)
            if m and sz > 13:
                chapters.append({'page': i + 1, 'y': round(y0, 2),
                                 'num': int(m.group(1)), 'text': text[:70]})
                continue
            if not (args.x0_min <= x0 <= args.x0_max):
                continue
            m = HEAD_RE.match(text)
            if m:
                try:
                    nn = ocr_num(m.group(2))
                except ValueError:
                    continue
                results.append({'page': i + 1, 'y': round(y0, 2), 'kind': m.group(1),
                                'num': nn, 'suffix': text[len(m.group(1)) + len(m.group(2)):].strip()[:2],
                                'text': text[:70]})
                continue
            m = EXER_RE.match(text)
            if m:
                exercises.append({'page': i + 1, 'y': round(y0, 2),
                                  'num': '%s.%s' % (m.group(1), m.group(2)),
                                  'text': text[:70]})
                continue
            m = SEC_RE.match(text)
            if m and m.group(3).strip() and re.match(r'[A-Za-z\u00c0-\u024f]', m.group(3).strip()):
                sections.append({'page': i + 1, 'y': round(y0, 2),
                                 'num': '%s.%s' % (m.group(1), m.group(2)),
                                 'text': text[:70]})

    # 编号作用域：每 (kind, num) 出现次数；>1 表示按节 / 按命题重编
    scope = {}
    by_kind = collections.defaultdict(list)
    for r in results:
        by_kind[r['kind']].append(r)
    for kind, rows in by_kind.items():
        c = collections.Counter(r['num'] for r in rows)
        scoped = sum(1 for v in c.values() if v > 1)
        scope[kind] = {'total': len(rows), 'unique': len(c),
                       'reused_numbers': scoped,
                       'verdict': 'per-section/per-proposition' if scoped else 'book-wide'}
    out = {'chapters': chapters, 'sections': sections,
           'exercises': exercises, 'results': results, 'scope': scope}
    return out


def scan_targets_zh(doc, args):
    """中文模式：扫描结果标题 / 节标题 / 习题标题 / 公式号定义点。"""
    n = doc.page_count
    skip = parse_pages(args.skip_pages)
    results, sections, exercises, equations = [], [], [], []
    for i in range(n):
        if i in skip:
            continue
        # 公式号定义点：按原始 span 扫右边缘 x>=eq_xmin，不聚行
        # （公式符号常与相邻公式 y 相差 <3pt，聚行会把它吞进公式文本）
        for y0, x0, text in zh_spans(doc[i]):
            if y0 < args.ymin or x0 < args.eq_xmin:
                continue
            num = zh_eq_num(text)
            if num:
                equations.append({'page': i + 1, 'y': round(y0, 2),
                                  'num': num, 'text': text[:40]})
        # 标题 / 习题 / 节标题：逐原始行判定，不能用 zh_vlines（见其注释）
        for y0, x0, text in zh_raw_lines(doc[i]):
            if y0 < args.ymin:
                continue
            m = ZH_HEAD_RE.match(text)
            if m:
                num = zh_cap_num(text, m.end(1))
                if num and args.x0_min_zh <= x0 <= args.x0_max_zh:
                    results.append({'page': i + 1, 'y': round(y0, 2),
                                    'x0': round(x0, 2), 'kind': m.group(1),
                                    'num': num, 'text': text[:70]})
                    continue
            m = ZH_EXER_RE.match(text)
            if m:
                exercises.append({'page': i + 1, 'y': round(y0, 2),
                                  'num': '%s.%s' % (m.group(2), m.group(3)),
                                  'text': text[:60]})
                continue
            m = ZH_SEC_RE.match(text)
            if m and x0 <= args.sec_x0_max:
                sections.append({'page': i + 1, 'y': round(y0, 2),
                                 'num': '%s.%s' % (m.group(1), m.group(2)),
                                 'text': text[:60]})
    # 编号作用域
    scope = {}
    by_kind = collections.defaultdict(list)
    for r in results:
        by_kind[r['kind']].append(r)
    for kind, rows in by_kind.items():
        c = collections.Counter(r['num'] for r in rows)
        scoped = sum(1 for v in c.values() if v > 1)
        scope[kind] = {'total': len(rows), 'unique': len(c),
                       'reused_numbers': scoped,
                       'verdict': 'per-section/reused' if scoped else 'book-wide'}
    return {'results': results, 'sections': sections,
            'exercises': exercises, 'equations': equations, 'scope': scope}


def build_index_zh(targets):
    idx = {'result': collections.defaultdict(list),
           'section': collections.defaultdict(list),
           'exercise': collections.defaultdict(list),
           'equation': collections.defaultdict(list)}
    for r in targets['results']:
        idx['result'][(r['kind'], r['num'])].append(r)
    for s in targets['sections']:
        idx['section'][s['num']].append(s)
    for e in targets['exercises']:
        idx['exercise'][e['num']].append(e)
    for q in targets['equations']:
        idx['equation'][q['num']].append(q)
    return idx


def zh_head_score(c):
    """同号多候选时，给"真标题"加分、给正文提及句减分。

    OCR 纠形扩大后，像 ``定理 3 該 2 说明...`` 这类正文句也会被当成标题；
    仅按页距选最近目标会跳到正文句。这里用编号之后的文字形态消歧。
    """
    text = c.get('text', '')
    m = ZH_HEAD_RE.match(text)
    if not m:
        return -5
    rest = text[m.end():].lstrip()
    n, end = zh_cap_num_end(rest, 0)
    after = rest[end:].lstrip() if n else rest
    score = 0
    if after.startswith(('（', '(', '（', '[')):
        score += 3                      # 标题常紧跟括号副题
    if re.match(r'^(说明|表明|可见|中|的证明|推出|给出|是|有|设|告诉|成立)', after):
        score -= 4                      # 明显的正文句
    if len(after) <= 2:
        score += 2                      # 纯编号标题行
    x0 = c.get('x0')
    if x0 is not None and 80 <= x0 <= 112:
        score += 1
    return score


def find_mentions_zh(doc, targets, idx, args):
    """中文模式（词级）：发现 引导词+类型词+编号 / 公式号 / N.N 节 引用。"""
    excluded = parse_pages(args.skip_pages)
    head_rows = collections.defaultdict(set)
    for key in ('results', 'sections', 'exercises', 'equations'):
        for r in targets[key]:
            head_rows[r['page']].add(r['y'])
    links, skipped = [], []

    def skip(kind, num, how, page0, text):
        skipped.append({'kind': kind, 'num': num, 'how': how,
                        'page': page0 + 1, 'text': text[:70]})

    # 类型词只要求出现在**词尾**：见例 / 由引理 / 证明由推论 / 使用定理 /
    # 定义见习题 / 勾股定理 全部覆盖。旧版要求整词恰为 引导词+类型词，
    # 把 "证明由引理"、"使用定理"、"根据勾股定理" 全漏掉了。
    kind_suffix = re.compile(
        r'(' + '|'.join(sorted(ZH_KINDS, key=len, reverse=True)) + r')$')
    digit = ZH_DIGIT_CLASS
    sep = '[' + re.escape(ZH_SEPS) + ']'
    num_tail = re.compile(
        r'.*?(' + digit + r'{1,3}(?:' + sep + digit + r'{0,3}){1,2})$')
    # 从词首抓完整编号；不能用 `digit{1,3}|...` 的 match，否则 '1.3' 只取到 '1'
    num_prefix = re.compile(
        r'^(' + digit + r'{1,3}(?:' + sep + digit + r'{0,3}){1,2})')
    punct_tail = ')）（(,.;:'   # 不剥 '」』]'：它们可能是 OCR 的 1
    eq_page = re.compile(r'^[（(]([0-9IilOoL]{1,2})[.．∙•，,]([0-9IilOoSsB]{1,3})[)）]$')
    sec_page = re.compile(r'^(\d{1,2})[.．∙•，,](\d{1,2})$')
    # 公式号引用在劣质 OCR 里几乎总是被拆成多个词：
    #   '利用等式' + '（' + '4' + '．' + '17' + '）'
    # 旧版只认单个词 '(4.17)'，全书 57 处引用只连到 3 处。
    eq_glued = re.compile(
        r'^[（(]\s*(' + digit + r'{1,3}(?:' + sep + digit + r'{1,3}){1,2})\s*[)）]')
    eq_split_close = re.compile(r'[)）]')

    def zh_trigger(tok, nxt=None):
        """返回 (kind, cue_offset, 黏在类型词尾部的编号或 None)。"""
        for word, off in ((tok, 0), (nxt, 1)):
            if not word:
                continue
            m = kind_suffix.search(word)
            if not m:
                continue
            tail = word[m.end():].rstrip(punct_tail)
            nm = num_tail.match(tail)
            num = zh_num(nm.group(1)) if nm else None
            return m.group(1), off, num
        return None

    def add_equation(num, rect, text):
        cand = idx['equation'].get(num, [])
        if not cand:
            skip('Equation', num, 'no-def', i, text)
            return
        links.append({'page': i + 1, 'page0': i, 'rect': rect_list(rect),
                      'text': text[:40], 'kind': 'Equation', 'num': num,
                      'target_page': cand[0]['page'], 'target_y': cand[0]['y'],
                      'target_text': cand[0].get('text', ''),
                      'how': 'equation-def'})

    def parse_sec_at(words, j):
        """解析 N.N 节：整词 '1.4节' 或拆词 '1'+'.'+'4'+'节'。"""
        w = words[j]
        tok = w[4].strip()
        m = re.match(r'^(\d{1,2})\s*[.．∙•，,]\s*(\d{1,2})\s*节', tok)
        if m:
            num = '%s.%s' % m.groups()
            return num, fitz.Rect(w[0], w[1], w[2], w[3]), tok, 1
        if not re.fullmatch(r'\d{1,2}', tok):
            return None
        pieces, k, close_word = [tok], j + 1, None
        while k < len(words) and k - j < 6:
            t = words[k][4].strip()
            if '节' in t:
                close_word = words[k]
                k += 1
                break
            clean = t.rstrip(punct_tail)
            if re.fullmatch(sep, clean) or re.fullmatch(r'\d{1,2}', clean):
                pieces.append(clean)
                k += 1
                continue
            break
        if close_word is None or len(pieces) < 3:
            return None
        num = zh_num(' '.join(pieces))
        if not num or num.count('.') != 1:
            return None
        t = close_word[4].strip()
        pos = t.index('节')
        x1 = close_word[0] + (close_word[2] - close_word[0]) * (pos + 1) / len(t)
        rect = fitz.Rect(w[0], w[1], x1, close_word[3])
        return num, rect, ' '.join(x[4] for x in words[j:k]), k - j

    def parse_eq_at(words, j):
        """解析 (N.M)：整词 '(4.17).' 或拆词 '（'+'4'+'．'+'17'+'）'。

        返回 (num, rect, text, consumed)；不是公式号返回 None。
        """
        w = words[j]
        tok = w[4].strip()
        m = eq_glued.match(tok)
        if m:
            num = zh_num(m.group(1))
            if num and num.count('.') >= 1:
                return num, fitz.Rect(w[0], w[1], w[2], w[3]), tok, 1
        if not re.fullmatch(r'[（(]', tok):
            return None
        pieces, k, close_word = [], j + 1, None
        while k < len(words) and k - j < 10:
            t = words[k][4].strip()
            mc = eq_split_close.search(t)
            if mc:
                pre = t[:mc.start()].strip().rstrip(punct_tail)
                if pre:
                    mp = num_prefix.match(pre)
                    val = mp.group(1) if mp else (
                        pre if re.fullmatch(digit + r'{1,3}|' + sep, pre) else None)
                    if val:
                        pieces.append(val)
                close_word = words[k]
                k += 1
                break
            clean = t.rstrip(punct_tail)
            if not clean:
                k += 1
                continue
            if re.fullmatch(digit + r'{1,3}', clean) or re.fullmatch(sep, clean):
                pieces.append(clean)
                k += 1
                continue
            mp = num_prefix.match(clean)
            if mp:
                pieces.append(mp.group(1))
                k += 1
                continue
            break
        if close_word is None or not pieces:
            return None
        num = zh_num(' '.join(pieces))
        if not num or num.count('.') < 1:
            return None
        rect = fitz.Rect(w[0], w[1], close_word[2], close_word[3])
        text = ' '.join(x[4] for x in words[j:k])
        return num, rect, text, k - j

    for i in range(doc.page_count):
        if i in excluded:
            continue
        pg = doc[i]

        def add_result(kind, num, rect, text, raw=None):
            cand = idx['result'].get((kind, num), [])
            if kind == '习题' and not cand:
                cand = idx['exercise'].get(num, [])
            if not cand:
                skip(kind, num, 'no-heading', i, text)
                return
            if len(cand) == 1:
                tgt = cand[0]
            else:
                # 先按"像不像标题"排序，再按页距；避免落到正文提及句上
                tgt = sorted(cand, key=lambda c: (-zh_head_score(c),
                                                  abs(c['page'] - (i + 1))))[0]
            links.append({'page': i + 1, 'page0': i,
                          'rect': rect_list(rect),
                          'text': text[:40], 'kind': kind, 'num': num,
                          'raw_num': (raw or text)[:60],
                          'target_page': tgt['page'], 'target_y': tgt['y'],
                          'target_text': tgt.get('text', ''),
                          'how': 'unique' if len(cand) == 1 else 'nearest'})

        ws = sorted(pg.get_text('words'), key=lambda w: (round(w[1], 1), w[0]))
        lines = []
        for w in ws:
            if lines and abs(w[1] - lines[-1][0]) < 3.0:
                lines[-1][1].append(w)
            else:
                lines.append([w[1], [w]])
        for y, words in lines:
            words.sort(key=lambda w: w[0])
            if any(abs(y - hy) < 3.0 for hy in head_rows.get(i + 1, set())):
                continue                                  # 标题行自身
            j = 0
            while j < len(words):
                w = words[j]
                tok = w[4].strip()
                nxt = words[j + 1][4].strip() if j + 1 < len(words) else None
                trig = zh_trigger(tok, nxt)
                consumed = 0
                if trig:
                    kind, cue_offset, glued = trig
                    kind_word = words[j + cue_offset]
                    start_word = words[j]
                    head = ' '.join(x[4] for x in words[j:j + cue_offset + 1])
                    if glued:
                        # 类型词与编号黏成一个词：定理1.2.3 / 由例1.1.6)
                        rect = fitz.Rect(start_word[0], kind_word[1],
                                         kind_word[2], kind_word[3])
                        add_result(kind, glued, rect, head)
                        consumed = 1 + cue_offset
                    else:
                        # 后续 1~7 个词拼编号：4 ． 2 ． 1 / 1.1.12 / 1 工 7
                        pieces = []          # [(原词, 清洗后文本)]
                        nseg = 0             # 已收集的数字段数；中文编号最多三段
                        k = j + cue_offset + 1
                        while k < len(words) and len(pieces) < 7:
                            clean = words[k][4].strip().rstrip(punct_tail)
                            if not clean:
                                break
                            is_sep = bool(re.fullmatch(sep, clean))
                            if is_sep:
                                # 三段已齐时不能继续吃 '，0' / '，7' 这类后续文字
                                if nseg >= 3:
                                    break
                                val = clean
                            elif re.fullmatch(digit + r'{1,3}', clean):
                                val = clean
                            else:
                                m = num_prefix.match(clean)
                                if not m:
                                    break
                                # 只取头部的编号部分：'1.6上' / '1.3.2(ii)' 这类
                                # OCR 粘连的尾缀不能让整段编号失效。
                                val = m.group(1)
                            pieces.append((words[k], val))
                            nn = zh_num(val)
                            if nn:
                                nseg += nn.count('.') + 1
                            elif re.fullmatch(digit + r'{1,3}', val):
                                nseg += 1       # 单独数字片段也占一段
                            k += 1
                            if nseg >= 3:
                                break
                        if pieces:
                            joined = ' '.join(p[1] for p in pieces)
                            num = zh_num(joined)
                            if num:
                                rect = fitz.Rect(start_word[0], kind_word[1],
                                                 pieces[-1][0][2], pieces[-1][0][3])
                                add_result(kind, num, rect, head + ' ' + joined)
                            consumed = k - j
                if consumed:
                    j += consumed
                    continue
                # 公式号引用 (N.M)：整词或拆词都要认
                eq = parse_eq_at(words, j)
                if eq:
                    num, rect, text, consumed = eq
                    add_equation(num, rect, text)
                    j += consumed
                    continue
                # N.N 节：整词或拆词都要认；词级矩形稳定，直接连
                sec = parse_sec_at(words, j)
                if sec:
                    num, rect, text, consumed = sec
                    cand = idx['section'].get(num, [])
                    if cand:
                        tgt = cand[0] if len(cand) == 1 else \
                            min(cand, key=lambda c: abs(c['page'] - (i + 1)))
                        links.append({'page': i + 1, 'page0': i,
                                      'rect': rect_list(rect),
                                      'text': text[:40], 'kind': 'Section',
                                      'num': num, 'target_page': tgt['page'],
                                      'target_y': tgt['y'],
                                      'target_text': tgt.get('text', ''),
                                      'how': 'unique' if len(cand) == 1 else 'nearest'})
                    else:
                        skip('Section', num, 'no-section', i, text)
                    j += consumed
                    continue
                j += 1
    return links, skipped

def rect_list(r):
    """fitz.Rect -> [x0,y0,x1,y1]，供 json 序列化。"""
    return [round(r.x0, 2), round(r.y0, 2), round(r.x1, 2), round(r.y1, 2)]


def zh_rect(page, line_text, y0, a, b):
    """按视觉行 y 与字符位置估算 [a,b) 的矩形。

    中文 OCR 的 search_for 对 NBSP/碎 span 很不可靠，rawdict 字符序列与
    聚行文本顺序也不一致。这里采用最稳的办法：取该视觉行 y 容差内的所有
    字符 span，按 x 排序，用"归一化字符在行内的比例"定位片段的起止 x。
    中文等宽近似成立，误差约 1~2 字，足够覆盖引用文字。
    """
    frag = re.sub(r'\s+', '', line_text[a:b])
    if not frag:
        return fitz.Rect(0, 0, 0, 0)
    chars = []
    for blk in page.get_text('rawdict')['blocks']:
        if blk['type'] != 0:
            continue
        for line in blk['lines']:
            for span in line['spans']:
                for c in span['chars']:
                    if abs(c['bbox'][1] - y0) <= 6.0 and c['c'].strip():
                        chars.append(c)
    if not chars:
        return fitz.Rect(0, 0, 0, 0)
    chars.sort(key=lambda c: c['bbox'][0])
    raw = re.sub(r'\s+', '', ''.join(c['c'] for c in chars))
    # 在行内找片段；找不到就用"从行首起第 a 个非空白字符"估算
    pos = raw.find(frag)
    if pos >= 0:
        i0, i1 = pos, pos + len(frag)
    else:
        prefix = len(re.sub(r'\s+', '', line_text[:a]))
        i0 = min(prefix, len(chars) - 1)
        i1 = min(i0 + len(frag), len(chars))
    sel = chars[i0:i1]
    if not sel:
        return fitz.Rect(0, 0, 0, 0)
    r = fitz.Rect(min(c['bbox'][0] for c in sel), min(c['bbox'][1] for c in sel),
                  max(c['bbox'][2] for c in sel), max(c['bbox'][3] for c in sel))
    return r if (r.x1 > r.x0 and r.y1 > r.y0) else fitz.Rect(0, 0, 0, 0)

def build_index(targets):
    """建索引：结果 (kind,num[,suffix]) / 节号 / 习题号 / 章号 -> 目标列表。"""
    idx = {'result': collections.defaultdict(list), 'section': collections.defaultdict(list),
           'exercise': collections.defaultdict(list), 'chapter': collections.defaultdict(list)}
    for r in targets['results']:
        key = (r['kind'], r['num'])
        idx['result'][key].append(r)
        if r['suffix'].startswith("'"):
            idx['result'][(r['kind'], r['num'], "'")].append(r)
    for s in targets['sections']:
        idx['section'][s['num']].append(s)
    for e in targets['exercises']:
        idx['exercise'][e['num']].append(e)
    for c in targets['chapters']:
        idx['chapter'][c['num']].append(c)
    return idx


def make_resolver(targets, idx, args):
    """返回 resolve(kind, num, page, y, context) -> (target, how)。"""
    sec_sorted = sorted((s['page'], s['y'], s['num']) for s in targets['sections'])

    def cur_section(pg, y):
        best = None
        for p, yy, s in sec_sorted:
            if p > pg or (p == pg and yy > y + 1):
                break
            best = s
        return best

    def resolve(kind, num, pg, y, context='', suffix=''):
        if kind == 'Exercise':
            cand = idx['exercise'].get(num, [])
            if not cand:
                return None, 'no-exercise'
            # 习题取第一个（编号全书唯一）
            return cand[0], 'unique'
        if kind == 'Chapter':
            cand = idx['chapter'].get(num, [])
            if not cand:
                return None, 'no-chapter'
            return cand[0], 'unique'
        if kind in ('Section', 'SectionRef'):
            # 裸 N.N：优先节号；上下文带 ex/exercise 时优先习题
            ex = bool(re.search(r'\bex\b\.?|exercise', context, re.I))
            if ex:
                cand = idx['exercise'].get(num, [])
                if len(cand) == 1:
                    return cand[0], 'exercise-in-context'
            cand = list(idx['section'].get(num, []))
            if not cand:
                cand2 = idx['exercise'].get(num, [])
                if len(cand2) == 1:
                    return cand2[0], 'exercise-fallback'
                return None, 'no-section'
            if len(cand) == 1:
                return cand[0], 'unique'
            # 多个同名节标题：取离引用页最近且在引用页之前的那一个
            before = [c for c in cand if (c['page'], c['y']) <= (pg, y)]
            pool = before or cand
            best = min(pool, key=lambda c: abs(c['page'] - pg))
            if abs(best['page'] - pg) <= 1:
                return best, 'nearest-section'
            return None, 'ambiguous-section(%d)' % len(cand)

        # 结果类
        key = (kind, num, suffix) if suffix else (kind, num)
        cand = idx['result'].get(key, [])
        if not cand and suffix:
            cand = idx['result'].get((kind, num), [])
        if not cand:
            return None, 'no-heading'
        if len(cand) == 1:
            return cand[0], 'unique'
        # 按节消歧（节内重编）
        sec = cur_section(pg, y)
        same = [c for c in cand if cur_section(c['page'], c['y']) == sec]
        if len(same) == 1:
            return same[0], 'same-section'
        # Corollary "to prop. M"：找紧跟 prop M 之后的那个 cor num
        m = re.search(r'\b(?:prop|proposition)\.?\s*([0-9IlO]{1,3})', context, re.I)
        if m and kind == 'Corollary':
            try:
                pm = ocr_num(m.group(1))
            except ValueError:
                pm = None
            if pm is not None:
                props = sorted([r for r in targets['results']
                                if r['kind'] == 'Proposition' and r['num'] == pm],
                               key=lambda r: (r['page'], r['y']))
                if len(props) == 1:
                    pp = props[0]
                    after = [c for c in cand
                             if (c['page'], c['y']) > (pp['page'], pp['y'])]
                    if after:
                        return after[0], 'to-prop-%d' % pm
        return None, 'ambiguous(%d)' % len(cand)

    return resolve


def find_mentions(doc, targets, idx, args):
    """发现正文里的交叉引用，返回 (links, skipped)。"""
    resolve = make_resolver(targets, idx, args)
    excluded = parse_pages(args.skip_pages)
    n = doc.page_count
    # 目标标题行的 y，用于跳过标题自身
    head_rows = collections.defaultdict(set)
    for kind_key in ('results', 'sections', 'exercises', 'chapters'):
        for r in targets[kind_key]:
            head_rows[r['page']].add(r['y'])
    # 类型词（可为缩写）+ 可选数字；句点可选
    kind_pat = '|'.join(sorted(KIND_ALIAS, key=len, reverse=True))
    word_re = re.compile(r'^(%s)\.?(?:[,\s]*)$' % kind_pat, re.I)
    glued_re = re.compile(r'^(%s)\.?([0-9IlO|SB]{1,4})$' % kind_pat, re.I)
    secnum_re = re.compile(r'^[0-9IlO]{1,2}\.[0-9IlO]{1,2}$')
    links, skipped = [], []
    def skip(kind, num, how, page0, text):
        skipped.append({'kind': kind, 'num': num, 'how': how,
                        'page': page0 + 1, 'text': text[:60]})

    for i in range(n):
        if i in excluded:
            continue
        ys = head_rows.get(i + 1, set())
        for y, ws in word_lines(doc[i]):
            if any(abs(y - hy) < 3.0 for hy in ys) and ws[0][0] < args.x0_max:
                continue                                      # 标题行自身
            j = 0
            while j < len(ws):
                raw = ws[j][4].strip().rstrip('.:,;')
                if raw.lower() in NOT_MENTION:
                    j += 1
                    continue
                kind = KIND_ALIAS.get(raw.lower())
                tok = raw
                tail = None
                suffix = ''
                if not kind:
                    m = glued_re.match(ws[j][4].strip())
                    if m:
                        kind = KIND_ALIAS[m.group(1).lower()]
                        tok = m.group(2)
                        tail = ws[j]
                elif j + 1 < len(ws):
                    nxt = ws[j + 1][4].strip().rstrip('.,;:)]')
                    if re.fullmatch(r'[0-9IlO|SB]{1,4}', nxt):
                        tok = nxt
                        tail = ws[j + 1]
                if kind and (tail is not None or kind == 'Exercise'):
                    context = ' '.join(w[4] for w in ws[max(0, j - 6):min(len(ws), j + 7)])
                    # 习题号形态一："ex. 14.4" —— 下一词本身就是 N.N
                    if kind == 'Exercise' and j + 1 < len(ws):
                        nxtword = ws[j + 1][4].strip().rstrip('.,;:)]')
                        if re.fullmatch(r'[0-9IlO]{1,2}\.[0-9IlO]{1,2}', nxtword):
                            exnum = nxtword.translate(OCR_DIGITS)
                            tgt, how = resolve('Exercise', exnum, i, y, context)
                            rect = fitz.Rect(ws[j][0], ws[j][1], ws[j + 1][2], ws[j + 1][3])
                            text = '%s %s' % (ws[j][4], ws[j + 1][4])
                            if tgt:
                                links.append(make_link(i, rect, text, tgt, how, kind, exnum))
                            else:
                                skip(kind, exnum, how, i, text)
                            j += 2
                            continue
                    if tail is None:      # 形态一未命中且无后续数字
                        j += 1
                        continue
                    try:
                        number = ocr_num(tok)
                    except ValueError:
                        j += 1
                        continue
                    # 薄撇变体：Theorem 23' / Theorem 23"
                    after = ws[j + 1][4] if tail is not ws[j] and j + 2 < len(ws) else ''
                    # 习题号形态二："ex. 14 . 4" —— 三个词拼成 N.N
                    if kind == 'Exercise' and j + 2 < len(ws):
                        nxt2 = ws[j + 2][4].strip().rstrip('.,;:)]')
                        if re.fullmatch(r'[0-9IlO]{1,2}', nxt2):
                            try:
                                exnum = '%d.%d' % (number, ocr_num(nxt2))
                            except ValueError:
                                exnum = None
                            if exnum:
                                tgt, how = resolve('Exercise', exnum, i, y, context)
                                rect = fitz.Rect(ws[j][0], ws[j][1], ws[j + 2][2], ws[j + 2][3])
                                text = '%s %s.%s' % (ws[j][4], tok, nxt2)
                                if tgt:
                                    links.append(make_link(i, rect, text, tgt, how, kind, exnum))
                                else:
                                    skip(kind, exnum, how, i, text)
                                j += 3
                                continue
                    tgt, how = resolve(kind, number, i, y, context, suffix)
                    rect = fitz.Rect(ws[j][0], ws[j][1], tail[2], tail[3])
                    text = '%s %s' % (ws[j][4], tail[4])
                    if tgt:
                        links.append(make_link(i, rect, text, tgt, how, kind, number))
                    else:
                        skip(kind, number, how, i, text)
                    j += 2
                    continue

                # 裸节号 N.N：排除页眉与表格数字
                if secnum_re.match(ws[j][4].strip().rstrip('.,;:)]')):
                    rawnum = ws[j][4].strip().rstrip('.,;:)]')
                    num = rawnum.translate(OCR_DIGITS)
                    if re.fullmatch(r'\d{1,2}\.\d{1,2}', num):
                        context = ' '.join(w[4] for w in ws[max(0, j - 5):j + 1])
                        tgt, how = resolve('Section', num, i, y, context)
                        rect = fitz.Rect(ws[j][0], ws[j][1], ws[j][2], ws[j][3])
                        if tgt:
                            links.append(make_link(i, rect, rawnum, tgt, how, 'Section', num))
                        else:
                            skip('Section', num, how, i, rawnum)
                j += 1
    return links, skipped


def make_link(page0, rect, text, target, how, kind, num):
    return {'page': page0 + 1, 'page0': page0,
            'rect': [round(rect.x0, 2), round(rect.y0, 2), round(rect.x1, 2), round(rect.y1, 2)],
            'text': text, 'kind': kind, 'num': num,
            'target_page': target['page'], 'target_y': target['y'],
            'target_text': target.get('text', ''), 'how': how}


def write_links(doc, links, args):
    for L in links:
        r = L['rect']
        doc[L['page0']].insert_link({
            'kind': fitz.LINK_GOTO,
            'from': fitz.Rect(r[0], r[1], r[2], r[3]),
            'page': L['target_page'] - 1,
            'to': fitz.Point(0, round(L['target_y'] - args.dy, 2)),
            'zoom': 0,
        })


def roman_to_int(s):
    """I/II/III/IV... -> 阿拉伯数字；失败返回 None。"""
    vals = {'I': 1, 'V': 5, 'X': 10, 'L': 50, 'C': 100, 'D': 500, 'M': 1000}
    total = prev = 0
    for ch in reversed(s.upper()):
        v = vals.get(ch)
        if v is None:
            return None
        total += -v if v < prev else v
        prev = max(prev, v)
    return total


def alnum_num_key(text):
    """从 '定理 G.II / 注 B.I / 例 4．2' 里取 (字母, 数字, 原文尾串) 供 audit 比对。"""
    m = re.search(r'([A-Za-z])\s*[.．∙•，,、:：;； ]*\s*([0-9]{1,3}|[IVXLCDM]{1,4})\b',
                  text or '')
    if not m:
        return None
    tail = m.group(2)
    return m.group(1).upper(), (int(tail) if tail.isdigit() else roman_to_int(tail)), tail


def alnum_key_eq(k1, k2):
    """字母+编号比对；兼容 OCR 把 '11' 读成罗马字形 'II' 的情况。"""
    if not k1 or not k2 or k1[0] != k2[0]:
        return False
    if k1[1] == k2[1]:
        return True
    for a, b in ((k1, k2), (k2, k1)):
        if a[2].isdigit() and b[2].upper() and set(b[2].upper()) == {'I'}:
            if a[2] == '1' * len(b[2]):
                return True
    return False


def audit_links(doc, links, args):
    """回读核验：目标页 / to.y / 落点下方标题文字。"""
    ok = 0
    bad = []
    for L in links:
        r = L['rect']
        # 同页可能有多条 from 矩形重合的链接（同一处引用被规则命中两次），
        # 必须在所有匹配者中找一条 page+to.y 都对得上的，不能只看第一条。
        got = [l for l in doc[L['page0']].get_links()
               if abs(l['from'].x0 - r[0]) < 0.8 and abs(l['from'].y0 - r[1]) < 0.8]
        want_y = round(L['target_y'] - args.dy, 2)
        hit = [l for l in got
               if l['page'] == L['target_page'] - 1
               and abs(l.get('to', fitz.Point(0, 0)).y - want_y) <= 0.8]
        if not hit:
            bad.append((L['page'], L['text'], 'link/target/coord'))
            continue
        # 目标文字校验（补充证据，不替代目视）
        pg = doc[L['target_page'] - 1]
        txt = pg.get_text('text', clip=fitz.Rect(0, L['target_y'] - 3,
                                                pg.rect.width, L['target_y'] + 18))
        flat = re.sub(r'\s+', ' ', txt.replace(NBSP, ' '))
        if getattr(args, 'lang', 'en') == 'zh':
            # 中文模式：目标是中文标题或右边缘公式号，OCR 字形不稳。
            # 只校验"编号数字串"是否出现，不要求整段标题吻合。
            key = re.sub(r'\s+', '', L['target_text'])
            digits = re.findall(r'\d+', key)
            ok_txt = bool(digits) and any(d in re.sub(r'\s+', '', flat) for d in digits)
            if not ok_txt:
                # 附录类编号是字母+罗马数字：目标 '注 B.I'，引用写 '注 B.1'。
                # zh_num 把 B→8 / G→6 后纯数字串对不上，这里按 (字母, 数字) 复核。
                k1 = alnum_num_key(L.get('raw_num') or L['text'])
                k2 = alnum_num_key(L['target_text'])
                ok_txt = alnum_key_eq(k1, k2)
            if not ok_txt:
                bad.append((L['page'], L['text'], 'target-text(zh): ' + flat[:30]))
                continue
        else:
            key = re.sub(r'\s+', ' ', L['target_text'])[:24]
            if key and key[:12] not in flat:
                bad.append((L['page'], L['text'], 'target-text: ' + flat[:30]))
                continue
        ok += 1
    return ok, bad


def cmd_scan(args):
    doc = fitz.open(args.pdf)
    t = scan_targets_zh(doc, args) if args.lang == 'zh' else scan_targets(doc, args)
    doc.close()
    json.dump(t, open(args.json, 'w'), ensure_ascii=False, indent=1)
    if args.lang == 'zh':
        print('节 %d / 习题 %d / 结果类 %d / 公式号定义点 %d'
              % (len(t['sections']), len(t['exercises']),
                 len(t['results']), len(t['equations'])))
    else:
        print('章 %d / 节 %d / 习题 %d / 结果类 %d'
              % (len(t['chapters']), len(t['sections']), len(t['exercises']), len(t['results'])))
    for k, v in t['scope'].items():
        print('  %-12s %3d 条 / %3d 唯一号 / 复用号 %2d -> %s'
              % (k, v['total'], v['unique'], v['reused_numbers'], v['verdict']))
    print('输出:', args.json)


def cmd_build(args):
    doc = fitz.open(args.pdf)
    if args.lang == 'zh':
        targets = scan_targets_zh(doc, args)
        idx = build_index_zh(targets)
        links, skipped = find_mentions_zh(doc, targets, idx, args)
        # 中文 OCR 的矩形定位可能失败，空矩形不能写成链接
        good = []
        for L in links:
            if L['rect'][2] > L['rect'][0] and L['rect'][3] > L['rect'][1]:
                good.append(L)
            else:
                skipped.append({'kind': L['kind'], 'num': L['num'],
                                'how': 'no-rect', 'page': L['page'],
                                'text': L['text'][:70]})
        links = good
    else:
        targets = scan_targets(doc, args)
        idx = build_index(targets)
        links, skipped = find_mentions(doc, targets, idx, args)
    print('发现引用 %d 条，跳过 %d 条'
          % (len(links), len(skipped)))
    c = collections.Counter((x['kind'], x['num'], x['how']) for x in skipped)
    for k, n in c.most_common(12):
        print('   跳过', k, n)
    print('落点 y = 标题行顶 − %.1f pt' % args.dy)
    report = {'pdf': args.pdf, 'dy': args.dy, 'skip_pages': args.skip_pages,
              'lang': args.lang,
              'links': [{k: v for k, v in L.items() if k != 'page0'} for L in links],
              'skipped': skipped}
    json.dump(report, open(args.report, 'w'), ensure_ascii=False, indent=1)
    doc.close()
    if args.dry_run:
        print('[dry-run] 报告:', args.report, '（未写副本）')
        return
    shutil.copyfile(args.pdf, args.out)
    out = fitz.open(args.out)
    write_links(out, links, args)
    out.saveIncr()
    out.close()
    print('已写副本:', args.out, '（原件未动）')


def cmd_audit(args):
    report = json.load(open(args.report))
    links = report['links']
    for L in links:
        L['page0'] = L['page'] - 1
    args.dy = report.get('dy', args.dy)
    args.lang = report.get('lang', getattr(args, 'lang', 'en'))
    doc = fitz.open(args.pdf)
    ok, bad = audit_links(doc, links, args)
    print('回读核验：%d 条，通过 %d，可疑 %d' % (len(links), ok, len(bad)))
    for b in bad[:15]:
        print('   可疑', b)
    if args.marks:
        marked = fitz.open(args.pdf)
        for L in links:
            r = L['rect']
            marked[L['page0']].draw_rect(fitz.Rect(r[0], r[1], r[2], r[3]),
                                         color=(1, 0, 0), width=0.6)
        marked.save(args.marks, garbage=3, deflate=True)
        marked.close()
        print('带框验证副本:', args.marks, '（红框仅可视化，不影响跳转）')
    doc.close()
    if bad:
        sys.exit(1)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest='cmd', required=True)

    def common(p):
        p.add_argument('--pdf', required=True, help='输入 PDF（原件）')
        p.add_argument('--lang', choices=['en', 'zh'], default='en',
                       help='识别语言；zh=中文劣质 OCR 模式（默认 en，行为不变）')
        p.add_argument('--skip-pages', default='', help='排除的 0-based 页，如 0-12,170-177')
        p.add_argument('--ymin', type=float, default=60.0, help='页眉剔除上界（距页顶 pt）')
        p.add_argument('--x0-min', type=float, default=54.0, help='标题左边距下界')
        p.add_argument('--x0-max', type=float, default=75.0, help='标题左边距上界')
        p.add_argument('--x0-min-zh', type=float, default=74.0, dest='x0_min_zh',
                       help='中文结果标题左边距下界（默认 74）')
        p.add_argument('--x0-max-zh', type=float, default=150.0, dest='x0_max_zh',
                       help='中文结果标题左边距上界（默认 150；"注" 类标题可到 x≈131）')
        p.add_argument('--sec-x0-max', type=float, default=100.0, dest='sec_x0_max',
                       help='中文节标题左边距上界（默认 100）')
        p.add_argument('--eq-xmin', type=float, default=180.0, dest='eq_xmin',
                       help='中文公式号定义点左边界（默认 180，实际多为 x≈441）')
        p.add_argument('--dy', type=float, default=2.0, help='落点 = 标题行顶 − dy')

    p = sub.add_parser('scan', help='清点目标标题')
    common(p)
    p.add_argument('--json', required=True, help='目标标题 JSON 输出')
    p.set_defaults(func=cmd_scan)

    p = sub.add_parser('build', help='发现引用并生成链接副本')
    common(p)
    p.add_argument('--out', help='链接副本输出路径')
    p.add_argument('--report', required=True, help='引用报告 JSON')
    p.add_argument('--dry-run', action='store_true', help='只出报告，不写副本')
    p.add_argument('--apply', action='store_true', help='写副本（与 --dry-run 互斥）')
    p.set_defaults(func=cmd_build)

    p = sub.add_parser('audit', help='回读核验链接')
    p.add_argument('--pdf', required=True, help='待核验的链接副本')
    p.add_argument('--report', required=True, help='build 产出的引用报告')
    p.add_argument('--dy', type=float, default=2.0)
    p.add_argument('--marks', help='另存带红框的验证副本')
    p.set_defaults(func=cmd_audit)

    args = ap.parse_args()
    if args.cmd == 'build' and not (args.dry_run or args.apply):
        ap.error('build 需要 --dry-run 或 --apply 之一')
    if args.cmd == 'build' and args.apply and not args.out:
        ap.error('--apply 需要 --out')
    args.func(args)


if __name__ == '__main__':
    main()
