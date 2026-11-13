#!/usr/bin/env bash
set -euo pipefail
cd "$(dirname "$0")/.."
if [[ "${1:-full}" != full ]]; then echo "Usage: tools/build.sh [full]" >&2; exit 2; fi
xelatex -interaction=nonstopmode -halt-on-error -file-line-error main.tex
xelatex -interaction=nonstopmode -halt-on-error -file-line-error main.tex
biber main
xelatex -interaction=nonstopmode -halt-on-error -file-line-error main.tex
xelatex -interaction=nonstopmode -halt-on-error -file-line-error main.tex
