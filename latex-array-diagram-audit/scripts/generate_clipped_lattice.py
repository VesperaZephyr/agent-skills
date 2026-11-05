"""Generate an editable finite rectangular view of a directed integer lattice.

For schematic lattice differentials, not arbitrary commutative diagrams. Verify
the source's rectangle and boundary convention before selecting this model.
"""
import argparse
import math
from pathlib import Path


def clipped_segment(x, y, dx, dy, xmax, ymin):
    """Liang-Barsky interval for (x,y)+t*(dx,-dy), t in [0,1]."""
    low, high = 0.0, 1.0
    for start, delta, minimum, maximum in ((x, dx, 0, xmax), (y, -dy, ymin, 0)):
        if delta == 0:
            if not minimum <= start <= maximum:
                return None
        else:
            a, b = sorted(((minimum - start) / delta, (maximum - start) / delta))
            low, high = max(low, a), min(high, b)
    return (low, high) if high - low > 1e-9 else None


def generate(rows=6, cols=7, dx=2, dy=1, x_cm=.55, y_cm=.5):
    if not (2 <= rows <= 100 and 2 <= cols <= 100 and 1 <= dx <= 100 and 0 <= dy <= 100):
        raise ValueError('Rows/cols must be 2..100; dx 1..100; dy 0..100')
    if not all(math.isfinite(v) and v > 0 for v in (x_cm, y_cm)):
        raise ValueError('Positive finite grid spacing required')
    xmax, ymin = cols - 1, 1 - rows
    lines = [f'\\begin{{tikzpicture}}[x={x_cm:g}cm,y={y_cm:g}cm,>=stealth]',
             r'\begin{scope}', f'\\clip (0,{ymin}) rectangle ({xmax},0);']
    for y in range(ymin, dy + 1):
        for x in range(-dx, cols):
            interval = clipped_segment(x, y, dx, dy, xmax, ymin)
            if interval is None:
                continue
            target_inside = 0 <= x + dx <= xmax and ymin <= y - dy <= 0
            style = '->,shorten >=1.5pt' if target_inside else '-'
            lines.append(f'\\draw[{style}] ({x},{y})--({x+dx},{y-dy});')
    lines.append(r'\end{scope}')
    # Outside the clipping scope: boundary dots retain their whole shape.
    for y in range(ymin, 1):
        for x in range(cols):
            lines.append(f'\\fill ({x},{y}) circle[radius=1.15pt];')
    lines.append(r'\end{tikzpicture}')
    return '\n'.join(lines) + '\n'


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--rows', type=int, default=6)
    parser.add_argument('--cols', type=int, default=7)
    parser.add_argument('--dx', type=int, default=2)
    parser.add_argument('--dy', type=int, default=1, help='Downward displacement')
    parser.add_argument('--x-cm', type=float, default=.55)
    parser.add_argument('--y-cm', type=float, default=.5)
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--standalone', action='store_true')
    args = parser.parse_args()
    text = generate(args.rows, args.cols, args.dx, args.dy, args.x_cm, args.y_cm)
    if args.standalone:
        text = ('\\documentclass{article}\n\\usepackage{tikz}\n\\begin{document}\n'
                + text + '\\end{document}\n')
    with args.out.open('x', encoding='utf-8', newline='\n') as stream:
        stream.write(text)


if __name__ == '__main__':
    main()
