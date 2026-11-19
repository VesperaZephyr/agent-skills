"""One-command post-write verification: content integrity + bookmark landing.

Why a wrapper
-------------
The two checks answer different questions and must both run, in this order:

1. ``pdf_integrity.py``  — did the rewrite damage any page content?
2. ``landing_audit.py``  — is each bookmark written where planned (Q1), and
   does the landing actually sit on the named heading (Q2)?

Two layers, never merged into one word
--------------------------------------
Automated evidence and human acceptance are different things, and this wrapper
refuses to blur them:

* **自动化检查** can only be called *complete* when ``--orig`` (content) and
  ``--items`` (planned y) were both supplied and nothing came back
  ``UNVERIFIED``.  Missing either one is a coverage gap, not a pass.
* **人工验收** is the full contact-sheet review the skill requires.  The tool
  cannot perform it; it can only read the record you hand it via
  ``--manual-review`` (a small JSON, schema below) and check the denominator.

Hence the verdicts:

    FAIL        硬失败: 内容变化 / 落点越界 / 落点可证错位      (exit 1)
    INCOMPLETE  自动检查本身覆盖不全, 连"自动通过"都不能说        (exit 3)
    AUTO-PASS   自动检查完整通过, 人工验收未记录(或未覆盖全部)    (exit 2)
    PASS        自动检查完整通过 + 人工验收记录覆盖全部条目       (exit 0)

An ``AUTO-PASS`` is the normal end state of a text-layer PDF that nobody has
looked at yet.  Q2 text matching is *supplementary* evidence: it says "the
text under the landing matches this heading", not "the layout puts the line
exactly on the heading's top edge".  So never report it as 已验证.

Manual review record
--------------------
    {"reviewed": 530,          # int, or [1,2,3,...] of 1-based entry indexes
     "total": 530,
     "sheets": 18,             # contact sheets actually looked at
     "method": "逐格拼版目视",
     "by": "who", "date": "2026-11-19", "notes": "..."}

``reviewed`` must cover every entry, ``method`` must be non-empty.  A partial
record downgrades the verdict; it never upgrades it.

Usage
-----
    python verify_writeback.py --new 写回后.pdf --orig 备份.pdf \
        --items 条目.json --sheet sheets --manual-review review.json
    python verify_writeback.py --new 写回后.pdf --orig 备份.pdf   # 自动层, 无 Q1

Exit codes: 0 PASS / 2 AUTO-PASS或待目视 / 3 自动覆盖不全 / 1 硬失败
"""
from __future__ import annotations

import argparse
import json
import os
import subprocess
import sys
import tempfile

HERE = os.path.dirname(os.path.abspath(__file__))


def run(script, args):
    cmd = [sys.executable, "-W", "ignore", os.path.join(HERE, script)] + args
    proc = subprocess.run(cmd, capture_output=True, text=True,
                          encoding="utf-8", errors="replace")
    return proc.returncode, (proc.stdout or "") + (proc.stderr or "")


def load_manual(path):
    """Return (record|None, problem|None).  Never guess on a broken record."""
    try:
        rec = json.load(open(path, encoding="utf-8-sig"))
    except Exception as exc:
        return None, f"人工验收记录无法读取: {exc}"
    if not isinstance(rec, dict):
        return None, "人工验收记录必须是 JSON 对象"
    if not str(rec.get("method") or "").strip():
        return None, "人工验收记录缺少 method(用什么方式看的)"
    rv = rec.get("reviewed")
    if isinstance(rv, list):
        n = len({int(x) for x in rv if str(x).strip()})
    elif isinstance(rv, (int, float)):
        n = int(rv)
    else:
        return None, "人工验收记录缺少 reviewed(已看条目数或序号列表)"
    if n <= 0:
        return None, "人工验收记录 reviewed<=0"
    out = dict(rec)
    out["_n"] = n
    return out, None


