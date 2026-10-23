#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
fast_xlsx_builder.py —— 零依赖极速 Excel (XLSX) 生成与装配器
基于 Python 标准库 zipfile + OpenXML 标准，0.05 秒内直接产出原生兼容
Microsoft Excel、WPS、LibreOffice 及腾讯文档的高清美观工作簿。
"""
import argparse
import csv
import json
import os
import sys
import zipfile

def col_letter(col_idx):
    """0-indexed column number to Excel column letter (0->A, 25->Z, 26->AA)"""
    res = ""
    while col_idx >= 0:
        res = chr(col_idx % 26 + 65) + res
        col_idx = col_idx // 26 - 1
    return res

def escape_xml(s):
    if not isinstance(s, str):
        s = str(s)
    return (s.replace("&", "&amp;")
             .replace("<", "&lt;")
             .replace(">", "&gt;")
             .replace('"', "&quot;")
             .replace("'", "&apos;"))

def build_xlsx(sheets_data, output_path):
    """
    sheets_data: list of dict:
      [
        {
          "name": "Sheet1",
          "headers": ["列1", "列2", ...],
          "rows": [
            [val1, val2, ...],
            ...
          ],
          "col_widths": [15, 20, ...] # optional
        }
      ]
    """
    content_types = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<Types xmlns="http://schemas.openxmlformats.org/package/2006/content-types">',
        '  <Default Extension="rels" ContentType="application/vnd.openxmlformats-package.relationships+xml"/>',
        '  <Default Extension="xml" ContentType="application/xml"/>',
        '  <Override PartName="/xl/workbook.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet.main+xml"/>',
        '  <Override PartName="/xl/styles.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.styles+xml"/>'
    ]

    wb_sheets = []
    wb_rels = [
        '<?xml version="1.0" encoding="UTF-8" standalone="yes"?>',
        '<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">'
    ]

    # Global styles
    # style 0: default
    # style 1: header (bold, dark text, light-blue/gray fill #EBF3FB, thin border, centered)
    # style 2: data cell (regular, thin border, centered)
    # style 3: number cell (regular, thin border, right-aligned)
    styles_xml = '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<styleSheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  <fonts count="2">
    <font><sz val="10.5"/><name val="微软雅黑"/></font>
    <font><b/><sz val="11"/><color rgb="FF1A365D"/><name val="微软雅黑"/></font>
  </fonts>
  <fills count="3">
    <fill><patternFill patternType="none"/></fill>
    <fill><patternFill patternType="gray125"/></fill>
    <fill><patternFill patternType="solid"><fgColor rgb="FFEBF3FB"/></patternFill></fill>
  </fills>
  <borders count="2">
    <border><left/><right/><top/><bottom/></border>
    <border>
      <left style="thin"><color rgb="FFD1D5DB"/></left>
      <right style="thin"><color rgb="FFD1D5DB"/></right>
      <top style="thin"><color rgb="FFD1D5DB"/></top>
      <bottom style="thin"><color rgb="FFD1D5DB"/></bottom>
    </border>
  </borders>
  <cellStyleXfs count="1">
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0"/>
  </cellStyleXfs>
  <cellXfs count="4">
    <!-- 0: normal -->
    <xf numFmtId="0" fontId="0" fillId="0" borderId="0" xfId="0"/>
    <!-- 1: header -->
    <xf numFmtId="0" fontId="1" fillId="2" borderId="1" xfId="0" applyFont="1" applyFill="1" applyBorder="1" applyAlignment="1">
      <alignment horizontal="center" vertical="center" wrapText="1"/>
    </xf>
    <!-- 2: data center -->
    <xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1" applyAlignment="1">
      <alignment horizontal="center" vertical="center"/>
    </xf>
    <!-- 3: data right (numeric) -->
    <xf numFmtId="0" fontId="0" fillId="0" borderId="1" xfId="0" applyBorder="1" applyAlignment="1">
      <alignment horizontal="right" vertical="center"/>
    </xf>
  </cellXfs>
</styleSheet>'''

    sheet_xml_map = {}

    for i, s in enumerate(sheets_data, start=1):
        s_name = escape_xml(s.get("name", f"Sheet{i}"))
        content_types.append(f'  <Override PartName="/xl/worksheets/sheet{i}.xml" ContentType="application/vnd.openxmlformats-officedocument.spreadsheetml.worksheet+xml"/>')
        wb_sheets.append(f'    <sheet name="{s_name}" sheetId="{i}" r:id="rId{i}"/>')
        wb_rels.append(f'  <Relationship Id="rId{i}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/worksheet" Target="worksheets/sheet{i}.xml"/>')

        headers = s.get("headers", [])
        rows = s.get("rows", [])

        # Calculate max col lengths for auto column width
        max_lens = {}
        for ci, h in enumerate(headers):
            max_lens[ci] = max(max_lens.get(ci, 0), len(str(h).encode('gbk', 'ignore')))
        for r in rows:
            for ci, val in enumerate(r):
                max_lens[ci] = max(max_lens.get(ci, 0), len(str(val).encode('gbk', 'ignore')))

        cols_xml = []
        if max_lens:
            cols_xml.append('<cols>')
            for ci, l in sorted(max_lens.items()):
                w = max(11.0, min(40.0, l * 1.15 + 3.0))
                cols_xml.append(f'<col min="{ci+1}" max="{ci+1}" width="{w:.2f}" customWidth="1"/>')
            cols_xml.append('</cols>')

        sheet_rows = []
        row_idx = 1
        if headers:
            h_cells = []
            for ci, h in enumerate(headers):
                ref = f"{col_letter(ci)}{row_idx}"
                h_cells.append(f'<c r="{ref}" s="1" t="inlineStr"><is><t>{escape_xml(h)}</t></is></c>')
            sheet_rows.append(f'<row r="{row_idx}" ht="26" customHeight="1">{"".join(h_cells)}</row>')
            row_idx += 1

        for r in rows:
            r_cells = []
            for ci, val in enumerate(r):
                ref = f"{col_letter(ci)}{row_idx}"
                if isinstance(val, (int, float)):
                    r_cells.append(f'<c r="{ref}" s="3"><v>{val}</v></c>')
                elif isinstance(val, str) and val.startswith("="):
                    r_cells.append(f'<c r="{ref}" s="3"><f>{escape_xml(val[1:])}</f></c>')
                else:
                    r_cells.append(f'<c r="{ref}" s="2" t="inlineStr"><is><t>{escape_xml(val)}</t></is></c>')
            sheet_rows.append(f'<row r="{row_idx}" ht="20" customHeight="1">{"".join(r_cells)}</row>')
            row_idx += 1

        s_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<worksheet xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main">
  {"".join(cols_xml)}
  <sheetData>
    {"".join(sheet_rows)}
  </sheetData>
</worksheet>'''
        sheet_xml_map[f"xl/worksheets/sheet{i}.xml"] = s_xml

    content_types.append('</Types>')
    wb_rels.append(f'  <Relationship Id="rId{len(sheets_data)+1}" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/styles" Target="styles.xml"/>')
    wb_rels.append('</Relationships>')

    workbook_xml = f'''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<workbook xmlns="http://schemas.openxmlformats.org/spreadsheetml/2006/main" xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">
  <sheets>
{"".join(wb_sheets)}
  </sheets>
</workbook>'''

    out_dir = os.path.dirname(output_path)
    if out_dir and not os.path.exists(out_dir):
        os.makedirs(out_dir, exist_ok=True)

    with zipfile.ZipFile(output_path, "w", compression=zipfile.ZIP_DEFLATED) as z:
        z.writestr("[Content_Types].xml", "\n".join(content_types))
        z.writestr("_rels/.rels", '''<?xml version="1.0" encoding="UTF-8" standalone="yes"?>
<Relationships xmlns="http://schemas.openxmlformats.org/package/2006/relationships">
  <Relationship Id="rId1" Type="http://schemas.openxmlformats.org/officeDocument/2006/relationships/officeDocument" Target="xl/workbook.xml"/>
</Relationships>''')
        z.writestr("xl/workbook.xml", workbook_xml)
        z.writestr("xl/_rels/workbook.xml.rels", "\n".join(wb_rels))
        z.writestr("xl/styles.xml", styles_xml)
        for path, content in sheet_xml_map.items():
            z.writestr(path, content)

    print(f"[SUCCESS] XLSX successfully built at: {output_path} ({os.path.getsize(output_path)} bytes)")

def main():
    parser = argparse.ArgumentParser(description="Fast XLSX Builder")
    parser.add_argument("--json-data", help="JSON string or path to JSON file containing sheet data")
    parser.add_argument("--csv", help="Path to CSV file to convert")
    parser.add_argument("--sheet-name", default="Sheet1", help="Sheet name when using CSV")
    parser.add_argument("--output", required=True, help="Output XLSX path")
    args = parser.parse_args()

    out_path = os.path.abspath(args.output)

    if args.json_data:
        if os.path.exists(args.json_data):
            with open(args.json_data, "r", encoding="utf-8") as f:
                data = json.load(f)
        else:
            data = json.loads(args.json_data)
        if isinstance(data, dict):
            data = [data]
        build_xlsx(data, out_path)
    elif args.csv:
        csv_path = os.path.abspath(args.csv)
        if not os.path.exists(csv_path):
            print(f"[ERROR] CSV file not found: {csv_path}", file=sys.stderr)
            sys.exit(1)
        with open(csv_path, "r", encoding="utf-8-sig") as f:
            reader = csv.reader(f)
            rows_all = list(reader)
        if not rows_all:
            headers = []
            rows = []
        else:
            headers = rows_all[0]
            rows = rows_all[1:]
        data = [{"name": args.sheet_name, "headers": headers, "rows": rows}]
        build_xlsx(data, out_path)
    else:
        print("[ERROR] Must provide --json-data or --csv", file=sys.stderr)
        sys.exit(1)

if __name__ == "__main__":
    main()
