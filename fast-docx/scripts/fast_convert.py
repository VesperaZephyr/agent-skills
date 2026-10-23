#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fast_convert.py —— 极速 Word 文档转换器
直通本地文档服务内核，跳过冗长的多子代理流转与繁复预检，实现 2~3 秒内高质量生成 DOCX。
"""
import argparse
import os
import subprocess
import sys

ENGINE_CONVERT_SCRIPT = r"E:\WorkBuddy\resources\app.asar.unpacked\resources\plugins\workbuddy-builtin\builtin-plugins\workbuddy-docx\skills\html-to-doc\scripts\convert_doc.py"
PYTHON_BIN = r"C:\Users\asus\.workbuddy\binaries\python\versions\3.13.12\python.exe"

def main():
    parser = argparse.ArgumentParser(description="Fast HTML to DOCX Converter")
    parser.add_argument("--html", required=True, help="Path to input HTML file")
    parser.add_argument("--output", required=True, help="Path to output DOCX file")
    args = parser.parse_args()

    html_path = os.path.abspath(args.html)
    output_path = os.path.abspath(args.output)

    if not os.path.exists(html_path):
        print(f"[ERROR] HTML file does not exist: {html_path}", file=sys.stderr)
        sys.exit(1)

    output_dir = os.path.dirname(output_path)
    if output_dir and not os.path.exists(output_dir):
        os.makedirs(output_dir, exist_ok=True)

    env = os.environ.copy()
    env["editor_sdk_port"] = "39099"  # 固定常驻端口，避免扫描 10 个端口浪费时间

    cmd = [
        PYTHON_BIN,
        ENGINE_CONVERT_SCRIPT,
        "--html", html_path,
        "--output", output_path,
        "--no-preflight",
        "--no-verify"
    ]

    result = subprocess.run(cmd, env=env, capture_output=True, text=True)
    if result.returncode == 0:
        print(f"[SUCCESS] Successfully generated DOCX at: {output_path}")
        print(result.stdout.strip())
        sys.exit(0)
    else:
        print(f"[ERROR] Convert failed with code {result.returncode}", file=sys.stderr)
        if result.stderr:
            print(result.stderr, file=sys.stderr)
        if result.stdout:
            print(result.stdout, file=sys.stderr)
        sys.exit(result.returncode)

if __name__ == "__main__":
    main()
