"""Audit where PDF bookmarks ACTUALLY land, bypassing PyMuPDF's echo.

Two different questions — do not conflate them
----------------------------------------------
**Q1 口径 (did the coordinate transform survive?)**
``get_toc(simple=False)`` reports ``dest['to'].y`` by converting the stored
``/XYZ top`` back into a "distance from page top" value.  That is exactly the
same number you handed to ``set_toc()``, so asserting ``readback == input`` is
a *circular* check: it returns 0.0001 pt even when the coordinates were flipped
vertically and every bookmark jumps to the wrong place.  (Real incident: 530
bookmarks, all self-checks "perfect", user clicked and every jump was wrong.)
This tool therefore reads the raw destination from the PDF object::

    <</S/GoTo/D[411 0 R/XYZ 0 625.8676 0]>>     ->  top = 625.8676

and converts it the way a viewer does::

    view_top = page.cropbox.y1 - top        (valid for rotation == 0)

**Q2 目标 (is the planned y on the intended heading?)**
Q1 passing proves nothing about Q2: if the planning JSON itself points at the
wrong line, "written == planned" still passes 100%.  Q2 needs independent
evidence, and this tool gathers the two admissible kinds:

* **text layer present** — extract the text just below the landing and check
  its leading number against the bookmark label (``"7.15"`` -> ``15.``), or
  against ``expect`` if the item supplies one.  Verdict: MATCH / MISMATCH.
* **no text layer (scan)** — nothing machine-checkable exists here.  The tool
  says so explicitly and requires ``--sheet`` plus human/vision review of every
  cell.  It never reports such items as "verified".

Everything printed is derived from the file on disk, never from the planning
JSON (except the ``planned y`` column, which is labelled as such).

Usage
-----
    python landing_audit.py BOOK.pdf
    python landing_audit.py BOOK.pdf --items items.json
    python landing_audit.py BOOK.pdf --items items.json --sheet outdir --every 10
    python landing_audit.py BOOK.pdf --items items.json --strict-text

``--items`` is a JSON array of ``{"level","page","title","y"}`` (same file
``bookmark_candidate.py`` consumes); an optional ``"expect"`` per item
overrides the label-derived expectation.

``--sheet DIR`` renders contact sheets whose red line is drawn at the
raw-derived landing, labelled ``cX nY`` for titles like ``"7.15"``.

Exit code 1 means at least one hard problem was found.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys
from collections import Counter

try:
    import pymupdf
except ImportError:  # older wheels
    import fitz as pymupdf


XYZ_RE = re.compile(r"/XYZ\s+(-?[\d.]+|-?null)\s+(-?[\d.]+|-?null)")
NUMTITLE_RE = re.compile(r"^(\d+)\s*[.\-]\s*(\d+)\s*\*?\s*$")


# ---------------------------------------------------------------- raw outline

def raw_dests(doc):
    """Return one dict per bookmark, with the landing derived from /XYZ only."""
    out = []
    for level, title, page1, dest in doc.get_toc(simple=False):
        note, top, left, landing, reason = "", None, None, None, ""
        xref = dest.get("xref")
        raw = ""
        if xref:
            for key in ("A", "Dest"):
                kind, val = doc.xref_get_key(xref, key)
                if kind != "null" and "/XYZ" in (val or ""):
                    raw = val
                    break
        m = XYZ_RE.search(raw) if raw else None
        if m:
            try:
                left = float(m.group(1)) if m.group(1) != "null" else None
                top = float(m.group(2)) if m.group(2) != "null" else None
            except ValueError:
                top = None
            if top is None:
                reason = "/XYZ 未锁定纵坐标(top=null)"
        elif raw:
            reason = "目标非 /XYZ(如 /Fit), 无纵坐标"
        else:
            reason = "无原始目标(A/Dest 皆空); 书签可能失效或指向 URI"

        pg = doc[page1 - 1]
        if top is not None and not reason:
            if pg.rotation:
                # /XYZ 在未旋转的默认用户空间里, 旋转后纵横轴互换, 公式不成立。
                # 这里不做推导(推错过一次), 标为未验证并列出页面, 由渲染裁决。
                reason = f"rotation={pg.rotation}"
            else:
                # 显示口径: 距可见页顶 = crop 上边 - top。cropbox.y0≠0 也成立
                # (pymupdf 的 rect 已归一化到 (0,0,w,h))。
                landing = pg.cropbox.y1 - top
                if abs(pg.cropbox.y0) > 0.01:
                    note = (note + " ").strip() + (
                        f"cropbox.y0={pg.cropbox.y0:.2f}(set_toc 按 crop 高换算, "
                        f"会带来同量固定偏移)")
        out.append({
            "level": level, "title": title, "page": page1,
            "landing": None if landing is None else round(landing, 4),
            "view_top": None if landing is None else round(landing, 4),
            "verified": landing is not None,
            "reason": reason, "left": left, "top_native": top,
            "rotation": pg.rotation, "height": pg.cropbox.height,
            "xref": xref, "raw": raw, "note": note,
        })
    return out


# ------------------------------------------------- Q2: is it the right heading?

def landing_text(pg, landing, span=40.0):
    """Text in the band just below the landing line (empty for scans).

    Starts a few points *above* the line on purpose: headings often mix fonts,
    and characters whose bbox pokes above the clip would otherwise be dropped,
    producing a truncated first line that looks like a mismatch.
    """
    clip = pymupdf.Rect(pg.rect.x0, max(pg.rect.y0, landing - 4.0),
                        pg.rect.x1, min(pg.rect.y1, landing + span))
    try:
        return pg.get_text("text", clip=clip) or ""
    except Exception:
        return ""


def numkey(s):
    """(章, 条) 或 (None, 条); 无编号返回 None。容忍前导 § 与 / 。"""
    s = str(s or "").strip().lstrip("§").strip()
    m = re.match(r"^(\d{1,3})\s*[.．\-]\s*(\d{1,3})", s)
    if m:
        return (int(m.group(1)), int(m.group(2)))
    m = re.match(r"^(\d{1,3})\b", s)
    if m:
        return (None, int(m.group(1)))
    return None


def body_of(title):
    """标题去掉编号前缀后的正文(压缩空白)。"""
    s = str(title).strip().lstrip("§").strip()
    s = re.sub(r"^\d{1,3}\s*(?:[.．\-]\s*\d{1,3})?\s*[*·]?\s*", "", s)
    return re.sub(r"\s+", "", s)


def judge(title, text, expect=None):
    """Return (status, first_line).

    status: MATCH      编号与标题正文都对上(或纯编号标签的编号对上)
            WEAK_NUM   标题正文命中但编号文字层不可信(数学字体常丢字形)
            MISMATCH   两者都不命中 —— 疑似落在别的行上
            WEAK       非编号标题且正文未命中(多为图片页/扉页)
            NO_TEXT    无文字层(扫描件)
    """
    t = (text or "").strip()
    if not t:
        return "NO_TEXT", ""
    lines = [l for l in t.splitlines() if l.strip()]
    first = re.sub(r"\s+", " ", lines[0])[:88] if lines else ""
    flat = re.sub(r"\s+", "", t[:500])

    if expect not in (None, ""):
        return ("MATCH" if str(expect) in flat else "MISMATCH"), first

    k = numkey(title)
    body = body_of(title)
    body_ok = len(body) >= 2 and body[:6] in flat

    if k:
        cands = {(None, k[1])}
        if k[0] is not None:
            cands.add((k[0], k[1]))
        num_ok = any(numkey(l) in cands for l in lines[:2])
        if not num_ok and k[0] is not None and f"{k[0]}.{k[1]}" in flat:
            num_ok = True
        if num_ok:
            return "MATCH", first
        return ("WEAK_NUM" if body_ok else "MISMATCH"), first

    return ("MATCH" if body_ok else "WEAK"), first


# ---------------------------------------------------------------------- audit

def audit(doc, rows, items=None, tol=0.05, strict_text=False):
    problems, warnings = [], []
    n = len(rows)
    print(f"bookmarks            : {n}")
    print(f"levels               : {dict(sorted(Counter(r['level'] for r in rows).items()))}")

    dead = [r for r in rows if r["landing"] is None and "无原始目标" in r["reason"]]
    unfit = [r for r in rows if r["landing"] is None and "无纵坐标" in r["reason"]]
    unverified = [r for r in rows if r["landing"] is None and r["reason"]
                  and r not in dead and r not in unfit]

    if dead:
        problems.append(f"{len(dead)} 条没有原始目标(书签会失效)")
        for r in dead[:5]:
            print(f"  ! {r['title']!r} p{r['page']}  {r['reason']}  raw={r['raw'][:70]}")
    if unfit:
        warnings.append(f"{len(unfit)} 条目标不是 /XYZ, 无法核对纵坐标")
    if unverified:
        pages = sorted({r["page"] for r in unverified})
        warnings.append(f"{len(unverified)} 条无法用公式反算(页 {pages[:8]}"
                        f"{' ...' if len(pages) > 8 else ''}); 必须渲染核验")

    # --- Q1 口径: 原始 /XYZ 反算 vs 计划 y -------------------------------
    print()
    print("── Q1 口径核对(原始 /XYZ 反算 vs 计划 y) ─────────────────────")
    errs = []
    if not items:
        print("未提供 --items, 跳过与计划值的比对")
    else:
        if len(items) != n:
            problems.append(f"条目数不符: 树 {n} vs JSON {len(items)}")
        for r, it in zip(rows, items):
            if r["landing"] is None:
                continue
            errs.append((abs(r["landing"] - float(it["y"])), r["title"], r["page"],
                         r["landing"], float(it["y"]), it.get("page")))
        if errs:
            print(f"可比对              : {len(errs)}/{n} 条")
            dys = sorted(vt - y for _, _, _, vt, y, _ in errs)
            med = dys[len(dys) // 2]
            resid = max(abs(d - med) for d in dys)
            print(f"有符号偏移          : 中位 {med:+.3f} pt, 范围 [{dys[0]:+.2f}, {dys[-1]:+.2f}]")
            print(f"扣除中位后的最大偏差: {resid:.4f} pt")
            if abs(med) > 3.0:
                warnings.append(f"整体存在 {med:+.2f} pt 的常数偏移(标定残差, "
                                f"非随机错位); 如需精确对齐应补偿")
            off = [e for e in errs if abs((e[3] - e[4]) - med) > tol]
            if off:
                off.sort(key=lambda e: -abs((e[3] - e[4]) - med))
                problems.append(f"{len(off)} 条偏离中位超过 {tol} pt(疑似错位, 非常数偏移)")
                for dy, t, p, vt, y, pj in off[:10]:
                    pg_msg = "" if pj in (None, p) else f" (JSON 页 {pj})"
                    print(f"  ! {t!r} p{p}{pg_msg} view_top={vt:.2f} 计划 y={y:.2f} "
                          f"偏 {vt - y - med:+.2f}(扣除常数偏移后)")
            else:
                print(f"全部 {len(errs)} 条扣除常数偏移后一致(≤ {tol} pt)")
            print("  注: 这一项只证明写入没走样, 不证明计划 y 选对了标题 —— 见 Q2")

    # --- Q2 目标正确性: 落点下方是否是该编号的标题 -----------------------
    print()
    print("── Q2 目标正确性(落点下方是否是该编号的标题) ────────────────")
    stat, bad, weak, weaknum, scanned = Counter(), [], [], [], []
    for i, r in enumerate(rows):
        if r["landing"] is None:
            stat["未反算"] += 1
            continue
        pg = doc[r["page"] - 1]
        text = landing_text(pg, r["landing"])
        expect = None
        if items and i < len(items):
            expect = items[i].get("expect")
        status, first = judge(r["title"], text, expect)
        r["landing_text"] = first
        r["text_status"] = status
        stat[status] += 1
        if status == "MISMATCH":
            bad.append((r, first))
        elif status == "WEAK_NUM":
            weaknum.append((r, first))
        elif status == "WEAK":
            weak.append((r, first))
        elif status == "NO_TEXT":
            scanned.append(r)

    print(f"文字层命中          : {stat['MATCH']} 条(编号+正文对上) "
          f"+ {stat['WEAK_NUM']} 条(正文对上但编号字形丢失)")
    if stat["MISMATCH"]:
        print(f"文字层不命中        : {stat['MISMATCH']} 条")
    if stat["WEAK"]:
        print(f"无法据此判定        : {stat['WEAK']} 条(非编号标题/图片页)")
    if stat["NO_TEXT"]:
        print(f"无文字层(扫描件)     : {stat['NO_TEXT']} 条 —— 目标正确性无法自动验证")
    if bad:
        problems.append(f"{len(bad)} 条落点下方既非该编号、也非该标题正文")
        for r, first in bad[:12]:
            print(f"  ! {r['title']!r} p{r['page']} 落点下方: {first!r}")
    if weaknum:
        warnings.append(f"{len(weaknum)} 条靠标题正文命中, 编号字形在文字层丢失; "
                        f"若两条标题正文相近, 必须目视确认")
        for r, first in weaknum[:6]:
            print(f"  ~ {r['title']!r} p{r['page']} 落点下方: {first!r}")
    if weak:
        warnings.append(f"{len(weak)} 条标题非编号标签且文字前缀未命中, 建议目视")
        for r, first in weak[:6]:
            print(f"  ~ {r['title']!r} p{r['page']} 落点下方: {first!r}")

    # --- 树序、编号顺序、left -------------------------------------------
    prev, prev_r, nonmono = None, None, []
    for i, r in enumerate(rows):
        if r["landing"] is None:
            continue
        cur = (r["page"], round(r["landing"], 3))
        if prev and cur < prev:
            nonmono.append({"i": i, "prev": prev_r, "cur": r})
        prev, prev_r = cur, r
    if nonmono:
        # 报警不等于错误: 有的目录本来就允许同页内不按 y 递增列出(如索引/并列条目),
        # 裁决必须回到目录顺序与实际页面。
        warnings.append(f"{len(nonmono)} 处树序非单调(需按目录顺序与实际页面裁决, 不必然是错误)")
        for m in nonmono[:5]:
            a = (m["prev"]["page"], round(m["prev"]["landing"], 3))
            b = (m["cur"]["page"], round(m["cur"]["landing"], 3))
            print(f"  ~ 树序 {a} -> {b}  @{m['cur']['title']!r}")

    seq = [(int(m.group(1)), int(m.group(2)), r["title"])
           for r in rows for m in [NUMTITLE_RE.match(str(r["title"]).strip())] if m]
    bad_order = [(a, b) for a, b in zip(seq, seq[1:]) if (b[0], b[1]) < (a[0], a[1])]
    if bad_order:
        warnings.append(f"{len(bad_order)} 处编号顺序乱(如 12.10 排在 12.9 前)")
        for a, b in bad_order[:5]:
            print(f"  ~ 编号顺序 {a[2]} -> {b[2]}")

    out_of_page = [r for r in rows if r["landing"] is not None
                   and not (-1.0 <= r["landing"] <= r["height"] + 1.0)]
    if out_of_page:
        problems.append(f"{len(out_of_page)} 条落点越出页面")
        for r in out_of_page[:5]:
            print(f"  ! {r['title']!r} p{r['page']} view_top={r['landing']:.2f} H={r['height']:.2f}")

    lefts = Counter(round(r["left"], 1) for r in rows if r["left"] is not None)
    if lefts:
        print(f"left 取值            : {dict(lefts.most_common(4))}")

    # --- 覆盖范围声明 ---------------------------------------------------
    print()
    print("── 覆盖范围(据此判断结论能覆盖多少条) ───────────────────────")
    print(f"口径可反算          : {n - len(unverified) - len(dead) - len(unfit)}/{n}")
    if unverified:
        print(f"口径未验证          : {len(unverified)}/{n}  (旋转/裁切几何, 需渲染)")
    txt_ok = stat["MATCH"] + stat["WEAK_NUM"]
    print(f"目标自动可验        : {txt_ok}/{n}  (文字层比对, 含正文命中)")
    print(f"目标需目视          : {n - txt_ok}/{n}"
          + ("  <== 全部, 必须逐格看 --sheet 拼版" if txt_ok == 0 and n else ""))
    print("说明: 自动可验只是'落点下方文字与标题相符', 仍不等于排版上恰好压在标题上沿;")
    print("      扫描件与旋转页没有任何自动证据, 只能靠拼版逐格目视。")
    if strict_text and n and txt_ok < n:
        problems.append(f"--strict-text: {n - txt_ok} 条目标正确性未获自动证据")

    print()
    for w in warnings:
        print(f"WARN     {w}")
    for p in problems:
        print(f"PROBLEM  {p}")
    if not problems:
        if unverified:
            print(f"PARTIAL  口径自洽, 但只覆盖 {n - len(unverified) - len(dead) - len(unfit)}/{n} 条; "
                  f"其余须渲染核验 —— 不要把上面这句当成'全部验证通过'")
        else:
            print("OK  口径自洽; 目标正确性见上方覆盖范围")
    return problems, nonmono


# ------------------------------------------------- nonmono 裁决工作表

def write_nonmono_review(path, rows, nonmono):
    """Write a fill-in worksheet for every non-monotonic step.

    A non-monotonic tree is a *signal*, not a verdict: indexes, side-by-side
    entries and panel reading order can legitimately go back up the page.  The
    decision needs the printed TOC order, the actual page and the rendered
    landing.  This worksheet forces those four columns to be recorded so the
    decision can be audited later instead of living in someone's memory.
    """
    lines = [
        "# 树序非单调 裁决工作表",
        "",
        f"- 生成时间: {__import__('datetime').datetime.now():%Y-%m-%d %H:%M}",
        f"- 条目总数: {len(rows)}    非单调处: {len(nonmono)}",
        "- 落点由原始 `/XYZ` 反算(`view_top = crop.y1 - top`), 与计划 JSON 无关。",
        "",
        "裁决栏只允许填下面四种之一, 并必须在「依据」里写清看了什么:",
        "",
        "| 裁决 | 含义 |",
        "|---|---|",
        "| `keep` | 合理非单调(索引/并列条目/分栏阅读顺序), 保留现状 |",
        "| `fix-landing` | 顺序对, 落点错(压错了行) —— 重定位后重跑本工具 |",
        "| `fix-order` | 落点对, 顺序错(树序与印刷目录不符) —— 调整树序 |",
        "| `unresolved` | 证据不足(缺原页/缺目录), 不得当成已通过 |",
        "",
        "## 明细",
        "",
        "| # | 树序 | 前置条目 | 前置 p/落点 | 当前条目 | 当前 p/落点 | 同页 | 目录里的先后 | 裁决 | 依据(印刷目录行/渲染图) |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]

    def cell(s, limit=40):
        s = re.sub(r"\s+", " ", str(s or "")).strip()
        return (s[:limit] + "…") if len(s) > limit else s

    for k, m in enumerate(nonmono, 1):
        a, b = m["prev"], m["cur"]
        same = "是" if a["page"] == b["page"] else "否"
        lines.append(
            f"| {k} | #{m['i'] + 1} | {cell(a['title'])} | p{a['page']}/{a['landing']:.2f} "
            f"| {cell(b['title'])} | p{b['page']}/{b['landing']:.2f} | {same} | 待核 "
            f"|  |  |")

    lines += [
        "",
        "## 结论",
        "",
        "- `keep` 共 ___ 处；`fix-landing` ___ 处；`fix-order` ___ 处；`unresolved` ___ 处。",
        "- 汇报时照抄这四个数字；`keep` 必须附一句理由(为什么这处回退是原书编排),",
        "  不能只写「已解释」。",
        "",
    ]
    with open(path, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lines))
    print(f"写出非单调裁决工作表 {path}  ({len(nonmono)} 处待裁决)")


# --------------------------------------------------------------------- sheets

def make_sheets(doc, rows, outdir, per=30, width=780, labw=175, every=1):
    from PIL import Image, ImageDraw, ImageFont
    os.makedirs(outdir, exist_ok=True)

    dropped = [r for r in rows if r["landing"] is None]
    if dropped:
        pages = sorted({r["page"] for r in dropped})
        print(f"WARN  拼版无法覆盖 {len(dropped)} 条(无 /XYZ 纵坐标或旋转页), "
              f"页 {pages[:8]}{' ...' if len(pages) > 8 else ''} —— 这些条目须另看原页")

    def _font(paths, size):
        for p in paths:
            try:
                return ImageFont.truetype(p, size)
            except OSError:
                continue
        return ImageFont.load_default()

    f = _font(["C:/Windows/Fonts/arialbd.ttf"], 22)
    fs = _font(["C:/Windows/Fonts/arial.ttf"], 17)
    f_cjk = _font(["C:/Windows/Fonts/msyh.ttc", "C:/Windows/Fonts/msyhbd.ttc",
                   "C:/Windows/Fonts/simhei.ttf", "C:/Windows/Fonts/simsun.ttc"], 20)
    rows = [r for r in rows if r["landing"] is not None][::max(1, every)]
    made = []
    for si in range(0, len(rows), per):
        chunk = rows[si:si + per]
        cells = []
        for r in chunk:
            pg, vt = doc[r["page"] - 1], r["landing"]
            clip = pymupdf.Rect(0, max(0, vt - 14), pg.rect.width,
                                min(pg.rect.height, vt + 34))
            sc = width / pg.rect.width
            pix = pg.get_pixmap(matrix=pymupdf.Matrix(sc, sc), clip=clip)
            img = Image.frombytes("RGB", (pix.width, pix.height), pix.samples)
            cv = Image.new("RGB", (labw + img.width, max(img.height, 46)), "white")
            cv.paste(img, (labw, 0))
            dr = ImageDraw.Draw(cv)
            m = NUMTITLE_RE.match(str(r["title"]).strip())
            if m:
                lab, lf = f"c{m.group(1)} n{m.group(2)}", f
            else:
                lab, lf = str(r["title"])[:12], f_cjk
            dr.text((6, 1), lab, fill=(180, 0, 0), font=lf)
            dr.text((6, 27), f"p{r['page']}", fill=(0, 0, 200), font=fs)
            off = int(img.height * (14 / (clip.y1 - clip.y0)))
            dr.line([(labw, off), (labw + img.width, off)], fill=(255, 0, 0), width=3)
            dr.rectangle([labw, 0, labw + img.width - 1, img.height - 1],
                         outline=(160, 160, 160))
            cells.append(cv)
        h = sum(c.height + 3 for c in cells)
        w = max(c.width for c in cells)
        sheet = Image.new("RGB", (w, h), "white")
        y = 0
        for c in cells:
            sheet.paste(c, (0, y))
            y += c.height + 3
        name = os.path.join(outdir, f"landing_{si // per + 1:02d}.png")
        sheet.save(name)
        made.append(name)
    print(f"拼版 {len(made)} 张 -> {outdir}  (红线由原始 /XYZ 反算, 与计划 JSON 无关)")
    return made


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("pdf")
    ap.add_argument("--items", help="规划用 JSON: [{level,page,title,y,expect?}]")
    ap.add_argument("--tol", type=float, default=0.5,
                    help="判为错位的阈值(pt), 默认 0.5pt≈0.18mm 肉眼不可辨")
    ap.add_argument("--sheet", help="输出拼版图目录(红线由原始 /XYZ 反算)")
    ap.add_argument("--nonmono-review",
                    help="把每处树序非单调写成可填写的裁决工作表(markdown)")
    ap.add_argument("--every", type=int, default=1, help="拼版抽样步长(默认 1=全量)")
    ap.add_argument("--json", help="把逐条反算结果(含落点文字)写成 JSON")
    ap.add_argument("--strict-text", action="store_true",
                    help="无文字层/无法证明目标正确性时返回非零(强制先看拼版)")
    args = ap.parse_args()

    doc = pymupdf.open(args.pdf)
    rows = raw_dests(doc)
    items = None
    if args.items:
        raw_items = json.load(open(args.items, encoding="utf-8-sig"))
        items = [{"level": it.get("level", it.get("lv")), "page": it["page"],
                  "title": it.get("title", ""), "y": float(it["y"]),
                  "expect": it.get("expect")} for it in raw_items]
    problems, nonmono = audit(doc, rows, items, tol=args.tol,
                              strict_text=args.strict_text)
    if args.nonmono_review:
        write_nonmono_review(args.nonmono_review, rows, nonmono)
    if args.json:
        json.dump(rows, open(args.json, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print(f"写出 {args.json}")
    if args.sheet:
        make_sheets(doc, rows, args.sheet, every=args.every)
    doc.close()
    sys.exit(1 if problems else 0)


if __name__ == "__main__":
    main()
