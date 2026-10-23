#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Sample the rendered colour of internal links in a PDF.

`\\hypersetup` is order-sensitive: a later `hidelinks` or `linkcolor=red`
silently overrides an earlier colour setting, and the source can lie.  This
script renders pages, reads every Link annotation rectangle and reports the
dominant non-white pixel colour, so `blue!70!black` can be asserted to be
(0, 0, 178).

Usage:
    python check_link_color.py main.pdf [--pages 10-12] [--dpi 300]
                                        [--expect 0,0,178]
"""
import argparse
import collections

try:
    import pymupdf as fitz
except ImportError:  # older wheels
    import fitz


def parse_pages(spec, n):
    if not spec:
        return list(range(n))
    out = []
    for part in spec.split(','):
        if '-' in part:
            a, b = part.split('-', 1)
            out.extend(range(int(a) - 1, int(b)))
        else:
            out.append(int(part) - 1)
    return [i for i in out if 0 <= i < n]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('pdf')
    ap.add_argument('--pages', default='')
    ap.add_argument('--dpi', type=int, default=300)
    ap.add_argument('--expect', default='')
    a = ap.parse_args()

    doc = fitz.open(a.pdf)
    expect = tuple(int(x) for x in a.expect.split(',')) if a.expect else None
    bad = 0
    seen = 0
    for pno in parse_pages(a.pages, doc.page_count):
        page = doc[pno]
        links = page.get_links()
        if not links:
            continue
        pix = page.get_pixmap(dpi=a.dpi)
        scale = a.dpi / 72.0
        for link in links:
            r = link['from']
            x0, y0, x1, y1 = (int(v * scale) for v in
                              (r.x0, r.y0, r.x1, r.y1))
            hist = collections.Counter()
            for x in range(x0, min(x1, pix.width)):
                for y in range(y0, min(y1, pix.height)):
                    c = pix.pixel(x, y)[:3]
                    if min(c) < 200:
                        hist[c] += 1
            if not hist:
                continue
            seen += 1
            top = hist.most_common(1)[0][0]
            ok = expect is None or top == expect
            if not ok:
                bad += 1
            txt = page.get_textbox(r).strip().replace('\n', ' ')[:24]
            print('page %3d  %-24s  %s%s' % (
                pno + 1, txt, top, '' if ok else '   <-- unexpected'))
    print('links sampled: %d, unexpected colour: %d' % (seen, bad))
    raise SystemExit(1 if bad else 0)


if __name__ == '__main__':
    main()
