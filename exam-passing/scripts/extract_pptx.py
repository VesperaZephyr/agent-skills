#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_pptx.py - 纯标准库 (zipfile + xml.etree.ElementTree) 高保真提取 PPTX 内容

功能:
1. 不依赖第三方库 (如 python-pptx), 在受限环境中原生解析 .pptx.
2. 按本地名 (local name) 匹配 XML 节点, 不假定命名空间前缀:
   PowerPoint 写 <a:txBody>, 而 WPS / 部分转换工具写 <p:txBody>, 只认前缀会把整份课件抽成空页.
3. 同一段落内同时聚合 <a:t> (普通文字) 与 <m:t> (OMML 公式), 保持文档顺序.
4. 表格按 Markdown 表格输出; 表格单元格内的 txBody 不重复计入正文.
5. 可导出每页引用的媒体 (jpeg / png / emf 等), 命名 s{页号}_{序号}.{ext},
   以便对公式截图的课件逐张做图像识别.
6. 输出 Markdown 或 JSON.

用法:
    python extract_pptx.py input.pptx [-o output.md] [--format md|json] [--media 目录] [--no-notes]
"""

import sys
import os
import zipfile
import json
import re
import xml.etree.ElementTree as ET

R_NS = 'http://schemas.openxmlformats.org/officeDocument/2006/relationships'


def local(tag):
    """取节点本地名, 忽略命名空间前缀与 URI."""
    return tag.rsplit('}', 1)[-1] if '}' in tag else tag


def _paragraph_text(p):
    """段落内所有 <a:t> / <m:t> 按顺序拼接 (两者的本地名都是 t)."""
    parts = []
    for e in p.iter():
        if local(e.tag) == 't' and e.text:
            parts.append(e.text)
    return ''.join(parts).strip()


def extract_slide_text(xml_bytes):
    """从单页 XML 提取文本块, 保持段落结构. 返回 (文本块列表, 表格块列表)."""
    root = ET.fromstring(xml_bytes)

    # 表格单元格内部的 txBody 会被下面的正文循环重复抓到, 先登记其 id
    cell_bodies = set()
    tables = []
    for tbl in root.iter():
        if local(tbl.tag) != 'tbl':
            continue
        rows = []
        for tr in tbl.iter():
            if local(tr.tag) != 'tr':
                continue
            cells = []
            for tc in tr.iter():
                if local(tc.tag) != 'tc':
                    continue
                cell_paras = []
                for tb in tc.iter():
                    if local(tb.tag) == 'txBody':
                        cell_bodies.add(id(tb))
                        for p in tb.iter():
                            if local(p.tag) == 'p':
                                line = _paragraph_text(p)
                                if line:
                                    cell_paras.append(line)
                cells.append(' '.join(cell_paras).strip())
            if any(cells):
                rows.append(cells)
        if rows:
            tables.append(rows)

    blocks = []
    for body in root.iter():
        if local(body.tag) != 'txBody' or id(body) in cell_bodies:
            continue
        paras = []
        for p in body.iter():
            if local(p.tag) != 'p':
                continue
            line = _paragraph_text(p)
            if line:
                paras.append(line)
        if paras:
            blocks.append('\n'.join(paras))

    table_md = []
    for rows in tables:
        header = rows[0]
        lines = ['| ' + ' | '.join(header) + ' |',
                 '| ' + ' | '.join(['---'] * len(header)) + ' |']
        for row in rows[1:]:
            padded = row + [''] * (len(header) - len(row))
            lines.append('| ' + ' | '.join(padded[:len(header)]) + ' |')
        table_md.append('\n'.join(lines))

    return blocks, table_md


def slide_media(z, slide_name):
    """返回该页引用的媒体在 zip 内的路径列表 (按文档顺序, 去重)."""
    base = os.path.basename(slide_name)
    rels_name = 'ppt/slides/_rels/%s.rels' % base
    rel_map = {}
    if rels_name in z.namelist():
        try:
            rroot = ET.fromstring(z.read(rels_name))
            for rel in rroot:
                rid = rel.get('Id')
                target = rel.get('Target') or ''
                if rid and target:
                    rel_map[rid] = target
        except ET.ParseError:
            pass

    order = []
    try:
        sroot = ET.fromstring(z.read(slide_name))
    except ET.ParseError:
        return order

    for e in sroot.iter():
        if local(e.tag) != 'blip':
            continue
        rid = e.get('{%s}embed' % R_NS) or e.get('{%s}link' % R_NS)
        target = rel_map.get(rid)
        if not target:
            continue
        # Target 形如 ../media/image3.png, 相对 ppt/slides/ 解析
        path = os.path.normpath(os.path.join('ppt/slides', target)).replace('\\', '/')
        if path in z.namelist() and path not in order:
            order.append(path)
    return order


def slide_notes_path(z, slide_name):
    """返回该页演讲者备注的 zip 内路径; 无备注时返回 None."""
    base = os.path.basename(slide_name)
    rels_name = 'ppt/slides/_rels/%s.rels' % base
    if rels_name not in z.namelist():
        return None
    try:
        rroot = ET.fromstring(z.read(rels_name))
    except ET.ParseError:
        return None
    for rel in rroot:
        if (rel.get('Type') or '').endswith('/notesSlide'):
            target = rel.get('Target') or ''
            path = os.path.normpath(os.path.join('ppt/slides', target)).replace('\\', '/')
            if path in z.namelist():
                return path
    return None


def parse_pptx(pptx_path, media_dir=None, with_notes=True):
    """解析 PPTX, 返回幻灯片列表."""
    if not os.path.exists(pptx_path):
        raise FileNotFoundError('PPTX 文件未找到: %s' % pptx_path)

    slides_data = []
    with zipfile.ZipFile(pptx_path, 'r') as z:
        names = [n for n in z.namelist() if re.match(r'ppt/slides/slide\d+\.xml$', n)]
        names.sort(key=lambda x: int(re.search(r'slide(\d+)\.xml$', x).group(1)))

        if media_dir:
            os.makedirs(media_dir, exist_ok=True)

        for idx, name in enumerate(names, 1):
            blocks, table_md = extract_slide_text(z.read(name))

            media_out = []
            for k, path in enumerate(slide_media(z, name), 1):
                ext = os.path.splitext(path)[1].lower() or '.bin'
                out_name = 's%d_%d%s' % (idx, k, ext)
                if media_dir:
                    with open(os.path.join(media_dir, out_name), 'wb') as f:
                        f.write(z.read(path))
                media_out.append(out_name)

            content = blocks + table_md
            title = 'Slide %d' % idx
            if blocks:
                head = blocks[0].split('\n')
                if len(head[0]) < 60:
                    title = head[0]
                    # 只摘掉首行, 首块其余段落必须保留, 否则整页正文会被吞掉
                    rest = '\n'.join(head[1:]).strip()
                    content = ([rest] if rest else []) + blocks[1:] + table_md

            notes = []
            if with_notes:
                np = slide_notes_path(z, name)
                if np:
                    notes = extract_slide_text(z.read(np))[0]

            slides_data.append({
                'slide_index': idx,
                'title': title,
                'content': content,
                'notes': notes,
                'media': media_out,
            })

    return slides_data


def convert_to_markdown(slides_data, pptx_name=''):
    lines = ['# PPT 课件内容提炼: %s' % os.path.basename(pptx_name), '']
    total_media = sum(len(s.get('media') or []) for s in slides_data)
    lines.append('> 共解析幻灯片 %d 页; 引用媒体 %d 个.'
                 ' 公式若为图片, 文字稿只能给出目录与结论, 公式本身需看图.' % (len(slides_data), total_media))
    lines += ['', '---', '']

    for s in slides_data:
        lines.append('## 第 %d 页: %s' % (s['slide_index'], s['title']))
        lines.append('')
        if not s['content']:
            lines.append('*(本页无文本内容或为纯插图)*')
        else:
            for b in s['content']:
                if b.strip().startswith('|'):
                    lines.append(b)
                else:
                    for p in b.split('\n'):
                        lines.append('- %s' % p)
        if s.get('media'):
            lines.append('')
            lines.append('图片: ' + ', '.join(s['media']))
        if s.get('notes'):
            lines.append('')
            lines.append('备注:')
            for n in s['notes']:
                for p in n.split('\n'):
                    lines.append('- %s' % p)
        lines += ['', '---', '']

    return '\n'.join(lines)


def main():
    if len(sys.argv) < 2:
        print('用法: python extract_pptx.py <input.pptx> [-o output_file] '
              '[--format md|json] [--media 目录] [--no-notes]')
        sys.exit(1)

    input_path = sys.argv[1]
    output_path = None
    output_format = 'md'
    media_dir = None
    with_notes = True

    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == '-o' and i + 1 < len(sys.argv):
            output_path = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == '--format' and i + 1 < len(sys.argv):
            output_format = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == '--media' and i + 1 < len(sys.argv):
            media_dir = sys.argv[i + 1]
            i += 2
        elif sys.argv[i] == '--no-notes':
            with_notes = False
            i += 1
        else:
            i += 1

    if not output_path:
        base, _ = os.path.splitext(input_path)
        output_path = '%s_extracted.%s' % (base, output_format)

    try:
        slides = parse_pptx(input_path, media_dir=media_dir, with_notes=with_notes)
        if output_format == 'json':
            text = json.dumps(slides, ensure_ascii=False, indent=2)
        else:
            text = convert_to_markdown(slides, input_path)

        # 统一 CRLF 且只写一层: 文本按 LF 组织, 最后整体写入字节, 避免 newline 参数二次转换出 \r\r\n
        data = text.replace('\r\n', '\n').replace('\r', '\n').replace('\n', '\r\n').encode('utf-8')
        with open(output_path, 'wb') as f:
            f.write(data)

        empty = [s['slide_index'] for s in slides if not s['content']]
        n_media = sum(len(s.get('media') or []) for s in slides)
        print('成功提取 PPTX 至: %s (共 %d 页, %d 个媒体)' % (output_path, len(slides), n_media))
        if empty:
            print('注意: %d 页无可提取文本 (页号 %s); 若课件以公式截图为主, 属正常, 请用 --media 导出后逐张识别.'
                  % (len(empty), ','.join(map(str, empty[:20]))))
        if media_dir:
            print('媒体已导出至: %s' % media_dir)
        elif n_media:
            print('提示: 加 --media <目录> 可导出这些图片, 用于识别公式.')
    except Exception as e:
        print('提取 PPTX 失败: %s' % e, file=sys.stderr)
        sys.exit(1)


if __name__ == '__main__':
    main()
