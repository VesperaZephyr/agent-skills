#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
rebuild_exercise_labels.py — 安全重建习题 label (exercise:c.s.i)。

默认 dry-run：打印每个将插入的 label，不写文件。
--apply：先备份为 <file>.bak，再写入带 label 的副本。

算法（对应实战坑 A / 坑 B）：
1. 跟踪当前节：扫描 \\label{sec:(\\d+\\.\\d+)}，记录当前 c.s（避免解析 LaTeX 计数器）。
2. 识别习题块：
   - exercises 环境：\\begin{exercises} ... \\end{exercises}
   - 手工展开：前文含 "Exercises" 的 \\begin{enumerate}
     （含 \\noindent{...Exercises...} 形态）
3. 计数规则：块内深度 + 顺序计数，只给习题块自身的 enumerate 深度的 \\item 派发 label；
   嵌套 enumerate（子题 a/b/c）跳过。
4. 同行锚点：若 \\item 前同行已有 \\gtmtarget{ixNNN}，插入为
   \\gtmtarget{ixNNN}\\label{exercise:c.s.i}\\item（坑 A）。

注意：本脚本是"模板"，不同 cls 的习题环境名 / 章节编号格式可能不同，
使用前请先 dry-run 核对编号连续，再 --apply。
"""
import sys, re, os

EXERCISE_ENV = 'exercises'
SEC_LABEL = re.compile(r'\\label\{sec:(\d+\.\d+)\}')
ITEM_RE = re.compile(r'\\item\b')
GTM_RE = re.compile(r'(\\gtmtarget\{[^}]*\})\s*(\\item\b)')


def rebuild(text, apply=False):
    lines = text.split('\n')
    out = []
    cur_sec = None
    results = []          # (lineno, label)
    enum_depth = 0
    in_ex_env = False
    block_depth = None    # 习题块起始时的 enumerate 深度
    block_count = 0

    for i, line in enumerate(lines, 1):
        m = SEC_LABEL.search(line)
        if m:
            cur_sec = m.group(1)

        if re.search(r'\\begin\{' + re.escape(EXERCISE_ENV) + r'\}', line):
            in_ex_env = True
            block_depth = 0
            block_count = 0
        if re.search(r'\\end\{' + re.escape(EXERCISE_ENV) + r'\}', line):
            in_ex_env = False
            block_depth = None

        enum_depth += len(re.findall(r'\\begin\{enumerate\}', line))
        enum_depth -= len(re.findall(r'\\end\{enumerate\}', line))

        manual_block = bool(re.search(r'[Ee]xercises', line)) and \
            re.search(r'\\begin\{enumerate\}', line)

        if cur_sec is None:
            out.append(line)
            continue

        if (in_ex_env or manual_block) and ITEM_RE.search(line):
            if manual_block and block_depth is None:
                block_depth = enum_depth
            if in_ex_env or (manual_block and enum_depth == block_depth):
                block_count += 1
                label = f'exercise:{cur_sec}.{block_count}'
                results.append((i, label))
                if apply:
                    line = GTM_RE.sub(
                        lambda mm: f'{mm.group(1)}\\label{{{label}}}{mm.group(2)}', line)
                    if '\\gtmtarget{' not in line:
                        line = ITEM_RE.sub(lambda mm: f'{mm.group(0)}\\label{{{label}}}',
                                          line, count=1)
        out.append(line)

    return '\n'.join(out), results


def main():
    args = sys.argv[1:]
    if not args or args[0] in ('-h', '--help'):
        print(__doc__)
        return
    apply = '--apply' in args
    files = [a for a in args if not a.startswith('--')]
    for path in files:
        with open(path, 'r', encoding='utf-8', errors='replace') as f:
            text = f.read()
        new_text, results = rebuild(text, apply=apply)
        if apply:
            bak = path + '.bak'
            if not os.path.exists(bak):
                os.replace(path, bak)
            with open(path, 'w', encoding='utf-8', newline='') as f:
                f.write(new_text)
            print(f'[APPLIED] {path}: {len(results)} labels; backup -> {bak}')
        else:
            print(f'[DRY-RUN] {path}: {len(results)} labels would be inserted')
        for lineno, label in results:
            print(f'  {path}:{lineno}\t{label}')


if __name__ == '__main__':
    main()