def tail(text, n=8):
    lines = [l for l in (text or "").rstrip().splitlines() if l.strip()]
    return "\n".join(lines[-n:])


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--new", required=True, help="写回后(或候选)的 PDF")
    ap.add_argument("--orig", help="改动前的原件/备份; 给了才做内容完整性比对")
    ap.add_argument("--items", help="规划用 JSON: [{level,page,title,y,expect?}]")
    ap.add_argument("--sheet", help="生成拼版图目录(红线由原始 /XYZ 反算)")
    ap.add_argument("--every", type=int, default=1, help="拼版抽样步长")
    ap.add_argument("--pages", help='内容比对只查这些页, 如 "1-40,300"')
    ap.add_argument("--manual-review", help="人工验收记录 JSON(见文件头 schema)")
    ap.add_argument("--strict-text", action="store_true",
                    help="Q2 未获文字层证据即视为失败(纯扫描件永远会失败, 慎用)")
    ap.add_argument("--quiet", action="store_true", help="只打印汇总")
    args = ap.parse_args()

    # ---- 1) 内容完整性 -------------------------------------------------
    content_state, content_note = "SKIP", "未提供 --orig, 内容完整性未比对"
    content_problems = []
    if args.orig:
        argv = ["--base", args.orig, "--new", args.new]
        if args.pages:
            argv += ["--pages", args.pages]
        content_rc, content_out = run("pdf_integrity.py", argv)
        content_problems = [l.strip() for l in content_out.splitlines()
                            if l.startswith("PROBLEM")]
        if content_rc == 0:
            content_state = "PASS"
            content_note = "0 硬差异, 0 未验证 facet"
        elif content_rc == 2:
            content_state = "PARTIAL"
            content_note = "无硬差异, 但有 facet 读取失败(见下)"
        else:
            content_state = "FAIL"
            content_note = (f"{len(content_problems)} 项硬差异" if content_problems
                            else "脚本执行失败(不是内容差异, 见诊断)")
            if not content_problems:
                print("[诊断] pdf_integrity.py 未给出 PROBLEM 行, 末尾输出:")
                print(tail(content_out))
        if not args.quiet:
            print(content_out.rstrip())
            print()

    # ---- 2) 落点: Q1 口径 + Q2 目标 ------------------------------------
    fd, tmp_json = tempfile.mkstemp(prefix="landing-", suffix=".json")
    os.close(fd)
    argv = [args.new, "--json", tmp_json]
    if args.items:
        argv += ["--items", args.items]
    if args.sheet:
        argv += ["--sheet", args.sheet, "--every", str(args.every)]
    landing_rc, landing_out = run("landing_audit.py", argv)
    landing_problems = [l.strip() for l in landing_out.splitlines()
                        if l.startswith("PROBLEM")]
    if not args.quiet:
        print(landing_out.rstrip())
        print()

    rows = []
    try:
        rows = json.load(open(tmp_json, encoding="utf-8"))
    except Exception:
        pass
    finally:
        try:
            os.unlink(tmp_json)
        except OSError:
            pass

    total = len(rows)
    if total == 0:
        landing_problems.append("landing_audit.py 未产出任何条目(脚本可能未执行成功)")
        print("[诊断] landing_audit.py 末尾输出:")
        print(tail(landing_out))
    coord_ok = sum(1 for r in rows if r.get("verified"))
    st = {}
    for r in rows:
        st[r.get("text_status") or "-"] = st.get(r.get("text_status") or "-", 0) + 1
    q2_auto = st.get("MATCH", 0) + st.get("WEAK_NUM", 0)
    q2_bad = st.get("MISMATCH", 0)
    q2_unver = total - q2_auto
    q1_on = bool(args.items) and total > 0
    manual, manual_problem = (None, None)
    if args.manual_review:
        manual, manual_problem = load_manual(args.manual_review)

    # ---- 汇总: 两层分开 -------------------------------------------------
    print("=" * 66)
    print("汇总 —— 自动化检查 与 人工验收 是两层证据, 不可互相替代")
    print("=" * 66)
    print("【自动化检查】")
    print(f"  内容完整性 : {content_state:<8} {content_note}")
    print(f"  Q1 口径    : {'PASS' if q1_on and coord_ok else 'SKIP':<8} "
          f"可反算 {coord_ok}/{total}"
          + ("" if args.items else "  (未给 --items, 没有与计划比对)"))
    print(f"  Q2 目标    : {q2_auto}/{total} 有文字层证据"
          f" (编号匹配 {st.get('MATCH', 0)}, 仅正文命中 {st.get('WEAK_NUM', 0)},"
          f" 不命中 {q2_bad}, 无文字层 {st.get('NO_TEXT', 0)})")
    print("               文字层证据只说明'落点下方文字与标题相符', 不等于排版上压准标题上沿;")
    print("               技能要求全量看拼版, 它不能替代人工验收。")
    for p in landing_problems[:6]:
        print(f"       {p}")
    if q2_unver and args.sheet:
        print(f"               待目视 {q2_unver} 条 -> 拼版: {args.sheet}")

    auto_complete = (content_state == "PASS" and q1_on and coord_ok == total)
    print("  —— 自动层结论: "
          + ("覆盖完整" if auto_complete else
             "有硬失败(见 PROBLEM) → 不能报'自动通过'" if content_state == "FAIL"
             else "覆盖不全(缺 --orig / --items, 或有 UNVERIFIED) → 不能报'自动通过'"))

    print("【人工验收】")
    manual_n = 0
    if manual_problem:
        print(f"  记录       : 无效 —— {manual_problem}")
        manual_n = 0
    elif manual:
        manual_n = manual["_n"]
        extra = []
        if manual.get("sheets") is not None:
            extra.append(f"{manual['sheets']} 张拼版")
        for k in ("method", "by", "date"):
            if manual.get(k):
                extra.append(str(manual[k]))
        print(f"  记录       : {manual_n}/{total} 条  (" + ", ".join(extra) + ")")
        if manual.get("total") not in (None, total):
            print(f"               记录声明的总数 {manual['total']} 与树的 {total} 不符")
        if manual_n < total:
            print(f"               覆盖不足: 还差 {total - manual_n} 条")
    else:
        print("  记录       : 未提供 --manual-review")

    # ---- 结论 ----------------------------------------------------------
    print("-" * 66)
    hard = (content_state == "FAIL") or (landing_rc != 0)
    if hard:
        print("结论: FAIL —— 不要写回; 按上面的 PROBLEM 修好后重跑")
        return 1
    if not auto_complete:
        print("结论: INCOMPLETE —— 自动检查本身没覆盖全, 既不能报 PASS 也不能报 AUTO-PASS;")
        print("      补 --orig / --items 重跑, 或先手工确认自动层未覆盖的那部分")
        return 3
    if args.strict_text and q2_unver:
        print(f"结论: FAIL (--strict-text) —— {q2_unver} 条目标未获文字层证据")
        return 1
    if manual_problem:
        print("结论: INCOMPLETE —— 人工验收记录无效, 按'未提供'处理; 修好记录后重跑")
        return 3
    if manual_n < total:
        print("结论: AUTO-PASS —— 自动检查完整通过, 人工验收未完成;")
        print("      汇报里只能写'自动检查通过 (Q2 自动证据 x/n)', 不得写'已验证'")
        return 2
    print("结论: PASS —— 自动检查完整通过, 人工验收记录覆盖全部条目;")
    print("      汇报时仍要分别列出两层结果与各自分母")
    return 0


if __name__ == "__main__":
    sys.exit(main())
