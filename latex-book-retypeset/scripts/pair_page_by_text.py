#!/usr/bin/env python
# -*- coding: utf-8 -*-
"""扫描页与重排页配对：扫描 PDF 没有文字层时，用逐页 OCR 文本对齐重排 PDF 的文本层。

思路：每页取字符 12-gram 集合（≥3 个数字的 shingle 单独加权），用加权重合度打分，
对每个重排页取最佳扫描页。只用于定位同一内容的页面，不证明内容正确。

用法：
  python pair_page_by_text.py --scan-ocr ocr.json --latex main.pdf -o pairs.json
  python pair_page_by_text.py --scan-ocr ocr.json --latex main.pdf --latex-range 200-230

ocr.json 兼容两种形态：
  1. [{ "markdown": { "text": "..." } }, ...]     PaddleOCR-VL 逐页结果
  2. ["第 1 页文本", "第 2 页文本", ...]
"""
import argparse, json, os, re, subprocess, sys

def scan_texts(path):
    if os.path.isdir(path):
        out = []
        for f in sorted(os.listdir(path)):
            if f.lower().endswith((".txt", ".md")):
                out.append(open(os.path.join(path, f), encoding="utf-8", errors="ignore").read())
        return out
    data = json.load(open(path, encoding="utf-8"))
    texts = []
    for item in data:
        if isinstance(item, str):
            texts.append(item)
        elif isinstance(item, dict):
            md = item.get("markdown") or {}
            texts.append(md.get("text") or item.get("text") or "")
    return texts

def latex_texts(pdf, pages):
    try:
        first = str(pages[0]); last = str(pages[-1])
        raw = subprocess.run(["pdftotext", "-f", first, "-l", last, "-layout", pdf, "-"],
                             capture_output=True, check=True).stdout.decode("utf-8", "ignore")
    except FileNotFoundError:
        sys.exit("pdftotext not found (install poppler)")
    out = [raw] if len(pages) == 1 else raw.split("\f")
    out = out[:len(pages)]
    while len(out) < len(pages):
        out.append("")
    return out

def norm(t):
    t = re.sub(r"\\[a-zA-Z]+", " ", t)
    t = re.sub(r"[^0-9\u4e00-\u9fffA-Za-z]+", "", t)
    return t.lower()

def shingles(t, n=12):
    s = {}
    for i in range(0, max(0, len(t) - n + 1)):
        g = t[i:i + n]
        w = 3 if sum(c.isdigit() for c in g) >= 3 else 1
        s[g] = s.get(g, 0) + w
    return s

def score(a, b):
    if not a or not b:
        return 0.0
    keys = set(a) & set(b)
    if not keys:
        return 0.0
    inter = sum(min(a[k], b[k]) for k in keys)
    return inter / (sum(a.values()) ** 0.5 * sum(b.values()) ** 0.5)

def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--scan-ocr", required=True)
    ap.add_argument("--latex", required=True, help="重排 PDF")
    ap.add_argument("--latex-range", default="", help="如 200-230；默认全书")
    ap.add_argument("-o", "--out", default="pairs.json")
    ap.add_argument("--min-score", type=float, default=0.02)
    a = ap.parse_args()

    scans = [shingles(norm(t)) for t in scan_texts(a.scan_ocr)]
    if a.latex_range:
        lo, hi = (int(x) for x in a.latex_range.split("-"))
        pages = list(range(lo, hi + 1))
    else:
        n = int(re.search(r"Pages:\s+(\d+)", subprocess.run(["pdfinfo", a.latex],
                capture_output=True).stdout.decode("utf-8", "ignore")).group(1))
        pages = list(range(1, n + 1))
    texts = latex_texts(a.latex, pages)

    pairs = {}
    raw = []
    for p, t in zip(pages, texts):
        sh = shingles(norm(t))
        row = {i + 1: score(sh, s) for i, s in enumerate(scans)}
        raw.append(row)

    # 1) 粗估：每页最佳扫描页，再用中位数抹掉离群点，得到平滑的「扫描页 ≈ 重排页 + 偏移」
    rough = []
    for row in raw:
        best = max(row, key=row.get) if row else 1
        rough.append(best)
    sm = 5
    est = []
    for i in range(len(rough)):
        w = rough[max(0, i - sm):i + sm + 1]
        est.append(sorted(w)[len(w) // 2])

    # 2) 单调对齐：在估计值 ±WIN 内做前缀最大值 DP，禁止扫描页倒退（同页可连续占用，原书一页拆成两页时合法）
    WIN = 12
    cand = []
    for i, row in enumerate(raw):
        lo = max(1, est[i] - WIN); hi = min(len(scans), est[i] + WIN)
        cand.append(list(range(lo, hi + 1)))
    dp, back = [], []
    for i, row in enumerate(raw):
        prev = dp[-1] if dp else None
        cur, bk = {}, {}
        best_j, best_v = None, -1e9
        for j in cand[i]:
            if prev is None:
                v, arg = row.get(j, 0.0), None
            else:
                # prev 只覆盖 i-1 的候选，取 j 以前的最优
                pass
            cur[j] = v
        if prev is None:
            dp.append(cur); back.append({j: None for j in cur}); continue
        ordered = sorted(prev.items())
        pref, parg = [], []
        acc, arg = -1e9, None
        for j, v in ordered:
            if v > acc:
                acc, arg = v, j
            pref.append((j, acc)); parg.append((j, arg))
        cur, bk = {}, {}
        ptr = 0
        for j in cand[i]:
            while ptr + 1 < len(pref) and pref[ptr + 1][0] <= j:
                ptr += 1
            if pref[ptr][0] > j:
                best_prev, argj = -1e9, None
            else:
                best_prev, argj = pref[ptr][1], parg[ptr][1]
            v = row.get(j, 0.0) + (best_prev if best_prev > -1e8 else 0.0)
            cur[j] = v; bk[j] = argj
        dp.append(cur); back.append(bk)

    # 回溯
    j = max(dp[-1], key=dp[-1].get)
    path = []
    for i in range(len(dp) - 1, -1, -1):
        path.append(j)
        j = back[i][j]
    path.reverse()

    for p, t, j in zip(pages, texts, path):
        sc = raw[pages.index(p)].get(j, 0.0)
        if sc >= a.min_score:
            pairs[str(p)] = {"scan_page": j, "score": round(sc, 3)}

    json.dump(pairs, open(a.out, "w", encoding="utf-8"), ensure_ascii=False, indent=1)
    print("paired", len(pairs), "of", len(pages), "pages ->", a.out)
    for k in list(pairs)[:8]:
        print("  latex p%s -> scan p%s  (%.3f)" % (k, pairs[k]["scan_page"], pairs[k]["score"]))

if __name__ == "__main__":
    main()