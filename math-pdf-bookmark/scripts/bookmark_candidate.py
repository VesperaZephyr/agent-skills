"""Create a calibrated bookmark candidate; never modify the source PDF."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import re
import shutil
import tempfile

import pymupdf

XYZ_RE = re.compile(r"/XYZ\s+(-?[\d.]+|-?null)\s+(-?[\d.]+|-?null)")


def raw_dest_top(doc, item_xref):
    """Read the stored /XYZ top, i.e. the truth a viewer uses.

    get_toc()['to'].y merely converts this back to "distance from page top",
    so comparing it with your own input is circular and can never detect a
    coordinate-system mistake (see detailed-rules.md rule 23).
    """
    if not item_xref:
        return None
    for key in ("A", "Dest"):
        kind, val = doc.xref_get_key(item_xref, key)
        if kind != "null" and "/XYZ" in (val or ""):
            match = XYZ_RE.search(val)
            if match and match.group(2) not in ("null", None):
                return float(match.group(2))
    return None


def digest(data):
    return hashlib.sha256(data or b'').hexdigest()


def signature(doc):
    """页面内容签名: 几何 + 文字层 + 内容流 + 图像 + 字体 + 矢量 + 链接。

    只比图像流不足以证明"正文无损": 文字层、矢量绘图、字体资源同样可能被
    重写破坏。也不拿 xref 编号当比较键 —— 重写后 xref 必然变化。
    """
    cache = {}

    def stream(xref):
        if xref not in cache:
            cache[xref] = digest(doc.xref_stream_raw(xref))
        return cache[xref]

    pages = []
    for page in doc:
        rects = tuple(tuple(round(float(v), 4) for v in r)
                      for r in (page.rect, page.mediabox, page.cropbox))
        contents = tuple(stream(x) for x in page.get_contents())
        images = tuple((tuple(info[2:]), stream(info[0]),
                        stream(info[1]) if info[1] else None)
                       for info in page.get_images(full=True))
        fonts = tuple(sorted(tuple(str(v) for v in f[1:])
                             for f in page.get_fonts(full=True)))
        try:
            ndraw = len(page.get_drawings())
        except Exception:
            ndraw = -1
        pages.append((rects, digest(page.get_text().encode('utf-8')), contents, images,
                      fonts, ndraw, len(page.get_links()), page.rotation))
    return (len(doc), doc.metadata, doc.get_page_labels(), pages)


def load_items(path, doc):
    items = json.loads(path.read_text(encoding='utf-8-sig'))
    if not isinstance(items, list) or not items:
        raise ValueError('条目文件必须是非空 JSON 数组')
    previous_level = 0
    for i, item in enumerate(items, 1):
        level, page, title, y = (item.get(k) for k in ('level', 'page', 'title', 'y'))
        if (type(level) is not int or level < 1 or level > previous_level + 1
                or type(page) is not int or not 1 <= page <= len(doc)
                or not isinstance(title, str) or not title.strip()
                or isinstance(y, bool) or not isinstance(y, (int, float))
                or not math.isfinite(y) or not 0 <= y <= doc[page- 1].rect.height):
            raise ValueError(f'第 {i} 条格式、层级、页码或坐标无效: {item!r}')
        previous_level = level
    return items


def build(source, items_path, output, report):
    paths = [p.resolve() for p in (source, items_path, output, report)]
    if len(set(paths)) != 4:
        raise ValueError('源文件、条目、候选文件和报告路径必须不同')
    if output.exists() or report.exists():
        raise FileExistsError('候选文件或报告已存在，请指定新路径')
    if not output.parent.is_dir() or not report.parent.is_dir():
        raise ValueError('输出目录必须已存在')
    with pymupdf.open(source) as original:
        items = load_items(items_path, original)
        rotated = sorted({it['page'] for it in items
                          if original[it['page'] - 1].rotation})
        if rotated:
            n_rot = sum(1 for it in items if original[it['page'] - 1].rotation)
            raise ValueError(
                f'{n_rot} 条书签落在 rotation≠0 的页 {rotated[:8]}。'
                'set_toc 对旋转页会额外套 rotation_matrix(纵横轴互换), '
                '两探针标定 k 会退化为 0 —— 本工具拒绝在无法验证的情况下写入。'
                '请把这些页按规则 26 单独处理(渲染确认显示方向后再定落点)。')
        before = signature(original)
    fd, temp_name = tempfile.mkstemp(prefix='.bookmark-candidate-', suffix='.pdf', dir=output.parent)
    os.close(fd)
    temp = Path(temp_name)
    try:
        shutil.copyfile(source, temp)
        with pymupdf.open(temp) as doc:
            def probe(values):
                doc.set_toc([[item['level'], f'probe-{i}', item['page'], value]
                             for i, (item, value) in enumerate(zip(items, values))])
                return [float(row[3]['to'].y) for row in doc.get_toc(simple=False)]
            ys = [float(item['y']) for item in items]
            a, b = probe(ys), probe([y + 37 for y in ys])
            calibrated = []
            for y, first, second in zip(ys, a, b):
                k = (second - first) / 37
                if not math.isfinite(k) or abs(abs(k) - 1) > 0.02:
                    raise ValueError(f'坐标变换异常: k={k}，请人工检查页面')
                offset = first - k * y
                calibrated.append((y - offset) / k)
            doc.set_toc([[item['level'], item['title'], item['page'], value]
                         for item, value in zip(items, calibrated)])
            doc.saveIncr()
        with pymupdf.open(temp) as doc:
            if signature(doc) != before:
                raise ValueError('页面内容或元数据与原件不一致')
            toc = doc.get_toc(simple=False)
            expected = [(x['level'], x['title'], x['page']) for x in items]
            if [tuple(row[:3]) for row in toc] != expected:
                raise ValueError('回读书签结构与输入不一致')
            errors = [abs(float(row[3]['to'].y) - y) for row, y in zip(toc, ys)]
            if max(errors) > 0.05:
                raise ValueError(f'回读落点误差过大: {max(errors):.6f} pt')
            # 上面的回读恒等于输入, 是循环验证(见 detailed-rules.md 规则 23)。
            # 真正的落点必须从原始 /XYZ 反算。**无法用公式反算的页(旋转页)既不能
            # 断言通过, 也不能算进误差最大值**, 必须单列为 unverified 并写进报告,
            # 否则"max_error 很小"会被误读成"全都验证过了"。
            raw_errors, unverified = [], []
            for row, y, item in zip(toc, ys, items):
                top = raw_dest_top(doc, row[3].get('xref'))
                page = doc[item['page'] - 1]
                if top is None:
                    unverified.append((item['title'], item['page'], '无 /XYZ 目标'))
                elif page.rotation:
                    unverified.append((item['title'], item['page'],
                                       f'rotation={page.rotation}'))
                else:
                    raw_errors.append((item['title'],
                                       abs(page.cropbox.y1 - top - y)))
            dead = [t for t, _, why in unverified if why == '无 /XYZ 目标']
            if dead:
                raise ValueError(f'{len(dead)} 条没有 /XYZ 目标(书签会失效): {dead[:3]}')
            raw_max = max((e for _, e in raw_errors), default=0.0)
            if raw_max > 0.5:
                raise ValueError(
                    f'原始 /XYZ 反算落点与目标差 {raw_max:.4f} pt。'
                    ' set_toc 的 y / to.y 语义是"距页顶磅数", 不要再按页高翻转 —— '
                    'double flip 会让每条都跳到镜像位置(详见 detailed-rules.md 硬规则 23)。')
            scope = f'{len(raw_errors)}/{len(items)}'
        # Exclusive creation avoids replacing a file that appeared during processing.
        created = False
        try:
            with output.open('xb') as target, temp.open('rb') as src:
                created = True
                shutil.copyfileobj(src, target)
        except Exception:
            if created:
                output.unlink(missing_ok=True)
            raise
        try:
            with report.open('x', encoding='utf-8', newline='\n') as f:
                f.write(f'entries={len(items)}\n')
                f.write('readback_error_pt={:.6f}  # 循环验证: 只证明树写进去了\n'
                        .format(max(errors)))
                f.write(f'raw_xyz_checked={scope}\n')
                f.write(f'raw_xyz_max_error_pt={raw_max:.6f}\n')
                f.write(f'raw_xyz_unverified={len(unverified)}\n')
                for title, page, why in unverified:
                    f.write(f'unverified\t{title}\tp{page}\t{why}\n')
                f.write('page_content_metadata_labels_unchanged=True'
                        '  # 几何+文字层+内容流+图像+字体+矢量+链接\n')
                for i, (item, err) in enumerate(zip(items, errors), 1):
                    f.write(f"{i:03d}\t{item['title']}\tp{item['page']}\ty={item['y']}\terror={err:.6f}\n")
        except Exception:
            output.unlink()
            raise
        print(f'候选文件: {output}\n条目: {len(items)}'
              f'，回读误差: {max(errors):.6f} pt(循环验证, 仅证明结构)'
              f'，原始 /XYZ 落点偏差: {raw_max:.6f} pt'
              f'，覆盖 {scope}')
        if unverified:
            pages = sorted({p for _, p, _ in unverified})
            print(f'  ! 有 {len(unverified)} 条无法用公式反算(页 {pages[:8]}'
                  f'{" ..." if len(pages) > 8 else ""}): 旋转页/无纵坐标。'
                  f' 这些条目的落点**尚未验证**, 必须渲染逐格核验, 不要引用上面的 max 值。')
    finally:
        temp.unlink(missing_ok=True)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('source', type=Path)
    parser.add_argument('items', type=Path)
    parser.add_argument('output', type=Path)
    parser.add_argument('--report', type=Path, required=True)
    args = parser.parse_args()
    build(args.source, args.items, args.output, args.report)


if __name__ == '__main__':
    main()
