# -*- coding: utf-8 -*-
"""ROUTE P-CN 模板：中文扫描本、印刷目录须人眼转录（李红《复变函数与积分变换 第5版》）.
   换书时重指：SRC / ROOT / BAKROOT / TMP / REP / K / E(条目表) / INK(墨迹测量兜底) / TOC_Y.

印刷目录系人工从 p8/p9/p10 扫描图转录(OCR 目录层乱码严重, 不可信)。
物理页 = 印刷页 + K (K=10, 由 74 条目录项逐一核对确认)。
定位: 只在期望页及其相邻页搜索, 按条目类型用不同判据, 全部命中才写。
"""
import os
import re
import shutil
import sys
import io

import fitz

SRC = r"F:/大学/数字资源/数学/分析学/复分析/工科复变函数/复变函数与积分变换 第5版 (李红).pdf"
ROOT = r"F:/大学/数字资源/数学"
BAKROOT = os.path.join(ROOT, "_bm_rerun_backup")
TMP = r"C:/Users/asus/_lh_tmp.pdf"
REP = r"C:/Users/asus/_lh_build.txt"
K = 10

# kind, level, 书签标题, 印刷页, 附加键
#   ch: (章号, 章名)   sec: (N, M)   sum/thk/ex/app/ans/front: None
E = [
    ('front', 1, '第五版前言', 5, '第五版前言'),      # 第4列 = 物理页(前言无印刷页码)
    ('front', 1, '第一版前言', 6, '第一版前言'),      # p6 = Ⅰ
    ('toc',   1, '目录',       8, None),              # p8 = Ⅰ(标题在深色条内)
    ('ch',  1, '第一章 复数与复变函数', 1, (1, '复数与复变函数')),
    ('sec', 2, '§ 1.1 复数', 1, (1, 1)),
    ('sec', 2, '§ 1.2 复数的三角表示', 4, (1, 2)),
    ('sec', 2, '§ 1.3 平面点集的一般概念', 12, (1, 3)),
    ('sec', 2, '§ 1.4 无穷大与复球面', 16, (1, 4)),
    ('sec', 2, '§ 1.5 复变函数', 18, (1, 5)),
    ('sum', 2, '本章小结', 22, None),
    ('thk', 2, '思考题', 23, None),
    ('ex',  2, '习题一', 23, 1),
    ('ch',  1, '第二章 解析函数', 25, (2, '解析函数')),
    ('sec', 2, '§ 2.1 解析函数的概念', 25, (2, 1)),
    ('sec', 2, '§ 2.2 解析函数和调和函数的关系', 30, (2, 2)),
    ('sec', 2, '§ 2.3 初等函数', 34, (2, 3)),
    ('sum', 2, '本章小结', 42, None),
    ('thk', 2, '思考题', 43, None),
    ('ex',  2, '习题二', 43, 2),
    ('ch',  1, '第三章 复变函数的积分', 46, (3, '复变函数的积分')),
    ('sec', 2, '§ 3.1 复积分的概念', 46, (3, 1)),
    ('sec', 2, '§ 3.2 柯西积分定理', 51, (3, 2)),
    ('sec', 2, '§ 3.3 柯西积分公式', 56, (3, 3)),
    ('sec', 2, '§ 3.4 解析函数的高阶导数', 61, (3, 4)),
    ('sum', 2, '本章小结', 64, None),
    ('thk', 2, '思考题', 65, None),
    ('ex',  2, '习题三', 65, 3),
    ('ch',  1, '第四章 解析函数的级数表示', 67, (4, '解析函数的级数表示')),
    ('sec', 2, '§ 4.1 复数项级数', 67, (4, 1)),
    ('sec', 2, '§ 4.2 复变函数项级数', 70, (4, 2)),
    ('sec', 2, '§ 4.3 泰勒（Taylor）级数', 75, (4, 3)),
    ('sec', 2, '§ 4.4 洛朗（Laurent）级数', 81, (4, 4)),
    ('sum', 2, '本章小结', 87, None),
    ('thk', 2, '思考题', 87, None),
    ('ex',  2, '习题四', 87, 4),
    ('ch',  1, '第五章 留数及其应用', 89, (5, '留数及其应用')),
    ('sec', 2, '§ 5.1 孤立奇点', 89, (5, 1)),
    ('sec', 2, '§ 5.2 留数', 97, (5, 2)),
    ('sec', 2, '§ 5.3 留数在定积分计算中的应用', 105, (5, 3)),
    ('sec', 2, '§ 5.4 对数留数与辐角原理', 110, (5, 4)),
    ('sum', 2, '本章小结', 115, None),
    ('thk', 2, '思考题', 115, None),
    ('ex',  2, '习题五', 115, 5),
    ('ch',  1, '第六章 共形映射', 118, (6, '共形映射')),
    ('sec', 2, '§ 6.1 共形映射的概念', 118, (6, 1)),
    ('sec', 2, '§ 6.2 共形映射的基本问题', 121, (6, 2)),
    ('sec', 2, '§ 6.3 分式线性映射', 124, (6, 3)),
    ('sec', 2, '§ 6.4 几个初等函数构成的共形映射', 135, (6, 4)),
    ('sum', 2, '本章小结', 143, None),
    ('ex',  2, '习题六', 143, 6),
    ('ch',  1, '第七章 解析函数在平面场的应用', 145, (7, '解析函数在平面场的应用')),
    ('sec', 2, '§ 7.1 复势的概念', 145, (7, 1)),
    ('sec', 2, '§ 7.2 复势的应用', 150, (7, 2)),
    ('sec', 2, '§ 7.3 用共形映射的方法研究平面场', 154, (7, 3)),
    ('sum', 2, '本章小结', 157, None),
    ('thk', 2, '思考题', 157, None),
    ('ex',  2, '习题七', 158, 7),
    ('ch',  1, '第八章 傅里叶变换', 159, (8, '傅里叶变换')),
    ('sec', 2, '§ 8.1 傅里叶变换的概念', 159, (8, 1)),
    ('sec', 2, '§ 8.2 单位冲激函数（δ函数）', 167, (8, 2)),
    ('sec', 2, '§ 8.3 傅里叶变换的性质', 171, (8, 3)),
    ('sum', 2, '本章小结', 182, None),
    ('ex',  2, '习题八', 183, 8),
    ('ch',  1, '第九章 拉普拉斯变换', 186, (9, '拉普拉斯变换')),
    ('sec', 2, '§ 9.1 拉普拉斯变换的概念', 186, (9, 1)),
    ('sec', 2, '§ 9.2 拉普拉斯变换的性质', 189, (9, 2)),
    ('sec', 2, '§ 9.3 拉普拉斯逆变换', 198, (9, 3)),
    ('sec', 2, '§ 9.4 拉普拉斯变换的应用及综合举例', 200, (9, 4)),
    ('sum', 2, '本章小结', 204, None),
    ('ex',  2, '习题九', 205, 9),
    ('app', 1, '附录 1 傅里叶变换简表', 207, 1),
    ('app', 1, '附录 2 拉普拉斯变换简表', 210, 2),
    ('ans', 1, '部分习题答案', 216, None),
]

