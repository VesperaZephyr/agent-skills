#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
homework_helper.py - 科目中立的作业辅助检索与脚手架生成工具

功能:
1. 以 --textbook <教材OCR.md> 指定任意课程的教材文本, 按章节号 / 题号检索课后习题.
   不指定教材时不检索, 由用户给出题面; 技能内不内置任何教材路径或题库.
2. 生成科目中立的作业解答骨架 LaTeX 文件:
   题目复述 / 前提与符号 / 逐步推导与证明 / 求解与计算 / 结果检验与讨论.

用法:
    python homework_helper.py --textbook <教材OCR.md> search <章节号> [题号]
    python homework_helper.py [--textbook <教材OCR.md>] scaffold <章节号> <题号1,题号2,...> <输出.tex> [--course <课程名>]
"""

import argparse
import os
import re
import sys


def latex_escape(text):
    """课程名等外部字符串写入 LaTeX 时做最小转义."""
    replacements = [
        ('\\', r'\textbackslash{}'), ('{', r'\{'), ('}', r'\}'),
        ('%', r'\%'), ('&', r'\&'), ('#', r'\#'),
        ('_', r'\_'), ('$', r'\$'), ('~', r'\textasciitilde{}'),
        ('^', r'\textasciicircum{}'),
    ]
    for old, new in replacements:
        text = text.replace(old, new)
    return text


def search_exercise(chapter_num, problem_num=None, textbook_path=None):
    """从指定教材的 Markdown / OCR 文本中定位指定章节的课后习题."""
    if not textbook_path:
        print('未指定教材 (--textbook). 请由用户给出题面; 本技能不内置任何教材文件.')
        return None
    if not os.path.exists(textbook_path):
        print(f'教材文件未找到: {textbook_path}')
        return None

    with open(textbook_path, 'r', encoding='utf-8') as f:
        text = f.read()

    # 定位 "习题 X" 并且后接数字序号题目的位置（避开目录）
    pattern = rf"习题\s*{chapter_num}\b[\s\S]*?(?=(?:第\s*{chapter_num+1}\s*章|习题\s*{chapter_num+1}\b|进阶篇|参考文献|$))"
    matches = list(re.finditer(pattern, text))
    if not matches:
        print(f'未匹配到第 {chapter_num} 章习题。')
        return None

    # 取正文习题部分（跳过前言和目录处的片段）
    target_match = None
    for m in matches:
        snippet = m.group(0)
        if re.search(r'\n\s*1[\.、\s]', snippet):
            target_match = snippet
            break
    if not target_match:
        target_match = matches[-1].group(0)

    if problem_num:
        prob_pattern = rf"(\n\s*{problem_num}[\.、\s][\s\S]*?)(?=(?:\n\s*{problem_num+1}[\.、\s]|\n\s*第|\n\s*习题|$))"
        prob_match = re.search(prob_pattern, target_match)
        if prob_match:
            return prob_match.group(1).strip()
        print(f'未找到第 {chapter_num} 章第 {problem_num} 题。')
        return target_match[:1500]

    return target_match.strip()


def generate_homework_scaffold(chapter, problem_ids, output_path,
                               course='[课程名]', textbook_path=None):
    """生成科目中立的作业解答 LaTeX 脚手架."""
    course_tex = latex_escape(course)
    header = r"""\documentclass[11pt,a4paper,UTF8]{ctexart}
\usepackage{geometry}
\geometry{left=2.5cm,right=2.5cm,top=2.5cm,bottom=2.5cm}
\usepackage{amsmath,amssymb,amsfonts,amsthm}
\usepackage{booktabs}
\usepackage{graphicx}
\usepackage{hyperref}
\usepackage{listings}
\usepackage{xcolor}
\usepackage{tcolorbox}
\usepackage{enumitem}

\hypersetup{
    colorlinks=true,
    linkcolor=blue,
    citecolor=blue,
    urlcolor=blue
}

\lstset{
    basicstyle=\small\ttfamily,
    keywordstyle=\color{blue}\bfseries,
    commentstyle=\color{gray}\itshape,
    stringstyle=\color{red},
    frame=single,
    breaklines=true,
    numbers=left,
    numberstyle=\tiny\color{gray}
}

