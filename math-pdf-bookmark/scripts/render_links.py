# -*- coding: utf-8 -*-
"""把 report.json 的每条链接渲染成「裁剪 + 红框」拼版图，供逐格目视。

每格：
  第一行红字  #序号  p页  kind+num
  图          链接框附近 110pt 宽的区域，红框 = 实际 /Link 矩形
格子按 3 列 x 4 行排，一张 12 条。
"""
import json
import sys

import pymupdf as fitz
from PIL import Image, ImageDraw

K2A = {'定理': 'Thm', '命题': 'Prop', '例': 'Ex', '引理': 'Lem',
       '推论': 'Cor', '定义': 'Def', 'Equation': 'Eq', 'Section': 'Sec'}


def main():
    pdf = sys.argv[1]
    report = sys.argv[2] if len(sys.argv) > 2 else 'report.json'
    prefix = sys.argv[3] if len(sys.argv) > 3 else 'lsheet'
    zoom = float(sys.argv[4]) if len(sys.argv) > 4 else 2.2
    links = json.load(open(report, encoding='utf-8'))
    doc = fitz.open(pdf)

    CW, CH = 620, 210          # 每格画布
    COLS, ROWS = 3, 4
    per = COLS * ROWS
    for si in range(0, len(links), per):
        batch = links[si:si + per]
        sheet = Image.new('RGB', (CW * COLS, CH * ROWS), 'white')
        dr = ImageDraw.Draw(sheet)
        for k, L in enumerate(batch):
            cx, cy = (k % COLS) * CW, (k // COLS) * CH
            r = fitz.Rect(*L['rect'])
            pg = doc[L['page0']]
            PW = pg.rect.width
            clip = fitz.Rect(max(r.x0 - 55, 0), max(r.y0 - 26, 0),
                             min(r.x1 + 55, PW), r.y1 + 22)
            pix = pg.get_pixmap(matrix=fitz.Matrix(zoom, zoom), clip=clip, alpha=False)
            im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
            # 缩到画布内
            mx, my = CW - 20, CH - 40
            sc = min(mx / im.width, my / im.height, 1.0)
            if sc < 1.0:
                im = im.resize((int(im.width * sc), int(im.height * sc)), Image.LANCZOS)
            ox, oy = cx + 10, cy + 32
            sheet.paste(im, (ox, oy))
            # 红框
            bx0 = ox + (r.x0 - clip.x0) * zoom * sc
            by0 = oy + (r.y0 - clip.y0) * zoom * sc
            bx1 = ox + (r.x1 - clip.x0) * zoom * sc
            by1 = oy + (r.y1 - clip.y0) * zoom * sc
            dr.rectangle([bx0, by0, bx1, by1], outline='red', width=2)
            dr.text((cx + 10, cy + 6),
                    '#%d p%d %s %s -> p%d' % (si + k + 1, L['page'],
                                              K2A.get(L['kind'], L['kind']),
                                              L['num'], L['target_page']),
                    fill='darkred')
        out = '%s_%d.png' % (prefix, si // per + 1)
        sheet.save(out)
        print(out, len(batch))


if __name__ == '__main__':
    main()
