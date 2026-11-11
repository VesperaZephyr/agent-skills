#!/usr/bin/env python3
"""Run XeLaTeX/Biber passes and audit the final log. Run in the project directory."""
import argparse
import re
import subprocess
import sys
from pathlib import Path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("tex", nargs="?", default="main.tex", help="TeX file in the current directory")
    parser.add_argument("--allow-overfull", action="store_true", help="report overfull boxes without failing")
    args = parser.parse_args()
    tex = Path(args.tex)
    if not tex.is_file() or tex.parent != Path("."):
        parser.error("specify an existing TeX file in the current directory")
    log = Path(tex.stem + ".log")
    for cmd in (["xelatex", "-interaction=nonstopmode", "-halt-on-error", tex.name],
                ["biber", tex.stem],
                ["xelatex", "-interaction=nonstopmode", "-halt-on-error", tex.name],
                ["xelatex", "-interaction=nonstopmode", "-halt-on-error", tex.name]):
        print("Running:", " ".join(cmd), flush=True)
        try:
            result = subprocess.run(cmd, check=False)
        except OSError as exc:
            print(f"Cannot run {cmd[0]}: {exc}", file=sys.stderr)
            return 1
        if result.returncode:
            print(f"Failed: {cmd[0]} returned {result.returncode}", file=sys.stderr)
            return 1
    if not log.is_file():
        print(f"Missing log: {log}", file=sys.stderr)
        return 1
    data = log.read_text(encoding="utf-8", errors="replace")
    checks = {
        "Errors": r"(?m)^! ",
        "Undefined references": r"(?im)^.*(?:reference.*undefined|undefined references).*$",
        "Undefined citations": r"(?im)^.*(?:citation.*undefined|undefined citations).*$",
        "Overfull hbox": r"(?m)^Overfull \\hbox.*$",
    }
    failed = False
    for title, pattern in checks.items():
        matches = re.findall(pattern, data)
        print(f"{title}: {len(matches)}")
        for match in matches:
            print("  ", match)
        if matches and not (title == "Overfull hbox" and args.allow_overfull):
            failed = True
    return int(failed)


if __name__ == "__main__":
    sys.exit(main())
