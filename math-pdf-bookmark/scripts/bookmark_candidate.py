"""Create a calibrated bookmark candidate; never modify the source PDF."""
import argparse
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import tempfile

import pymupdf


def digest(data):
    return hashlib.sha256(data or b'').hexdigest()


def signature(doc):
    cache = {}
    def stream(xref):
        if xref not in cache:
            cache[xref] = digest(doc.xref_stream_raw(xref))
        return cache[xref]
    pages = []
    for page in doc:
        rects = tuple(tuple(round(float(v), 4) for v in r)
                      for r in (page.rect, page.mediabox, page.cropbox))
        contents = tuple((x, stream(x)) for x in page.get_contents())
        images = tuple((info, stream(info[0]), stream(info[1]) if info[1] else None)
                       for info in page.get_images(full=True))
        pages.append((rects, digest(page.get_text().encode('utf-8')), contents, images))
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
                f.write(f'entries={len(items)}\nmax_error_pt={max(errors):.6f}\n')
                f.write('page_content_metadata_labels_unchanged=True\n')
                for i, (item, err) in enumerate(zip(items, errors), 1):
                    f.write(f"{i:03d}\t{item['title']}\tp{item['page']}\ty={item['y']}\terror={err:.6f}\n")
        except Exception:
            output.unlink()
            raise
        print(f'候选文件: {output}\n条目: {len(items)}，最大回读误差: {max(errors):.6f} pt\n报告: {report}')
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
