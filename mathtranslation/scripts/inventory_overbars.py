#!/usr/bin/env python3
"""Inventory explicit TeX overbar commands for manual source-page review.

This is a lexical locator, not a TeX interpreter or a fidelity checker.
It does not discover omitted bars, expanded macros, or mathematical meaning.
"""
import argparse
import csv
import hashlib
import re
import sys
from pathlib import Path

COMMAND = re.compile(r"\\(?:overline|widebar|bar)(?![A-Za-z@])")
FIELDS = ("file", "sha256", "line", "column", "command", "argument", "parse_status",
          "source_page_region", "meaning", "source_evidence", "verdict", "notes")


def without_comments(text):
    """Replace comments with spaces, retaining offsets and newlines."""
    out = list(text)
    i = 0
    while i < len(text):
        if text[i] == "%":
            n = 0
            j = i - 1
            while j >= 0 and text[j] == "\\":
                n += 1
                j -= 1
            if n % 2 == 0:
                while i < len(text) and text[i] not in "\r\n":
                    out[i] = " "
                    i += 1
                continue
        i += 1
    return "".join(out)


def argument_at(text, pos):
    while pos < len(text) and text[pos].isspace():
        pos += 1
    if pos == len(text):
        return "", "missing_argument"
    start = pos
    if text[pos] != "{":
        if text[pos] == "\\":
            match = re.match(r"\\(?:[A-Za-z@]+|.)", text[pos:])
            return (match.group(0), "unbraced") if match else ("\\", "unbraced")
        return text[pos], "unbraced"
    depth = 0
    while pos < len(text):
        if text[pos] == "\\":
            match = re.match(r"\\(?:[A-Za-z@]+|.)", text[pos:], re.DOTALL)
            pos += len(match.group(0)) if match else 1
            continue
        if text[pos] == "{":
            depth += 1
        elif text[pos] == "}":
            depth -= 1
            if depth == 0:
                return text[start:pos + 1], "braced"
        pos += 1
    return text[start:], "unclosed_group"


def inventory(path):
    raw = path.read_bytes()
    text = raw.decode("utf-8-sig")
    clean = without_comments(text)
    digest = hashlib.sha256(raw).hexdigest()
    for m in COMMAND.finditer(clean):
        arg, status = argument_at(clean, m.end())
        line = clean.count("\n", 0, m.start()) + 1
        column = m.start() - clean.rfind("\n", 0, m.start())
        yield dict(file=str(path), sha256=digest, line=line, column=column,
                   command=m.group(), argument=arg, parse_status=status)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("paths", nargs="+", type=Path, help="TeX files or directories (recursively scans *.tex)")
    parser.add_argument("-o", "--output", type=Path, help="CSV path; default stdout")
    args = parser.parse_args()
    files = set()
    for path in args.paths:
        if path.is_dir():
            files.update(p for p in path.rglob("*.tex") if p.is_file())
        elif path.is_file():
            files.add(path)
        else:
            parser.error(f"path not found: {path}")
    if args.output and args.output.resolve() in {p.resolve() for p in files}:
        parser.error("output must not overwrite an input")
    try:
        rows = [row for p in sorted(files) for row in inventory(p)]
        if args.output:
            with args.output.open("w", encoding="utf-8-sig", newline="") as f:
                writer = csv.DictWriter(f, fieldnames=FIELDS)
                writer.writeheader()
                writer.writerows(rows)
        else:
            writer = csv.DictWriter(sys.stdout, fieldnames=FIELDS, lineterminator="\n")
            writer.writeheader()
            writer.writerows(rows)
    except (OSError, UnicodeError) as exc:
        print(f"inventory failed: {exc}", file=sys.stderr)
        return 1
    print(f"{len(rows)} candidates; manual source-page review required", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
