# -*- coding: utf-8 -*-
"""heading_scan.py — ROUTE H：不手抄目录，靠"排版找标题 + 目录当白名单"自动建书签树。

为什么快：整本法只跑三件事——(1) 逐页 span 聚成视觉行；(2) 用**字号/加粗/上方留白**
找出标题行；(3) 若正文里存在**可解析的印刷目录**，把目录当白名单+层级来源去对齐标题行。
标题锚点来自正文本身（不是目录行），所以不会像 Phase 1b 那样自匹配；
条目集合来自印刷目录（不是随手抓正文标题），所以不会像福昕那样把 `Theorem 3.4` /
`Exercises` 挂成书签。

闸门（全过才输出 ACCEPT，才允许 --write；任一 FAIL → REJECT，该书回落 ROUTE R/P）：
  前提 有可解析的印刷目录（白名单）。目录解析不出来 = 只剩"排版找标题" = 福昕的失败模式，
       一律 REJECT（沈维孝笔记实测：ent=0 却"ACCEPT"了 11 条，就是这条闸门补上的）。
  G0 标题卫生（bm_quality 五类脏物 + 行内引导线残留 + 页码粘进标题）
     ⚠️ 这条是被"四道闸门全过、标题却是 `J | 214R Mandelbrot set`"逼出来的：
        其余闸门只看锚点，**不看字面**。
  G1 编号连续性（章号无跳、`N.M(.K)` 每层无洞）
  G2 (page,y) 单调
  G3 ink_audit 全量（调用 references/ink_audit.py --items --nosheet，需 --g3 或 --write 才跑）
  ＋ MISS=0 ＋ 联合验收 `页码偏差 = Counter(落点物理页 − (印刷页 + K))` 必须 `{0: N}`
定位三趟：① 排版标题 ↔ 目录标题；② 页窗口内"排版像标题"的行（含编号锚）；
③ 目录顺序驱动的全文行搜索（夹在上一条/下一条已匹配之间 + 节号否决）。
K 定不下来时用①②③的结果反推众数 K 再跑一遍（只有条目不减、MISS 不增才采纳）。
纯扫描件（每页 get_text 都空）判 **NO-TEXT**，不崩栈。

用法：
    python heading_scan.py <pdf>                       # dry-run（候选树 + 目录对齐 + 闸门）
    python heading_scan.py <pdf> --g3                  # 连 G3 墨顶一起验（只读，不写）
    python heading_scan.py <pdf> --full                # 打印全部条目
    python heading_scan.py <pdf> --against-toc         # 额外与 PDF 现存书签逐条 diff（试验田）
    python heading_scan.py <pdf> --write [--bak DIR]   # 备份 + 增量写回（闸门必须全过）
    python heading_scan.py <pdf> --write --labels      # 顺带补 /PageLabels（已有标签不覆盖）
    python heading_scan.py <pdf> --labels              # 只看页码标签建议
    调参：--gap 12 --size-tol 0.8 --bf 0.8 --from 1 --to N --maxhead 340 --tilex1 400
"""
import os
import re
import sys
import time
import shutil
import unicodedata
from collections import Counter, defaultdict

import pymupdf as fitz

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

INK = r"C:/Users/asus/.qoder/skills/math-pdf-bookmark/references/ink_audit.py"
sys.path.insert(0, os.path.dirname(INK))
# 标题脏物的五类判据**必须和 bm_quality.py 一致**，否则"ROUTE H 说干净、复审说脏"。
from bm_quality import LEADER_RE, ESCAPE_RE, MOJI_MARKS, CTRL_RE, TEX_RE   # noqa: E402


def norm(s):
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    return re.sub(r"[^0-9a-z\u4e00-\u9fff]", "", s.lower())


NUM = re.compile(r"([0-9]{1,4}|[0-9ivxlcdm]{1,8})\s*$", re.I)
# 引导线：分隔符**可以带空格**（`标题 . . . . 55` 是最常见排版），必须从最左的引导线
# 字符开始剥，否则标题里会残留 " . . . ."。
SEP_TAIL = re.compile(r"(?:[.…·•\-\u2013\u2014|:\u2502]\s*){1,}([0-9]{1,4}|[ivxlcdmIVXLCDM]{1,8})\s*$")
NUMHEAD = re.compile(r"^(\d+(?:[.．]\d+){0,3})(?![0-9])\s*[A-Za-z\u4e00-\u9fff]")
PAGEWORD = re.compile(r"^(part|volume|chapter|kapitel|anhang|appendix|app\.)\b", re.I)
# 页眉/页脚带里"就是一个页码"的短 span（补罗马前置段用，见 roman_front()）
FOLIO_DIG = re.compile(r"^[0-9]{1,4}$")
FOLIO_ROM = re.compile(r"^[ivxlcdmIVXLCDM]{1,8}$")
ROM_VAL = {"I": 1, "V": 5, "X": 10, "L": 50, "C": 100, "D": 500, "M": 1000}
CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f\ufffd]")
DOTRUN = re.compile(r"(?:\s*[.·‥•|｜]){3,}\s*$")     # 点线跑到行尾（页码可能掉字）
LEADTOK = re.compile(r"^(?:[0-9]{1,4}|[ivxlcdmIVXLCDM]{1,6})[ .·)\]]+\s*")


def strip_lead_tok(t):
    """`viii Contents` / `82 Contents` -> `Contents`：剥掉行首页码，用来认页眉"""
    return LEADTOK.sub("", t).strip()


class NoText(Exception):
    """这本书没有文字层：ROUTE H 的前提不成立，直接判定"不适用"而不是崩。"""


def clean(t):
    t = CTRL.sub("", t)
    t = SEP_TAIL.sub("", t)
    t = re.sub(r"\s+([|])\s*$", "", t)
    return re.sub(r"\s+", " ", t).strip(" \u200b\t")


def unjam(t):
    """文字层把章节号和标题粘在一起（`7Harmonic functions`）-> `7 Harmonic functions`"""
    return re.sub(r"^(\d+(?:\.\d+)*)\s*([A-Za-z])", r"\1 \2", t)


