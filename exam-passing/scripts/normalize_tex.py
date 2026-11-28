#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
normalize_tex.py - 讲义 .tex 标点与编码后处理 (纯 Python 标准库)

功能:
  1. 在 \begin{document} 之后的正文文本中, 自动跳过 % 注释、数学环境
     ($...$, $$...$$, \[...\], \(...\), equation/align/gather/multline/flalign/tikzpicture)
     与敏感命令参数 (\label, \ref, \cref, \Cref, \eqref, \url, \href, \includegraphics, \verb),
     将中文全角标点归一化为半角英文标点 + 适当空格 (保留中文顿号「、」),
     并将中文双引号 “...” 转为 LaTeX 成对引号 ``...'' .
  2. 去除 UTF-8 BOM, 统一行尾为 CRLF (或 --eol lf).
  3. --in-place 模式写回前自动备份到 _backups/.

设计目的:
  让写作阶段专注数学/物理逻辑与流畅中文叙述, 把「半角标点」红线交给确定性脚本收口.

用法:
  python normalize_tex.py 讲义.tex                # 预览变更统计 (不写文件)
  python normalize_tex.py 讲义.tex --in-place     # 自动备份并就地写回
  python normalize_tex.py 讲义.tex -o out.tex     # 写入新文件
"""

import argparse
import re
import shutil
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

PROTECTED_ENVS = (
    "equation", "equation*", "align", "align*", "alignat", "alignat*",
    "gather", "gather*", "multline", "multline*", "flalign", "flalign*",
    "eqnarray", "eqnarray*", "tikzpicture", "verbatim", "lstlisting",
)
PROTECTED_CMDS = (
    "label", "ref", "cref", "Cref", "eqref", "pageref", "labelcref",
    "url", "href", "includegraphics", "texttt", "path",
)

# 全角标点 -> (替换串, 是否在后面补空格)
PUNCT_MAP = {
    "，": (",", True),
    "。": (".", True),
    "；": (";", True),
    "：": (":", True),
    "？": ("?", True),
    "！": ("!", True),
    "（": ("(", False),
    "）": (")", True),
    "“": ("``", False),
    "”": ("''", False),
    "‘": ("`", False),
    "’": ("'", False),
}

NO_SPACE_AFTER = set(" \t\r\n}]).,;:?!'\"`~")


def _skip_brace_group(text, pos):
    """从 pos 处的 '{' 跳到匹配的 '}' 之后; 若不是 '{' 则返回 pos."""
    n = len(text)
    if pos >= n or text[pos] != "{":
        return pos
    depth = 1
    i = pos + 1
    while i < n and depth > 0:
        if text[i] == "\\" and i + 1 < n:
            i += 2
            continue
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
        i += 1
    return i


def normalize_body(body):
    """只改写正文文本中的全角标点, 返回 (新正文, 替换计数 Counter)."""
    out = []
    counts = Counter()
    i = 0
    n = len(body)

    while i < n:
        c = body[i]

        # 1. 注释: 未转义的 % 直到行尾
        if c == "%":
            nl = body.find("\n", i)
            end = n if nl < 0 else nl + 1
            out.append(body[i:end])
            i = end
            continue

        # 2. 反斜杠命令与 \[...\], \(...\), \begin{protected}, \cmd{...}, \verb
        if c == "\\":
            if i + 1 < n and body[i + 1] in ("\\", "%", "$", "{", "}", "[", "]", "(", ")"):
                if body[i + 1] == "[":
                    end = body.find(r"\]", i + 2)
                    end = n if end < 0 else end + 2
                    out.append(body[i:end])
                    i = end
                    continue
                if body[i + 1] == "(":
                    end = body.find(r"\)", i + 2)
                    end = n if end < 0 else end + 2
                    out.append(body[i:end])
                    i = end
                    continue
                out.append(body[i:i + 2])
                i += 2
                continue

            m_env = re.match(r"\\begin\{([^}]+)\}", body[i:])
            if m_env and m_env.group(1) in PROTECTED_ENVS:
                env_name = m_env.group(1)
                end_tag = r"\end{" + env_name + "}"
                end = body.find(end_tag, i + m_env.end())
                end = n if end < 0 else end + len(end_tag)
                out.append(body[i:end])
                i = end
                continue

            if body.startswith(r"\verb", i) and i + 5 < n:
                delim = body[i + 5]
                if delim == "*" and i + 6 < n:
                    delim = body[i + 6]
                    end = body.find(delim, i + 7)
                else:
                    end = body.find(delim, i + 6)
                end = n if end < 0 else end + 1
                out.append(body[i:end])
                i = end
                continue

            m_cmd = re.match(r"\\([a-zA-Z]+)", body[i:])
            if m_cmd and m_cmd.group(1) in PROTECTED_CMDS:
                j = i + m_cmd.end()
                while j < n and body[j] in " \t":
                    j += 1
                if j < n and body[j] == "[":
                    sq = body.find("]", j)
                    j = n if sq < 0 else sq + 1
                j = _skip_brace_group(body, j)
                if m_cmd.group(1) == "href":
                    j = _skip_brace_group(body, j)
                out.append(body[i:j])
                i = j
                continue

            if m_cmd:
                out.append(m_cmd.group(0))
                i += m_cmd.end()
                continue

            out.append(c)
            i += 1
            continue

        # 3. 数学环境 $$...$$ 与 $...$
        if c == "$":
            if i + 1 < n and body[i + 1] == "$":
                end = body.find("$$", i + 2)
                end = n if end < 0 else end + 2
                out.append(body[i:end])
                i = end
                continue
            j = i + 1
            while j < n:
                if body[j] == "\\" and j + 1 < n:
                    j += 2
                    continue
                if body[j] == "$":
                    j += 1
                    break
                j += 1
            out.append(body[i:j])
            i = j
            continue

        # 4. 全角标点替换
        if c in PUNCT_MAP:
            repl, need_space = PUNCT_MAP[c]
            counts[c] += 1
            # 左括号前若紧贴非空白字符且不是行首/左括号, 补一个空格更美观 (不强行插)
            out.append(repl)
            if need_space and i + 1 < n:
                nxt = body[i + 1]
                if nxt not in NO_SPACE_AFTER and nxt not in PUNCT_MAP:
                    out.append(" ")
            i += 1
            continue

        out.append(c)
        i += 1

    return "".join(out), counts


def normalize_tex(text):
    idx = text.find(r"\begin{document}")
    if idx < 0:
        new_body, counts = normalize_body(text)
        return new_body, counts
    preamble = text[:idx]
    body = text[idx:]
    new_body, counts = normalize_body(body)
    return preamble + new_body, counts


def main():
    ap = argparse.ArgumentParser(description="讲义 .tex 标点半角化与编码归一化")
    ap.add_argument("tex", help="待处理的 .tex 文件")
    ap.add_argument("--in-place", action="store_true", help="自动备份并就地写回")
    ap.add_argument("-o", "--out", help="输出到指定路径")
    ap.add_argument("--eol", choices=("crlf", "lf"), default="crlf", help="目标行尾 (默认 crlf)")
    args = ap.parse_args()

    src = Path(args.tex)
    if not src.is_file():
        raise SystemExit("文件不存在: %s" % src)

    raw = src.read_bytes()
    had_bom = raw.startswith(b"\xef\xbb\xbf")
    text = raw.decode("utf-8-sig" if had_bom else "utf-8")
    text_lf = text.replace("\r\n", "\n").replace("\r", "\n")

    new_lf, counts = normalize_tex(text_lf)
    eol = "\r\n" if args.eol == "crlf" else "\n"
    new_bytes = new_lf.replace("\n", eol).encode("utf-8")
    changed = (new_bytes != raw)

    total_repl = sum(counts.values())
    print("=== LaTeX 标点与编码归一化 ===")
    print("文件: %s" % src)
    print("BOM: %s -> 无 BOM | 目标行尾: %s | 标点替换总计: %d" %
          ("有" if had_bom else "无", args.eol.upper(), total_repl))
    if counts:
        detail = ", ".join("%s->%s (%d)" % (k, PUNCT_MAP[k][0], v)
                           for k, v in counts.most_common())
        print("明细: %s" % detail)

    if not args.in_place and not args.out:
        print("预览模式 (未写回; 加 --in-place 就地写回或 -o 指定输出).")
        return 0

    if args.in_place:
        if not changed:
            print("无需修改, 文件已符合规范.")
            return 0
        bdir = src.resolve().parent / "_backups"
        bdir.mkdir(parents=True, exist_ok=True)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
        bak = bdir / ("%s_prenorm_%s.tex" % (src.stem, stamp))
        shutil.copy2(str(src), str(bak))
        src.write_bytes(new_bytes)
        print("已备份至: %s" % bak)
        print("已写回: %s (%d bytes)" % (src, len(new_bytes)))
    else:
        out = Path(args.out)
        out.parent.mkdir(parents=True, exist_ok=True)
        out.write_bytes(new_bytes)
        print("已写入: %s (%d bytes)" % (out, len(new_bytes)))
    return 0


if __name__ == "__main__":
    sys.exit(main())
