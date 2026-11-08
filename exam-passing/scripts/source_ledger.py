#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
source_ledger.py - 题源台账生成与讲义出处扫描 (跨科目通用)

子命令:
  init   从 assets/source_ledger_template.md 生成一份课程题源台账
  scan   扫描讲义 .tex, 按章统计题源标注覆盖率, 列出未标注环境与重复占用的出处

scan 复用 lecture_notes_audit.py 的解析核心 (同一 scripts 目录下), 保证两处口径一致.
同一道真题常含多个小问, 因此「同一出处出现在多道题目」只作为信息项列出;
只有「同一出处出现在两道及以上 example」才判为需要人工核对的重复占用.

用法:
  python source_ledger.py init --out 题源台账.md --course "<课程名>"
  python source_ledger.py scan 讲义.tex --json sources.json --strict
"""

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from lecture_notes_audit import (Auditor, CONCLUSION_ENVS, PROBLEM_ENVS,
                                 SOURCE_RE)  # noqa: E402

SKILL_ROOT = Path(__file__).resolve().parent.parent
TEMPLATE = SKILL_ROOT / "assets" / "source_ledger_template.md"

FAMILIES = (
    ("教材页码题", re.compile(r"教材\s*P\.?\s*\d+")),
    ("教材节习题", re.compile(r"教材\s*(?:\\S|§)\s*\d+")),
    ("课程作业", re.compile(r"第[一二三四五六七八九十\d]+次作业")),
    ("历年真题", re.compile(r"\d{4}--\d{4}\s*学年")),
    ("试卷卷别", re.compile(r"[AB]\s*卷")),
)


def cmd_init(args):
    if not TEMPLATE.is_file():
        raise SystemExit("找不到台账模板: %s" % TEMPLATE)
    text = TEMPLATE.read_text(encoding="utf-8").replace("[课程名]", args.course)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists() and not args.force:
        raise SystemExit("目标已存在: %s (加 --force 覆盖)" % out)
    out.write_text(text, encoding="utf-8")
    print("已生成题源台账: %s" % out)
    print("下一步: 按「知识点 -> 题号 -> 出处 -> 是否已有解答」逐章登记, 并给每题打 结/例/练 标签.")
    return 0


def normalize(s):
    return re.sub(r"\s+", "", s or "")


def cmd_scan(args):
    tex = Path(args.tex)
    if not tex.is_file():
        raise SystemExit("文件不存在: %s" % tex)
    a = Auditor(str(tex), eol_mode="any")
    code = a.code
    entries = a.env_optional_args()
    chapter_marks = [(m.start(), m.group(1))
                     for m in re.finditer(r"\\chapter\{([^}]*)\}", code)]
    if not chapter_marks:
        chapter_marks = [(0, tex.stem)]
    bounds = [x[0] for x in chapter_marks] + [len(code)]

    chapters = []
    for idx, (start, title) in enumerate(chapter_marks):
        end = bounds[idx + 1]
        mine = [e for e in entries if start <= e[0] < end]
        ann = [e for e in mine if e[2] and SOURCE_RE.search(e[2])]
        chapters.append({
            "title": title,
            "start_line": a.line_of(start),
            "envs": len(mine),
            "annotated": len(ann),
            "examples": sum(1 for e in mine if e[1] == "example"),
            "exercises": sum(1 for e in mine if e[1] == "exercise"),
        })

    families = defaultdict(int)
    for _s, _name, arg, _e in entries:
        if not arg:
            continue
        for label, pat in FAMILIES:
            families[label] += len(pat.findall(arg))

    unannotated = []
    for s, name, arg, _e in entries:
        if not (arg and SOURCE_RE.search(arg)):
            unannotated.append({"line": a.line_of(s), "env": name,
                                "optional_arg": (arg or "")[:60]})

    seen = defaultdict(list)
    for s, name, arg, _e in entries:
        if name not in PROBLEM_ENVS or not (arg and SOURCE_RE.search(arg)):
            continue
        seen[normalize(arg)].append({"line": a.line_of(s), "env": name})
    duplicates = []
    for key, places in seen.items():
        if len(places) < 2:
            continue
        n_examples = sum(1 for p in places if p["env"] == "example")
        duplicates.append({"source": key[:100], "places": places,
                           "example_count": n_examples,
                           "needs_review": n_examples > 1})

    need_review = [d for d in duplicates if d["needs_review"]]
    unannotated_problems = [u for u in unannotated if u["env"] in PROBLEM_ENVS]

    print("=== 题源台账扫描 ===")
    print("文件: %s" % tex)
    print("结论与题目环境 %d 个, 其中带题源标注 %d 个" %
          (len(entries), sum(1 for e in entries if e[2] and SOURCE_RE.search(e[2]))))
    print("")
    print("按章:")
    for c in chapters:
        print("  L%-4d %-34s 环境 %3d / 标注 %3d | example %2d | exercise %2d" %
              (c["start_line"], c["title"][:32], c["envs"], c["annotated"],
               c["examples"], c["exercises"]))
    print("")
    print("题源类别命中: %s" % ", ".join("%s %d" % (k, v) for k, v in families.items()))
    print("未标注环境 %d 个 (其中 example / exercise %d 个)" %
          (len(unannotated), len(unannotated_problems)))
    for u in unannotated_problems[:20]:
        print("  L%-5d %-10s %s" % (u["line"], u["env"], u["optional_arg"]))
    print("重复出处 %d 组, 其中需人工核对 (两道及以上 example 共用) %d 组" %
          (len(duplicates), len(need_review)))
    for d in need_review[:15]:
        print("  ! %s -> %s" % (d["source"][:70], d["places"]))
    print("")
    print("注: 同一道真题常含多个小问, 例 + 练 共用一个出处未必是错误; 以项目题源台账为准.")

    if args.json_out:
        payload = {"file": str(tex.resolve()), "chapters": chapters,
                   "families": dict(families), "unannotated": unannotated,
                   "duplicates": duplicates,
                   "summary": {"envs": len(entries),
                               "annotated": sum(1 for e in entries
                                                if e[2] and SOURCE_RE.search(e[2])),
                               "unannotated_problems": len(unannotated_problems),
                               "duplicates_needing_review": len(need_review)}}
        Path(args.json_out).write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                                       encoding="utf-8")
        print("JSON 已写入: %s" % args.json_out)

    if args.strict and (unannotated_problems or need_review):
        return 1
    return 0


def main():
    ap = argparse.ArgumentParser(description="题源台账生成与讲义出处扫描")
    sub = ap.add_subparsers(dest="cmd", required=True)
    p = sub.add_parser("init", help="生成题源台账")
    p.add_argument("--out", required=True)
    p.add_argument("--course", required=True)
    p.add_argument("--force", action="store_true")
    p.set_defaults(func=cmd_init)

    p = sub.add_parser("scan", help="扫描讲义题源标注")
    p.add_argument("tex")
    p.add_argument("--json", dest="json_out")
    p.add_argument("--strict", action="store_true",
                   help="存在未标注题目或 example 重复出处时返回非零")
    p.set_defaults(func=cmd_scan)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
