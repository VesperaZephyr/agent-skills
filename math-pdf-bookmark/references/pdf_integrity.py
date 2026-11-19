"""Prove (or refute) that a PDF rewrite left the *page content* untouched.

Why this tool exists
--------------------
Comparing only image streams answers "did the scans change?", not "is the
document lossless?".  A PDF page also carries a text layer, vector drawings,
fonts, annotations, links, form fields and its own geometry; any of those can
be damaged by a re-save while every image stays byte-identical.  This tool
compares all of those facets per page, and separates

    CONTENT_DIFF   real content change                     -> hard failure
    RECOMPRESSED   stream bytes differ, decoded content identical
                   (e.g. deflate re-run)                    -> soft, listed
    META           document-level metadata differs          -> soft, listed
    UNVERIFIED     a facet could not be read on one side    -> never "equal"

Coverage, stated honestly
-------------------------
This is a *strong* check, not a proof of "everything is intact".  It cannot
see what PyMuPDF cannot read:

* links are compared by kind / target page / ``to`` point / URI / file /
  named destination / click rect -- a URI that both sides fail to expose is
  invisible, and launch/remote actions outside that tuple are not enumerated;
* form widgets are compared by name / type / value / flags / rect / choice
  values -- appearance streams and JavaScript actions are not compared;
* a facet that raises on either side is reported as ``UNVERIFIED`` and the
  run can never print a clean ``OK`` (exit 2).  It is **not** silently
  treated as "both empty, therefore equal".

So a pass supports "no *detected* content change in the compared facets";
it does not license the sentence "all content and interactions are intact".
Say "逐页 facet 比对未见差异 (范围见工具头)".

The outline/bookmarks are deliberately NOT compared: they are the thing a
bookmark job rewrites on purpose.  Use ``landing_audit.py`` for those.

Never used as a comparison key: xref numbers.  They are renumbered by
``save``/``garbage=``, so comparing them reports "every object differs".

Usage
-----
    python pdf_integrity.py --base ORIG.pdf --new REWRITTEN.pdf
    python pdf_integrity.py --base A.pdf --new B.pdf --pages 1-40,300
    python pdf_integrity.py --base A.pdf --new B.pdf --json diff.json

Exit codes: 0 = no hard difference and nothing unverified
            2 = no hard difference, but some facets/targets could not be read
                (coverage incomplete -- do not call this "lossless")
            1 = at least one hard difference (CONTENT_DIFF / page-count /
                page-label change)
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys

try:
    import pymupdf
except ImportError:  # older wheels
    import fitz as pymupdf


def _digest(data) -> str:
    if isinstance(data, str):
        data = data.encode("utf-8", "surrogatepass")
    return hashlib.sha1(data or b"").hexdigest()


def _num(v):
    """Normalise geometry values so repr() is stable across saves."""
    if isinstance(v, (int, float)):
        return round(float(v), 4)
    if isinstance(v, (list, tuple)):
        return tuple(_num(x) for x in v)
    for attr in ("x", "y"):  # pymupdf.Point
        if hasattr(v, attr) and not isinstance(v, (str, bytes)):
            try:
                return tuple(_num(c) for c in v)
            except TypeError:
                break
    for attr in ("x0", "y0", "x1", "y1"):  # pymupdf.Rect
        if hasattr(v, attr) and not isinstance(v, (str, bytes)):
            try:
                return tuple(_num(c) for c in v)
            except TypeError:
                break
    return repr(v)


def page_facets(doc, pno):
    """Everything on page ``pno`` (0-based) that a viewer can show.

    Returns ``(facets, unverified)``: ``unverified`` names the facets whose
    read raised (or returned nothing where something was expected).  Callers
    must exclude those from the equality test instead of comparing two Nones.
    """
    pg = doc[pno]
    unv = set()
    f = {}

    f["rect"] = _num(tuple(pg.rect))
    f["media"] = _num(tuple(pg.mediabox))
    f["crop"] = _num(tuple(pg.cropbox))
    f["rotation"] = pg.rotation

    # 内容流: 原始字节 与 解码后字节 分别取摘要
    try:
        contents = pg.get_contents() or []
    except Exception:
        contents = None
    if contents is None:
        unv.update(("stream_raw", "stream_dec"))
        f["stream_raw"] = f["stream_dec"] = None
    else:
        raw, dec, bad = [], [], False
        for x in contents:
            try:
                r = doc.xref_stream_raw(x)
                d = doc.xref_stream(x)
            except Exception:
                r = d = None
            if r is None or d is None:
                bad = True
                break
            raw.append(r)
            dec.append(d)
        if bad:
            unv.update(("stream_raw", "stream_dec"))
            f["stream_raw"] = f["stream_dec"] = None
        else:
            f["stream_raw"] = _digest(b"".join(raw))
            f["stream_dec"] = _digest(b"".join(dec))

    # 文字层: 全文本 + 逐词坐标(能抓出"文字位置被挪动"这类改写)
    try:
        f["text"] = _digest(pg.get_text("text"))
    except Exception:
        unv.add("text")
        f["text"] = None
    try:
        words = pg.get_text("words")
        f["word_geom"] = _digest(repr([(w[4], _num(w[:4])) for w in words]))
        f["nwords"] = len(words)
    except Exception:
        unv.update(("word_geom", "nwords"))
        f["word_geom"] = f["nwords"] = None

    # 图像: 尺寸/位深/色彩空间 + 解码字节(不含 xref)
    imgs, bad = [], False
    try:
        infos = pg.get_images(full=True)
    except Exception:
        infos, bad = [], True
    for info in infos:
        xref = info[0]
        try:
            d = doc.xref_stream(xref)
            r = doc.xref_stream_raw(xref)
        except Exception:
            d = r = None
        if d is None or r is None:
            bad = True
            break
        imgs.append((info[2], info[3], info[4], info[5], _digest(d), _digest(r)))
    if bad:
        unv.add("images")
        f["images"] = None
    else:
        f["images"] = tuple(sorted(imgs))

    # 字体: 名称/类型/编码/是否内嵌(不含 xref)
    try:
        fonts = [tuple(str(v) for v in fo[1:]) for fo in pg.get_fonts(full=True)]
        f["fonts"] = tuple(sorted(fonts))
    except Exception:
        unv.add("fonts")
        f["fonts"] = None

    # 矢量绘图: 操作符与几何
    try:
        draws = pg.get_drawings()
    except Exception:
        unv.update(("ndraw", "draw_geom"))
        f["ndraw"] = f["draw_geom"] = None
    else:
        f["ndraw"] = len(draws)
        f["draw_geom"] = _digest(repr([(d.get("type"),
                                        _num([it for it in d.get("items", [])]))
                                       for d in draws]))

    # 链接: kind / 目标页 / to 点 / URI / 文件 / 命名目标 / 点击区
    # (旧版只留 kind+page+rect, 两个不同网址会被当成"相同")
    try:
        links = [(l.get("kind"), l.get("page"), _num(l.get("to")),
                  l.get("uri") or "", l.get("file") or "",
                  l.get("nameddest") or "", _num(l.get("from")))
                 for l in pg.get_links()]
        f["links"] = tuple(sorted(links, key=repr))
    except Exception:
        unv.add("links")
        f["links"] = None

    # 注释
    try:
        annots = []
        for a in (pg.annots() or []):
            info = a.info or {}
            annots.append((a.type[1] if a.type else "",
                           _digest(info.get("content", "")),
                           _digest(info.get("title", "")),
                           info.get("subject", "") or "",
                           _num(tuple(a.rect))))
        f["annots"] = tuple(sorted(annots, key=repr))
    except Exception:
        unv.add("annots")
        f["annots"] = None

    # 表单控件: 名称/类型/当前值/标志/可选项/位置
    # (旧版只比名称与位置, 字段值被改掉也报"一致")
    try:
        widgets = []
        for w in (pg.widgets() or []):
            try:
                choices = tuple(w.choice_values or ())
            except Exception:
                choices = ()
            widgets.append((w.field_name or "", w.field_type_string or "",
                            "" if w.field_value is None else str(w.field_value),
                            int(getattr(w, "field_flags", 0) or 0),
                            choices, _num(tuple(w.rect))))
        f["widgets"] = tuple(sorted(widgets, key=repr))
    except Exception:
        unv.add("widgets")
        f["widgets"] = None

    return f, unv


FACET_LABEL = {
    "rect": "页面尺寸", "media": "MediaBox", "crop": "CropBox", "rotation": "旋转",
    "stream_raw": "内容流(原始)", "stream_dec": "内容流(解码)", "text": "文字层",
    "word_geom": "文字坐标", "nwords": "词数", "images": "图像", "fonts": "字体",
    "ndraw": "矢量对象数", "draw_geom": "矢量几何", "links": "链接",
    "annots": "注释", "widgets": "表单控件",
}

DOC_LABEL = {"labels": "页码标签", "embfiles": "嵌入文件", "meta": "元数据"}


def parse_pages(spec, total):
    if not spec:
        return list(range(total))
    out = []
    for part in spec.split(","):
        part = part.strip()
        if not part:
            continue
        m = re.match(r"^(\d+)\s*-\s*(\d+)$", part)
        if m:
            a, b = int(m.group(1)), int(m.group(2))
            out.extend(range(max(1, a) - 1, min(total, b)))
        elif part.isdigit():
            if 1 <= int(part) <= total:
                out.append(int(part) - 1)
        else:
            raise SystemExit(f"无法解析页范围: {part!r}")
    return sorted(set(out))


def doc_facets(doc):
    unv = set()
    d = {"pages": doc.page_count, "encrypted": bool(doc.is_encrypted)}
    try:
        d["labels"] = json.loads(json.dumps(doc.get_page_labels(), default=str))
    except Exception:
        unv.add("labels")
        d["labels"] = None
    try:
        d["embfiles"] = tuple(sorted(
            getattr(doc, "embfile_names", lambda: [])()))
    except Exception:
        unv.add("embfiles")
        d["embfiles"] = None
    try:
        meta = dict(doc.metadata or {})
    except Exception:
        unv.add("meta")
        meta = {}
    return d, meta, unv


def collect(a, b, pages):
    """Per-page comparison, returning (rows, stats)."""
    rows, content_diff, recompressed, unverified, clean = [], [], [], [], 0
    for pno in pages:
        fa, ua = page_facets(a, pno)
        fb, ub = page_facets(b, pno)
        skip = ua | ub
        diffs = [k for k in fa if k not in skip and fa[k] != fb[k]]
        row = {"page": pno + 1, "differs": diffs, "unverified": sorted(skip)}
        if diffs or skip:
            rows.append(row)
        if skip:
            unverified.append(row)
        if not diffs:
            if not skip:
                clean += 1
        elif diffs == ["stream_raw"]:
            recompressed.append(pno + 1)
        else:
            content_diff.append((pno + 1, diffs))
    return rows, {"clean": clean, "content_diff": content_diff,
                  "recompressed": recompressed, "unverified": unverified}


def compare(base_path, new_path, pages_spec=None, verbose=False, json_path=None):
    a, b = pymupdf.open(base_path), pymupdf.open(new_path)
    da, meta_a, dua = doc_facets(a)
    db, meta_b, dub = doc_facets(b)
    print(f"base : {base_path}  ({da['pages']} 页)")
    print(f"new  : {new_path}  ({db['pages']} 页)")
    print("比较范围: 页面内容全部 facet(尺寸/旋转/内容流/文字层/文字坐标/图像/"
          "字体/矢量/链接(含网址)/注释/控件(含字段值));")
    print("          书签不在比较范围内(那是本次要改的东西)。读取失败的 facet 记为"
          " UNVERIFIED, 不当作'两侧都空=相等'。")

    hard, soft, unver = [], [], []
    if da["pages"] != db["pages"]:
        hard.append(f"页数不同: {da['pages']} vs {db['pages']}")
    for key in ("labels", "encrypted", "embfiles"):
        if key in (dua | dub):
            unver.append(f"文档级 {DOC_LABEL.get(key, key)} 读取失败, 未验证")
            continue
        if da[key] != db[key]:
            hard.append(f"文档级 {DOC_LABEL.get(key, key)} 不同")
    if "meta" in (dua | dub):
        unver.append("文档级 元数据 读取失败, 未验证")
    elif meta_a != meta_b:
        diff_keys = sorted(k for k in set(meta_a) | set(meta_b)
                           if meta_a.get(k) != meta_b.get(k))
        soft.append(f"元数据不同: {diff_keys}")

    rows, stats = [], {"clean": 0, "content_diff": [], "recompressed": [],
                       "unverified": []}
    if da["pages"] == db["pages"]:
        pages = parse_pages(pages_spec, da["pages"])
        rows, stats = collect(a, b, pages)
    a.close(); b.close()

    for pno, diffs in stats["content_diff"]:
        if verbose or len(stats["content_diff"]) <= 20:
            print(f"  ! p{pno}: " + ", ".join(FACET_LABEL.get(k, k) for k in diffs))
    for pno, bad in [(r["page"], r["unverified"]) for r in stats["unverified"]]:
        if verbose or len(stats["unverified"]) <= 20:
            print(f"  ? p{pno}: 未验证 " + ", ".join(FACET_LABEL.get(k, k) for k in bad))

    if da["pages"] != db["pages"]:
        for msg in soft:
            print(f"WARN     {msg}")
        for msg in unver:
            print(f"UNKNOWN  {msg}")
        for msg in hard:
            print(f"PROBLEM  {msg}")
        if json_path:
            json.dump([{"page": None, "differs": [], "unverified": []}],
                      open(json_path, "w", encoding="utf-8"),
                      ensure_ascii=False, indent=1)
        return 1

    pages = parse_pages(pages_spec, da["pages"])
    print()
    print(f"逐页比较            : {len(pages)} 页")
    print(f"内容一致            : {stats['clean']} 页")
    if stats["unverified"]:
        print(f"未验证(读取失败)     : {len(stats['unverified'])} 页(见上方 ? 行; 这些项没有证据)")
    if stats["recompressed"]:
        rc = stats["recompressed"]
        print(f"仅流字节不同(重压缩) : {len(rc)} 页 -> {rc[:12]}"
              f"{' ...' if len(rc) > 12 else ''}")
        soft.append(f"{len(rc)} 页内容流字节变化但解码内容一致(重压缩)")
    if stats["content_diff"]:
        cd = stats["content_diff"]
        hard.append(f"{len(cd)} 页内容不同: "
                    + ", ".join(f"p{p}" for p, _ in cd[:12])
                    + (" ..." if len(cd) > 12 else ""))
    if stats["unverified"]:
        uv = [r["page"] for r in stats["unverified"]]
        unver.append(f"{len(uv)} 页存在读取失败的 facet(详见上表): "
                     + ", ".join(f"p{p}" for p in uv[:12])
                     + (" ..." if len(uv) > 12 else "")
                     + " —— 这些项没有任何证据, 不能算'一致'")

    for msg in soft:
        print(f"WARN     {msg}")
    for msg in unver:
        print(f"UNKNOWN  {msg}")
    for msg in hard:
        print(f"PROBLEM  {msg}")

    if not hard and not unver:
        if stats["recompressed"]:
            print(f"OK  页面内容一致({len(stats['recompressed'])} 页仅内容流字节重压缩, "
                  f"解码后相同); 范围见工具头")
        else:
            print("OK  所比 facet 逐页一致(范围见工具头; 未覆盖的交互类型不算已证)")
    elif not hard:
        print("PARTIAL  无硬差异, 但覆盖不完整: 不得据此宣称全量无损")

    if json_path:
        json.dump(rows or [], open(json_path, "w", encoding="utf-8"),
                  ensure_ascii=False, indent=1)
        print(f"写出 {json_path}")
    return 1 if hard else (2 if unver else 0)


def main():
    ap = argparse.ArgumentParser(description=__doc__,
                                 formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", required=True, help="原始 PDF(未改动)")
    ap.add_argument("--new", required=True, help="重写后的 PDF")
    ap.add_argument("--pages", help='只比较这些页, 如 "1-40,300" (默认全书)')
    ap.add_argument("--json", help="把逐页差异写成本 JSON")
    ap.add_argument("--verbose", action="store_true", help="打印全部差异页")
    args = ap.parse_args()

    rc = compare(args.base, args.new, args.pages, args.verbose, args.json)
    sys.exit(rc)


if __name__ == "__main__":
    main()
