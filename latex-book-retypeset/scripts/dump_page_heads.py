#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Page-head / folio verifier for a re-typeset (LaTeX) book with
per-chapter page codes (e.g. Serre, "Abelian l-Adic Representations").

It answers the question a compiler log cannot: does EVERY page carry the
running head and folio the original prints?  A `\\pagestyle{empty}` leak (set
in the title pages, never restored) silently strips the head/folio from every
*continuation* page while leaving the opening pages intact -- this script
catches exactly that.

What it reports, per page:
  * the top text band  (running head + folio)
  * the bottom text band (bare centered folio on opening pages)

With `--check-toc-links` it additionally asserts that every TOC page-number
hyperlink resolves to a real named destination (`page.<folio>`), i.e. the
"page numbers carry cross references" requirement.

Usage
-----
    python dump_page_heads.py main.pdf
    python dump_page_heads.py main.pdf --band 55            # band height in pt
    python dump_page_heads.py main.pdf --check-toc-links
    python dump_page_heads.py main.pdf --require-head 16-129   # pages that MUST have a head
    python dump_page_heads.py main.pdf --require-bare 15,34,59 # opening pages (headless)

Exit code 0 when every gate passes, 1 otherwise.
"""

import argparse
import sys


def band_words(page, band):
    """Return (top_words, bottom_words) sorted left-to-right, within `band` pt."""
    h = page.rect.height
    top = [w for w in page.get_text('words') if w[1] < band]
    bot = [w for w in page.get_text('words') if w[1] > h - band]
    key = lambda w: (round(w[1]), w[0])
    return sorted(top, key=key), sorted(bot, key=key)


def fmt(words):
    return ' '.join(w[4] for w in words)


def parse_ranges(spec):
    """'16-129,140' -> set of ints."""
    out = set()
    for part in spec.split(','):
        part = part.strip()
        if not part:
            continue
        if '-' in part:
            a, b = part.split('-', 1)
            out.update(range(int(a), int(b) + 1))
        else:
            out.add(int(part))
    return out


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('pdf', help='path to the built PDF')
    ap.add_argument('--band', type=float, default=55.0,
                    help='height (pt) of the top/bottom text bands to inspect (default 55)')
    ap.add_argument('--check-toc-links', action='store_true',
                    help='assert every TOC page-number hyperlink resolves (page.<folio> dests)')
    ap.add_argument('--require-head', metavar='PAGES',
                    help='pages that MUST carry a running head (ranges like 16-129,140)')
    ap.add_argument('--require-bare', metavar='PAGES',
                    help='opening pages that MUST be headless (ranges like 15,34,59)')
    args = ap.parse_args()

    try:
        import pymupdf
    except ImportError:
        raise SystemExit('pymupdf (fitz) is required: pip install pymupdf')

    doc = pymupdf.open(args.pdf)
    ok = True

    print('pages = %d  (band = %.0f pt)\n' % (doc.page_count, args.band))
    print('%-5s %-46s %s' % ('page', 'TOP band (head + folio)', 'BOTTOM band'))
    print('-' * 100)

    heads = {}
    for i in range(doc.page_count):
        p = i + 1
        top, bot = band_words(doc[i], args.band)
        t, b = fmt(top), fmt(bot)
        heads[p] = t
        print('%-5d %-46s %s' % (p, t if t else '-', b if b else '-'))

    # gate: required heads present
    if args.require_head:
        missing = [p for p in sorted(parse_ranges(args.require_head))
                   if p <= doc.page_count and not heads[p]]
        print('\n--require-head: %s' % ('all present' if not missing
                                        else 'MISSING on pages %s' % missing))
        if missing:
            ok = False

    # gate: required opening pages are headless
    if args.require_bare:
        extra = [p for p in sorted(parse_ranges(args.require_bare))
                 if p <= doc.page_count and heads[p]]
        print('--require-bare: %s' % ('all headless' if not extra
                                      else 'UNEXPECTED head on pages %s' % extra))
        if extra:
            ok = False

    # gate: TOC page-number hyperlinks resolve to named destinations
    if args.check_toc_links:
        dests = doc.resolve_names() if hasattr(doc, 'resolve_names') else {}
        page_dests = {k: v for k, v in dests.items() if k.startswith('page.')}
        named_links = 0
        unresolved = []
        for i in range(doc.page_count):
            for l in doc[i].get_links():
                if l.get('kind') == pymupdf.LINK_NAMED:
                    named_links += 1
                    nd = l.get('nameddest')
                    if nd not in dests:
                        unresolved.append((i + 1, nd))
        print('\n--check-toc-links: %d named links, %d page.* dests, %d unresolved'
              % (named_links, len(page_dests), len(unresolved)))
        for pg, nd in unresolved[:10]:
            print('     p%d -> %s (UNRESOLVED)' % (pg, nd))
        if named_links == 0 or unresolved:
            ok = False

    print('\nRESULT: %s' % ('PASS' if ok else 'FAIL'))
    return 0 if ok else 1


if __name__ == '__main__':
    sys.exit(main())
