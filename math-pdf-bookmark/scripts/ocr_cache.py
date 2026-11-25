# -*- coding: utf-8 -*-
"""零文字层扫描件：整书行级 OCR 缓存（并行 + 可续跑），供 xref_ocr.py 使用。

只产出 {page0: [(x0,y0,x1,y1,text), ...]}（pt 坐标），**不写文本层**。
扫描件做交叉引用不需要文本层：/Link 是独立注解，只要 OCR 给出引用文字与
目标定义点的坐标即可。加文本层反而要做 40 万次 insert_text + 整书重压缩，
实测 405 页要十几分钟且极易被误认为卡死。

用法：
  python ocr_cache.py --pdf book.pdf --cache ocr.pkl --workers 6 --threads 2
"""
import argparse
import os
import pickle
import time
import traceback

import numpy as np
import pymupdf as fitz

_DOC = None
_ENG = None
_DPI = 300


def _init(pdf, dpi, threads):
    global _DOC, _ENG, _DPI
    _DPI = dpi
    _DOC = fitz.open(pdf)
    from rapidocr import RapidOCR
    _ENG = RapidOCR(params={
        'EngineConfig.onnxruntime.intra_op_num_threads': threads,
        'EngineConfig.onnxruntime.inter_op_num_threads': 1,
        'Global.log_level': 'error',
    })


def _work(pno):
    try:
        pg = _DOC[pno]
        pix = pg.get_pixmap(dpi=_DPI)
        img = np.frombuffer(pix.samples, dtype=np.uint8).reshape(
            pix.height, pix.width, pix.n)[:, :, :3]
        r = _ENG(img)
        if not r.txts:
            return pno, []
        s = 72.0 / _DPI
        out = []
        for b, t in zip(r.boxes, r.txts):
            b = np.asarray(b, dtype=float)
            out.append((float(b[:, 0].min()) * s, float(b[:, 1].min()) * s,
                        float(b[:, 0].max()) * s, float(b[:, 1].max()) * s, t))
        return pno, out
    except Exception:
        return pno, [(0.0, 0.0, 0.0, 0.0,
                      '__OCR_ERROR__' + traceback.format_exc().replace('\n', ' ')[:200])]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--pdf', required=True)
    ap.add_argument('--cache', default='ocr.pkl')
    ap.add_argument('--workers', type=int, default=6)
    ap.add_argument('--threads', type=int, default=2)
    ap.add_argument('--dpi', type=int, default=300)
    ap.add_argument('--pages', default='')
    a = ap.parse_args()
    os.environ.setdefault('OMP_NUM_THREADS', '1')

    d0 = fitz.open(a.pdf)
    total = d0.page_count
    d0.close()

    cache = {}
    if os.path.exists(a.cache):
        with open(a.cache, 'rb') as f:
            cache = pickle.load(f)
        print('resume: %d cached' % len(cache), flush=True)

    want = []
    if a.pages:
        for part in a.pages.split(','):
            if '-' in part:
                s, e = part.split('-')
                want.extend(range(int(s), int(e) + 1))
            else:
                want.append(int(part))
    else:
        want = list(range(total))
    todo = [p for p in want if p not in cache
            or (cache[p] and cache[p][0][4].startswith('__OCR_ERROR__'))]
    print('pages %d, todo %d, %dx%d' % (total, len(todo), a.workers, a.threads),
          flush=True)

    t0 = time.time()
    if todo:
        from multiprocessing import Pool
        with Pool(a.workers, initializer=_init,
                  initargs=(a.pdf, a.dpi, a.threads)) as pool:
            for i, (pno, rows) in enumerate(pool.imap_unordered(
                    _work, todo, chunksize=2), 1):
                cache[pno] = rows
                if i % 25 == 0:
                    with open(a.cache, 'wb') as f:
                        pickle.dump(cache, f)
                    el = time.time() - t0
                    print('  %d/%d %.0fs eta %.0fs' %
                          (i, len(todo), el, el / i * (len(todo) - i)), flush=True)
    with open(a.cache, 'wb') as f:
        pickle.dump(cache, f)
    errs = [k + 1 for k, v in cache.items()
            if v and v[0][4].startswith('__OCR_ERROR__')]
    print('done %.0fs, pages %d, errors %d %s' %
          (time.time() - t0, len(cache), len(errs), errs[:10]))


if __name__ == '__main__':
    main()
