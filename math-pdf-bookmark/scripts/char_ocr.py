# -*- coding: utf-8 -*-
"""对指定页做「字符级 bbox」OCR，供交叉引用精确落框。

xref_ocr.py 的行内 x 定位原先用字符宽度权重插值，ASCII 密集行会偏 1~2 个字符
（如 `(定理 7.1)` 只框到 `7.`）。RapidOCR 的 return_word_box +
return_single_char_box 给出每个字符的四点框，换算成 pt 后即可精确到字。

输出 char.pkl: {page0: [{'text':..., 'box':(x0,y0,x1,y1),
                          'chars':[(ch,x0,y0,x1,y1), ...]}]}
注意 chars 是「去掉空白」后的序列，与 text 去空白后逐字对齐。
"""
import argparse
import os
import pickle
import traceback
from multiprocessing import Pool

import numpy as np
import pymupdf as fitz

_DOC = None
_ENG = None


def _init(pdf, threads):
    global _DOC, _ENG
    _DOC = fitz.open(pdf)
    from rapidocr import RapidOCR
    _ENG = RapidOCR(params={
        'EngineConfig.onnxruntime.intra_op_num_threads': threads,
        'EngineConfig.onnxruntime.inter_op_num_threads': 1,
        'Global.log_level': 'error',
    })


def _work(args):
    pno, dpi = args
    try:
        pg = _DOC[pno]
        pix = pg.get_pixmap(dpi=dpi)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.height, pix.width, pix.n)[:, :, :3]
        r = _ENG(img, return_word_box=True, return_single_char_box=True)
        if not r.txts:
            return pno, []
        s = 72.0 / dpi
        out = []
        for i, txt in enumerate(r.txts):
            wr = r.word_results[i] if i < len(r.word_results) else ()
            chars = []
            for ch, _score, quad in wr:
                xs = [p[0] * s for p in quad]
                ys = [p[1] * s for p in quad]
                chars.append((ch, min(xs), min(ys), max(xs), max(ys)))
            if not chars:
                b = np.asarray(r.boxes[i], dtype=float)
                box = (b[:, 0].min() * s, b[:, 1].min() * s,
                       b[:, 0].max() * s, b[:, 1].max() * s)
            else:
                box = (min(c[1] for c in chars), min(c[2] for c in chars),
                       max(c[3] for c in chars), max(c[4] for c in chars))
            out.append({'text': txt, 'box': box, 'chars': chars})
        return pno, out
    except Exception:
        return pno, [{'text': '__OCR_ERROR__' + traceback.format_exc()[:200],
                      'box': (0, 0, 0, 0), 'chars': []}]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pdf', required=True)
    ap.add_argument('--pages', required=True, help='逗号分隔的 0-based 页')
    ap.add_argument('--out', default='char.pkl')
    ap.add_argument('--workers', type=int, default=6)
    ap.add_argument('--threads', type=int, default=2)
    ap.add_argument('--dpi', type=int, default=300)
    a = ap.parse_args()
    os.environ.setdefault('OMP_NUM_THREADS', '1')
    want = [int(x) for x in a.pages.split(',') if x.strip()]

    res = {}
    if os.path.exists(a.out):
        with open(a.out, 'rb') as f:
            res = pickle.load(f)
    todo = [p for p in want if p not in res]
    print('pages %d, todo %d' % (len(want), len(todo)), flush=True)
    if todo:
        with Pool(a.workers, initializer=_init,
                  initargs=(a.pdf, a.threads)) as pool:
            for i, (pno, out) in enumerate(pool.imap_unordered(
                    _work, [(p, a.dpi) for p in todo], chunksize=2), 1):
                res[pno] = out
                if i % 20 == 0:
                    print('  %d/%d' % (i, len(todo)), flush=True)
                    with open(a.out, 'wb') as f:
                        pickle.dump(res, f)
    with open(a.out, 'wb') as f:
        pickle.dump(res, f)
    errs = [k for k, v in res.items() if v and v[0]['text'].startswith('__OCR_ERROR__')]
    print('done %d pages, errors %d %s' % (len(res), len(errs), errs[:5]))


if __name__ == '__main__':
    main()