# ================================================================ 一本书
class Book:
    # ⚠️ depth() 在 tree_from_headings() 里被用来**算** HAS_PART，
    # 于是第一次进 genexpr 时属性还不存在 → AttributeError（Krantz 解答册，正文里
    # 一个 `Chapter` 都没有、只有 2 条旧书签那条路径）。给个类级默认值斩断自指。
    HAS_PART = False

    def __init__(self, path, gap=12.0, tol=0.8, bfmin=0.80, frm=None, to=None):
        self.path = path
        self.GAP, self.TOL, self.BFMIN = gap, tol, bfmin
        t0 = time.time()
        d = fitz.open(path)
        self.doc = d
        self.n = d.page_count
        self.H = d[0].rect.height
        self.W = d[0].rect.width
        self.lo, self.hi = (frm or 1), (to or self.n)
        self.rows = {}
        for p in range(self.lo, self.hi + 1):
            self.rows[p] = self._rows(p)
        self.load_s = time.time() - t0
        self.calibrate()

    def _rows(self, p):
        raw = []
        for blk in self.doc[p - 1].get_text("dict").get("blocks", []):
            if blk.get("type") != 0:
                continue
            for ln in blk.get("lines", []):
                for s in ln.get("spans", []):
                    if not s["text"].strip():
                        continue
                    x0, y0, x1, y1 = s["bbox"]
                    # [y0, y1, x0, x1, size, nch, bold, italic, text, frag]
                    raw.append([y0, y1, x0, x1, s["size"], len(s["text"].strip()),
                                1 if s["flags"] & 16 else 0, 1 if s["flags"] & 2 else 0,
                                s["text"], 0])
        raw.sort(key=lambda r: r[0])
        # groups: [ytop, items, y0max, y1max, gx0, gx1]
        groups = []
        for r in raw:
            if groups:
                g = groups[-1]
                base = max(i[4] for i in g[1])
                if r[0] - g[2] <= 2.6:
                    g[1].append(r)
                    g[2] = max(g[2], r[0])
                elif (len(r[8].strip()) <= 3 and r[4] <= base - 1.5
                      and r[0] - g[2] <= 6.0
                      and 0.5 * (r[0] + r[1]) <= g[3] - 1.0
                      and g[4] - 2.0 <= r[2] <= g[5] + 2.0):
                    # ---- 上下标碎片：数学字形常单独成 span（`J_ℝ` 的 ℝ 掉到下一基线，
                    #      y0 只低 5 pt、字号小 1.5+）。**在 span 层按 x 插回本行**，
                    #      而不是"并成下一行再追加到上一行末尾"——后者会把目录行的
                    #      `标题 | 页码` 拆坏（实测 Schiff：`Basic properties of J | 214R`）。
                    r[9] = 1
                    g[1].append(r)
                else:
                    groups.append([r[0], [r], r[0], r[1], r[2], r[3]])
                    continue
                g[2] = max(g[2], r[0]) if r[9] == 0 else g[2]
                g[3] = max(g[3], r[1])
                g[4] = min(g[4], r[2])
                g[5] = max(g[5], r[3])
                continue
            groups.append([r[0], [r], r[0], r[1], r[2], r[3]])
        out = []
        for ytop, items, _, _, gx0, gx1 in groups:
            items.sort(key=lambda q: q[2])
            nch = sum(i[5] for i in items) or 1
            buf = []
            for i in items:
                if buf and i[9] == 0:
                    buf.append(" ")          # 碎片**不加空格**，直接贴在前一片末尾
                buf.append(i[8].strip())
            out.append(dict(y0=round(ytop, 2), y1=round(max(i[1] for i in items), 2),
                            x0=round(min(i[2] for i in items), 2),
                            x1=round(max(i[3] for i in items), 2),
                            size=round(max(i[4] for i in items), 2),
                            bf=round(sum(i[5] * i[6] for i in items) / nch, 3),
                            tf=round(sum(i[5] * i[7] for i in items) / nch, 3),
                            text=re.sub(r"\s+", " ", "".join(buf)).strip(),
                            last_x1=round(items[-1][3], 2)))
        return out

    # ---------------------------------------------------------- 校准
    def calibrate(self):
        ch = Counter()
        for rs in self.rows.values():
            for r in rs:
                if 0.06 * self.H < r["y0"] < 0.90 * self.H and len(r["text"]) >= 40:
                    ch[round(r["size"], 1)] += len(r["text"])
        if not ch:
            for rs in self.rows.values():
                for r in rs:
                    ch[round(r["size"], 1)] += len(r["text"])
        if not ch:
            raise NoText("每页 get_text 都是空的（纯扫描件）——ROUTE H 不适用，"
                         "请走 ROUTE P-IMG / Phase 5-6 全本 OCR")
        self.M = ch.most_common(1)[0][0]

        cnt = Counter()
        for rs in self.rows.values():
            seen = set()
            for r in rs:
                k = norm(r["text"])
                if 2 <= len(k) <= 60 and k not in seen:
                    cnt[k] += 1
                    seen.add(k)
        self.REPEAT = {k for k, v in cnt.items() if v >= max(8, 0.06 * len(self.rows))}

        # 贴顶行里"剥掉行首页码后跨页重复"的 = running head（`82 Contents` / `viii Contents`）
        # 只统计"正文号级或小"的贴顶行，避免把章标题（大号）自己当成页眉键
        cnt2 = Counter()
        for p, rs in self.rows.items():
            seen = set()
            for r in rs:
                if r["y0"] < 0.10 * self.H and r["size"] <= self.M + 1.0 and len(r["text"]) <= 45:
                    k2 = norm(strip_lead_tok(r["text"]))
                    if 2 <= len(k2) <= 60 and k2 not in seen:
                        cnt2[k2] += 1
                        seen.add(k2)
        self.RHEAD = {k for k, v in cnt2.items() if v >= 3}

        x0s = Counter(round(r["x0"]) for rs in self.rows.values() for r in rs if len(r["text"]) >= 40)
        x1s = Counter(round(r["last_x1"]) for rs in self.rows.values() for r in rs if len(r["text"]) >= 40)
        self.X0 = x0s.most_common(1)[0][0] if x0s else round(0.06 * self.W)
        self.X1 = x1s.most_common(1)[0][0] if x1s else round(0.94 * self.W)
        self.CW = max(60.0, self.X1 - self.X0)

        # 页眉带：只认"贴顶 + 短 + 跨页重复（整行或剥行首页码后）"的行，公式行不算
        hy = [r["y1"] for rs in self.rows.values() for r in rs
              if r["y0"] < 0.062 * self.H and len(r["text"]) <= 45
              and r["size"] <= self.M + 3
              and (norm(r["text"]) in self.REPEAT
                   or norm(strip_lead_tok(r["text"])) in self.RHEAD)]
        self.HDR = round(max(hy) + 1.0, 1) if hy else round(0.05 * self.H, 1)

        self.TOC = self.find_toc_pages()

    # ---------------------------------------------------------- 候选行
    def is_head_band(self, r):
        """页眉带里的行：整行跨页重复，或剥掉行首页码后跨页重复（后者只认小字号短行）。"""
        return (norm(r["text"]) in self.REPEAT
                or (r["y0"] < 0.10 * self.H and r["size"] <= self.M + 1.0
                    and len(r["text"]) <= 45
                    and norm(strip_lead_tok(r["text"])) in self.RHEAD))

    def scan_rows(self):
        for p in sorted(self.rows):
            if p in self.TOC:
                continue
            prev = None
            for r in self.rows[p]:
                keep = (r["y0"] > self.HDR and r["y0"] < 0.93 * self.H
                        and not self.is_head_band(r))
                gapv = r["y0"] - (prev if prev is not None else self.HDR)
                if keep:
                    rr = dict(r)
                    rr["p"] = p
                    rr["gap"] = round(gapv, 1)
                    yield rr
                prev = r["y1"] if prev is None else max(prev, r["y1"])

    def headings(self):
        res = []
        for r in self.scan_rows():
            t = r["text"]
            if not (2 <= len(t) <= 90):
                continue
            if not re.search(r"[A-Za-z\u4e00-\u9fff]", t):
                continue
            if SEP_TAIL.search(t):
                continue
            big = r["size"] >= self.M + self.TOL
            boldline = r["bf"] >= self.BFMIN and r["size"] >= self.M - 0.6
            if not (big or boldline):
                continue
            if r["x1"] - r["x0"] > 0.80 * self.CW and not big:
                continue
            huge = r["size"] >= self.M + 2.0          # 比正文大 2 pt 以上 = 无歧义标题
            if r["gap"] < self.GAP and not (huge or (big and r["y0"] <= self.HDR + 22)):
                continue
            if boldline and not big and len(t.split()) > 12:
                continue
            res.append(r)
        # 目录页上的**大字号标题行**（`Contents` 自己不会被目录列出）
        for p in sorted(self.TOC):
            prev = None
            for r in self.rows[p]:
                gapv = r["y0"] - (prev if prev is not None else self.HDR)
                if (r["y0"] > self.HDR and r["size"] >= self.M + 3.0
                        and r["bf"] >= 0.5 and 2 <= len(r["text"]) <= 60
                        and gapv >= self.GAP and not SEP_TAIL.search(r["text"])):
                    rr = dict(r)
                    rr["p"] = p
                    rr["gap"] = round(gapv, 1)
                    rr["toc_page"] = True
                    res.append(rr)
                prev = r["y1"] if prev is None else max(prev, r["y1"])
        res.sort(key=lambda r: (r["p"], r["y0"]))
        # ---- 部/章开页的"多行式标题"：'Chapter 13' + 'Special Functions and' + 'Transforms'
        #      合成一条候选（锚取第一行）。目录里印整行，正文常拆成 2–3 行。
        merged, skip = [], set()
        for i, r in enumerate(res):
            if i in skip:
                continue
            if not re.match(r"^(part|volume|chapter|book)\s+([0-9]{1,4}|[ivxlcdm]+)$",
                            r["text"].strip(), re.I):
                continue
            txt, prev, added = r["text"].strip(), r, 0
            for j in range(i + 1, min(i + 6, len(res))):
                o = res[j]
                if j in skip or o["p"] != r["p"] or o["y0"] - prev["y1"] > 60:
                    break
                if not re.search(r"[A-Za-z\u4e00-\u9fff]", o["text"]):
                    break
                if o["size"] < prev["size"] - 1.5:          # 字号掉下来 = 已经进小节了
                    break
                txt += " " + o["text"].strip()
                prev, added = o, added + 1
                if added >= 3:
                    break
            if added:
                rr = dict(r)
                rr["text"] = txt
                merged.append(rr)
                for k in range(1, added + 1):
                    skip.add(i + k)
        if merged:
            res = [r for i, r in enumerate(res) if i not in skip] + merged
            res.sort(key=lambda r: (r["p"], r["y0"]))
        return res

    # ---------------------------------------------------------- 目录页 / 目录行
    def split_lead(self, r):
        """这行是不是目录行？是则返回 (标题, 印刷页码原文)，否则 None。
        三种排版都认：`标题 .... 55` / `标题 | 55`（点线或竖线在前），
        `标题<空白>55` 且页码**贴右边界**（右对齐页码栏），
        以及 `标题 . . . .`（点线到右边界、页码掉字/未印 -> 页码记 None）。"""
        t = r["text"]
        m = SEP_TAIL.search(t)
        if m:
            return t[:m.start()], m.group(1)
        m = NUM.search(t)
        if m and r["last_x1"] >= self.X1 - 10:
            return t[:m.start()], m.group(1)
        m = DOTRUN.search(t)
        if m and len(t) > 12 and r["x1"] >= self.X1 - 20:
            return t[:m.start()], None
        return None

    def _page_rank(self, p):
        """页码大小（罗马 < 阿拉伯，罗马内部按值）"""
        s = str(p).lower().strip()
        if s.isdigit():
            return (1, int(s))
        if s and set(s) <= set("ivxlcdm"):
            v = {"i": 1, "v": 5, "x": 10, "l": 50, "c": 100, "d": 500, "m": 1000}
            tot, prev = 0, 0
            for c in reversed(s):
                x = v[c]
                tot += -x if x < prev else x
                prev = max(prev, x)
            return (0, tot)
        return (0, 0)

    def find_toc_pages(self):
        """目录页 = 满版"标题+引导线+页码"的页。
        种子页必须有 >=4 行**真页码**且页码单调（这一条把索引页挡在外面：
        索引行也带点线页码，但页码是乱序的）；纯点线无页码的页（Alpay 那类掉字的
        目录）只有紧邻已确认目录页时才收，避免把正文里的点线行当目录。"""
        seed, dotonly = set(), set()
        for p, rs in self.rows.items():
            good = [r for r in rs if self.HDR < r["y0"] < 0.92 * self.H
                    and len(r["text"]) >= 4 and not self.is_head_band(r)]
            lead = [(r, s) for r, s in ((r, self.split_lead(r)) for r in good) if s]
            if len(lead) < 4 or len(lead) < 0.5 * len(good):
                continue
            real = [s[1] for _, s in lead if s[1] is not None]
            if len(real) < 4:
                dotonly.add(p)
                continue
            nums = [self._page_rank(x) for x in real]
            up = sum(1 for a, b in zip(nums, nums[1:]) if b >= a)
            if up < 0.8 * (len(nums) - 1):
                continue                            # 页码不单调 = 索引页，不是目录页
            seed.add(p)
        toc = set(seed)
        changed = True
        while changed:                              # 纯点线页只当"目录的续页"收
            changed = False
            for p in dotonly:
                if p not in toc and ((p - 1) in toc or (p + 1) in toc):
                    toc.add(p)
                    changed = True
        return toc

    def toc_entries(self):
        if not self.TOC:
            return []
        ent, buf, buf_ind = [], [], 0.0
        for p in sorted(self.TOC):
            page = [r for r in self.rows[p]
                    if r["y0"] > self.HDR and not self.is_head_band(r)]
            if not page:
                continue
            mx = min(r["x0"] for r in page)
            for r in page:
                s = self.split_lead(r)
                ind = r["x0"] - mx
                if s is None:
                    t = clean(r["text"])
                    if r["size"] >= self.M + 3.0 or not t:
                        continue                      # 目录页自己的大标题
                    if r["bf"] >= 0.5 or r["size"] > self.M + 0.8:
                        if buf:                       # 上一段悬空的续行先落成条目
                            ent.append(dict(title=unjam(" ".join(buf)), printed=None,
                                            x=buf_x, ind=buf_ind, p=p))
                            buf = []
                        ent.append(dict(title=unjam(t), printed=None,
                                        x=r["x0"], ind=ind, p=p))
                        continue
                    if len(t) <= 80:                  # 真正的换行续行
                        buf.append(t)
                        buf_ind, buf_x = ind, r["x0"]
                    continue
                title = clean(s[0])
                if buf:
                    title = " ".join(buf) + " " + title
                    ind, buf_ind = buf_ind, ind
                    buf = []
                if not title:
                    continue
                ent.append(dict(title=unjam(title), printed=s[1], x=r["x0"],
                                ind=ind, p=p))
        if not ent:
            return []
        # 层级：本页缩进分档（逐页取自己的左边界）
        ds = sorted({round(e["ind"]) for e in ent})
        cuts = []
        for k in range(1, len(ds)):
            if ds[k] - ds[k - 1] >= 8:
                cuts.append(ds[k - 1] + (ds[k] - ds[k - 1]) / 2.0)
        for e in ent:
            lv = 1
            for c in cuts:
                if e["ind"] >= c:
                    lv += 1
            if re.match(r"^(part|volume)\b", e["title"].lower()):
                e["part"] = True
            e["lv"] = min(lv, 4)
        # ---- 层级校正：**编号深度优先于缩进分档**（缩进会被排版习惯骗到）
        #      有"部/卷"分组行时 章=2 节=3 小节=4；没有时 章=1 节=2 小节=3。
        #      纯文字标题的目录（Schiff 那类不带编号）不动，仍用缩进分档。
        def ndepth(t):
            m = NUMHEAD.match(t)
            if not m:
                return None
            return len(m.group(1).replace("．", ".").split("."))
        numbered = [e for e in ent if ndepth(e["title"]) is not None]
        if len(numbered) >= max(6, 0.5 * len(ent)):
            shift = 2 if any(e.get("part") for e in ent) else 1
            for e in ent:
                d = ndepth(e["title"])
                if d is not None:
                    e["lv"] = min(4, shift - 1 + d)
                elif e.get("part"):
                    e["lv"] = 1
                else:
                    e["lv"] = min(e["lv"], shift)
        # ---- 借页：分组行（章名/部名整行没印页码）用**它后面第一条有页码的条目**
        #      的印刷页当近似页——章一定开在它第一个小节之前。
        nxt = None
        for e in reversed(ent):
            if str(e["printed"]).isdigit():
                nxt = int(e["printed"])
            elif nxt is not None:
                e["approx"] = nxt
        return ent

    # ---------------------------------------------------------- 层级（纯排版路线）
    def depth(self, r):
        t = r["text"]
        m = NUMHEAD.match(t)
        if m:
            return len(m.group(1).replace("．", ".").split(".")), "num"
        pw = PAGEWORD.match(t)
        if pw:
            w = pw.group(1).lower()
            if w in ("part", "volume"):
                return 1, "part"
            if w in ("chapter", "kapitel"):
                return 2 if self.HAS_PART else 1, "chapter"
            return 1, "kw"
        return None, None

    def tree_from_headings(self, hs):
        sizes = sorted({round(h["size"], 1) for h in hs}, reverse=True)
        self.SIZES = sizes
        rank = {s: i for i, s in enumerate(sizes)}
        self.HAS_PART = any(self.depth(h)[1] == "part" for h in hs)
        cal = defaultdict(Counter)
        for h in hs:
            d, k = self.depth(h)
            if d is not None:
                cal[round(h["size"], 1)][d] += 1
        self.SIZE2LV = {s: c.most_common(1)[0][0] for s, c in cal.items()}
        out, prev, prev_lv, prev_key = [], (0, 0.0), 0, None
        for h in hs:
            k = norm(h["text"])
            if k == prev_key:
                continue
            prev_key = k
            d, how = self.depth(h)
            if d is None:
                s = round(h["size"], 1)
                d, how = (self.SIZE2LV[s], "size-cal") if s in self.SIZE2LV \
                    else (1 + rank[s], "size-rank")
            lv = max(1, min(int(d), prev_lv + 1, 4))
            if (h["p"], h["y0"]) <= prev:
                continue
            out.append(dict(lv=lv, title=clean(h["text"]), p=h["p"], y=h["y0"],
                            size=h["size"], bf=h["bf"], gap=h["gap"], x0=h["x0"],
                            x1=h.get("x1", h["x0"] + 200.0), how=how))
            prev_lv, prev = lv, (h["p"], h["y0"])
        return out

    # ---------------------------------------------------------- 标题比对
    @staticmethod
    def tscore(a, b):
        """0 不同 / 1 差一个字符 / 2 长串包含 / 3 全等（a、b 都过 norm）"""
        if not a or not b:
            return 0
        if a == b:
            return 3
        if min(len(a), len(b)) >= 12 and (a in b or b in a):
            return 2
        if min(len(a), len(b)) >= 8 and abs(len(a) - len(b)) == 1:
            lo, hi = (a, b) if len(a) < len(b) else (b, a)
            for i in range(len(hi)):
                if hi[:i] + hi[i + 1:] == lo:
                    return 1
        return 0

    # ---------------------------------------------------------- K：印刷页 -> 物理页
    def estimate_k(self, hs, ent):
        """K = 物理页 − 印刷页。用**目录里带页码、标题在目录中唯一**的条目投票：
        优先"裸编号开头"的章名（全书只出现一次、又带页码，最可靠）；章名不印页码的
        书（Alpay 那类）退到全体有页码的唯一标题。投票取众数，噪声被正确票压掉。"""
        uniq = Counter(norm(e["title"]) for e in ent)
        def ok(e):
            return (str(e["printed"]).isdigit() and int(e["printed"]) > 0
                    and uniq[norm(e["title"])] == 1)
        l1 = {norm(e["title"]): e for e in ent if ok(e) and re.match(r"^\d+\s", e["title"])}
        if len(l1) < 3:
            l1 = {norm(e["title"]): e for e in ent if ok(e)}
        v = Counter()
        for h in hs:
            m = NUMHEAD.match(h["text"])
            if m and ("." in m.group(1) or "．" in m.group(1)):
                continue
            e = l1.get(norm(h["text"]))
            if e:
                v[h["p"] - int(e["printed"])] += 1
        if not v:
            for h in hs:
                for k, e in l1.items():
                    if self.tscore(k, norm(h["text"])) == 3:
                        v[h["p"] - int(e["printed"])] += 1
        return v

    # ---------------------------------------------------------- 目录白名单对齐
    def align(self, hs, ent):
        """两趟：先按 estimate_k 的页码偏移对齐；**K 定不下来**的书（前置不印 folio、
        目录页码掉字）用第一趟的对齐结果反推 K（众数、且占多数），再跑第二趟。
        只有"条目不减、MISS 不增"才采纳第二趟——K 猜错会让整体错位。"""
        items, miss, extra = self._align(hs, ent)
        if self.K is None:
            v = Counter(i["p"] - int(i["printed"]) for i in items
                        if str(i["printed"]).isdigit() and int(i["printed"]) > 0
                        and i["how"] in ("align", "fallback", "num"))
            if v:
                k, c = v.most_common(1)[0]
                if c >= max(5, 0.5 * sum(v.values())):
                    it2, mi2, ex2 = self._align(hs, ent, _kf=k)
                    if len(it2) >= len(items) and len(mi2) <= len(miss):
                        return it2, mi2, ex2
        return items, miss, extra

    def _align(self, hs, ent, _kf=None):
        hkeys = [norm(h["text"]) for h in hs]
        self.KV = self.estimate_k(hs, ent)
        self.K = self.KV.most_common(1)[0][0] if self.KV else None
        if self.K is None and _kf is not None:
            self.K = _kf
        arab = [int(e["printed"]) for e in ent if str(e["printed"]).isdigit()]
        self.first_body_page = (min(arab) + self.K - 1) if (arab and self.K is not None) \
            else self.hi
        WIN = 3
        self.n_numhit = 0
        used = [False] * len(hs)
        fb = []                       # 兜底行单独存，避免污染 hs 的下标
        match, miss = {}, []
        last = (0, 0.0)               # 上一条已匹配条目的 (页, y)：目录顺序 = 正文顺序

        def like_heading(r):
            return (r["size"] >= self.M + self.TOL
                    or (r["bf"] >= self.BFMIN and r["size"] >= self.M - 0.6))

        for ei, e in enumerate(ent):
            key = norm(e["title"])
            pr = e["printed"]
            ap = e.get("approx")
            me = NUMHEAD.match(e["title"])
            enum = me.group(1).replace("．", ".") if me else None
            if self.K is not None and str(pr).isdigit() and int(pr) > 0:
                exp, wl, wh = int(pr) + self.K, WIN, WIN
            elif self.K is not None and ap:
                exp, wl, wh = ap + self.K, 25, 5     # 借页：章开在它第一个小节之前
            else:
                exp, wl, wh = None, 0, 0
            best, bsc = None, 1.99              # 至少要"长串包含"级
            for j, h in enumerate(hs):
                if used[j] or (h["p"], h["y0"]) < last:
                    continue
                if exp is not None:
                    if h["p"] - exp > wh or exp - h["p"] > wl:
                        continue
                elif h["p"] > self.first_body_page:
                    continue                     # 前置条目只在正文起点之前找
                sc = self.tscore(key, hkeys[j])
                if not sc:
                    continue
                if exp is not None:
                    sc += (max(wl, wh) - abs(h["p"] - exp)) / 100.0
                if sc > bsc:
                    best, bsc = j, sc
            if best is None and exp is not None and str(pr).isdigit():  # 兜底：页窗口里找"排版像标题"的这一行
                cand = []
                for p in range(max(self.lo, exp - WIN), min(self.hi, exp + WIN) + 1):
                    if p in self.TOC:
                        continue
                    for r in self.rows[p]:
                        if (r["y0"] <= self.HDR or r["y0"] > 0.93 * self.H
                                or self.is_head_band(r)
                                or not like_heading(r) or len(r["text"]) > 80
                                or SEP_TAIL.search(r["text"])):
                            continue
                        if (p, r["y0"]) < last:
                            continue
                        sc = self.tscore(key, norm(r["text"]))
                        bynum = 0
                        if not sc and enum:         # 编号锚：印刷目录与正文标题措辞不同
                            m2 = NUMHEAD.match(r["text"])
                            if m2 and m2.group(1).replace("．", ".") == enum:
                                sc, bynum = 2.05, 1
                        if sc >= 2:
                            cand.append((sc + (WIN - abs(p - exp)) / 10.0, p, r, bynum))
                if cand:
                    cand.sort(key=lambda q: (-q[0], q[1], q[2]["y0"]))
                    sc, p, r, bynum = cand[0]
                    fb.append(dict(r, p=p, gap=99.0, toc_page=False, numhit=bynum,
                                   j=len(fb) + 10 ** 6))
                    best = ("fb", len(fb) - 1)
                    if bynum:
                        self.n_numhit = getattr(self, "n_numhit", 0) + 1
            if best is None:
                miss.append(e["title"])
                continue
            if isinstance(best, tuple):
                h = fb[best[1]]
            else:
                used[best] = True
                h = hs[best]
            match[ei] = h
            last = (h["p"], h["y0"])

        # ---- 第三趟：目录顺序驱动的**全文行**搜索。前两趟只在"排版像标题"的行里找，
        #      行距紧、标题又不加粗的书（Ahlfors 实测 172 条只对齐 7 条）正文标题根本
        #      进不了候选表。这里放开排版条件，但把搜索**夹在上一条已匹配和下一条已匹配
        #      之间**（顺序闸门），再加节号否决，所以不会跑到隔壁节里去。
        todo = [ei for ei in range(len(ent)) if ei not in match]
        if todo:
            body = self.body_rows()
            done = sorted(match)
            anchor, di = (0, 0.0), 0
            for ei in todo:
                while di < len(done) and done[di] < ei:
                    hm = match[done[di]]
                    anchor = max(anchor, (hm["p"], hm["y0"]))
                    di += 1
                hi_pos = ((match[done[di]]["p"], match[done[di]]["y0"])
                          if di < len(done) else (self.hi + 2, 0.0))
                e = ent[ei]
                key = norm(e["title"])
                pr = e["printed"]
                exp = (int(pr) + self.K) if (self.K is not None and str(pr).isdigit()
                                             and int(pr) > 0) else None
                me = NUMHEAD.match(e["title"])
                enum = me.group(1).replace("．", ".") if me else None
                best = None
                if len(key) >= 6:
                    seen = 0
                    for p, r, rk in self.body_range(anchor, hi_pos):
                        if seen >= 4000:
                            break                          # 防病态运行时（整本书重扫）
                        seen += 1
                        hd = like_heading(r)
                        if exp is not None:
                            # **有印刷页码线索就必须落在 ±3 页内**（和第一趟同一个窗口）。
                            # 放宽到 ±12 实测把 dev 直方图搅成 {0:16, -3:28, …}（Narasimhan
                            # 128 条），宁可 MISS 也不要"看着对齐了"的错锚。
                            if abs(p - exp) > 3:
                                continue
                        elif not hd:
                            continue                       # 没页码线索时只认"排版也像标题"的
                        sc = self.tscore(key, rk)
                        if not sc:
                            continue
                        m2 = NUMHEAD.match(r["text"])
                        rn = m2.group(1).replace("．", ".") if m2 else None
                        if enum and rn and enum != rn:
                            continue                       # 节号否决
                        if hd:
                            sc += 0.4
                        if best is None or sc > best[0]:
                            best = (sc, p, r)
                            if sc >= 3.4:
                                break                    # 全等 + 排版像标题，不用再扫
                if best is None:
                    continue                             # 真找不到：留给 miss 统计
                sc, p, r = best
                fb.append(dict(r, p=p, gap=99.0, toc_page=False, numhit=0,
                               textonly=1, j=len(fb) + 10 ** 6))
                match[ei] = fb[-1]
                anchor = (p, r["y0"])
            miss = [e["title"] for ei, e in enumerate(ent) if ei not in match]

        items = []
        for ei in range(len(ent)):
            if ei not in match:
                continue
            e, h = ent[ei], match[ei]
            items.append(dict(tvl=e["lv"], title=e["title"], p=h["p"], y=h["y0"],
                              size=h["size"], bf=h["bf"], gap=h["gap"], x0=h["x0"],
                              x1=h.get("x1", h["x0"] + 200.0), printed=e["printed"],
                              how=("num" if h.get("numhit") else
                                   ("text" if h.get("textonly") else
                                    ("fallback" if h["gap"] >= 99 else "align")))))
        # 目录页自己的大标题（`Contents` 这种"目录不会列自己"的条目）补回去
        for j, h in enumerate(hs):
            if h.get("toc_page") and not used[j]:
                items.append(dict(tvl=1, title=clean(h["text"]), p=h["p"], y=h["y0"],
                                  size=h["size"], bf=h["bf"], gap=h["gap"], x0=h["x0"],
                                  x1=h.get("x1", h["x0"] + 200.0), printed="?",
                                  how="toc-title"))
        items.sort(key=lambda i: (i["p"], i["y"]))
        out, prev_lv = [], 0
        for i in items:
            i["lv"] = max(1, min(i.pop("tvl"), prev_lv + 1))
            prev_lv = i["lv"]
            out.append(i)
        extra = [hs[j]["text"] for j in range(len(hs))
                 if not used[j] and hs[j]["gap"] < 99 and not hs[j].get("toc_page")]
        return out, miss, extra

    # ---------------------------------------------------------- 全文行（第三趟用）
    def body_rows(self):
        """正文里所有"像一行标题文字"的行（**不做排版筛选**），带预计算 norm。
        排除目录页自身（自匹配陷阱）和页眉带。"""
        if getattr(self, "_body", None) is None:
            arr, pgs, st = [], [], []
            for p in sorted(self.rows):
                if p in self.TOC:
                    continue
                first = True
                for r in self.rows[p]:
                    t = r["text"]
                    if (r["y0"] <= self.HDR or r["y0"] > 0.93 * self.H
                            or self.is_head_band(r) or not (2 <= len(t) <= 90)
                            or SEP_TAIL.search(t)
                            or not re.search(r"[A-Za-z\u4e00-\u9fff]", t)):
                        continue
                    if first:
                        pgs.append(p)
                        st.append(len(arr))
                        first = False
                    arr.append((p, r, norm(t)))
            self._body, self._bpg, self._bst = arr, pgs, st
        return self._body

    def body_range(self, lo_pos, hi_pos):
        """取 (page,y) 落在 lo（不含）.. hi（不含）之间的那些正文行。"""
        import bisect
        arr, pgs, st = self._body, self._bpg, self._bst
        if not arr:
            return []
        i = st[bisect.bisect_left(pgs, lo_pos[0])] if lo_pos[0] <= pgs[-1] else len(arr)
        while i < len(arr) and (arr[i][0], arr[i][1]["y0"]) <= lo_pos:
            i += 1
        k = bisect.bisect_left(pgs, hi_pos[0])
        j = st[k] if (k < len(pgs) and pgs[k] == hi_pos[0]) else len(arr)
        while j < len(arr) and (arr[j][0], arr[j][1]["y0"]) < hi_pos:
            j += 1
        return arr[i:min(j, len(arr))]

    # ---------------------------------------------------------- 墨顶
    def snap(self, items, dpi=200.0, lo=2.0, hi=12.0):
        import numpy as np
        SC = 72.0 / dpi
        n = 0
        for it in items:
            y = it["y"] + 1.0
            try:
                pix = self.doc[it["p"] - 1].get_pixmap(
                    matrix=fitz.Matrix(SC, SC),
                    clip=fitz.Rect(it["x0"], y, min(it["x1"] + 6, self.W), y + 22.0),
                    colorspace=fitz.csGRAY)
            except Exception:
                continue
            a = np.frombuffer(pix.samples, np.uint8).reshape(pix.height, pix.stride)[:, :pix.width]
            on = (a < 140).mean(axis=1) > 0.004
            rw = np.where(on)[0]
            if not len(rw):
                continue
            top = y + rw[0] / SC
            d = top - it["y"]
            if lo <= d <= hi:
                it["y"] = float(round(top, 2))
                n += 1
        self.n_snapped = n
        return n

    # ---------------------------------------------------------- 写回
    @staticmethod
    def _rom2int(t):
        t, v, prev = t.upper(), 0, 0
        for c in reversed(t):
            n = ROM_VAL[c]
            v += n if n >= prev else -n
            prev = max(prev, n)
        return v

    def roman_front(self, upto):
        """前 `upto` 页（0 基，不含）里**印刷罗马 folio 的连续游程** → (startpage0, style)。

        为什么需要：目录条目只收得到"印了页码的条目"，而 **Alpay 这类书前置不编号**
        （Contents 里 Prologue 之前一条罗马页码都没有），于是纯目录推导会漏掉
        `pages 3..12 = i..x` 这一段，读者看到封面被标成"1"，与书面不符。
        这里不猜版式，只认"逐页 +1 的游程"：真 folio 天然满足，
        `Part II` / 章节号 / 脚注号这类误抓会打断递推 → 形不成 ≥3 页的游程。
        """
        cand, txtd = [], []
        for i in range(min(upto, self.n)):
            pg, H = self.doc[i], self.doc[i].rect.height
            vals, tok = Counter(), {}
            for b in pg.get_text("dict")["blocks"]:
                for l in b.get("lines", []):
                    for s in l["spans"]:
                        # ⚠️ bbox = (x0, **y0**, x1, **y1**)。判"整条 span 在带内"要用
                        # **上带的 y1**（`bbox[3] ≤ 0.10H`）和**下带的 y0**（`bbox[1] ≥ 0.90H`）。
                        # 写成 `bbox[1] ≤ 0.10H` 就把"起点刚过线、主体在正文里"的行当 folio：
                        # Alpay p10 的 `Part II` 起于 67.2 pt（<0.10H=68.03）、底在 79.2，
                        # 误当候选后那页出现两个值 → 游程断掉、罗马段消失（实测踩过）。
                        if not (s["bbox"][3] <= 0.10 * H or s["bbox"][1] >= 0.90 * H):
                            continue
                        t = s["text"].strip()
                        if FOLIO_ROM.match(t) and len(t) <= 6:
                            try:
                                v = self._rom2int(t)
                            except KeyError:
                                continue
                            vals[v] += 1
                            tok.setdefault(v, t)
            if len(vals) == 1:
                v = next(iter(vals))
                cand.append(v)
                txtd.append(tok[v])
            else:                      # 一页两个不同数字 = 版式歧义，整页弃
                cand.append(None)
                txtd.append("")
        best = None
        i = 0
        while i < len(cand):
            if cand[i] is None:
                i += 1
                continue
            v0, L = cand[i], 1
            while i + L < len(cand) and cand[i + L] == v0 + L:
                L += 1
            if L >= 3 and (best is None or L > best[2]):
                best = (i, v0, L)
            i += 1                            # 只走一页：游程 <3 时从下一页重新试
        if not best:
            return None
        i0, v0, L = best
        st = i0 - v0 + 1
        if st < 0:
            return None
        seq = txtd[i0:i0 + L]                 # 书面实际大小写（Schiff 印 I…XVI）
        return st, ("R" if sum(t.isupper() for t in seq)
                              > sum(t.islower() for t in seq) else "r")

    def propose_labels(self, items):
        """由目录条目的 (印刷页, 物理页) 反推 /PageLabels：前置罗马段 + 正文阿拉伯段。
        只给"建议"，是否落盘看现有标签——出版商写对的书不许覆盖（Schiff 就是）。
        ⚠️ **`startpage` 是 0-based**（实测：Alpay 印刷页 1 在物理第 13 页 → 必须写 12；
        写 13 会让 `doc[12].get_label()` 直接抛 IndexError，阅读器整本偏一页）。
        内部 `i["p"]` 是 1-based 物理页，所以出口统一 −1。"""
        rom, ara = [], []
        for i in items:
            pr = str(i["printed"] or "")
            if not pr:
                continue
            if pr.isdigit():
                ara.append((int(pr), i["p"]))
            elif set(pr.lower()) <= set("ivxlcdm") and self._page_rank(pr)[0] == 0:
                rom.append((self._page_rank(pr)[1], i["p"], pr))
        segs = []
        if rom:
            off = Counter(p - r for r, p, _ in rom).most_common(1)[0][0]
            up = any(x[2].isupper() for x in rom) and not any(x[2].islower() for x in rom)
            segs.append({'startpage': 0, 'style': 'R' if up else 'r',
                         'firstpagenum': max(1, 1 - off)})
        elif ara:
            # 目录里一条罗马页码都没有 → 去**书面**找连续 folio 游程补这一段（Alpay）
            rf = self.roman_front(max(0, min(p for _, p in ara) - 1))
            if rf:
                segs.append({'startpage': rf[0], 'style': rf[1], 'firstpagenum': 1})
        if ara:
            off = Counter(p - n for n, p in ara).most_common(1)[0][0]
            start = min(p for _, p in ara)
            segs.append({'startpage': max(0, start - 1), 'style': 'D',
                         'firstpagenum': max(1, start - off)})
        if segs and segs[0]["startpage"] > 0:
            # 前置那几页没有罗马 folio 可依据（章/部不印页码的书常这样）也要有标签：
            # 补一段从封面起的阿拉伯段，否则标签数组不从第 0 页起，
            # `page.get_label()` 会抛 "no label"，阅读器也可能整本错位。
            segs.insert(0, {'startpage': 0, 'style': 'D', 'firstpagenum': 1})
        return segs

    def verify_labels(self, segs):
        """写完必须自己读回：每段起点那一页的 label 必须等于该页的印刷页码。"""
        c = fitz.open(self.path)
        bad = []
        for s in segs:
            i = s["startpage"]
            if i >= c.page_count:
                bad.append("startpage %d 越界" % i)
                continue
            try:
                got = c[i].get_label()
            except Exception as e:
                bad.append("page %d get_label 抛 %s" % (i, type(e).__name__))
                continue
            exp = ("%d" % s["firstpagenum"]) if s["style"] == "D" else \
                self._roman(s["firstpagenum"]).upper() if s["style"] == "R" else \
                self._roman(s["firstpagenum"])
            if got.replace(s.get("prefix", ""), "") != exp:
                bad.append("page %d 读到 %s 期望 %s" % (i, got, exp))
        n = c.page_count
        c.close()
        return bad, n

    @staticmethod
    def _roman(v):
        tbl = [(1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"), (90, "xc"),
               (50, "l"), (40, "xl"), (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")]
        s = ""
        for n, r in tbl:
            while v >= n:
                s += r
                v -= n
        return s


    def apply_labels(self, segs):
        if not segs:
            return "无页码数据，跳过标签"
        cur = self.doc.get_page_labels()
        if cur:
            return "已有 %d 段页码标签，**不覆盖**（先人工核对）: %s" % (len(cur), cur)
        tmp = os.path.join(os.environ.get("TEMP", "."), "_hs_lab.pdf")
        shutil.copy2(self.path, tmp)
        d = fitz.open(tmp)
        d.set_page_labels(segs)
        d.saveIncr()
        d.close()
        shutil.move(tmp, self.path)
        c = fitz.open(self.path)
        got = c.get_page_labels()
        c.close()
        self.doc = fitz.open(self.path)
        bad, npg = self.verify_labels(segs)
        return "写入 %d 段 -> 读回 %s  逐段起点核对 %s（共 %d 页）" % (
            len(segs), got, ("PASS" if not bad else "FAIL %s" % bad), npg)

    def shift(self, p):
        pg = self.doc[p - 1]
        return pg.mediabox.y1 - pg.cropbox.y1

    def write(self, items, bak=None):
        tmp = os.path.join(os.environ.get("TEMP", "."), "_hs_write.pdf")
        if bak:
            os.makedirs(bak, exist_ok=True)
            dst = os.path.join(bak, os.path.basename(self.path).replace(".pdf", "_pre1.pdf"))
            if not os.path.exists(dst):
                shutil.copy2(self.path, dst)
        shutil.copy2(self.path, tmp)
        d = fitz.open(tmp)
        toc, prev = [], 0
        sh = {p: self.shift(p) for p in range(1, self.n + 1)}
        for it in items:
            lv = min(it["lv"], prev + 1)
            toc.append([lv, it["title"], it["p"], round(it["y"] - sh[it["p"]], 2)])
            prev = lv
        for row in toc:
            row[3] = float(row[3])          # 必须 python float：numpy 标量会静默写坏 dest
            assert row[2] == int(row[2])
        d.set_toc(toc)
        d.saveIncr()
        d.close()
        shutil.move(tmp, self.path)
        c = fitz.open(self.path)
        got = c.get_toc(simple=False)
        err = 0.0
        for (lv, t, p, y), e in zip(toc, got):
            err = max(err, abs(e[3]["to"].y - (y + self.shift(p))))
        hist = Counter(round(v, 2) for v in sh.values())
        print("   wrote=%d max_err=%.3f cropbox shifts=%s size=%d" %
              (len(got), err, dict(hist), os.path.getsize(self.path)))
        c.close()
        self.doc.close()
        self.doc = fitz.open(self.path)          # 后面的验收要看写回后的文件
        return err


# ================================================================ 闸门
def g1_numbering(items):
    bad = []
    chs = [int(re.match(r"^(\d+)", i["title"]).group(1)) for i in items
           if i["lv"] == 1 and re.match(r"^\d+\s", i["title"])]
    for a, b in zip(chs, chs[1:]):
        if b - a == 2:
            bad.append("章号跳 %d->%d" % (a, b))
        elif b <= a:
            bad.append("章号回退 %d->%d" % (a, b))
    stack = {}
    for i in items:
        m = re.match(r"^(\d+(?:\.\d+)+)\b", i["title"])
        if not m:
            continue
        parts = m.group(1).split(".")
        parent = ".".join(parts[:-1])
        exp = stack.get(parent, 0) + 1
        if int(parts[-1]) != exp:
            bad.append("%s 下出现 %s（期望 %s.%d）%s" %
                       (parent, m.group(1), parent, exp, i["title"][:30]))
        stack[parent] = int(parts[-1])
    return bad


def g2_mono(items):
    bad, prev = [], (0, 0.0)
    for i in items:
        if (i["p"], i["y"]) <= prev:
            bad.append("非单调 p%d y%.1f（在 p%d y%.1f 后）" % (i["p"], i["y"], prev[0], prev[1]))
        prev = max(prev, (i["p"], i["y"]))
    return bad


# ---- G0 标题卫生：五类脏物沿用 bm_quality.py 的判据（leader/escape/moji/ctrl/latex），
#      再加两条 ROUTE H 特有的：**行内引导线残留**（`标题 | 214`）和
#      **页码粘进标题**（`... | 214R Mandelbrot set`、`transformations2`）。
#      这两条是本轮实战逼出来的：并入下标碎片时把目录行的页码搅进了标题，
#      而 MISS/偏差/单调/ink 四道闸门**全部照过**——闸门只看锚点，不看字面。
G0_LEADER = re.compile(r"[|｜]").search
G0_GLUE = re.compile(r"\d[A-Za-z]").search
G0_LEADNUM = re.compile(LEADER_RE)
G0_ESC = re.compile(ESCAPE_RE)
G0_TEX = re.compile(TEX_RE)
G0_CTRL = re.compile(CTRL_RE)


def g0_titles(items):
    bad = []
    for i in items:
        t = str(i["title"])
        why = ("引导线" if G0_LEADER(t) else
               "页码粘连" if G0_GLUE(t) else
               "点线+页码" if G0_LEADNUM.search(t) else
               "转义" if G0_ESC.search(t) else
               "LaTeX" if G0_TEX.search(t) else
               "控制符" if G0_CTRL.search(t) else
               "乱码" if any(m in t for m in MOJI_MARKS) else
               "空/超长" if not (2 <= len(t) <= 120) else None)
        if why:
            bad.append("%s: %s" % (why, t[:70]))
    return bad


# ================================================================ main
def main():
    argv = sys.argv[1:]
    if not argv:
        print(__doc__)
        return 1
    pdf = argv[0]

    def opt(name, cast=str, dflt=None):
        return cast(argv[argv.index(name) + 1]) if name in argv else dflt

    t0 = time.time()
    try:
        b = Book(pdf, gap=opt("--gap", float, 12.0), tol=opt("--size-tol", float, 0.8),
                 bfmin=opt("--bf", float, 0.80), frm=opt("--from", int), to=opt("--to", int))
    except NoText as e:
        print("== %s\n== ROUTE H 判定: NO-TEXT（%s）" % (os.path.basename(pdf), e))
        return 3
    hs = b.headings()
    ent = b.toc_entries()
    if ent:
        items, miss, extra = b.align(hs, ent)
    else:
        items, miss, extra = b.tree_from_headings(hs), [], []
    b.snap(items)
    el = time.time() - t0

    print("== %s" % os.path.basename(pdf))
    print("   pages=%d  M=%.1f  HDR=%.1f  x=[%d,%d] cw=%d  load=%.1fs total=%.1fs" %
          (b.n, b.M, b.HDR, b.X0, b.X1, b.CW, b.load_s, el))
    print("   TOC pages=%s  repeated=%d kinds  body headings=%d  sizes=%s size2lv=%s" %
          (sorted(b.TOC), len(b.REPEAT), len(hs), b.SIZES if hasattr(b, "SIZES") else "-",
           b.SIZE2LV if hasattr(b, "SIZE2LV") else "-"))
    print("   目录条目=%d -> 对齐 %d / MISS %d / 正文多抓(已丢) %d  K=%s  墨顶校正=%d" %
          (len(ent), len(items), len(miss), len(extra), b.K if hasattr(b, "K") else "-", b.n_snapped))
    print("   定位方式=%s  借页条目=%d" %
          (dict(Counter(i["how"] for i in items)), sum(1 for e in ent if e.get("approx"))))
    print("   levels=%s" % dict(Counter(i["lv"] for i in items)))
    if miss:
        print("   MISS: %s" % miss[:15])
    if extra:
        print("   多抓: %s" % extra[:15])
    for i in (items if "--full" in argv else items[:30]):
        print("   L%d p%-4d y%-7.1f sz%-5.1f bf%-4.2f gap%-5.1f %-8s %s" %
              (i["lv"], i["p"], i["y"], i["size"], i["bf"], i["gap"], i["how"], i["title"][:58]))

    gates = {}
    # 没有可解析的印刷目录 = 只剩"排版找标题"，那正是福昕的失败模式（run-in 定理、
    # Exercises 全挂成书签）。**这种书一律不许 ACCEPT**，回落 ROUTE R/P。
    gates["有印刷目录(白名单)"] = bool(ent)
    gates["MISS=0"] = (len(miss) == 0)
    if hasattr(b, "K") and b.K is not None and ent:
        dev = Counter(i["p"] - (int(i["printed"]) + b.K)
                      for i in items if str(i["printed"]).isdigit())
        gates["页码偏差={0:N}"] = (set(dev) == {0})
        print("   页码偏差直方图: %s" % dict(dev))
    bad1, bad2 = g1_numbering(items), g2_mono(items)
    bad0 = g0_titles(items)
    gates["G0 标题卫生"] = not bad0
    gates["G1 编号连续"] = not bad1
    gates["G2 (page,y) 单调"] = not bad2
    if bad0:
        print("   G0: %s" % bad0[:6])
    if bad1:
        print("   G1: %s" % bad1[:6])
    if bad2:
        print("   G2: %s" % bad2[:4])
    tmp = os.path.join(os.environ.get("TEMP", "."), "_hs_items.txt")
    with open(tmp, "w", encoding="utf-8") as f:
        for i in items:
            f.write("%d\t%.2f\t%d\t%s\n" % (i["p"], i["y"], i["lv"], i["title"]))
    cmd = [sys.executable, INK, pdf, "--maxhead",
           opt("--maxhead", str, str(int(min(b.CW + 12, 460)))),
           "--tilex1", opt("--tilex1", str, str(int(min(b.X1 + 10, b.W - 4)))),
           "--items", tmp, "--nosheet"]
    print("G3 ink_audit: %s" % " ".join('"%s"' % x for x in cmd))
    if "--write" in argv or "--g3" in argv:
        import subprocess
        try:
            rr = subprocess.run(cmd, capture_output=True, text=True, encoding="utf-8",
                                errors="replace", timeout=1800)
            line = [x for x in (rr.stdout or "").splitlines() if "ok=" in x]
            m = re.search(r"ok=(\d+)/(\d+)\s+bad=(\d+)", line[-1]) if line else None
            if m:
                gates["G3 墨顶 ink_audit"] = (int(m.group(3)) == 0)
                print("   G3: ok=%s/%s bad=%s" % (m.group(1), m.group(2), m.group(3)))
            else:
                gates["G3 墨顶 ink_audit"] = False
                print("   G3: 无结论 %r" % ((rr.stdout or "")[-200:] + (rr.stderr or "")[-200:]))
        except Exception as e:
            gates["G3 墨顶 ink_audit"] = False
            print("   G3: 运行失败 %r" % (e,))
    print("闸门: %s" % "  ".join("%s=%s" % (k, "PASS" if v else "FAIL")
                                for k, v in gates.items()))
    fail = [k for k, v in gates.items() if not v]
    part = (fail == ["MISS=0"] and len(items) >= 10
            and len(miss) <= max(2, int(0.03 * len(ent))))
    verdict = "ACCEPT" if not fail else ("PARTIAL" if part else "REJECT")
    print("== ROUTE H 判定: %s%s" % (verdict,
          "（丢 %d 条定位不到的，其余 %d 条闸门全过）" % (len(miss), len(items))
          if verdict == "PARTIAL" else ""))

    if "--against-toc" in argv:
        old = b.doc.get_toc(simple=False)
        print("---- vs 现存书签 %d 条 ----" % len(old))
        nk = [norm(str(i["title"])) for i in items]
        miss2 = [str(e[1]) for e in old if not any(b.tscore(norm(str(e[1])), x) >= 3 for x in nk)]
        extra2 = [i["title"] for i in items
                  if not any(b.tscore(norm(i["title"]), norm(str(e[1]))) >= 3 for e in old)]
        hit = sum(1 for i in items for e in old
                  if b.tscore(norm(i["title"]), norm(str(e[1]))) >= 3 and e[2] == i["p"])
        print("   旧有新无 (%d): %s" % (len(miss2), miss2[:12]))
        print("   新有旧无 (%d): %s" % (len(extra2), extra2[:12]))
        print("   同标题同页 %d/%d" % (hit, len(items)))

    if "--write" in argv:
        if verdict == "REJECT":
            print("REFUSE: 闸门未过 %s，不落盘；请走 ROUTE R/P 手抄目录" % fail)
            return 2
        if verdict == "PARTIAL" and "--allow-miss" not in argv:
            print("REFUSE: 有 %d 条目录条目定位不到 %s；确认只写其余的请加 --allow-miss"
                  % (len(miss), miss))
            return 2
        b.write(items, bak=opt("--bak", str))
        if "--labels" in argv:
            print("   页码标签: %s" % b.apply_labels(b.propose_labels(items)))
    elif "--labels" in argv:
        print("   页码标签建议: %s   （加 --write 才落盘）" % b.propose_labels(items))
    return 0


if __name__ == "__main__":
    sys.exit(main())