# 三条"习题"标题在文字层与 WinRT OCR(300dpi) 中均缺失,
# 由 _lh_ink.py 的墨迹带测量得到 (h≈11.5pt 的未覆盖带, 与已命中的习题四..九同形):
INK = {1: (33, 238.2), 2: (53, 317.8), 3: (75, 303.8)}
TOC_Y = 42.5          # p8 "目录" 标题在深色条内, 取条带顶


def rows(page):
    sp = []
    for b in page.get_text('dict')['blocks']:
        if b['type'] != 0:
            continue
        for l in b['lines']:
            for s in l['spans']:
                if s['text'].strip():
                    sp.append(s)
    sp.sort(key=lambda s: (s['bbox'][1], s['bbox'][0]))
    cl = []
    for s in sp:
        y = s['bbox'][1]
        if cl and abs(cl[-1][0] - y) <= 2.5:
            cl[-1][1].append(s)
        else:
            cl.append([y, [s]])
    res = []
    for y, ss in cl:
        ss.sort(key=lambda s: s['bbox'][0])
        t = ''.join(s['text'] for s in ss)
        res.append((y, min(s['bbox'][0] for s in ss),
                    max(s['size'] for s in ss), t))
    return res


def nz(t):
    return re.sub(r'[\s\xa0]+', '', t)


