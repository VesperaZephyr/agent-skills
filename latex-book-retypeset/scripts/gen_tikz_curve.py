#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Generate TikZ `plot[smooth] coordinates{...}` snippets for xeCJK book classes.

Why this exists
---------------
In xeCJK-based custom classes (zhmbook and friends), the parametric form

    \\draw[domain=0:6.2832, samples=70] plot (\\x - sin(\\x r), 1 - cos(\\x r));

fails to parse (verified: \\draw, \\fill and \\path with a `domain` option all fail).
The stable, always-working form is

    \\draw[very thick] plot[smooth] coordinates {(0,0) (0.16,0.01) ... };

so the curve has to be evaluated here in Python and injected as literals.

Usage
-----
    # parametric curve x(t), y(t)
    python gen_tikz_curve.py --param "t - sin(t)" "1 - cos(t)" --t0 0 --t1 6.2832 -n 40

    # cartesian graph y = f(x)
    python gen_tikz_curve.py --func "sin(x)/x" --x0 0.01 --x1 6.28 -n 40 --sx 1.2 --sy 1.0

    # polar curve r(theta)
    python gen_tikz_curve.py --polar "1+cos(t)" --t0 0 --t1 6.2832 -n 60

    # emit a ready-to-paste \\draw line
    python gen_tikz_curve.py --func "x**2" --x0 -2 --x1 2 -n 21 --wrap

Notes
-----
* `samples` of 30-60 is plenty; very dense sampling makes `smooth` wobble.
* For a filled region close the path explicitly:
  `(x0,0) -- plot[smooth] coordinates{...} -- (x1,0) -- cycle`
* Only `math` names plus the running variable are exposed to the expression.
"""

import argparse
import math
import sys

SAFE = {k: getattr(math, k) for k in dir(math) if not k.startswith('_')}
SAFE.update({'pi': math.pi, 'e': math.e, 'tau': math.tau})


def evaluate(expr, var, value):
    ns = dict(SAFE)
    ns[var] = value
    try:
        return eval(expr, {'__builtins__': {}}, ns)
    except Exception as exc:  # noqa: BLE001 - surfaced to the user
        raise SystemExit('cannot evaluate %r at %s=%r: %s' % (expr, var, value, exc))


def sample(kind, exprs, a, b, n, sx, sy):
    pts = []
    for i in range(n + 1):
        t = a + (b - a) * i / n
        if kind == 'param':
            x = evaluate(exprs[0], 't', t) * sx
            y = evaluate(exprs[1], 't', t) * sy
        elif kind == 'func':
            x = t * sx
            y = evaluate(exprs[0], 'x', t) * sy
        else:  # polar
            r = evaluate(exprs[0], 't', t)
            x = r * math.cos(t) * sx
            y = r * math.sin(t) * sy
        pts.append((x, y))
    return pts


def format_coords(pts, per_line=5, nd=3, indent='    '):
    chunks = ['(%.{}f,%.{}f)'.format(nd, nd) % (x, y) for x, y in pts]
    lines = []
    for i in range(0, len(chunks), per_line):
        lines.append(indent + ' '.join(chunks[i:i + per_line]))
    return '\n'.join(lines)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument('--param', nargs=2, metavar=('X', 'Y'),
                   help='parametric curve x(t), y(t)')
    g.add_argument('--func', metavar='F', help='cartesian graph y = f(x)')
    g.add_argument('--polar', metavar='R', help='polar curve r(theta)')

    ap.add_argument('--t0', type=float, default=0.0, help='start of parameter (default 0)')
    ap.add_argument('--t1', type=float, default=2 * math.pi,
                    help='end of parameter (default 2pi)')
    ap.add_argument('--x0', type=float, help='start of x (for --func)')
    ap.add_argument('--x1', type=float, help='end of x (for --func)')
    ap.add_argument('-n', '--samples', type=int, default=40, help='number of samples (default 40)')
    ap.add_argument('--sx', type=float, default=1.0, help='x scale factor (default 1)')
    ap.add_argument('--sy', type=float, default=1.0, help='y scale factor (default 1)')
    ap.add_argument('--nd', type=int, default=3, help='decimals per coordinate (default 3)')
    ap.add_argument('--per-line', type=int, default=5, help='points per source line (default 5)')
    ap.add_argument('--wrap', action='store_true',
                    help='wrap output in a complete \\draw ... plot[smooth] command')
    args = ap.parse_args()

    if args.param:
        kind, exprs = 'param', args.param
        a, b = args.t0, args.t1
    elif args.func:
        kind, exprs = 'func', [args.func]
        a = args.x0 if args.x0 is not None else args.t0
        b = args.x1 if args.x1 is not None else args.t1
    else:
        kind, exprs = 'polar', [args.polar]
        a, b = args.t0, args.t1

    pts = sample(kind, exprs, a, b, args.samples, args.sx, args.sy)
    body = format_coords(pts, args.per_line, args.nd)

    if args.wrap:
        print('\\draw[very thick] plot[smooth] coordinates {')
        print(body)
        print('};')
    else:
        print(body)


if __name__ == '__main__':
    sys.exit(main())
