#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""从整页渲染图裁出"同一块内容"，并给出可写进 CSS 的高亮坐标。

用法：
  # 1) 裁切 + 打印墨迹行带表
  python make_compare_crops.py --image hi-latex-214.png \
      --box 0.045,0.045,0.965,0.492 --out assets/xu-latex-cor.png --width 2000

  # 2) 指定行带，输出可直接用的高亮矩形（百分比）
  python make_compare_crops.py --image assets/xu-latex-cor.png --bands-only --highlight 9

box 是整页图上的归一化框 x0,y0,x1,y1；行带编号按从上到下 0 起。
只做像素测量，不判断内容是否正确；选中哪一行、标什么颜色由人决定。
"""
import argparse, sys
from PIL import Image
Image.MAX_IMAGE_PIXELS = None   # 300dpi 大扫描件会超过默认 1.79 亿像素上限
import numpy as np

def bands(path, min_ink=3, merge=8):
    im = Image.open(path).convert("L")
    a = np.array(im)
    ink = a < 150
    rows = ink.sum(axis=1)
    segs, inb = [], False
    for y, v in enumerate(rows):
        if v > min_ink and not inb:
            s, inb = y, True
        elif v <= min_ink and inb:
            segs.append((s, y)); inb = False
    if inb: segs.append((s, len(rows)))
    merged = []
    for s, e in segs:
        if merged and s - merged[-1][1] < merge:
            merged[-1] = (merged[-1][0], e)
        else:
            merged.append((s, e))
    H, W = ink.shape
    out = []
    for s, e in merged:
        cols = ink[s:e].sum(axis=0)
        xs = np.where(cols > 0)[0]
        out.append({
            "y": (round(s / H, 4), round(e / H, 4)),
            "x": (round(float(xs.min()) / W, 4), round(float(xs.max()) / W, 4)),
            "px": (s, e),
        })
    return out, (W, H)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--image", required=True)
    ap.add_argument("--box", help="x0,y0,x1,y1（归一化）")
    ap.add_argument("--out", help="裁切输出 PNG")
    ap.add_argument("--width", type=int, default=2000, help="输出宽度上限（默认 2000）")
    ap.add_argument("--bands-only", action="store_true")
    ap.add_argument("--highlight", type=int, help="行带编号，输出高亮矩形")
    ap.add_argument("--pad", type=float, default=0.004, help="高亮与行带底部的间距（占高比）")
    a = ap.parse_args()

    if a.box and a.out:
        im = Image.open(a.image).convert("RGB")
        W, H = im.size
        x0, y0, x1, y1 = (float(v) for v in a.box.split(","))
        c = im.crop((int(W * x0), int(H * y0), int(W * x1), int(H * y1)))
        w = min(a.width, c.size[0])
        h = int(round(c.size[1] * w / c.size[0]))
        c.resize((w, h), Image.LANCZOS).save(a.out)
        print("crop %s from %dx%d -> %dx%d" % (a.out, W, H, w, h))

    bs, (W, H) = bands(a.image)
    print("bands of %s (%dx%d):" % (a.image, W, H))
    for i, b in enumerate(bs):
        print("  [%d] y %.3f-%.3f  x %.3f-%.3f  (px y %d-%d)" % (i, b["y"][0], b["y"][1], b["x"][0], b["x"][1], b["px"][0], b["px"][1]))
    if a.highlight is not None:
        if a.highlight >= len(bs):
            sys.exit("band %d out of range (%d bands)" % (a.highlight, len(bs)))
        b = bs[a.highlight]
        top = b["y"][1] + a.pad
        print("CSS: left:%0.1f%%; top:%0.1f%%; width:%0.1f%%" % (b["x"][0] * 100, top * 100, (b["x"][1] - b["x"][0]) * 100))

if __name__ == "__main__":
    main()