% 科目中立骨架: 课程名由 --course 指定; 题面须逐题人工核对.
\title{\textbf{""" + course_tex + r""" 平时作业第 """ + str(chapter) + r""" 次}}
\author{姓名：\underline{\hspace{3cm}} \quad 学号：\underline{\hspace{3cm}}}
\date{\today}

\begin{document}
\maketitle

"""
    body = []
    for pid in problem_ids:
        prob_text = search_exercise(chapter, pid, textbook_path) if textbook_path else None
        if not prob_text:
            prob_text = f'（第 {chapter} 章第 {pid} 题题目内容待填入）'
        else:
            # 清理 OCR 带来的换行和页眉杂质
            prob_text = re.sub(r'\n\s*•\s*\d+\s*•[^\n]*', '', prob_text)

        block = f"""\\section*{{第 {pid} 题}}

\\begin{{tcolorbox}}[title=题目要求,colback=gray!5!white,colframe=gray!75!black]
{prob_text}
% OCR 题干须逐题人工核对后再编译
\\end{{tcolorbox}}

\\subsection*{{一、题目复述与已知条件}}
% 已知量, 求解目标, 所依附的定义与定理

\\subsection*{{二、前提与符号约定}}
% 适用条件, 边界与退化情形; 符号统一列在三线表中
\\begin{{table}}[htbp]
\\centering
\\begin{{tabular}}{{cclc}}
\\toprule
符号 & 含义 & 类型 & 单位 / 取值范围 \\\\
\\midrule
$x$ & 未知量 & 变量 & --- \\\\
$\\lambda$ & 待定系数 & 参数 & $\\mathbb{{R}}$ \\\\
\\bottomrule
\\end{{tabular}}
\\end{{table}}

\\subsection*{{三、逐步推导与证明}}
% 每一步写出依据, 定理带条件, 不跳步

\\subsection*{{四、求解与计算}}
% 完整解析推导; 课程确需数值计算时附代码与结果

\\subsection*{{五、结果检验与讨论}}
% 特例, 边界情形, 量纲或数值复核; 适用范围与失效情形

\\vspace{{1cm}}
"""
        body.append(block)

    footer = r"\end{document}"
    full_content = header + "\n".join(body) + footer
    with open(output_path, 'w', encoding='utf-8', newline='\r\n') as f:
        f.write(full_content)
    print(f'成功生成作业解答脚手架: {output_path}')


def main():
    parser = argparse.ArgumentParser(
        description='科目中立的作业题源检索与 LaTeX 脚手架生成工具')
    parser.add_argument('--textbook', default=None,
                        help='任意课程的教材 OCR / Markdown 文件路径; 不指定则不检索题源')
    sub = parser.add_subparsers(dest='command')

    p_search = sub.add_parser('search', help='按章节 / 题号检索课后习题')
    p_search.add_argument('chapter', type=int, help='章节号')
    p_search.add_argument('problem', type=int, nargs='?', help='题号 (可选)')
    p_search.add_argument('--textbook', dest='textbook_sub', default=None)

    p_scaffold = sub.add_parser('scaffold', help='生成科目中立的作业解答骨架')
    p_scaffold.add_argument('chapter', type=int, help='章节号')
    p_scaffold.add_argument('problems', help='题号列表, 逗号分隔, 如 1,2,3')
    p_scaffold.add_argument('output', nargs='?', help='输出 .tex 路径')
    p_scaffold.add_argument('--course', default='[课程名]', help='课程名, 写入标题')
    p_scaffold.add_argument('--textbook', dest='textbook_sub', default=None)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    textbook_path = getattr(args, 'textbook_sub', None) or args.textbook

    if args.command == 'search':
        res = search_exercise(args.chapter, args.problem, textbook_path)
        if res:
            print(res)
    elif args.command == 'scaffold':
        pids = [int(x.strip()) for x in args.problems.split(',') if x.strip()]
        out = args.output or f'homework_ch{args.chapter}.tex'
        generate_homework_scaffold(args.chapter, pids, out, args.course, textbook_path)


if __name__ == '__main__':
    main()
