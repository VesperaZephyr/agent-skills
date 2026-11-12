#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""全角 -> 半角标点统一（全书独立收编遍）。

手写稿/翻译稿标点全半角混用时，全书统一是合并后的独立一遍：先 --report
统计再 --apply 落盘（万行级 diff 要留档）。默认跳过 verbatim/lstlisting
环境与 % 注释（转录备注常有意保留全角；--punctuate-comments 连注释一起
替换）。显示式内标点本就该是 ASCII（全角逗号进数学模式会报 Missing
character），同表覆盖。

只替换字符，不改措辞、不补缺失标点（句末标点缺失走提案文件逐条裁决）。
写回保留原行尾（CRLF/LF）与 BOM 状态。

默认映射：，。，：；？！（）、「」『』"" '' 、 —— 其中顿号、与
弯引号可经 --map k=v 覆盖或 --no-map 排除。

用法：
  python unify_punct_halfwidth.py chapters/*.tex --report
  python unify_punct_halfwidth.py chapters/ch16.tex --apply --backup-dir work/bak
  python unify_punct_halfwidth.py ch.tex --apply --map '、=,'
"""
import argparse
import io
import os
import re
import shutil
import sys

DEFAULT_MAP = {
    '，': ',', '。': '.', '：': ':', '；': ';', '？': '?', '！': '!',
    '（': '(', '）': ')', '、': ',',
    '“': '"', '”': '"', '‘': "'", '’': "'",
    '「': '"', '」': '"', '『': '"', '』': '"',
}
SKIP_ENVS = ('verbatim', 'lstlisting', ' Verbatim')


def protected_spans(lines, punctuate_comments):
    """返回行号 -> 该行内受保护字符位置集合。"""
    prot = {}
    env_re = re.compile(r'\\begin\{(' + '|'.join(e.strip() for e in SKIP_ENVS)
                        + r')\}|\\end\{(' + '|'.join(e.strip() for e in SKIP_ENVS) + r')\}')
    in_env = False
    for i, l in enumerate(lines):
        s = set()
        m = env_re.search(l)
        if m:
            if m.group(0).startswith(r'\begin'):
                in_env = True
                s.update(range(m.start(), len(l)))
            else:
                s.update(range(0, m.end()))
                in_env = False
        elif in_env:
            s.update(range(len(l)))
        if not punctuate_comments:
            cm = re.search(r'(?<!\\)%', l)
            if cm:
                s.update(range(cm.start(), len(l)))
        if s:
            prot[i] = s
    return prot


def main():
    ap = argparse.ArgumentParser(description='fullwidth -> halfwidth punctuation')
    ap.add_argument('files', nargs='+')
    ap.add_argument('--map', action='append', default=[],
                    help='extra mapping k=v (single chars)')
    ap.add_argument('--no-map', action='append', default=[],
                    help='exclude a default mapping key')
    ap.add_argument('--punctuate-comments', action='store_true')
    ap.add_argument('--report', action='store_true')
    ap.add_argument('--apply', action='store_true')
    ap.add_argument('--backup-dir', help='copy originals here before apply')
    a = ap.parse_args()

    sys.stdout.reconfigure(encoding='utf-8')
    mapping = dict(DEFAULT_MAP)
    for kv in a.map:
        k, v = kv.split('=', 1)
        mapping[k] = v
    for k in a.no_map:
        mapping.pop(k, None)

    grand = {}
    for f in a.files:
        raw = io.open(f, encoding='utf-8', newline='').read()
        had_bom = raw.startswith('﻿')
        lines = raw.split('\n')
        prot = protected_spans(lines, a.punctuate_comments)
        counts, changed = {}, 0
        out = []
        for i, l in enumerate(lines):
            skip = prot.get(i, set())
            buf, hit = [], False
            for j, ch in enumerate(l):
                if j in skip or ch not in mapping:
                    buf.append(ch)
                    continue
                counts[ch] = counts.get(ch, 0) + 1
                buf.append(mapping[ch])
                hit = True
            changed += hit
            out.append(''.join(buf))
        new = '\n'.join(out)
        for k, v in sorted(counts.items()):
            grand[k] = grand.get(k, 0) + v
        status = 'REPORT' if a.report else ('APPLIED' if a.apply else 'DRY')
        print(f'{status}  {f}: lines_changed={changed} '
              f'chars={sum(counts.values())} {counts}')
        if a.apply and changed:
            if a.backup_dir:
                os.makedirs(a.backup_dir, exist_ok=True)
                dst = os.path.join(a.backup_dir, os.path.basename(f) + '.bak-punct')
                shutil.copy2(f, dst)
            enc = 'utf-8-sig' if had_bom else 'utf-8'
            io.open(f, 'w', encoding=enc, newline='').write(new)

    print('\n全书总计：')
    for k, v in sorted(grand.items(), key=lambda x: -x[1]):
        print(f'  {k!r} -> {mapping[k]!r} : {v}')
    if not (a.report or a.apply):
        print('\n（dry-run，未落盘；加 --report 只看统计，--apply 落盘）')


if __name__ == '__main__':
    main()
