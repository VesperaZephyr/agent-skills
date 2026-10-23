#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
audit_text_refs.py — 列出 LaTeX 源中尚未 \\ref 化的硬编码交叉引用。

不修改任何文件，仅作为每轮开工前的"待办清单"。

用法:
    python audit_text_refs.py chapters/ch01.tex
    python audit_text_refs.py chapters/ --ext .tex
    python audit_text_refs.py a.tex b.tex

输出:  file:line \t TYPE \t matched_text \t [suggest: label-prefix]

说明:
- 先剔除 \\ref{} \\eqref{} \\cite{} \\hyperref{} \\gtmref{} \\gtmtarget{} \\hyperlink{} 内容，
  避免把已经链接的引用再次报出。
- 检测规则覆盖：跨章/章内 条目引用 (Theorem/Lemma/...)、括号公式引用 (N.M)/(C.2)、
  Section / § 引用、跨章/章内 Exercise 引用。
- 本工具是"清单"不是"精确分类器"，少量误报（如正文里恰好出现的 (2.3)）属正常，
  最终以人工 + 编译验证为准。
"""
import sys, os, re, glob

# 章号：罗马数字 I..XII 或附录字母 A..C
ROMAN = (r'(?:X(?:I{1,3}|IV|V?I{0,3})|I{1,3}|IV|VI{0,3}|IX|V?I{0,3}'
         r'|I{1,3}|V{1,3}|VI{0,3}|VII{0,3}|VIII|IX|X{0,3})')
LETTER = r'[A-C]'
CHAPTER = r'(?:' + LETTER + r'|' + ROMAN + r')'

STMT = (r'(Theorem|Proposition|Lemma|Corollary|Definition|Example|'
        r'Remark|Claim|Exercise|Section)')

# 剔除已链接内容
def strip_linked(t):
    t = re.sub(r'\\(?:eq)?ref\{[^}]*\}', ' ', t)
    t = re.sub(r'\\cite(?:\[[^\]]*\])?\{[^}]*\}', ' ', t)
    t = re.sub(r'\\hyperref(?:\[[^\]]*\])?\{[^}]*\}', ' ', t)
    t = re.sub(r'\\gtmref\{[^}]*\}\{[^}]*\}', ' ', t)
    t = re.sub(r'\\gtmtarget\{[^}]*\}', ' ', t)
    t = re.sub(r'\\hyperlink\{[^}]*\}\{[^}]*\}', ' ', t)
    return t

RULES = [
    # 跨章 条目引用: Theorem II.3.1 / Lemma IV.3.2
    ('stmt-xchapter', re.compile(
        r'\b' + STMT + r'\s*~?\s*(' + CHAPTER + r')\s*\.\s*(\d+)\.(\d+)')),
    # 章内 条目引用: Theorem 2.3 / Lemma 1.4
    ('stmt-plain', re.compile(
        r'\b' + STMT + r'\s*~?\s*(\d+)\.(\d+)\b')),
    # 跨章 括号公式: (III.2.3) / \textup{(C.2)} / (A.1.9)
    ('eq-xchapter', re.compile(
        r'(?:\\textup\{)?\(\s*(' + CHAPTER + r')\.(\d+)(?:\.(\d+))?\s*\)\}?')),
    # 章内 括号公式: (2.3)
    ('eq-plain', re.compile(r'(?<!\\)\(\s*(\d+)\.(\d+)\s*\)')),
    # Section / § 引用: Section V.4 / § 4 / §II.3
    ('section', re.compile(r'\\?[S' + '\u00A7' + r']\s*~?\s*(' + CHAPTER +
                            r')\s*\.\s*(\d+)')),
    ('section-plain', re.compile(r'\\?[S' + '\u00A7' + r']\s*~?\s*(\d+)')),
]

SUGGEST = {
    'stmt-xchapter': 'kind:c.s.i',
    'stmt-plain': 'kind:s.i (按当前节补章号)',
    'eq-xchapter': 'eq:c.s.i',
    'eq-plain': 'eq:s.i (按当前节补章号)',
    'section': 'sec:c.s',
    'section-plain': 'sec:c.s',
}


def scan_file(path):
    out = []
    with open(path, 'r', encoding='utf-8', errors='replace') as f:
        for lineno, raw in enumerate(f, 1):
            line = strip_linked(raw)
            if line.lstrip().startswith('%'):
                continue
            for name, rx in RULES:
                for m in rx.finditer(line):
                    out.append((lineno, name, m.group(0).strip(), SUGGEST[name]))
    return out


def iter_inputs(items, ext):
    for it in items:
        if os.path.isdir(it):
            for p in sorted(glob.glob(os.path.join(it, '**', '*' + ext), recursive=True)):
                yield p
        else:
            yield it


def main():
    args = sys.argv[1:]
    if not args or args[0] in ('-h', '--help'):
        print(__doc__)
        return
    ext = '.tex'
    inputs = []
    for a in args:
        if a == '--ext' and args.index(a) + 1 < len(args):
            ext = args[args.index(a) + 1]
            continue
        inputs.append(a)
    total = 0
    for path in iter_inputs(inputs, ext):
        try:
            hits = scan_file(path)
        except Exception as e:  # noqa
            print(f'# ERROR {path}: {e}')
            continue
        for lineno, name, text, suggest in hits:
            total += 1
            print(f'{path}:{lineno}\t{name}\t{text}\t[{suggest}]')
    print(f'# total hard-coded refs found: {total}', file=sys.stderr)


if __name__ == '__main__':
    main()
