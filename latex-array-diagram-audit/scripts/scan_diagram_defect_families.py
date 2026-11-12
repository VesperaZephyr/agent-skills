#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""tikzcd 方向反向缺陷族候选扫描器（清单器，非裁决器）。

转录代理的箭头方向错误呈三类系统性缺陷族，个案审阅提案之外应按族全文
扫描同款模式（手写笔记重排 ch15/ch16 沉淀：一轮按族修复 150+ 幅）：

  F1  \\ar[l] 族      横向左指箭头。挂列反向高危：手写稿主流向右，
                      \\ar[l] 极易因挂在右端单元格而整族反向。
  F2  无钩竖边族      \\ar[u]/\\ar[d]（含 uu/dd）既无 hook 也无 two heads/
                      equal/dashed。单态射竖边按现代惯例应向下带钩。
  F3  顶点射出族      同一行同时出现 \\ar[dl 与 \\ar[dr（或 ul+ur）：
                      自一个单元格向两侧放射。泛性质三角中顶点=余域时
                      数据箭头应射入顶点，此模式即反向嫌疑。

输出候选清单（默认 markdown 表，--json 可选）。只做盘点：\\ar[l] 在从右
向左的图、F3 在一分二分支图中完全合法，逐条仍须对照原稿裁定。

用法：
  python scan_diagram_defect_families.py chapters/ch16.tex
  python scan_diagram_defect_families.py ch.tex --lines 1872-3167 --json out.json
"""
import argparse
import io
import json
import re
import sys

F1 = re.compile(r'\\ar\[l{1,3}[\],]')
F2 = re.compile(r'\\ar\[((?:u|d){1,3})\b([^\]]*)\]')
F3A = re.compile(r'\\ar\[d[lu]\b')
F3B = re.compile(r'\\ar\[d[rl]\b')
F3C = re.compile(r'\\ar\[u[lu]\b')
F3D = re.compile(r'\\ar\[u[rl]\b')
KEEP_STYLES = ('hook', 'two heads', 'equal', 'dashed', 'dotted', 'phantom')


def main():
    ap = argparse.ArgumentParser(description='tikzcd defect-family candidate inventory')
    ap.add_argument('texfile')
    ap.add_argument('--lines', help='restrict to 1-based line range A-B')
    ap.add_argument('--json', dest='json_out', help='also write inventory as JSON')
    a = ap.parse_args()

    sys.stdout.reconfigure(encoding='utf-8')
    lo, hi = 1, 10 ** 9
    if a.lines:
        lo, hi = (int(x) for x in a.lines.split('-'))

    lines = io.open(a.texfile, encoding='utf-8').read().splitlines()
    env, hits = 0, {'F1': [], 'F2': [], 'F3': []}
    for idx, l in enumerate(lines, 1):
        if not (lo <= idx <= hi):
            continue
        if '\\begin{tikzcd}' in l:
            env += 1
        if env == 0:
            continue
        for m in F1.finditer(l):
            hits['F1'].append((idx, env, l.strip()))
        for m in F2.finditer(l):
            if not any(s in m.group(2) for s in KEEP_STYLES):
                hits['F2'].append((idx, env, m.group(0)))
        if (F3A.search(l) and F3B.search(l)) or (F3C.search(l) and F3D.search(l)):
            hits['F3'].append((idx, env, l.strip()))

    out = {'file': a.texfile, 'lines': a.lines, 'candidates': {}}
    for fam in ('F1', 'F2', 'F3'):
        out['candidates'][fam] = [
            {'line': i, 'env': e, 'snippet': s[:160]} for i, e, s in hits[fam]]
        print(f'\n## {fam}（{len(hits[fam])} 处候选）')
        for i, e, s in hits[fam][:200]:
            print(f'  L{i}  [图{e}]  {s.strip()[:120]}')
        if len(hits[fam]) > 200:
            print(f'  ... 其余 {len(hits[fam]) - 200} 条见 JSON')
    print('\n注：候选清单仅供逐条对照原稿裁定，不代表缺陷判定。')

    if a.json_out:
        io.open(a.json_out, 'w', encoding='utf-8', newline='\n').write(
            json.dumps(out, ensure_ascii=False, indent=2))
        print(f'json -> {a.json_out}')


if __name__ == '__main__':
    main()
