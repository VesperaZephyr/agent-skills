# -*- coding: utf-8 -*-
"""目视校验跳转目标：渲染目标页 target_y 附近（视口顶部），拼版。"""
import json
import sys

import pymupdf as fitz
from PIL import Image, ImageDraw

K2A = {'定理': 'Thm', '命题': 'Prop', '例': 'Ex', '引理': 'Lem',
       '推论': 'Cor', '定义': 'Def', 'Equation': 'Eq', 'Section': 'Sec'}


def main():
    pdf, report = sys.argv[1], sys.argv[2]
    prefix = sys.argv[3] if len(sys.argv) > 3 else 'tsheet'
    step = int(sys.argv[4]) if len(sys.argv) > 4 else 8
    links = json.load(open(report, encoding='utf-8'))
    doc = fitz.open(pdf)
    pick = links[::step]
    CW, CH, COLS, ROWS = 620, 230, 3, 4
    per = COLS * ROWS
    for si in range(0, len(pick), per):
        batch = pick[si:si + per]
        sheet = Image.new('RGB', (CW * COLS, CH * ROWS), 'white')
        dr = ImageDraw.Draw(sheet)
        for k, L in enumerate(batch):
            cx, cy = (k % COLS) * CW, (k // COLS) * CH
            pgi = L['target_page'] - 1
            pg = doc[pgi]
            top = max(L['target_y'] - 12, 0)
            clip = fitz.Rect(0, top, pg.rect.width, min(top + 95, pg.rect.height))
            pix = pg.get_pixmap(matrix=fitz.Matrix(2.0, 2.0), clip=clip, alpha=False)
            im = Image.frombytes('RGB', (pix.width, pix.height), pix.samples)
            sc = min((CW - 20) / im.width, (CH - 42) / im.height, 1.0)
            if sc < 1.0:
                im = im.resize((int(im.width * sc), int(im.height * sc)), Image.LANCZOS)
            ox, oy = cx + 10, cy + 34
            sheet.paste(im, (ox, oy))
            # 视口顶线（= 跳转落点）
            ly = oy + 12 * 2.0 * sc
            dr.line([ox, ly, ox + im.width, ly], fill='red', width=2)
            dr.text((cx + 10, cy + 6),
                    '#%d %s %s -> p%d y%.0f' % (pick.index(L) + 1,
                                                K2A.get(L['kind'], L['kind']),
                                                L['num'], L['target_page'],
                                                L['target_y']), fill='darkred')
        out = '%s_%d.png' % (prefix, si // per + 1)
        sheet.save(out)
        print(out, len(batch))


if __name__ == '__main__':
    main()
