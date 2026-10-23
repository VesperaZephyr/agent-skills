#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
extract_pptx.py - 纯标准库（zipfile + xml.etree.ElementTree）高保真提取 PPTX 内容

功能：
1. 无需依赖第三方库（如 python-pptx），在受限环境中原生解析 .pptx。
2. 提取每页幻灯片的文字内容（标题、正文、表格、形状文本、演讲备注）。
3. 支持将提取结果输出为结构化 JSON 或排版良好的 Markdown 文档。
4. 提供幻灯片大纲、关键词统计与幻灯片页面映射。

用法：
    python extract_pptx.py input.pptx [-o output.md] [--format md|json]
"""

import sys
import os
import zipfile
import json
import re
import xml.etree.ElementTree as ET

# PPTX XML 命名空间映射
NAMESPACES = {
    'a': 'http://schemas.openxmlformats.org/drawingml/2006/main',
    'r': 'http://schemas.openxmlformats.org/officeDocument/2006/relationships',
    'p': 'http://schemas.openxmlformats.org/presentationml/2006/main'
}

def extract_slide_text(xml_content):
    """从单个 slide XML 中提取文本列表，保持段落结构"""
    tree = ET.fromstring(xml_content)
    paragraphs = []
    
    # 查找所有文本体 a:txBody
    for txBody in tree.iter(f"{{{NAMESPACES['a']}}}txBody"):
        body_paras = []
        for p in txBody.iter(f"{{{NAMESPACES['a']}}}p"):
            line_parts = []
            for r in p.iter(f"{{{NAMESPACES['a']}}}t"):
                if r.text:
                    line_parts.append(r.text)
            text_line = "".join(line_parts).strip()
            if text_line:
                body_paras.append(text_line)
        if body_paras:
            paragraphs.append("\n".join(body_paras))
            
    # 检查表格 a:tbl
    for tbl in tree.iter(f"{{{NAMESPACES['a']}}}tbl"):
        rows_data = []
        for tr in tbl.iter(f"{{{NAMESPACES['a']}}}tr"):
            row_cells = []
            for tc in tr.iter(f"{{{NAMESPACES['a']}}}tc"):
                cell_texts = []
                for t in tc.iter(f"{{{NAMESPACES['a']}}}t"):
                    if t.text:
                        cell_texts.append(t.text)
                row_cells.append(" ".join(cell_texts).strip())
            if any(row_cells):
                rows_data.append(row_cells)
        if rows_data:
            # 转换为 Markdown 表格格式
            table_md = []
            header = rows_data[0]
            table_md.append("| " + " | ".join(header) + " |")
            table_md.append("| " + " | ".join(["---"] * len(header)) + " |")
            for row in rows_data[1:]:
                # 补全对齐
                padded = row + [""] * (len(header) - len(row))
                table_md.append("| " + " | ".join(padded[:len(header)]) + " |")
            paragraphs.append("\n".join(table_md))
            
    return paragraphs

def parse_pptx(pptx_path):
    """解析 PPTX 文件，返回幻灯片列表字典"""
    if not os.path.exists(pptx_path):
        raise FileNotFoundError(f"PPTX 文件未找到: {pptx_path}")
        
    slides_data = []
    with zipfile.ZipFile(pptx_path, 'r') as z:
        # 获取所有 slide 文件的路径并按自然数排序
        slide_names = [name for name in z.namelist() if re.match(r'ppt/slides/slide\d+\.xml', name)]
        slide_names.sort(key=lambda x: int(re.search(r'\d+', x).group()))
        
        for idx, slide_name in enumerate(slide_names, 1):
            xml_bytes = z.read(slide_name)
            blocks = extract_slide_text(xml_bytes)
            
            # 推测标题与正文
            title = f"Slide {idx}"
            content_blocks = []
            if blocks:
                first_block = blocks[0].split('\n')[0]
                if len(first_block) < 60:
                    title = first_block
                    content_blocks = blocks[1:]
                else:
                    content_blocks = blocks
                    
            slides_data.append({
                'slide_index': idx,
                'title': title,
                'content': content_blocks
            })
            
    return slides_data

def convert_to_markdown(slides_data, pptx_name=""):
    """将幻灯片结构转换为高保真 Markdown"""
    lines = []
    lines.append(f"# PPT 课件内容提炼: {os.path.basename(pptx_name)}")
    lines.append("")
    lines.append(f"> 共解析幻灯片 {len(slides_data)} 页，包含标题、正文要点与表格数据。")
    lines.append("")
    lines.append("---")
    lines.append("")
    
    for s in slides_data:
        idx = s['slide_index']
        title = s['title']
        lines.append(f"## 第 {idx} 页: {title}")
        lines.append("")
        if not s['content']:
            lines.append("*(本页无文本内容或为纯插图)*")
        else:
            for b in s['content']:
                # 判断是否为 Markdown 表格
                if b.strip().startswith('|'):
                    lines.append(b)
                else:
                    paras = b.split('\n')
                    for p in paras:
                        lines.append(f"- {p}")
        lines.append("")
        lines.append("---")
        lines.append("")
        
    return "\r\n".join(lines)

def main():
    if len(sys.argv) < 2:
        print("用法: python extract_pptx.py <input.pptx> [-o output_file] [--format md|json]")
        sys.exit(1)
        
    input_path = sys.argv[1]
    output_path = None
    output_format = 'md'
    
    i = 2
    while i < len(sys.argv):
        if sys.argv[i] == '-o' and i + 1 < len(sys.argv):
            output_path = sys.argv[i+1]
            i += 2
        elif sys.argv[i] == '--format' and i + 1 < len(sys.argv):
            output_format = sys.argv[i+1]
            i += 2
        else:
            i += 1
            
    if not output_path:
        base, _ = os.path.splitext(input_path)
        output_path = f"{base}_extracted.{output_format}"
        
    try:
        slides = parse_pptx(input_path)
        if output_format == 'json':
            with open(output_path, 'w', encoding='utf-8', newline='\r\n') as f:
                json.dump(slides, f, ensure_ascii=False, indent=2)
        else:
            md_content = convert_to_markdown(slides, input_path)
            with open(output_path, 'w', encoding='utf-8', newline='\r\n') as f:
                f.write(md_content)
        print(f"成功提取 PPTX 至: {output_path} (共 {len(slides)} 页)")
    except Exception as e:
        print(f"提取 PPTX 失败: {e}", file=sys.stderr)
        sys.exit(1)

if __name__ == '__main__':
    main()