def cjk(s):
    return [c for c in s if '\u4e00' <= c <= '\u9fff']


def ov(a, b):
    """a 的汉字有多少出现在 b 里(按重数)。"""
    if not a:
        return 1.0
    bl = list(b)
    hit = 0
    for c in a:
        if c in bl:
            bl.remove(c)
            hit += 1
    return hit / float(len(a))


def digits(t):
    return [c for c in t if c.isdigit()]


def match(kind, key, y, x, sz, t):
    s = nz(t)
    if y < 35:
        return False
    if kind == 'ch':
        n, name = key
        m = re.match(r'^第([一二三四五六七八九十]+)章', s)
        if not m or sz < 13:
            return False
        CN = {'一': 1, '二': 2, '三': 3, '四': 4, '五': 5, '六': 6, '七': 7, '八': 8, '九': 9}
        return CN.get(m.group(1)) == n and ov(cjk(name), s) >= 0.6
    if kind == 'sec':
        # 该书的 §N.M 标题行字号有时被 OCR 记成 3.0(如 p120 的 §5.4), 故不用字号判据,
        # 改用"数字前缀不含汉字 + 节号位数 + 标题汉字重合率 + 行首位置"四重判据。
        N, M = key
        i = re.search(r'\d', s)
        if not i:
            return False
        pre = s[:i.start()]
        if cjk(pre) or len(pre) > 3 or x > 140 or len(s) > 34:
            return False
        j = len(s)
        for c in s:
            if '\u4e00' <= c <= '\u9fff':
                j = s.index(c)
                break
        head = s[i.start():j]
        dg = digits(head)
        if dg[:2] != [str(N), str(M)] or len(dg) >= 3:
            return False                       # 3 位数字 = 小节, 不是目录项
        title = s[j:]
        return ov(cjk(E_TITLE_CACHE[(N, M)]), cjk(title)) >= 0.5
    if kind == 'sum':
        return '本章小结' in s and len(s) <= 8 and sz >= 8.5
    if kind == 'thk':
        return re.match(r'^[^思]{0,3}思考题$', s) is not None and sz >= 8.5
    if kind == 'ex':
        return re.match(r'^[^习]{0,3}习题[一二三四五六七八九]$', s) is not None and sz >= 8.5
    if kind == 'app':
        return s.startswith('附录') and sz >= 13
    if kind == 'ans':
        return '部分习题答案' in s and len(s) <= 8 and sz >= 13
    if kind == 'front':
        return s.startswith(key) and sz >= 13
    return False


E_TITLE_CACHE = {(n, m): t for k, l, t, p, key in E if k == 'sec' for (n, m) in [key]}


def locate(doc, kind, key, exp, report):
    """exp = 期望物理页(1-based)。只在其前后小窗内搜索, 命中优先取期望页。"""
    cands = []
    for dp in (-1, 0, 1, 2):
        p = exp + dp
        if p < 1 or p > doc.page_count:
            continue
        for y, x, sz, t in rows(doc[p - 1]):
            if match(kind, key, y, x, sz, t):
                cands.append((abs(dp), -sz, p, y, x, sz, t))
    if not cands:
        return None
    cands.sort()
    a, b, p, y, x, sz, t = cands[0]
    return p, y, 'p%d y=%.1f x=%.1f sz=%.1f %r%s' % (
        p, y, x, sz, nz(t)[:34], '' if a == 0 else '  [偏移 %+d 页]' % (-a if a else 0))


