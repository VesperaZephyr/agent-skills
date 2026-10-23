# -*- coding: utf-8 -*-
"""墨迹带定位：找出"有墨迹但文字层没有"的行带 —— 定位被正文层与 OCR 同时漏掉的标题.
   用法: python _lh_ink.py <page> [page...]
   渲染 4x 灰度, 逐行统计 x∈[25,150]pt 的暗像素; 连续暗行合并成带;
   与文字层行 bbox 比对, 打印未被覆盖的带。"""
import sys
import fitz

SRC = r"F:/大学/数字资源/数学/分析学/复分析/工科复变函数/复变函数与积分变换 第5版 (李红).pdf"
SC = 4
XL, XR = 25, 150          # pt: 标题所在左栏

d = fitz.open(SRC)
for arg in sys.argv[1:]:
    p = int(arg)
    pg = d[p - 1]
    pix = pg.get_pixmap(matrix=fitz.Matrix(SC, SC), colorspace=fitz.csGRAY)
    w, h, n = pix.width, pix.height, pix.n
    buf = pix.samples
    x0, x1 = int(XL * SC), min(int(XR * SC), w)
    counts = []
    for yy in range(h):
        base = yy * w * n
        c = 0
        for xx in range(x0, x1):
            if buf[base + xx * n] < 140:
                c += 1
        counts.append(c)
    bands = []
    y = 0
    while y < h:
        if counts[y] >= 3:
            y2 = y
            mx = 0
            while y2 + 1 < h and counts[y2 + 1] >= 2:
                y2 += 1
            mx = max(counts[y:y2 + 1])
            bands.append((y / SC, (y2 + 1) / SC, mx))
            y = y2 + 1
        else:
            y += 1
    lines = []
    for b in pg.get_text('dict')['blocks']:
        if b['type'] != 0:
            continue
        for l in b['lines']:
            t = ''.join(s['text'] for s in l['spans']).strip()
            if t:
                lines.append((l['bbox'][1] - 2, l['bbox'][3] + 2, t))
    print('===== p%d  (%d ink bands) =====' % (p, len(bands)))
    for a, b, mx in bands:
        cov = [t for lo, hi, t in lines if not (b < lo or a > hi)]
        if not cov:
            print('  UNCOVERED y=%6.1f..%6.1f h=%4.1f maxdark=%d' % (a, b, b - a, mx))
