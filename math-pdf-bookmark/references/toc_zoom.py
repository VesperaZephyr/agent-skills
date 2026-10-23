# -*- coding: utf-8 -*-
"""toc_zoom.py — 把印刷目录页切成**高分辨率横带**，供人眼逐字转录（ROUTE P-CN/P-TXT 的第一步）。

为什么需要它：目录页的**文字层不可信**（孙永生实测：整行漏掉一个 `习 题`、`§2 Hilbert空间`
凭空插成 `§ 2 Hilbert 空间`、点线读成尾拖 `∙`、纸污读成 `积分算子庵`、简体 `赋` 读成繁体 `賦`），
而书签标题必须**逐字等于印刷目录**（硬规则 6/7）。所以条目表只能从**图**里抄，不能从层里抄。
切带的原因：整页 300 dpi 一次读图会漏行/串行，`bands=3` 时每带约 280 pt 高，行与 folio 一对一。

    python toc_zoom.py <pdf> <tag> 13-15                  # p13..p15，每页 3 带
    python toc_zoom.py <pdf> <tag> 13,14,15 --bands 4 --dpi 350
    python toc_zoom.py <pdf> <tag> 6-16 --x 40,556 --out ./zoom
    python toc_zoom.py <pdf> <tag> 12 --rows 30,300,560,861   # 手工带边界（pt）

输出：`<tag>_p<物理页>_<带号>.png`（**物理页**，1-based；转录时写下的 folio 才是印刷页码，
两者相差 `K`，K 由 `folio_runs.py` 的 +1 游程证明）。然后逐个 **Read 图片**抄条目。

注意：
  * 页号参数是**物理页**。先用 `--pages` 模式跑 `size_census.py` 或 `pdfium` 看前 20 页确认目录在哪。
  * 缩放矩阵用 `Z = dpi/72`；`clip` 用页面（CropBox）坐标，与 `get_text` 的 span bbox、
    与 `set_toc` 读回的 `to.y` **同一坐标系**（硬规则 9：不要再 `+shift`）。
  * 转录完的白名单要落成 `<tag>_toc.py`（`ENTRIES = [(lvl, folio, 显示标题), ...]`），
    它是 G0/条目差集的唯一权威，也是"这本书做完了"的定义之一。
"""
import argparse
import os
import sys

import fitz

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def parse_pages(spec):
    out = []
    for part in spec.split(","):
        if "-" in part:
            s, e = part.split("-")
            out += list(range(int(s), int(e) + 1))
        else:
            out.append(int(part))
    return out


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("pdf")
    ap.add_argument("tag")
    ap.add_argument("pages")
    ap.add_argument("--bands", type=int, default=3)
    ap.add_argument("--dpi", type=float, default=300.0)
    ap.add_argument("--x", default="", help="左/右版心，如 25,570（pt）")
    ap.add_argument("--rows", default="", help="带边界 y 列表，如 30,300,560,861（优先于 --bands）")
    ap.add_argument("--out", default=".")
    a = ap.parse_args()

    d = fitz.open(a.pdf)
    os.makedirs(a.out, exist_ok=True)
    Z = a.dpi / 72.0
    H = d[0].rect.height
    W = d[0].rect.width
    x0, x1 = (map(float, a.x.split(",")) if a.x else (0.0, W))
    if a.rows:
        edges = [float(v) for v in a.rows.split(",")]
        bands = list(zip(edges[:-1], edges[1:]))
    else:
        step = H / a.bands
        bands = [(max(0.0, i * step - 12.0), min(H, (i + 1) * step + 12.0))
                 for i in range(a.bands)]
    n = 0
    for p in parse_pages(a.pages):
        pg = d[p - 1]
        for i, (y0, y1) in enumerate(bands, 1):
            fn = os.path.join(a.out, "%s_p%d_%d.png" % (a.tag, p, i)).replace("\\", "/")
            pix = pg.get_pixmap(matrix=fitz.Matrix(Z, Z),
                                clip=fitz.Rect(x0, y0, x1, y1))
            pix.save(fn)
            print("%s  %dx%d  y=%.0f..%.0f" % (fn, pix.width, pix.height, y0, y1))
            n += 1
    print("tiles=%d  （逐张 Read 看图抄条目，别读文字层）" % n)
    d.close()


if __name__ == "__main__":
    main()
