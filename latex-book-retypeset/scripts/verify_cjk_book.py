#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Final whole-book verification for a re-typeset (LaTeX) book.

Checks the things that a compiler log alone will not tell you:

  1. `??` leftovers in the PDF text layer (unresolved \\ref / \\cite)
  2. PDF bookmarks (outline): total count + top-level entries
  3. back-filled cross references actually resolved to numbers
  4. bibliography page: entry count + a sanity string
  5. `Missing character` count in the build log (CJK font coverage)

Usage
-----
    python verify_cjk_book.py main.pdf
    python verify_cjk_book.py main.pdf --log main.log
    python verify_cjk_book.py main.pdf --check '定理\\s*6\\.3\\.2' --check '注\\s*6\\.3\\.1'
    python verify_cjk_book.py main.pdf --bib-page 551 --bib-needle 菲赫金戈尔兹

Exit code is 0 when every hard gate passes, 1 otherwise.
"""

import argparse
import re
import sys
from pathlib import Path


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('pdf', help='path to the built PDF')
    ap.add_argument('--log', help='xelatex log to scan for "Missing character"')
    ap.add_argument('--check', action='append', default=[], metavar='REGEX',
                    help='regex that must resolve to a numbered reference somewhere '
                         '(repeatable); used to verify back-filled \\ref targets')
    ap.add_argument('--bib-page', type=int, help='page number expected to hold the bibliography')
    ap.add_argument('--bib-needle', default=None,
                    help='a string that must appear on the bibliography page')
    args = ap.parse_args()

    try:
        import pymupdf
    except ImportError:
        raise SystemExit('pymupdf (fitz) is required: pip install pymupdf')

    doc = pymupdf.open(args.pdf)
    pages = [doc[i].get_text() for i in range(doc.page_count)]
    ok = True

    print('pages = %d' % doc.page_count)

    # 1) ?? leftovers
    qq = [i + 1 for i, t in enumerate(pages) if '??' in t]
    print('1) ?? leftover pages      : %s' % (qq if qq else 'none'))
    if qq:
        ok = False

    # 2) bookmarks
    toc = doc.get_toc()
    top = [e[1] for e in toc if e[0] == 1]
    print('2) bookmarks              : %d total, %d top-level' % (len(toc), len(top)))
    for name in top:
        print('     - %s' % name)
    if not toc:
        ok = False

    # 3) back-filled references
    if args.check:
        print('3) back-filled references :')
        for pat in args.check:
            hits = [i + 1 for i, t in enumerate(pages) if re.search(pat, t)]
            flag = 'OK' if hits else 'NOT FOUND'
            if not hits:
                ok = False
            print('     %-28s %s -> pages %s' % (pat, flag, hits[:8]))
    else:
        print('3) back-filled references : (skipped, pass --check)')

    # 4) bibliography page
    if args.bib_page:
        txt = pages[args.bib_page - 1]
        nums = re.findall(r'(?m)^\s*(\d+)\s*$', txt)
        needle_ok = (args.bib_needle in txt) if args.bib_needle else True
        print('4) bibliography p.%d      : %d numbered entries, needle %r present = %s'
              % (args.bib_page, len(nums), args.bib_needle, needle_ok))
        if not nums or not needle_ok:
            ok = False
    else:
        print('4) bibliography           : (skipped, pass --bib-page)')

    # 5) missing glyphs
    if args.log:
        log = Path(args.log).read_text(encoding='utf-8', errors='replace')
        miss = re.findall(r'Missing character[^\n]*', log)
        print('5) missing characters     : %d' % len(miss))
        for m in miss[:10]:
            print('     %s' % m.strip())
        if miss:
            ok = False
    else:
        print('5) missing characters     : (skipped, pass --log)')

    print('\nRESULT: %s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
