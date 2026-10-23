#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""List cross-references that are still bare text (not hyperlinks).

Masks, before searching:
  * whole ``\\hyperref[...]{...}`` commands, including their displayed text
    (brace-matched; masking only the prefix produces false positives);
  * inline math ``$...$`` and display math ``\\[...\\]`` (DOTALL);
  * ``equation`` environments, ``\\pdfbookmark[...]``, ``\\newcommand{...}[n]``.

Reported kinds:
  STMT   - ``Theorem 3`` / ``Lemma 1`` ...
  PAREN  - ``(4)`` standalone (candidate equation/item reference)
  FORM   - ``formula (4)`` / ``equation (4)``
  BIB    - ``[3]`` (candidate bibliography citation)
  EXERC  - ``exercise 8`` / ``Exercise 3``

Usage:
    python audit_bare_xrefs.py [paths ...] [--types Theorem,Proposition,...]
    # default paths: chapters/*.tex back/*.tex
"""
import argparse
import glob
import os
import re

BS = chr(92)
S = chr(167)
DEFAULT_TYPES = ('Theorem', 'Proposition', 'Corollary', 'Lemma',
                 'Definition', 'Example', 'Remark', 'Conjecture')


def mask_hyperref(s):
    out = list(s)
    i = 0
    pat = BS + 'hyperref['
    while True:
        p = s.find(pat, i)
        if p < 0:
            break
        q = s.find(']', p)
        r = s.find('{', q)
        if r < 0:
            break
        depth = 0
        j = r
        while j < len(s):
            if s[j] == '{':
                depth += 1
            elif s[j] == '}':
                depth -= 1
                if depth == 0:
                    break
            j += 1
        for k in range(p, j + 1):
            out[k] = ' '
        i = j + 1
    return ''.join(out)


def mask_all(s):
    s = mask_hyperref(s)
    s = re.sub(r'\$[^$]*\$', lambda m: ' ' * len(m.group(0)), s)
    s = re.sub(re.escape(BS + '[') + r'.*?' + re.escape(BS + ']'),
               lambda m: ' ' * len(m.group(0)), s, flags=re.S)
    s = re.sub(re.escape(BS + 'begin{equation}') + r'.*?' +
               re.escape(BS + 'end{equation}'),
               lambda m: ' ' * len(m.group(0)), s, flags=re.S)
    # optional arguments of any control sequence: \pdfbookmark[0], \item[...]
    s = re.sub(r'\\[A-Za-z@]+\s*\[[^\]]*\]',
               lambda m: ' ' * len(m.group(0)), s)
    return s


def skip_line(line):
    st = line.lstrip()
    return (st.startswith('%') or st.startswith(BS + 'newcommand') or
            st.startswith(BS + 'pdfbookmark') or st.startswith(BS + 'item['))


def report(kind, rx, original, masked, counts):
    for m in rx.finditer(masked):
        ls = original.rfind('\n', 0, m.start()) + 1
        le = original.find('\n', m.start())
        line = original[ls:le].strip()
        if skip_line(line):
            continue
        counts[kind] = counts.get(kind, 0) + 1
        print('%-6s %s:%d  %-14s | %s' % (
            kind, os.path.basename(report.path),
            original[:m.start()].count('\n') + 1,
            m.group(0)[:14], line[:100]))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('paths', nargs='*')
    ap.add_argument('--types', default=','.join(DEFAULT_TYPES))
    a = ap.parse_args()

    files = a.paths or (sorted(glob.glob('chapters/*.tex')) +
                        sorted(glob.glob('back/*.tex')))
    if not files:
        raise SystemExit('no .tex files matched (pass paths explicitly)')

    types = '(' + '|'.join(x.strip() for x in a.types.split(',') if x.strip()) + ')'
    counts = {}
    for f in files:
        original = open(f, encoding='utf-8').read()
        masked = mask_all(original)
        report.path = f
        report('STMT', re.compile(r'\b' + types + r'\s+\d+\b'),
               original, masked, counts)
        report('FORM', re.compile(r'\b(formula|equation)\s*\(\d{1,2}\)'),
               original, masked, counts)
        report('PAREN', re.compile(r'(?<![A-Za-z0-9])\(\d{1,2}\)(?!\d)'),
               original, masked, counts)
        report('BIB', re.compile(r'\[\d\]'), original, masked, counts)
        report('EXERC', re.compile(r'exercise[s]?\s+\d+', re.I),
               original, masked, counts)

    print('---- counts ----')
    print(counts)


if __name__ == '__main__':
    main()
