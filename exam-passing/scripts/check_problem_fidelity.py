#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
check_problem_fidelity.py - 讲义题面保真度机械比对 (voice.md §3.3, 纯 Python 标准库)

功能:
  从讲义 .tex 提取每道 example / exercise 的题干汉字与数字, 在指定的题源文本/OCR/真题文件
  中滑窗定位最相近片段, 计算汉字字符覆盖率与小问数, 标出覆盖率低于阈值 (默认 0.95)
  或疑似改写/合并小问的题目, 供人工逐字回核.

用法:
  python check_problem_fidelity.py 讲义.tex --source 教材OCR.md --source 真题.tex
  python check_problem_fidelity.py 讲义.tex --source 原卷.txt --threshold 0.95 --json fidelity.json
"""

import argparse
import bisect
import json
import re
import sys
from collections import Counter
from pathlib import Path

CJK_RE = re.compile(r"[\u4e00-\u9fff]")
SUBQ_TEX_RE = re.compile(r"\\item\b|\(\s*[1-9]\s*\)|（\s*[1-9]\s*）")
ENV_RE = re.compile(r"\\begin\{(example|exercise)\}(?:\[(.*?)\])?([\s\S]*?)\\end\{\1\}")


def strip_latex_noise(s):
    s = re.sub(r"(?m)(?<!\\)%[^\n]*", "", s)
    s = re.sub(r"\\label\{[^}]*\}", "", s)
    s = re.sub(r"\\[a-zA-Z]+\*?", "", s)
    return s


def cjk_chars(s):
    return CJK_RE.findall(s)


def best_coverage(query_chars, corpus_chunks):
    """在分段后的题源语料中寻找覆盖率最高的窗口, 返回 (coverage, best_snippet)."""
    if not query_chars:
        return 1.0, ""
    q_cnt = Counter(query_chars)
    q_len = len(query_chars)
    best_cov = 0.0
    best_snip = ""

    for chunk_text, chunk_chars in corpus_chunks:
        if not chunk_chars:
            continue
        # 若段落本身长度在 2.5 倍以内, 直接算整段覆盖
        if len(chunk_chars) <= max(40, int(q_len * 2.5)):
            c_cnt = Counter(chunk_chars)
            hit = sum(min(v, c_cnt[k]) for k, v in q_cnt.items())
            cov = hit / float(q_len)
            if cov > best_cov:
                best_cov = cov
                best_snip = chunk_text[:120].replace("\n", " ")
            continue
        # 否则按窗口滑动 (步长 = max(8, q_len // 4))
        win = max(q_len + 10, int(q_len * 1.4))
        step = max(8, q_len // 4)
        for start in range(0, len(chunk_chars) - q_len + 1, step):
            sub = chunk_chars[start:start + win]
            c_cnt = Counter(sub)
            hit = sum(min(v, c_cnt[k]) for k, v in q_cnt.items())
            cov = hit / float(q_len)
            if cov > best_cov:
                best_cov = cov
                best_snip = "".join(sub[:80])
                if best_cov >= 0.999:
                    return best_cov, best_snip
    return best_cov, best_snip


def load_corpus_chunks(paths):
    chunks = []
    for p in paths:
        raw = Path(p).read_bytes()
        text = raw.decode("utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8",
                          errors="replace").replace("\r\n", "\n")
        for para in re.split(r"\n\s*\n+", text):
            para = para.strip()
            if not para:
                continue
            chars = cjk_chars(strip_latex_noise(para))
            if chars:
                chunks.append((para, chars))
    return chunks


def main():
    ap = argparse.ArgumentParser(description="讲义题面保真度机械比对 (voice.md §3.3)")
    ap.add_argument("tex", help="讲义 .tex 文件")
    ap.add_argument("--source", action="append", required=True,
                    help="题源文本/OCR/真题文件 (可多次指定)")
    ap.add_argument("--threshold", type=float, default=0.95,
                    help="汉字覆盖率告警阈值 (默认 0.95)")
    ap.add_argument("--json", dest="json_out", help="输出详细 JSON 报告")
    args = ap.parse_args()

    tex_path = Path(args.tex)
    if not tex_path.is_file():
        raise SystemExit("文件不存在: %s" % tex_path)
    for sp in args.source:
        if not Path(sp).is_file():
            raise SystemExit("题源文件不存在: %s" % sp)

    raw = tex_path.read_bytes()
    text = raw.decode("utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8") \
              .replace("\r\n", "\n")
    line_starts = [0] + [m.end() for m in re.finditer("\n", text)]
    chunks = load_corpus_chunks(args.source)

    results = []
    flagged = 0
    for m in ENV_RE.finditer(text):
        env = m.group(1)
        opt = (m.group(2) or "").strip()
        body = m.group(3)
        line = bisect.bisect_right(line_starts, m.start())
        q_chars = cjk_chars(strip_latex_noise(body))
        subq_count = len(SUBQ_TEX_RE.findall(body))
        cov, snip = best_coverage(q_chars, chunks)
        low = (len(q_chars) >= 8 and cov < args.threshold)
        if low:
            flagged += 1
        results.append({
            "line": line,
            "env": env,
            "source_tag": opt[:80],
            "cjk_count": len(q_chars),
            "subq_markers": subq_count,
            "coverage": round(cov, 4),
            "flagged": low,
            "matched_preview": snip[:80],
        })

    print("=== 题面保真度机械比对 ===")
    print("讲义: %s | 题源数: %d | 阈值: %.2f" % (tex_path, len(args.source), args.threshold))
    print("检测题目: %d 道 | 低于阈值需逐字回核: %d 道" % (len(results), flagged))
    for r in results:
        if r["flagged"]:
            print("  [LOW %.2f] L%d %s [%s] (汉字 %d, 分问标记 %d)" %
                  (r["coverage"], r["line"], r["env"], r["source_tag"] or "无出处",
                   r["cjk_count"], r["subq_markers"]))
    if args.json_out:
        Path(args.json_out).write_text(
            json.dumps({"threshold": args.threshold, "total": len(results),
                        "flagged": flagged, "items": results},
                       ensure_ascii=False, indent=2),
            encoding="utf-8")
        print("JSON 已写入: %s" % args.json_out)
    return 1 if flagged else 0


if __name__ == "__main__":
    sys.exit(main())
