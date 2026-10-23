#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
4-Pass 自动化构建与日志审计流水线
执行：XeLaTeX -> Biber -> XeLaTeX -> XeLaTeX
并严格扫描 main.log 断言四项红线：0 Errors, 0 Overfull \\hbox, 0 Undefined refs, 0 Undefined citations
"""

import subprocess
import sys
import os

def run_pass(cmd):
    print(f"Running: {cmd}")
    p = subprocess.run(cmd, shell=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True, errors="replace")
    print(f"Return code: {p.returncode}")
    if p.returncode != 0:
        print(f"Warning: {cmd} exited with return code {p.returncode}")

def main():
    tex_file = sys.argv[1] if len(sys.argv) > 1 else "main.tex"
    job_name = os.path.splitext(os.path.basename(tex_file))[0]
    log_file = f"{job_name}.log"

    # 4-Pass 构建链
    run_pass(f"xelatex -interaction=nonstopmode {tex_file}")
    run_pass(f"biber {job_name}")
    run_pass(f"xelatex -interaction=nonstopmode {tex_file}")
    run_pass(f"xelatex -interaction=nonstopmode {tex_file}")

    if not os.path.exists(log_file):
        print(f"Error: {log_file} does not exist!")
        sys.exit(1)

    with open(log_file, "r", encoding="utf-8", errors="replace") as f:
        log = f.read()

    errors = [line for line in log.splitlines() if line.startswith("! ")]
    undef_refs = [line for line in log.splitlines() if "undefined" in line.lower() and "reference" in line.lower()]
    undef_cits = [line for line in log.splitlines() if "undefined" in line.lower() and "citation" in line.lower()]
    overfulls = [line for line in log.splitlines() if line.startswith("Overfull \\hbox")]

    print("\n=== AUDIT REPORT ===")
    print(f"Errors: {len(errors)}")
    for e in errors:
        print("  ", e)
    print(f"Undefined refs: {len(undef_refs)}")
    for r in undef_refs:
        print("  ", r)
    print(f"Undefined citations: {len(undef_cits)}")
    for c in undef_cits:
        print("  ", c)
    print(f"Overfull \\hbox: {len(overfulls)}")
    for o in overfulls:
        print("  ", o)

    # 严守质量红线
    success = True
    if len(errors) > 0:
        print("\n[FAIL] Found LaTeX compilation errors!")
        success = False
    if len(undef_refs) > 0:
        print("\n[FAIL] Found undefined references!")
        success = False
    if len(undef_cits) > 0:
        print("\n[FAIL] Found undefined citations!")
        success = False
    if len(overfulls) > 0:
        print("\n[FAIL] Found Overfull \\hbox warnings!")
        success = False

    if success:
        print("\n[PASS] All audit checks passed successfully (0 Errors, 0 Overfull, 0 Undefined).")
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
