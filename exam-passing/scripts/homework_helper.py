#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
homework_helper.py - 作业辅助检索与脚手架生成工具

功能：
1. 根据章节号（如 1, 2, 3）或关键词检索课后习题内容。
2. 自动生成标准建模“五步法”答题骨架 LaTeX 文件或 Markdown 文件。
"""

import sys
import os
import re

TEXTBOOK_PATH = r"F:/LaTeXFiles/期末复习/数学建模/数学建模(祁永强).pdf_by_PaddleOCR-VL-1.6.md"

def search_exercise(chapter_num, problem_num=None):
    """从教材 Markdown 中定位指定章节的课后习题"""
    if not os.path.exists(TEXTBOOK_PATH):
        print(f"教材文件未找到: {TEXTBOOK_PATH}")
        return None
        
    with open(TEXTBOOK_PATH, 'r', encoding='utf-8') as f:
        text = f.read()
        
    # 定位 "习题 X" 并且后接数字序号题目的位置（避开目录）
    pattern = rf"习题\s*{chapter_num}\b[\s\S]*?(?=(?:第\s*{chapter_num+1}\s*章|习题\s*{chapter_num+1}\b|进阶篇|参考文献|$))"
    matches = list(re.finditer(pattern, text))
    if not matches:
        print(f"未匹配到第 {chapter_num} 章习题。")
        return None
        
    # 取最后的正文习题部分（跳过前言和目录处的片段）
    target_match = None
    for m in matches:
        snippet = m.group(0)
        # 如果包含 "1. " 或 "1." 说明是正文习题
        if re.search(r'\n\s*1[\.、\s]', snippet):
            target_match = snippet
            break
    if not target_match:
        target_match = matches[-1].group(0)
        
    if problem_num:
        # 寻找指定小题，形如 "1. " 或 "1、"
        prob_pattern = rf"(\n\s*{problem_num}[\.、\s][\s\S]*?)(?=(?:\n\s*{problem_num+1}[\.、\s]|\n\s*第|\n\s*习题|$))"
        prob_match = re.search(prob_pattern, target_match)
        if prob_match:
            return prob_match.group(1).strip()
        else:
            print(f"未找到第 {chapter_num} 章第 {problem_num} 题。")
            return target_match[:1500]
            
    return target_match.strip()

def generate_homework_scaffold(chapter, problem_ids, output_path):
    """生成平时作业的 LaTeX 解答应答脚手架"""
    header = r"""\documentclass[11pt,a4paper,UTF8]{ctexart}
\usepackage{geometry}
\geometry{left=2.5cm,right=2.5cm,top=2.5cm,bottom=2.5cm}
\usepackage{amsmath,amssymb,amsfonts,amsthm}
\usepackage{booktabs}
\usepackage{graphicx}
\usepackage{hyperref}
\usepackage{listings}
\usepackage{xcolor}

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

\title{\textbf{数学建模平时作业第 """ + str(chapter) + r""" 次}}
\author{姓名：\underline{\hspace{3cm}} \quad 学号：\underline{\hspace{3cm}}}
\date{\today}

\begin{document}
\maketitle

"""
    body = []
    for pid in problem_ids:
        prob_text = search_exercise(chapter, pid)
        if not prob_text:
            prob_text = f"（第 {chapter} 章第 {pid} 题题目内容待填入）"
        else:
            # 清理 OCR 带来的换行和页眉杂质
            prob_text = re.sub(r'\n\s*•\s*\d+\s*•[^\n]*', '', prob_text)
            
        block = f"""\\section*{{第 {pid} 题}}

\\begin{{tcolorbox}}[title=题目要求,colback=gray!5!white,colframe=gray!75!black]
{prob_text}
\\end{{tcolorbox}}

\\subsection*{{一、问题重述与背景分析}}
% 提炼题目核心意图、已知量与求解目标

\\subsection*{{二、模型假设与约定}}
\\begin{{enumerate}}
    \\item 假设...
    \\item 忽略...
\\end{{enumerate}}

\\subsection*{{三、符号说明}}
\\begin{{table}}[htbp]
\\centering
\\begin{{tabular}{ccc}
\\toprule
符号 & 物理意义 & 单位 / 取值范围 \\\\
\\midrule
$x$ & 决策变量 & $\\mathbb{{R}}$ \\\\
\\bottomrule
\\end{{tabular}}
\\end{{table}}

\\subsection*{{四、模型的建立与公式推导}}
% 机理分析、控制方程、目标函数与约束

\\subsection*{{五、模型求解与数值结果}}
% 给出解析解或编写 MATLAB/Python 求解代码与结果

\\subsection*{{六、结果分析与讨论}}
% 结论解释、灵敏度分析与合理性评价

\\vspace{{1cm}}
"""
        body.append(block)
        
    footer = r"\end{document}"
    
    full_content = header + "\n".join(body) + footer
    with open(output_path, 'w', encoding='utf-8', newline='\r\n') as f:
        f.write(full_content)
    print(f"成功生成作业解答脚手架: {output_path}")

def main():
    if len(sys.argv) < 3:
        print("用法:")
        print("  1. 检索题目: python homework_helper.py search <章节号> [题号]")
        print("  2. 生成作业脚手架: python homework_helper.py scaffold <章节号> <题号1,题号2,...> <输出文件.tex>")
        sys.exit(1)
        
    cmd = sys.argv[1]
    if cmd == 'search':
        ch = int(sys.argv[2])
        pid = int(sys.argv[3]) if len(sys.argv) > 3 else None
        res = search_exercise(ch, pid)
        print(res)
    elif cmd == 'scaffold':
        ch = int(sys.argv[2])
        pids = [int(x.strip()) for x in sys.argv[3].split(',')]
        out = sys.argv[4] if len(sys.argv) > 4 else f"homework_ch{ch}.tex"
        generate_homework_scaffold(ch, pids, out)

if __name__ == '__main__':
    main()
