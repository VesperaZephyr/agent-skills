"""Create a page-label candidate without modifying the source.

Usage: python page_labels_candidate.py SOURCE.pdf PLAN.json OUTPUT.pdf --report REPORT.json
PLAN is a UTF-8 JSON array of segments, using 1-based physical start pages:
[{"page":1,"prefix":"Cover"},{"page":2,"prefix":"Intro-","style":"r","start":1},
 {"page":5,"style":"D","start":1}]
Styles: D (decimal), r/R (Roman), a/A (PDF alphabetic). A prefix-only
segment is for one unnumbered page. This tool cannot verify the plan against
printed pages. It refuses duplicate labels, existing outputs, malformed plans,
and unverified or changed content. It never overwrites the original PDF.
"""
import argparse
import collections
import hashlib
import json
import os
from pathlib import Path
import shutil
import tempfile

import pymupdf
from pdf_integrity import collect, doc_facets


def sha256(path):
    h = hashlib.sha256()
    with path.open('rb') as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b''):
            h.update(chunk)
    return h.hexdigest()


def suffix(style, value):
    if style == 'D':
        return str(value)
    if style in ('a', 'A'):
        # PDF alphabetic numbering is A..Z, AA..ZZ, AAA..ZZZ, not Excel columns.
        return chr((65 if style == 'A' else 97) + (value - 1) % 26) * ((value - 1) // 26 + 1)
    if style in ('r', 'R'):
        if value > 3999:
            raise ValueError('罗马数字超过 3999，请调整分段')
        out = ''
        for n, token in ((1000,'M'),(900,'CM'),(500,'D'),(400,'CD'),(100,'C'),(90,'XC'),(50,'L'),(40,'XL'),(10,'X'),(9,'IX'),(5,'V'),(4,'IV'),(1,'I')):
            count, value = divmod(value, n)
            out += token * count
        return out if style == 'R' else out.lower()
    raise ValueError(f'不支持的编号样式: {style!r}')


def plan_labels(plan, count):
    if not isinstance(plan, list) or not plan:
        raise ValueError('方案必须是非空 JSON 数组')
    rules = []
    for i, seg in enumerate(plan):
        if not isinstance(seg, dict) or set(seg) - {'page', 'prefix', 'style', 'start'}:
            raise ValueError(f'第 {i+1} 段字段无效')
        page, prefix, style = seg.get('page'), seg.get('prefix', ''), seg.get('style')
        if type(page) is not int or not 1 <= page <= count:
            raise ValueError(f'第 {i+1} 段物理页无效')
        if (i == 0 and page != 1) or (i and page <= plan[i-1]['page']):
            raise ValueError('分段必须从第 1 物理页开始并严格递增')
        if not isinstance(prefix, str) or not prefix.isascii() or any(ord(c) < 32 or ord(c) == 127 for c in prefix):
            raise ValueError('前缀须为可打印 ASCII，以避免 PDF 库的非 ASCII 编码问题')
        if style is None:
            if not prefix or 'start' in seg:
                raise ValueError('无编号样式的分段须有前缀且不能有 start')
            rule = {'startpage': page - 1, 'prefix': prefix}
        else:
            start = seg.get('start', 1)
            if style not in ('D', 'r', 'R', 'a', 'A') or type(start) is not int or start < 1:
                raise ValueError(f'第 {i+1} 段样式或起始数字无效')
            rule = {'startpage': page - 1, 'prefix': prefix, 'style': style, 'firstpagenum': start}
        rules.append(rule)
    labels = []
    for i, rule in enumerate(rules):
        end = rules[i+1]['startpage'] if i+1 < len(rules) else count
        for p in range(rule['startpage'], end):
            tail = suffix(rule['style'], rule['firstpagenum'] + p - rule['startpage']) if 'style' in rule else ''
            labels.append(rule['prefix'] + tail)
    duplicates = [x for x, n in collections.Counter(labels).items() if n > 1]
    if duplicates:
        raise ValueError(f'存在重复页码标签: {duplicates[:5]}；请为重复段加前缀')
    return rules, labels


def run(source, plan_path, output, report):
    source, plan_path, output, report = (Path(x).resolve() for x in (source, plan_path, output, report))
    if len({source, plan_path, output, report}) != 4:
        raise ValueError('原件、方案、候选和报告必须是不同文件')
    if output.exists() or report.exists():
        raise FileExistsError('输出文件或报告已存在')
    if not output.parent.is_dir() or not report.parent.is_dir():
        raise ValueError('输出目录不存在')
    plan = json.loads(plan_path.read_text(encoding='utf-8-sig'))
    source_hash = sha256(source)
    with pymupdf.open(source) as d:
        rules, expected = plan_labels(plan, len(d))
        orig_toc = d.get_toc(simple=False)
    fd, name = tempfile.mkstemp(prefix='.labels-', suffix='.pdf', dir=output.parent)
    os.close(fd)
    temp = Path(name)
    made_output = False
    made_report = False
    try:
        shutil.copyfile(source, temp)
        with pymupdf.open(temp) as d:
            d.set_page_labels(rules)
            d.saveIncr()
        with pymupdf.open(source) as a, pymupdf.open(temp) as b:
            actual = [p.get_label() for p in b]
            if actual != expected:
                bad = [i+1 for i,(x,y) in enumerate(zip(actual,expected)) if x != y]
                raise ValueError(f'写后标签与预期不符: 物理页 {bad[:10]}')
            if orig_toc != b.get_toc(simple=False):
                raise ValueError('原书签结构或落点发生变化')
            da, ma, ua = doc_facets(a)
            db, mb, ub = doc_facets(b)
            if (ua | ub) - {'labels'}:
                raise ValueError(f'文档信息未验证: {(ua | ub) - {"labels"}}')
            if any(da[k] != db[k] for k in ('pages','encrypted','embfiles')) or ma != mb:
                raise ValueError('文档信息发生变化')
            _, stats = collect(a, b, list(range(len(a))))
            if stats['content_diff'] or stats['unverified']:
                raise ValueError(f'页面内容差异 {len(stats["content_diff"])} 页，未验证 {len(stats["unverified"])} 页')
            if sha256(source) != source_hash:
                raise ValueError('原文件在处理时发生变化')
        result = {'source_sha256':source_hash, 'pages':len(expected), 'bookmarks':len(orig_toc),
                  'labels':expected, 'rules':rules, 'page_content_differences':0,
                  'unverified_pages':0, 'recompressed_pages':len(stats['recompressed']),
                  'note':'标签与方案一致；印刷页码对应关系仍须对照原页核验。候选不代表原件已写回。'}
        with output.open('xb') as f, temp.open('rb') as g:
            made_output = True
            shutil.copyfileobj(g, f)
        with report.open('x', encoding='utf-8', newline='\n') as f:
            made_report = True
            json.dump(result, f, ensure_ascii=False, indent=2)
        print(f'候选: {output}\n报告: {report}\n页数: {len(expected)}；书签保持 {len(orig_toc)} 条；标签唯一。')
        print('注意：标签方案是否符合印刷原页，仍须另行核验。')
    except Exception:
        if made_report: report.unlink(missing_ok=True)
        if made_output: output.unlink(missing_ok=True)
        raise
    finally:
        temp.unlink(missing_ok=True)


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('source'); p.add_argument('plan'); p.add_argument('output'); p.add_argument('--report', required=True)
    a = p.parse_args()
    try:
        run(a.source, a.plan, a.output, a.report)
    except Exception as exc:
        p.exit(1, f'失败: {exc}\n')

if __name__ == '__main__':
    main()
