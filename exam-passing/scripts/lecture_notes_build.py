#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
lecture_notes_build.py - 期末复习讲义编译与 PDF 验收 (跨科目通用, Python 标准库 + TeX 工具链)

功能:
  1. 把 .tex 同步到构建目录, 连续运行 XeLaTeX 多轮以稳定交叉引用
  2. 逐轮解析日志: error / warning / undefined reference / Overfull+Underfull hbox /
     Missing character / 页数
  3. pdftotext -layout 检查 PDF: ??, 字面斜杠命令, \cref 类型名分布, 式 (章.节.序) 引用
  4. 可选 pdftoppm 渲染抽样页 (章首页 / 新公式页 / 手册表页 / 练习解答页)
  5. 构建目录固定用 ASCII 文件名, 绕开 Windows + Git Bash 下 XeLaTeX 把中文
     文件名写成乱码、PDF 落到错误文件的坑; --copy-back 遇目标被占用时另存 *_终稿.pdf
  5. 可选把最终 PDF 回拷到 .tex 同目录

退出码: 最终一轮有任何 error / warning / undefined / hbox / missing, 或 PDF 文本检查异常, 返回 1。

用法:
  python lecture_notes_build.py 讲义.tex --workdir <构建目录> --passes 3 --copy-back
  python lecture_notes_build.py 讲义.tex --render 1,20,40 --no-compile
  python lecture_notes_build.py 讲义.tex --json build.json --strict
