#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
lecture_notes_scaffold.py - 期末复习讲义骨架与分章迭代脚手架 (跨科目通用)

子命令:
  init         从 assets/lecture_notes_template.tex 生成新讲义 (替换占位符, CRLF 无 BOM)
  backup       为现有讲义建立带时间戳的备份
  add-chapter  在 \end{document} 前追加一章骨架 (自动备份, 自动识别 article / ctexbook)

生成的骨架只含结构性 LaTeX 与 % 注释形式的写作提示, 不注入任何会渲染出来的占位正文,
因此追加后立刻可以编译. 环境、题源标注与解答由写作者按规范填充.

用法:
  python lecture_notes_scaffold.py init --out 讲义.tex --course "<课程名>" --author 某某
  python lecture_notes_scaffold.py backup 讲义.tex
  python lecture_notes_scaffold.py add-chapter 讲义.tex --title "域论: 子域与单扩域" \
      --sections "子域与扩域,单扩域与极小多项式,代数扩域" --dry-run
"""

import argparse
import re
import shutil
import sys
from datetime import datetime
from pathlib import Path

SKILL_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = SKILL_ROOT / "assets" / "lecture_notes_template.tex"
PLACEHOLDER_NOTE = "[考点或方法名, 例如: 某类问题的标准解法]"


def write_tex(path, text, eol="\r\n"):
    """UTF-8 无 BOM 写入, 默认 CRLF."""
    data = text.replace("\r\n", "\n").replace("\r", "\n").replace("\n", eol)
    Path(path).write_bytes(data.encode("utf-8"))
    return len(data.encode("utf-8"))


def read_tex(path):
    raw = Path(path).read_bytes()
    return raw.decode("utf-8-sig" if raw.startswith(b"\xef\xbb\xbf") else "utf-8") \
              .replace("\r\n", "\n").replace("\r", "\n")


def cmd_init(args):
    if not TEMPLATE.is_file():
        raise SystemExit("找不到模板: %s" % TEMPLATE)
    text = read_tex(TEMPLATE)
    text = text.replace("[课程名]", args.course).replace("[编写者]", args.author)
    if args.title:
        text = re.sub(r"\\title\{[^}]*\}", lambda m: "\\title{%s}" % args.title, text, count=1)
    text = text.replace(PLACEHOLDER_NOTE, "[考点或方法名]")
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists() and not args.force:
        raise SystemExit("目标已存在: %s (加 --force 覆盖)" % out)
    n = write_tex(out, text)
    print("已生成讲义骨架: %s (%d bytes, UTF-8 无 BOM + CRLF)" % (out, n))
    print("课程名: %s | 编写者: %s" % (args.course, args.author))
    print("下一步: 按 references/lecture_notes_workflow.md 建台账并分章迭代.")
    return 0


def make_backup(tex, backup_dir=None):
    tex = Path(tex).resolve()
    d = Path(backup_dir).resolve() if backup_dir else tex.parent / "_backups"
    d.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target = d / ("%s_%s.tex" % (tex.stem, stamp))
    shutil.copy2(str(tex), str(target))
    print("已备份: %s" % target)
    return target


def cmd_backup(args):
    make_backup(args.tex, args.dir)
    return 0


def chapter_skeleton(text, title, sections, chapter_no, use_chapter,
                     with_manual=True):
    ch_cmd = r"\chapter" if use_chapter else r"\section"
    sec_cmd = r"\section" if use_chapter else r"\subsection"
    manual_cmd = sec_cmd
    slug = "ch%s" % chapter_no
    buf = []
    buf.append("")
    buf.append("% " + "=" * 68)
    buf.append("%% 第 %s 章骨架 (由 lecture_notes_scaffold.py 生成)" % chapter_no)
    buf.append("% 每节按: 机理推导与前提 -> 结论型命题(带题源)与证明 -> example + solution")
    buf.append("%          -> exercise + solution -> 交叉引用; 提示只讲结构, 末节按适用条件收口.")
    buf.append("% " + "=" * 68)
    buf.append("%s{%s}" % (ch_cmd, title))
    buf.append(r"\label{chap:%s}" % slug)
    buf.append("")
    for i, name in enumerate(sections, 1):
        buf.append("%s{%s}" % (sec_cmd, name.strip()))
        buf.append(r"\label{sec:%s-%d}" % (slug, i))
        buf.append("% 在此写来源, 推导与适用前提; 再写结论型命题与证明, 例题与练习, 二者各配完整解答.")
        buf.append("% 每个 example 与每个 exercise 都必须紧跟一个 solution, 给出完整解析; 不设章末集中提示段.")
        buf.append("% 题源格式: \\begin{example}[{教材 P.11 第 6 题; 第一次作业}]")
        buf.append("")
    if with_manual:
        buf.append("%s{结论与判据手册}" % manual_cmd)
        buf.append(r"\label{sec:%s-manual}" % slug)
        buf.append("% 用 booktabs + tabularx 按「适用条件—判据—结论」编排三线表;")
        buf.append("% X 列中的 \\cref 用 \\mbox{\\cref{...}} 固定, 必要时调 \\hsize 比例.")
        buf.append("")
    # 每道 exercise 就地配完整 solution; 不再生成章末集中提示段.
    buf.append("% 每道 exercise 之后就地写完整 solution, 章末不设集中提示段.")
    return "\n".join(buf)


def cmd_add_chapter(args):
    tex = Path(args.tex).resolve()
    if not tex.is_file():
        raise SystemExit("文件不存在: %s" % tex)
    text = read_tex(tex)
    doc_end = text.rfind(r"\end{document}")
    if doc_end < 0:
        raise SystemExit("找不到 \\end{document}, 拒绝插入")
    if text.count(r"\end{document}") != 1:
        raise SystemExit("文件中出现多个 \\end{document}, 请先手工确认插入点")
    use_chapter = re.search(r"\\documentclass\[[^\]]*\]\{ctexbook\}", text) is not None
    chapter_no = args.chapter_no or str(len(re.findall(r"\\chapter\{", text)) + 1)
    sections = [x.strip() for x in args.sections.split(",") if x.strip()]
    if not sections:
        raise SystemExit("--sections 不能为空; 章节名应为考点 / 方法名")
    block = chapter_skeleton(text, args.title, sections, chapter_no, use_chapter,
                             not args.no_manual)
    new_text = text[:doc_end] + block + "\n" + text[doc_end:]
    print("追加章节: 第 %s 章「%s」, %d 节, 文档类 %s" %
          (chapter_no, args.title, len(sections), "ctexbook" if use_chapter else "article"))
    print("插入点: 第 %d 行 (\\end{document} 之前)" %
          (text[:doc_end].count("\n") + 1))
    if args.dry_run:
        print("--- 预览 (未写入) ---")
        print(block)
        return 0
    if not args.no_backup:
        make_backup(tex, args.backup_dir)
    n = write_tex(tex, new_text)
    print("已写入: %s (%d bytes, UTF-8 无 BOM + CRLF)" % (tex, n))
    print("提示: 同步更新封面 / pdftitle / 副标题, 再执行 build.py 与 audit.py.")
    return 0


def main():
    ap = argparse.ArgumentParser(description="期末复习讲义骨架与分章迭代脚手架")
    sub = ap.add_subparsers(dest="cmd", required=True)

    p = sub.add_parser("init", help="从模板生成新讲义")
    p.add_argument("--out", required=True, help="输出 .tex 路径")
    p.add_argument("--course", required=True, help="课程名, 替换模板占位符")
    p.add_argument("--author", default="", help="编写者, 替换模板占位符")
    p.add_argument("--title", help="覆盖 \\title{...}")
    p.add_argument("--force", action="store_true", help="目标已存在时覆盖")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("backup", help="备份现有讲义")
    p.add_argument("tex")
    p.add_argument("--dir", help="备份目录 (默认 <tex 同目录>/_backups)")
    p.set_defaults(func=cmd_backup)

    p = sub.add_parser("add-chapter", help="追加一章骨架")
    p.add_argument("tex")
    p.add_argument("--title", required=True, help="章标题 (考点 / 方法名)")
    p.add_argument("--sections", required=True, help="节标题, 英文逗号分隔")
    p.add_argument("--chapter-no", help="章号 (默认按已有 \\chapter 数自动推断)")
    # 章末集中提示段已废止: 每道 exercise 必须紧跟一份完整 solution.
    p.add_argument("--no-manual", action="store_true", help="不生成结论手册节")
    p.add_argument("--no-backup", action="store_true", help="不自动备份")
    p.add_argument("--backup-dir", help="备份目录")
    p.add_argument("--dry-run", action="store_true", help="只预览, 不写入")
    p.set_defaults(func=cmd_add_chapter)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