def next_bak(src):
    rel = os.path.relpath(src, ROOT)
    d = os.path.join(BAKROOT, os.path.dirname(rel))
    os.makedirs(d, exist_ok=True)
    base = os.path.splitext(os.path.basename(src))[0]
    n = 1
    while os.path.exists(os.path.join(d, '%s_pre%d.pdf' % (base, n))):
        n += 1
    return os.path.join(d, '%s_pre%d.pdf' % (base, n))


def main():
    write = '--write' in sys.argv
    doc = fitz.open(SRC)
    out = io.open(REP, 'w', encoding='utf-8')
    out.write('pages=%d  K=%d  entries=%d\n' % (doc.page_count, K, len(E)))
    toc = []
    miss = []
    for kind, lvl, title, printed, key in E:
        if kind == 'toc':
            toc.append([lvl, title, 8, TOC_Y])
            out.write('OK   %-5s %-28s -> p8 y=%.1f  [深色条带顶]\n' % (kind, title, TOC_Y))
            continue
        # front 的第4列已是物理页; 其余条目是印刷页, 物理页 = 印刷页 + K
        exp = printed if kind == 'front' else printed + K
        hit = locate(doc, kind, key, exp, out)

        if hit is None and kind == 'ex' and key in INK:
            p, y = INK[key]
            toc.append([lvl, title, p, y])
            out.write('OK*  %-5s %-28s -> p%d y=%.1f  [墨迹测量: 文字层与OCR均缺]\n' % (kind, title, p, y))
            continue
        if hit is None:
            miss.append((kind, title, printed))
            out.write('MISS %-5s %-28s 印刷页 %s\n' % (kind, title, printed))
            continue
        p, y, how = hit
        toc.append([lvl, title, p, y])
        out.write('OK   %-5s %-28s -> %s\n' % (kind, title, how))
    out.write('\n命中 %d / %d, MISS %d\n' % (len(toc), len(E), len(miss)))
    # 单调性检查
    bad = 0
    for i in range(1, len(toc)):
        if toc[i][2] < toc[i - 1][2]:
            bad += 1
            out.write('NONMONO #%d %s p%d < 前一条 p%d\n' % (i, toc[i][1], toc[i][2], toc[i - 1][2]))
    out.write('nonmono=%d\n' % bad)
    if miss or bad:
        out.write('\n未写入(存在 MISS 或非单调)。\n')
        out.close()
        print('dry-run done, see report')
        return
    if not write:
        out.write('\ndry-run: 未写入。加 --write 生效。\n')
        out.close()
        print('dry-run clean')
        return
    bak = next_bak(SRC)
    shutil.copy2(SRC, bak)
    shutil.copy2(SRC, TMP)
    w = fitz.open(TMP)
    w.set_toc(toc)
    w.set_page_labels([
        {'startpage': 0, 'prefix': '', 'firstpagenum': 1, 'style': 'a'},
        {'startpage': 5, 'prefix': '', 'firstpagenum': 1, 'style': 'r'},
        {'startpage': 7, 'prefix': '', 'firstpagenum': 1, 'style': 'r'},
        {'startpage': 10, 'prefix': '', 'firstpagenum': 1, 'style': 'D'}])
    w.saveIncr()
    w.close()
    shutil.move(TMP, SRC)
    v = fitz.open(SRC)
    tt = v.get_toc(simple=False)
    top = sum(1 for e in tt if isinstance(e[3], dict) and e[3].get('to') and e[3]['to'].y <= 0.5)
    out.write('\nWROTE n=%d page_top=%d labels=%s\n' % (len(tt), top, str(v.get_page_labels())))
    out.close()
    print('written %d bookmarks' % len(tt))


main()
