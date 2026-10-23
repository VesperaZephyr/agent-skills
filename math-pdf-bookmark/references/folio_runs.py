# -*- coding: utf-8 -*-
"""folio_probe.py —— 用"页眉/页脚带里的连续 folio 游程"反推 /PageLabels 分段。

动机：ROUTE H 的 --labels 原先只从**目录条目的印刷页码**推段，遇到
①目录里前置部分不印页码（Alpay 前 12 页无 folio，但 9–12 页印 vii…x）、
②纯扫描重排本没有出版商 /PageLabels（库里 ~75 本待补标签）
时就会漏掉罗马数字前置段 → 读者看到的页码 ≠ 书上的页码。

算法（比"众数 K"更准，因为 Lang 那种**断页**天然产生多段）：
  每页只取**页眉带 y1 ≤ 0.10H 或页脚带 y0 ≥ 0.90H** 里的短 token，
  分成"纯数字"和"纯罗马"两类；然后在物理页序列上找**最大游程**：
  连续 L 页各自有该类候选，且 value 逐页 +1。
  `startpage(0 基) = first_idx - first_value + 1`。
真 folio 天然满足这个递推（每页恰一个、逐页加一），而 `Part II`、章节号、
脚注号这类误抓的 token 会打断递推 → 不会形成 ≥3 页的游程。
"""
import re
import sys
from collections import Counter

import pymupdf

DIG_RE = re.compile(r"^[0-9]{1,4}$")
ROM_RE = re.compile(r"^[ivxlcdmIVXLCDM]{1,8}$")
ROM_V = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}


def rom2int(t):
    t = t.upper()
    v, prev = 0, 0
    for c in reversed(t):
        n = ROM_V[c]
        v += n if n >= prev else -n
        prev = max(prev, n)
    return v


def page_cands(pg, band=0.10):
    """-> {'D': Counter(value->text), 'r': Counter(...)}，只收带内且该值唯一的候选。"""
    H = pg.rect.height
    boxes = []
    for b in pg.get_text("dict")["blocks"]:
        for l in b.get("lines", []):
            for s in l["spans"]:
                y0, y1 = s["bbox"][1], s["bbox"][3]
                if not (y1 <= band * H or y0 >= (1 - band) * H):
                    continue
                t = s["text"].strip()
                if DIG_RE.match(t):
                    boxes.append(("D", int(t), t))
                elif ROM_RE.match(t) and len(t) <= 6:
                    boxes.append(("r", rom2int(t), t))
    out = {}
    for kind, v, t in boxes:
        out.setdefault(kind, Counter())[v] += 1
    # 同值多个 token（如页脚 '1' 和页眉 '1'）无妨；但一页出现两个不同数字 = 版式歧义，弃
    return {k: c for k, c in out.items() if len(c) == 1}


def runs(cands, kind, min_len=3):
    """cands: list of per-page dict。-> [(first_idx, first_value, length, uppercase?)]"""
    res, i, n = [], 0, len(cands)
    while i < n:
        c = cands[i].get(kind)
        if not c:
            i += 1
            continue
        v0 = next(iter(c))
        L, j = 1, i + 1
        while j < n:
            cc = cands[j].get(kind)
            if cc and v0 + L in cc:
                L += 1
                j += 1
            else:
                break
        if L >= min_len:
            res.append((i, v0, L))
        i = max(j, i + 1)
    return res


def style_of(doc, i0, v0, L, kind, band=0.10):
    """看游程里实际印的是大写还是小写罗马；数字段恒 'D'。"""
    if kind == "D":
        return "D"
    up = lo = 0
    for k in range(i0, i0 + L):
        for b in doc[k].get_text("dict")["blocks"]:
            for l in b.get("lines", []):
                for s in l["spans"]:
                    y0, y1 = s["bbox"][1], s["bbox"][3]
                    if not (y1 <= band * doc[k].rect.height
                            or y0 >= (1 - band) * doc[k].rect.height):
                        continue
                    t = s["text"].strip()
                    if ROM_RE.match(t) and len(t) <= 6 and rom2int(t) == v0 + (k - i0):
                        up += t.isupper()
                        lo += t.islower()
    return "R" if up > lo else "r"


def segments(path, min_len=3, report=False):
    doc = pymupdf.open(path)
    cands = [page_cands(doc[i]) for i in range(doc.page_count)]
    segs = []
    for kind in ("r", "D"):
        for (i0, v0, L) in runs(cands, kind, min_len):
            st = i0 - v0 + 1
            if st < 0:
                continue
            segs.append({"startpage": st, "style": style_of(doc, i0, v0, L, kind),
                         "firstpagenum": 1, "len": L, "kind": kind,
                         "probe": "p%d=%s" % (i0 + 1, v0)})
    doc.close()
    segs.sort(key=lambda s: (s["startpage"], 0 if s["kind"] == "r" else 1))
    keep, last = [], -1
    for s in segs:                       # 同起点/被前段覆盖的丢掉，保留最长
        if s["startpage"] > last:
            keep.append(s)
            last = s["startpage"]
    if report:
        print("   游程: %s" % [(s["probe"], s["len"], s["style"], s["startpage"])
                                for s in keep])
    return [{"startpage": s["startpage"], "style": s["style"],
             "firstpagenum": s["firstpagenum"]} for s in keep]


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    for path in sys.argv[1:]:
        d = pymupdf.open(path)
        print("== %s  (%d 页)" % (path.split("/")[-1][:58], d.page_count))
        seg = segments(path, report=True)
        print("   反推: %s" % seg)
        print("   出版商: %s" % [{"startpage": x["startpage"], "style": x.get("style", "-"),
                                  "firstpagenum": x["firstpagenum"]}
                                 for x in d.get_page_labels()])
        d.close()
