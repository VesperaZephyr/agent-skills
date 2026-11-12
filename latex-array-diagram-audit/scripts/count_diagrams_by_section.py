#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""按节统计环境数量矩阵（图审分片用）。

千图级大章不可一次审：先产出「节 -> 行区间 -> tikzcd 数」矩阵，
按节边界切成 <=100 图的片再派审阅代理。只做统计，不证明图数正确
（计数含被注释掉的环境须人工排除）。

用法：
  python count_diagrams_by_section.py chapters/ch16.tex
  python count_diagrams_by_section.py chapters/ch16.tex --env tikzcd --json out.json
  python count_diagrams_by_section.py ch.tex --marker '\\\\notesec\\{([^}]*)\\}'

节标题匹配 \\notesec{...} / \\section{...} / \\subsection{...}（星号可选），
可用 --marker 追加自定义正则（须含一个捕获组作为标题）。
退出码恒为 0；--json 落盘结构化矩阵。
"""
import argparse
import io
import json
import re
import sys

BUILTIN_MARKERS = [
    r'\\notesec\{(?P<title>[^}]*)\}',
    r'\\section\*?\{(?P<title>[^}]*)\}',
    r'\\subsection\*?\{(?P<title>[^}]*)\}',
]


def main():
    ap = argparse.ArgumentParser(description='per-section environment count matrix')
    ap.add_argument('texfile')
    ap.add_argument('--env', default='tikzcd', help='environment name to count (default tikzcd)')
    ap.add_argument('--marker', action='append', default=[],
                    help='extra section-heading regex with one capture group')
    ap.add_argument('--json', dest='json_out', help='also write matrix as JSON')
    a = ap.parse_args()

    sys.stdout.reconfigure(encoding='utf-8')
    pats_head = [re.compile(p) for p in BUILTIN_MARKERS + list(a.marker)]
    pat_env = re.compile(r'\\begin\{' + re.escape(a.env) + r'\}')

    lines = io.open(a.texfile, encoding='utf-8').read().splitlines()
    secs = []  # (title, 1-based start line)
    for i, l in enumerate(lines):
        for pat in pats_head:
            m = pat.search(l)
            if m:
                secs.append((m.group(1) or '?', i + 1))
                break
    secs.append(('__END__', len(lines) + 1))

    rows, total = [], 0
    for k in range(len(secs) - 1):
        title, s = secs[k]
        e = secs[k + 1][1]
        n = sum(1 for l in lines[s - 1:e - 1] if pat_env.search(l))
        total += n
        rows.append({'section': title, 'start_line': s, 'end_line': e - 1, 'count': n})
    rows.append({'section': '__TOTAL__', 'start_line': 1,
                 'end_line': len(lines), 'count': total})

    print(f'{"section":<28} {"lines":<16} count')
    for r in rows:
        print(f'{r["section"]:<28.28} L{r["start_line"]}-L{r["end_line"]:<8} {r["count"]}')

    if a.json_out:
        io.open(a.json_out, 'w', encoding='utf-8', newline='\n').write(
            json.dumps({'file': a.texfile, 'env': a.env, 'rows': rows},
                       ensure_ascii=False, indent=2))
        print(f'json -> {a.json_out}')


if __name__ == '__main__':
    main()
