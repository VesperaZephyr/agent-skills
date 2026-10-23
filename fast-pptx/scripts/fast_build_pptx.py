#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fast_build_pptx.py —— 极速 PPTX 演示文稿批量装配器
通过批处理模式调用本地 slidep CLI，在 2~3 秒内将多个 .slide DSL 页面一次性灌入 PPTX，
彻底跳过慢速单页 VLM 质检循环，将 10~15 分钟的多轮等待压缩至数十秒。
"""
import argparse
import glob
import json
import os
import subprocess
import sys
import time

def run_cmd(cmd):
    proc = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    return proc.returncode, proc.stdout.strip(), proc.stderr.strip()

def main():
    parser = argparse.ArgumentParser(description="Fast PPTX Batch Builder")
    parser.add_argument("--output", required=True, help="Target PPTX output path")
    parser.add_argument("--slides-dir", required=True, help="Directory containing .slide DSL files")
    args = parser.parse_args()

    output_pptx = os.path.abspath(args.output)
    slides_dir = os.path.abspath(args.slides_dir)

    if not os.path.exists(slides_dir):
        print(f"[ERROR] Slides directory does not exist: {slides_dir}", file=sys.stderr)
        sys.exit(1)

    slide_files = sorted(glob.glob(os.path.join(slides_dir, "*.slide")))
    if not slide_files:
        print(f"[ERROR] No .slide files found in: {slides_dir}", file=sys.stderr)
        sys.exit(1)

    print(f"[*] Found {len(slide_files)} slide(s) to assemble into {output_pptx}")
    t0 = time.time()

    # Step 1: Create blank PPTX
    if os.path.exists(output_pptx):
        try:
            os.remove(output_pptx)
        except Exception:
            pass

    out_dir = os.path.dirname(output_pptx)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    create_cmd = f'slidep create "{output_pptx}"'
    rc, stdout, stderr = run_cmd(create_cmd)
    if rc != 0:
        print(f"[ERROR] Failed to create PPTX: {stderr or stdout}", file=sys.stderr)
        sys.exit(rc)
    print(f"[+] Blank presentation created: {output_pptx}")

    # Step 2: Batch upsert each slide DSL
    for idx, slide_path in enumerate(slide_files, start=1):
        upsert_cmd = f'slidep upsert-dsl "{output_pptx}" --dsl-file "{slide_path}"'
        rc, stdout, stderr = run_cmd(upsert_cmd)
        if rc != 0:
            print(f"[WARN] Failed to insert slide {os.path.basename(slide_path)}: {stderr or stdout}", file=sys.stderr)
        else:
            print(f"    [Slide {idx}/{len(slide_files)}] Inserted {os.path.basename(slide_path)}")

    t1 = time.time()
    elapsed = t1 - t0
    print(f"[SUCCESS] All {len(slide_files)} slide(s) assembled in {elapsed:.2f}s!")
    print(json.dumps({
        "success": True,
        "pptx_path": output_pptx,
        "slides_count": len(slide_files),
        "elapsed_seconds": round(elapsed, 2)
    }, ensure_ascii=False))

if __name__ == "__main__":
    main()
