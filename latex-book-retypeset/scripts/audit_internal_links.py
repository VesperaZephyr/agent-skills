#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Audit every internal link target in a LaTeX project.

Checks ``\\ref``, ``\\eqref``, ``\\pageref`` and ``\\hyperref[...]`` against the
labels actually written to ``main.aux``.  The ``\\newlabel`` parser uses brace
matching on purpose: enumerate-item labels such as ``{{(1)}}`` and
``\\phantomsection`` labels make a naive regex miss existing targets.

Usage:
    python audit_internal_links.py [--aux main.aux] [--root .] [--quiet]

Exit code 0 when every target resolves, 1 otherwise.
"""
import argparse
import os
import re
import sys

BS = chr(92)


def balanced(s, pos):
    """s[pos] == '{' -> (content, index just past the closing brace)."""
    assert s[pos] == '{', s[pos:pos + 1]
    depth = 0
    for i in range(pos, len(s)):
        if s[i] == '{':
            depth += 1
        elif s[i] == '}':
            depth -= 1
            if depth == 0:
                return s[pos + 1:i], i + 1
    return s[pos + 1:], len(s)


def read_labels(aux_path):
    aux = open(aux_path, encoding='utf-8', errors='replace').read()
    labels = {}
    i = 0
    needle = BS + 'newlabel'
    while True:
        j = aux.find(needle, i)
        if j < 0:
            break
        key, k = balanced(aux, j + len(needle))
        val, k = balanced(aux, k)
        labels[key] = val
        i = k
    return labels


def iter_tex(root):
    skip = {'work', 'bak', '_bak', 'backup', 'render', 'build', 'out',
            '.git', 'node_modules'}
    seen = set()
    for dirpath, dirnames, filenames in os.walk(root):
        dirnames[:] = [d for d in dirnames if d not in skip]
        for name in filenames:
            if not name.endswith('.tex'):
                continue
            ap = os.path.abspath(os.path.join(dirpath, name))
            if ap in seen:
                continue
            seen.add(ap)
            yield ap


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--aux', default='main.aux')
    ap.add_argument('--root', default='.')
    ap.add_argument('--quiet', action='store_true')
    a = ap.parse_args()

    if not os.path.exists(a.aux):
        sys.exit('aux not found: %s (compile first)' % a.aux)
    labels = read_labels(a.aux)

    pats = [(BS + 'ref{', 'ref'), (BS + 'eqref{', 'eqref'),
            (BS + 'pageref{', 'pageref'), (BS + 'hyperref[', 'hyperref')]
    problems = []
    total = 0
    for f in sorted(iter_tex(a.root)):
        txt = open(f, encoding='utf-8', errors='replace').read()
        for pat, kind in pats:
            pos = 0
            while True:
                p = txt.find(pat, pos)
                if p < 0:
                    break
                e = txt.find('}' if kind != 'hyperref' else ']', p)
                key = txt[p + len(pat):e]
                ln = txt[:p].count('\n') + 1
                total += 1
                if key not in labels:
                    problems.append((os.path.relpath(f, a.root), ln, kind, key))
                pos = e

    if not a.quiet:
        print('labels: %d' % len(labels))
        print('links checked: %d' % total)
    print('missing targets: %d' % len(problems))
    for x in problems:
        print('  %s:%d  %s  [%s]' % x)
    sys.exit(1 if problems else 0)


if __name__ == '__main__':
    main()
