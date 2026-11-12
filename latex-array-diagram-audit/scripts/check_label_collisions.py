#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""字形—矢量段碰撞检测（description 白盒遮蔽豁免）。

对 PDF 矢量层做几何检查：每个文本 word 的 bbox 与绘图段（线段、矩形边、
曲线弦）求交（Liang-Barsky）。若相交段属于一个完全罩住该 word 的白色/
近白填充矩形（tikzcd description 样式的白底标签盒），记 MASKED；否则记
REAL。退出码 REAL>0 -> 1，可直接当验收闸门。

判定的是「字被杆压」，不是「图内容正确」；MASKED 计数备案供布局披露。
word 级 bbox 较粗，边缘擦碰可加 --margin 收紧（默认 0.5pt，word 四边内缩）。

用法：
  python check_label_collisions.py main.pdf --pages 469,471,505
  python check_label_collisions.py main.pdf --pages 500-520 --json out.json
  python check_label_collisions.py main.pdf --pages 471 --margin 1.0

依赖 PyMuPDF（import fitz）。页码 1 起，物理页。
"""
import argparse
import io
import json
import sys

WHITE = 0.97  # RGB 三通道均 >= 此值视为白底盒


def seg_rect_hit(p1, p2, r, margin=0.0):
    """Liang-Barsky：线段与（内缩 margin 后的）矩形是否相交。"""
    x0, y0, x1, y1 = r[0] + margin, r[1] + margin, r[2] - margin, r[3] - margin
    dx, dy = p2[0] - p1[0], p2[1] - p1[1]
    t0, t1 = 0.0, 1.0
    for p, q in ((-dx, p1[0] - x0), (dx, x1 - p1[0]),
                 (-dy, p1[1] - y0), (dy, y1 - p1[1])):
        if p == 0:
            if q < 0:
                return False
        else:
            t = q / p
            if p < 0:
                t0 = max(t0, t)
            else:
                t1 = min(t1, t)
            if t0 > t1:
                return False
    return True


def page_segments(page):
    """页绘图段列表 [(p1, p2, is_white_box_fill)]。"""
    segs = []
    try:
        drawings = page.get_drawings()
    except Exception:
        return segs
    for d in drawings:
        white = (d.get('fill') is not None
                 and all(c >= WHITE for c in d['fill']))
        for it in d['items']:
            if it[0] == 'l':
                segs.append((it[1], it[2], white))
            elif it[0] == 're':
                r = it[1]
                corners = [(r.x0, r.y0), (r.x1, r.y0),
                           (r.x1, r.y1), (r.x0, r.y1)]
                for k in range(4):
                    segs.append((corners[k], corners[(k + 1) % 4], white))
            elif it[0] == 'c':  # 贝塞尔取弦近似
                segs.append((it[1], it[4], white))
    return segs


def main():
    ap = argparse.ArgumentParser(description='glyph-vs-vector collision check')
    ap.add_argument('pdf')
    ap.add_argument('--pages', required=True, help='1-based, e.g. 469,471,500-520')
    ap.add_argument('--margin', type=float, default=0.5,
                    help='shrink word bbox by this many pt on each side')
    ap.add_argument('--json', dest='json_out', help='write full report as JSON')
    a = ap.parse_args()

    sys.stdout.reconfigure(encoding='utf-8')
    import fitz

    pages = []
    for part in a.pages.split(','):
        if '-' in part:
            lo, hi = (int(x) for x in part.split('-'))
            pages.extend(range(lo, hi + 1))
        else:
            pages.append(int(part))

    real, masked = [], []
    doc = fitz.open(a.pdf)
    for pno in pages:
        page = doc[pno - 1]
        segs = page_segments(page)
        boxes = [(s[0], s[1]) for s in segs if s[2]]
        for w in page.get_text('words'):
            r = (w[0], w[1], w[2], w[3])
            text = w[4].strip()
            if not text:
                continue
            hit_real = hit_masked = False
            for p1, p2, white in segs:
                if seg_rect_hit(p1, p2, r, a.margin):
                    if white and any(p1[0] <= r[0] and r[2] <= p2[0]
                                     and p1[1] <= r[1] and r[3] <= p2[1]
                                     for p1, p2 in boxes):
                        hit_masked = True
                    else:
                        hit_real = True
                        break
            rec = {'page': pno, 'word': text[:40],
                   'bbox': [round(v, 1) for v in r]}
            if hit_real:
                real.append(rec)
            elif hit_masked:
                masked.append(rec)
        print(f'p{pno}: real={sum(1 for x in real if x["page"] == pno)} '
              f'masked={sum(1 for x in masked if x["page"] == pno)}')

    for x in real:
        print(f"REAL  p{x['page']}  {x['word']!r}  bbox={x['bbox']}")
    print(f'\nREAL={len(real)}  MASKED={len(masked)}'
          f'  -> {"FAIL" if real else "PASS"}')

    if a.json_out:
        io.open(a.json_out, 'w', encoding='utf-8', newline='\n').write(
            json.dumps({'pdf': a.pdf, 'pages': pages, 'margin': a.margin,
                        'real': real, 'masked': masked},
                       ensure_ascii=False, indent=2))
    sys.exit(1 if real else 0)


if __name__ == '__main__':
    main()
