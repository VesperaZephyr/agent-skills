# -*- coding: utf-8 -*-
"""size_census.py — 一本 PDF 的"标题解剖学普查"：字号 → 层级，一次量清楚。

为什么每个 ROUTE P / P-CN / H 的书都要先跑它：层级判据（`MIN_SZ`）必须用**绝对字号下限**，
而绝对下限只能从这本书自己的字号分布里读出来（硬规则/SKILL：Terse 实测 L3 与正文同字号，
孙永生实测 章 21.88–23.12 / 节 15.27–15.69 / 习题 14.45–14.86 / 正文 9.9–12.4）。
**不要**用"比正文大 X pt"的相对判据——那会让最小一层整层消失。

    python size_census.py <pdf>                       # 普查：所有 sz>=--min-sz 的行 + 字号直方图
    python size_census.py <pdf> --pages 13,16,34      # 解剖：指定页的**全部**行（y/x/sz/文本）
    python size_census.py <pdf> --from 16 --min-sz 12 --out _xx_census.txt

读法（照这个顺序得出 `MIN_SZ`）：
  1) 直方图里**面积最大**的一档 = 正文 size `bs`（孙永生 9.9–12.4 那一坨）。
  2) 比 `bs` 大的档按"出现次数 + 是否居中(x 居中、y 在页上半)"分组：
     章 = 最大档、节 = 次大档、习题/附录 = 第三档。**每档取组内最小值再减 0.3 pt 余量**当下限。
  3) ⚠️ **大字号 ≠ 标题**。数学式里的花体/黑板字母会以较大字号单独成行——孙永生实测
     `16.92 pt` 有 26 行、`16.51 pt` 有 9 行，全是 `乥 max @的@） 一严 ）@月` 这种公式碎片，
     比节标题(15.69)还大。**必须**再用"行内含中文/拉丁单词 + 水平居中 + 只出现在章首页或页首"
     过滤，否则 `MIN_SZ` 定到公式字号上，整层标题被判没。
  4) ⚠️ 同一档里若混进**页眉 running head**（孙永生 p16 y=51.5 `第一章距离空间`、
     p240 y=51.6 `索引 225`）：页眉底 y1 实测 ≈65 ⇒ 判层级之前先按页眉带整条扔
     （`y1 <= 0.10*H or y0 >= 0.90*H`），别把页眉字号当成章字号。
  5) ⚠️ 大字号 span 的 **bbox 顶 ≠ 墨顶**（rule 7）：本工具只报 `y=bbox[1]`，落点请用
     `ink_audit.py`/`inkband.py` 实测墨带顶。
  6) ⚠️ 文字层可能把标题拆成上下标小 span（Terse：上标 y−2.1、下标 y+4.3）：本工具按
     **行**聚合并取 `max(size)`，所以上标不会污染直方图；但 `--pages` 模式看到的 y 是行的。

只读不写原文件。退出码 0 = 跑了；无输出 = 该书文字层为空（纯扫描件，先走 OCR）。
"""
import argparse
import collections
import io
import sys

import fitz

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass


def lines_of(pg):
    """该页的视觉行：[(y_top, x_left, max_size, text)]，跳过非文字块与空行。"""
    out = []
    for b in pg.get_text("dict")["blocks"]:
        if b.get("type") != 0:
            continue
        for ln in b["lines"]:
            txt = "".join(s["text"] for s in ln["spans"]).strip()
            if not txt:
                continue
            out.append((ln["bbox"][1], ln["bbox"][0],
                        max(s["size"] for s in ln["spans"]), txt))
    return out


def main():
    ap = argparse.ArgumentParser(add_help=True)
    ap.add_argument("pdf")
    ap.add_argument("--from", dest="frm", type=int, default=1,
                    help="普查起始物理页（1-based；正文起点，跳过目录/前置）")
    ap.add_argument("--to", dest="to", type=int, default=0)
    ap.add_argument("--min-sz", type=float, default=13.0)
    ap.add_argument("--pages", default="", help="解剖模式：逗号分隔的物理页")
    ap.add_argument("--hdr", type=float, default=0.10, help="页眉带高度比例（打印时标注）")
    ap.add_argument("--out", default="")
    a = ap.parse_args()

    d = fitz.open(a.pdf)
    L = ["pdf = %s   pages=%d" % (a.pdf, d.page_count)]
    hist = collections.Counter()
    rows = []
    if a.pages:
        for ps in a.pages.split(","):
            p = int(ps)
            L.append("===== p%d  rect=%s ====="
                     % (p, tuple(round(v, 1) for v in d[p - 1].rect)))
            for y, x, sz, txt in sorted(lines_of(d[p - 1])):
                L.append("y=%7.2f x=%6.2f sz=%5.2f  %r" % (y, x, sz, txt[:70]))
            L.append("")
    else:
        hi = a.to or d.page_count
        H = d[0].rect.height
        for p in range(a.frm, hi + 1):
            for y, x, sz, txt in sorted(lines_of(d[p - 1])):
                hist[round(sz, 2)] += 1
                if sz >= a.min_sz:
                    band = "HDR" if y <= a.hdr * H else ("FTR" if y >= (1 - a.hdr) * H else "  ")
                    rows.append("p=%-4d %s y=%7.2f x=%6.2f sz=%5.2f  %s"
                               % (p, band, y, x, sz, txt[:60]))
        L.append("")
        L.append("== 字号直方图（sz>=2 的所有行；最大档 = 正文）==")
        for sz, n in sorted(hist.items()):
            L.append("   %6.2f pt : %5d 行%s" % (sz, n, "   <-- BODY"
                                                 if n == max(hist.values()) else ""))
        L.append("")
        L.append("== sz >= %.1f 的行（候选标题；HDR/FTR = 页眉页脚带，必须扔）==" % a.min_sz)
        L += rows
    txt = "\n".join(L) + "\n"
    if a.out:
        io.open(a.out, "w", encoding="utf-8").write(txt)
        print("rows=%d -> %s" % (len(rows) if not a.pages else len(L), a.out))
    else:
        print(txt)
    d.close()


if __name__ == "__main__":
    main()
