#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""修正劣质 OCR 扫描件的 invisible 文本层（不碰扫描图像）。

用途：交叉引用/搜索依赖文本层，但劣质 OCR 把编号写成 ``1.2．1``（全角点）、
``I.I.IO``（字母替身）、附录 ``B.I``（罗马数字）。本工具按人工/规则确认过的
清单，把错误编号的**字符级矩形**抹掉，在原位重写标准编号（render_mode=3，
视觉上完全不可见）。

铁律（2026-11-24《101 泛函分析》实测）：
  1. 扫描件文本层是 ``3 Tr``（invisible），图像才是肉眼所见；redact 必须
     ``images=fitz.PDF_REDACT_IMAGE_NONE``，否则底图被擦出白洞。
  2. 插入文本必须 ``render_mode=3``，否则页面出现可见错版字。
  3. 矩形取 ``get_text('rawdict')`` 的 **char bbox**，不是 span/行 bbox。
  4. 附录 B/C/D/E/F/G 的字母编号不可当 OCR 错误（B.I=B.1 不是 8.1）。
  5. 判不准不猜：吞点字符（L/上/刀/}）与正文引用均不写回，只写标题行。

命令：
  python fix_ocr.py apply --pdf book.pdf --candidates fix.json --out fixed.pdf
  python fix_ocr.py verify --pdf fixed.pdf --candidates fix.json
  python fix_ocr.py prepare --pdf book.pdf --out fix.json   # 仅打印候选框架，需人工确认
"""
import sys, re, json, argparse, collections
import pymupdf as fitz

FONT = 'china-s'   # PyMuPDF 内置 CJK 字体，写回时会嵌入；ASCII 编号也能正常显示


def char_rects(page, chars):
    """chars: [{c, bbox}] -> (fitz.Rect 合集, 起点, 平均字号)。"""
    rects = [fitz.Rect(c['bbox']) for c in chars]
    if not rects:
        return [], None, 0
    x0 = min(r.x0 for r in rects)
    y0 = min(r.y0 for r in rects)
    y1 = max(r.y1 for r in rects)
    height = y1 - y0
    return rects, fitz.Point(x0, y0), max(3.0, height * 0.92)


def apply(pdf, candidates, out, dry_run=False):
    by_page = collections.defaultdict(list)
    for c in candidates:
        by_page[c['page']].append(c)
    doc = fitz.open(pdf)
    # redaction 会删除与修正矩形相交的 /Link 注释（实测《101》p242 掉 1 条）。
    # 写回前备份全库链接，redact 后原样重建。
    saved_links = [[dict(l) for l in pg.get_links()] for pg in doc]
    changed = 0
    for pno, items in sorted(by_page.items()):
        pg = doc[pno - 1]
        redactions = []
        inserts = []
        for c in items:
            rects, start, size = char_rects(pg, c['chars'])
            if not start:
                continue
            replaced = c['fixed']
            # 起点 y 用基线：char bbox 的 y1 减一点，字号按原字符高度
            baseline = fitz.Point(start.x, rects[-1].y1 - size * 0.13)
            for r in rects:
                redactions.append((r, None))
            inserts.append((baseline, replaced, size))
        if dry_run:
            changed += len(inserts)
            continue
        for r, _ in redactions:
            pg.add_redact_annot(r)
        pg.apply_redactions(images=fitz.PDF_REDACT_IMAGE_NONE)
        for pt, text, size in inserts:
            pg.insert_text(pt, text, fontname=FONT, fontsize=size, render_mode=3)
        changed += len(inserts)
    if not dry_run:
        # 重建链接：只补当前页缺失的（按 from 矩形 + page + to 识别）
        for i, pg in enumerate(doc):
            have = [l['from'] for l in pg.get_links()]
            for l in saved_links[i]:
                if l['from'] in have:
                    continue
                nl = {k: v for k, v in l.items()
                      if k in ('kind', 'from', 'page', 'to', 'zoom', 'nameddest', 'uri')}
                try:
                    pg.insert_link(nl)
                except Exception:
                    pass
        doc.save(out, garbage=3, deflate=True)
    doc.close()
    return changed


def verify(pdf, candidates):
    """回读：每个候选页里应能搜到修正后的编号串。"""
    doc = fitz.open(pdf)
    bad = []
    for c in candidates:
        pg = doc[c['page'] - 1]
        txt = pg.get_text().replace('\xa0', ' ')
        # 直搜标准串；附录点号前后允许空白
        needle = c['fixed']
        if needle in txt or re.search(re.escape(needle).replace('\\.', r'\s*[.]\s*'), txt):
            continue
        bad.append((c['page'], c['raw'], c['fixed']))
    doc.close()
    return bad


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    sub = ap.add_subparsers(dest='cmd', required=True)
    p = sub.add_parser('apply')
    p.add_argument('--pdf', required=True)
    p.add_argument('--candidates', required=True)
    p.add_argument('--out', required=True)
    p.add_argument('--dry-run', action='store_true')
    p = sub.add_parser('verify')
    p.add_argument('--pdf', required=True)
    p.add_argument('--candidates', required=True)
    a = ap.parse_args()
    cands = json.load(open(a.candidates, encoding='utf-8'))
    if a.cmd == 'apply':
        n = apply(a.pdf, cands, a.out, a.dry_run)
        print('applied', n, 'of', len(cands), 'dry_run' if a.dry_run else '-> ' + a.out)
    else:
        bad = verify(a.pdf, cands)
        print('verify', len(cands) - len(bad), '/', len(cands), 'OK')
        for x in bad[:40]:
            print('  MISS', x)


if __name__ == '__main__':
    main()