"""

import argparse
import json
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

# PDF 文本里出现这些字面串, 说明源码把反斜杠误写成了斜杠 (编译层无感).
LITERAL_SLASH_RE = re.compile(
    r"(?<!\\)/(?:infty|alpha|beta|cdots|ldots|subseteq|leqslant|geqslant|"
    r"oplus|otimes|qquad|quad|to|mapsto|iso|cong|sum|prod|partial|nabla|"
    r"frac|sqrt|text|mathrm|mathbb|overline|gen|id|Ker|Ima|normal|sgn)\b"
)
CREF_NAME_RE = re.compile(r"(定义|定理|命题|推论|引理|例|练习|式)\s*(\d+(?:\.\d+)*)")
EQREF_RE = re.compile(r"式\s*\((\d+(?:\.\d+)+)\)")


def tool_available(name):
    return shutil.which(name) is not None


def run_command(cmd, cwd, log_path=None):
    try:
        proc = subprocess.run(cmd, cwd=str(cwd), stdout=subprocess.PIPE,
                              stderr=subprocess.STDOUT, timeout=600)
    except FileNotFoundError:
        return 127, "命令不存在: %s" % cmd[0]
    except subprocess.TimeoutExpired:
        return 124, "命令超时: %s" % " ".join(cmd)
    text = proc.stdout.decode("utf-8", errors="replace")
    if log_path:
        Path(log_path).write_text(text, encoding="utf-8")
    return proc.returncode, text


def parse_tex_log(text):
    """从一轮编译输出里提取验收指标."""
    errors = len(re.findall(r"^! ", text, re.M))
    # -file-line-error 下部分错误只有 file:line: 前缀, 补一个兜底
    fatal = len(re.findall(r"(?m)^.*?:\d+:\s*(?:Undefined control sequence|"
                           r"Emergency stop|Fatal error|Misplaced|Missing \$ inserted)", text))
    warnings = len(re.findall(r"(?:LaTeX Warning|Package \S+ Warning|Class \S+ Warning)", text))
    undefined = len(re.findall(r"(?:Reference|Citation) [^\n]*undefined", text))
    overfull = len(re.findall(r"Overfull \\hbox", text))
    underfull = len(re.findall(r"Underfull \\hbox", text))
    missing = len(re.findall(r"Missing character", text))
    pages = [int(x) for x in re.findall(r"Output written on [^\n]*?\((\d+) page", text)]
    return {
        "errors": errors,
        "fatal_lines": fatal,
        "warnings": warnings,
        "undefined": undefined,
        "overfull": overfull,
        "underfull": underfull,
        "missing_chars": missing,
        "pages": pages[-1] if pages else None,
    }


def check_pdf_text(text):
    """返回 (问题列表, 统计字典)."""
    problems = []
    stats = {}
    qm = text.count("??")
    stats["undefined_marks"] = qm
    if qm:
        problems.append("PDF 中仍有 %d 处 ??" % qm)
    slash = list(LITERAL_SLASH_RE.finditer(text))
    stats["literal_slash_commands"] = len(slash)
    for m in slash[:10]:
        problems.append("PDF 中残留字面斜杠命令 %r: %s" %
                        (m.group(0), text[max(0, m.start() - 50):m.start() + 50]
                         .replace("\n", " ")))
    cref = {}
    for name, num in CREF_NAME_RE.findall(text):
        cref[name] = cref.get(name, 0) + 1
    stats["cref_names"] = cref
    eqrefs = EQREF_RE.findall(text)
    stats["equation_refs"] = eqrefs
    # 若源码用了 \cref{eq:...}, PDF 中应能看到「式 (x.y.z)」
    return problems, stats


def main():
    ap = argparse.ArgumentParser(description="期末复习讲义编译与 PDF 验收 (跨科目通用)")
    ap.add_argument("tex", help="讲义 .tex 文件")
    ap.add_argument("--workdir", help="构建目录 (缺省为系统临时目录)")
    ap.add_argument("--passes", type=int, default=3, help="编译轮数 (默认 3)")
    ap.add_argument("--engine", default="xelatex", help="TeX 引擎 (默认 xelatex)")
    ap.add_argument("--copy-back", action="store_true", help="把最终 PDF 回拷到 .tex 同目录")
    ap.add_argument("--render", help="渲染抽样页, 逗号分隔, 如 1,20,40,76")
    ap.add_argument("--dpi", type=int, default=130, help="渲染分辨率 (默认 130)")
    ap.add_argument("--no-compile", action="store_true",
                    help="跳过编译, 直接用已有 PDF 做文本检查与渲染")
    ap.add_argument("--pdf", help="指定用于文本检查 / 渲染的 PDF (配合 --no-compile)")
    ap.add_argument("--json", dest="json_out", help="把结果写成 JSON")
    ap.add_argument("--strict", action="store_true", help="任一编译轮有问题即返回非零")
    ap.add_argument("--quiet", action="store_true", help="只输出汇总与问题")
    args = ap.parse_args()

    tex = Path(args.tex).resolve()
    if not tex.is_file():
        raise SystemExit("文件不存在: %s" % tex)
    workdir = Path(args.workdir).resolve() if args.workdir else \
        Path(tempfile.gettempdir()) / "lecture_notes_build"
    workdir.mkdir(parents=True, exist_ok=True)
    # Windows + Git Bash 下 XeLaTeX 按 UTF-8 字节写中文文件名, 系统按 GBK
    # 解释后 PDF 会落到乱码文件名, 而正确名字的 PDF 仍是旧版 (日志却报成功).
    # 构建目录里固定用 ASCII 文件名, 回拷时再写回中文名.
    BUILD_STEM = "lecture_notes_main"
    in_place = workdir.resolve() == tex.parent.resolve()
    build_stem = tex.stem if in_place else BUILD_STEM
    build_tex = workdir / (build_stem + ".tex")

    print("=== 期末复习讲义编译与 PDF 验收 ===")
    print("源码: %s" % tex)
    print("构建目录: %s" % workdir)

    passes = []
    if not args.no_compile:
        if not tool_available(args.engine):
            raise SystemExit("找不到 %s, 请确认 TeX 工具链在 PATH 中" % args.engine)
        # 就地编译时不复制 (copy2 到自身会触发 WinError 32), 但中文文件名
        # 无法绕开编码问题, 明确提示改用 --workdir.
        if not in_place:
            shutil.copy2(str(tex), str(build_tex))
        else:
            print("  构建目录即源码目录, 跳过同步复制; 中文文件名可能使 PDF 落到乱码文件名, 建议指定 --workdir")
        for i in range(1, args.passes + 1):
            code, text = run_command(
                [args.engine, "-interaction=nonstopmode", "-halt-on-error",
                 "-file-line-error", build_tex.name],
                workdir, workdir / ("pass%d.log" % i))
            metric = parse_tex_log(text)
            metric["pass"] = i
            metric["exit"] = code
            passes.append(metric)
            print("  第 %d 轮: exit=%d errors=%d warnings=%d undefined=%d "
                  "over/underfull=%d/%d missing=%d pages=%s" %
                  (i, code, metric["errors"], metric["warnings"], metric["undefined"],
                   metric["overfull"], metric["underfull"], metric["missing_chars"],
                   metric["pages"]))
            if code not in (0, 1) and metric["pages"] is None:
                print("  编译异常终止, 日志: %s" % (workdir / ("pass%d.log" % i)))
                break
        if args.quiet is False and passes:
            first_undef = passes[0]["undefined"]
            if first_undef and passes[-1]["undefined"] == 0:
                print("  注: 首轮 %d 条 undefined reference 为 .aux 未稳定所致, 三轮后归零." %
                      first_undef)
    else:
        print("  跳过编译 (--no-compile)")

    pdf = Path(args.pdf).resolve() if args.pdf else \
        (tex.with_suffix(".pdf") if args.no_compile else workdir / (build_stem + ".pdf"))
    if not pdf.is_file():
        print("  未找到 PDF: %s" % pdf)
        pdf_text_problems, pdf_stats = ["未找到 PDF, 跳过文本检查"], {}
    else:
        if tool_available("pdftotext"):
            txt_path = workdir / "pdftext.txt"
            code, out = run_command(["pdftotext", "-layout", str(pdf), str(txt_path)], workdir)
            text = txt_path.read_text(encoding="utf-8", errors="replace") if txt_path.is_file() else ""
            pdf_text_problems, pdf_stats = check_pdf_text(text)
            print("  PDF 文本检查: ?? %d | 字面斜杠命令 %d | 式引用 %s | 类型名 %s" %
                  (pdf_stats.get("undefined_marks", 0),
                   pdf_stats.get("literal_slash_commands", 0),
                   sorted(set(pdf_stats.get("equation_refs", [])))[:8],
                   pdf_stats.get("cref_names", {})))
        else:
            pdf_text_problems, pdf_stats = ["未找到 pdftotext, 跳过文本检查"], {}
            print("  未找到 pdftotext, 跳过 PDF 文本检查")

    rendered = []
    if args.render:
        if not tool_available("pdftoppm"):
            print("  未找到 pdftoppm, 跳过渲染抽样")
        elif not pdf.is_file():
            print("  无 PDF, 跳过渲染抽样")
        else:
            outdir = workdir / "render"
            outdir.mkdir(exist_ok=True)
            for page in [x.strip() for x in args.render.split(",") if x.strip()]:
                stem = outdir / ("page-%s" % page)
                code, out = run_command(
                    ["pdftoppm", "-f", page, "-l", page, "-r", str(args.dpi),
                     "-png", "-singlefile", str(pdf), str(stem)], workdir)
                png = Path(str(stem) + ".png")
                if code == 0 and png.is_file():
                    rendered.append(str(png))
                    print("  已渲染第 %s 页: %s" % (page, png))
                else:
                    print("  渲染第 %s 页失败 (exit=%d)" % (page, code))

    copied = None
    if args.copy_back and pdf.is_file():
        target = tex.with_suffix(".pdf")
        if pdf.resolve() != target.resolve():
            try:
                shutil.copy2(str(pdf), str(target))
                copied = str(target)
                print("  已回拷 PDF: %s" % target)
            except (PermissionError, OSError) as exc:
                alt = target.with_name(target.stem + "_终稿.pdf")
                shutil.copy2(str(pdf), str(alt))
                copied = str(alt)
                print("  目标 PDF 被占用 (%s), 已另存为: %s" % (exc, alt))
        else:
            copied = str(target)
            print("  PDF 已在源码同目录, 跳过回拷")

    # 汇总
    final = passes[-1] if passes else {}
    bad_passes = [p for p in passes if p["errors"] or p["warnings"] or p["undefined"] or
                  p["overfull"] or p["underfull"] or p["missing_chars"]]
    # 首轮 .aux 未稳定造成的 warning / undefined 属正常现象, 不算硬失败;
    # error, hbox 与缺字符在多轮编译后不会自行消失, 任一出现都要报.
    hard_bad_passes = [p for p in passes if p["errors"] or p["overfull"] or
                       p["underfull"] or p["missing_chars"]]
    final_bad = bool(final) and (final["errors"] or final["warnings"] or final["undefined"] or
                                 final["overfull"] or final["underfull"] or
                                 final["missing_chars"])
    print("")
    print("结论: 编译轮数 %d | 有提示的轮次 %d (首轮 aux 未稳定属正常) | 硬问题轮次 %d | "
          "最终一轮 %s | PDF 文本问题 %d" %
          (len(passes), len(bad_passes), len(hard_bad_passes),
           "不通过" if final_bad else "通过", len(pdf_text_problems)))
    for msg in pdf_text_problems:
        print("  ! %s" % msg)
    print("  注: 本工具不检查数学内容, 中文引号方向与表格断行; "
          "请人工查看渲染抽样页 (见 lecture_notes_workflow.md §5).")

    if args.json_out:
        payload = {"tex": str(tex), "workdir": str(workdir), "pdf": str(pdf),
                   "passes": passes, "pdf_stats": pdf_stats,
                   "pdf_problems": pdf_text_problems,
                   "rendered": rendered, "copied_back": copied,
                   "final_ok": not final_bad and not pdf_text_problems}
        Path(args.json_out).write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                                       encoding="utf-8")
        print("  JSON 已写入: %s" % args.json_out)

    if final_bad or pdf_text_problems or (args.strict and hard_bad_passes):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
