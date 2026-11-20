"""List blank lines at display-math boundaries for editorial review."""
import argparse
import re
from pathlib import Path

ENV = r"(?:equation|align|alignat|flalign|gather|multline|displaymath|eqnarray)\*?"
OPEN = re.compile(r"^\\(?:\[|begin\{" + ENV + r"\})")
CLOSE = re.compile(r"^\\(?:\]|end\{" + ENV + r"\})")
ITEM = re.compile(r"^\\item\b")
OPAQUE = re.compile(r"^\\begin\{(verbatim\*?|Verbatim|lstlisting|minted|comment)\}")

def scan(path):
    lines = path.read_text(encoding="utf-8-sig").splitlines()
    opaque = None
    for i, raw in enumerate(lines):
        line = raw.strip()
        if opaque:
            if line.startswith(r"\end{" + opaque + "}"):
                opaque = None
            continue
        match = OPAQUE.match(line)
        if match:
            opaque = match[1]
            continue
        before = OPEN.match(line)
        after = CLOSE.match(line)
        # Recognize legacy $$ delimiters without assuming direction.
        if line == "$$":
            before = after = True
        for active, step, side in ((before, -1, "before"), (after, 1, "after")):
            if not active:
                continue
            j = i + step
            blanks = []
            while 0 <= j < len(lines):
                neighbor = lines[j].strip()
                if neighbor.startswith("%"):
                    j += step
                    continue
                if neighbor:
                    break
                blanks.append(j + 1)
                j += step
            if blanks and 0 <= j < len(lines):
                context = lines[j].strip()
                kind = "item" if step == -1 and ITEM.match(context) else side
                print(f"{path}:{i+1}: {kind}; blank lines "
                      f"{','.join(map(str, sorted(blanks)))}; {context[:130]}")
                yield 1

def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path, help="TeX files or directories")
    args = parser.parse_args()
    paths = set()
    for path in args.paths:
        if path.is_dir():
            paths.update(p.resolve() for p in path.rglob("*.tex"))
        elif path.is_file() and path.suffix.lower() == ".tex":
            paths.add(path.resolve())
        else:
            parser.error(f"not a TeX file or directory: {path}")
    if not paths:
        parser.error("no TeX files found")
    count = sum(sum(scan(path)) for path in sorted(paths))
    print(f"{count} candidate boundaries in {len(paths)} files")

if __name__ == "__main__":
    main()
