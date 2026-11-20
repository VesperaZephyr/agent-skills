#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
audit_label_numbers.py — 核对「label 名中的编号」与「实际渲染编号」一致性。

用途：手工编号陈述/公式书里，label 名按原书编号命名（如 prop:IV.4.20）。
若正文漏排一条、跳号未实现或计数器漂移，渲染号（\\newlabel 的第一项）会与
label 名的尾号错位——例如漏排 Proposition 4.20 后 Definition 4.21 渲染成 4.20。
本核对器逐条比对，任何错位即 exit=1（交付前必跑；Iversen 项目实测抓出
IV.4 漏排整条 Proposition + 跳号未实现的双重缺陷）。

用法:
    python audit_label_numbers.py main.aux
    python audit_label_numbers.py main.aux --roman-as-is   # 章号罗马照比较
规则:
- name 形如 kind:C.S.I（章.节.条）或 kind:C.S 或 kind:S.I，取**点分段尾部的
  数字段**与渲染号分段比对：sec.item 两段全等（章号不进 \\theivitem，忽略）。
- 渲染号缺失段（如 sec 只印节号）按可比分段对齐比较。
- 纯非数字 label（chap:VI 等）跳过；bib:/page: 跳过。
"""
import io, re, sys, os

sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8', errors='replace')

def brace_balanced(s, i):
    """Parse one {...} group starting at s[i]=='{' with brace balancing.
    Returns (content_without_outer_braces, next_index) or (None, i)."""
    if i >= len(s) or s[i] != '{':
        return None, i
    depth, j = 0, i
    while j < len(s):
        c = s[j]
        if c == '\\':
            j += 2
            continue
        if c == '{':
            depth += 1
        elif c == '}':
            depth -= 1
            if depth == 0:
                return s[i+1:j], j+1
        j += 1
    return None, j

def parse_newlabels(aux):
    out = []
    for m in re.finditer(r'\\newlabel\{', aux):
        name, j = brace_balanced(aux, m.end()-1)
        if name is None:
            continue
        first, k = brace_balanced(aux, j)
        if first is None:
            continue
        # \newlabel{...}{{number}{page}[...]{anchor}...} — number 在双花括组内
        inner_num, _ = brace_balanced(first, 0)
        rendered = (inner_num or first).strip()
        out.append((name, rendered))
    return out

def num_parts(s):
    return [p for p in s.split('.') if p != '']

def numeric_tail(parts, k):
    """Last k numeric parts of the name (None if any part non-numeric)."""
    tail = parts[-k:] if len(parts) >= k else None
    if tail is None or any(not p.isdigit() for p in tail):
        return None
    return [int(p) for p in tail]

def main():
    aux_path = sys.argv[1] if len(sys.argv) > 1 else 'main.aux'
    aux = open(aux_path, encoding='utf-8', errors='replace').read()
    labels = parse_newlabels(aux)
    bad = []
    checked = 0
    for name, rendered in labels:
        if name.startswith(('bib:', 'page:', 'chap:')):
            continue
        rparts = num_parts(rendered)
        if not rparts or any(not p.isdigit() for p in rparts):
            continue  # 渲染号非纯数字（罗马章号等）跳过
        nparts = num_parts(name.replace('-', '.'))
        if not nparts:
            continue
        # 可比对齐：取 name 与 rendered 的公共尾段数
        k = min(len(nparts), len(rparts))
        ntail = numeric_tail(nparts, k)
        if ntail is None:
            continue  # 名内含非数字段（如 exer:R1）跳过
        rtail = [int(p) for p in rparts[-k:]]
        checked += 1
        if ntail != rtail:
            bad.append((name, rendered,
                        '.'.join(str(x) for x in ntail),
                        '.'.join(str(x) for x in rtail)))
    print(f'labels compared: {checked}, mismatches: {len(bad)}')
    for name, rendered, ntail, rtail in bad:
        print(f'  MISMATCH {name}: rendered "{rendered}" vs name implies "{ntail}"')
    if bad:
        sys.exit(1)

if __name__ == '__main__':
    main()
