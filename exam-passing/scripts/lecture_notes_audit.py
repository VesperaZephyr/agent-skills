#!/usr/bin/env python3
# -*- coding: utf-8 -*-
r"""
lecture_notes_audit.py - 期末复习讲义源码层静态验收 (跨科目通用, 仅需 Python 标准库)

检查项:
  1. 编码 (UTF-8 无 BOM) 与行尾 (CRLF / LF)
  2. 环境统计: 结论型环境, example 与 exercise 各自紧跟 solution, proof, 表格, 编号公式
  3. \label 重复与 \cref / \Cref / \ref / \eqref 未定义引用
  4. 题源标注覆盖率, example / exercise 中重复占用的出处
  5. 每个 exercise 是否紧跟完整 solution, 且全书不存在「练习提示」段 (硬规则)
  6. 语言红线 (正文禁用词, 全角标点, ASCII 双引号, Markdown 加粗);
     「必背」只允许作末章章名「必背公式与结论手册」, 章名之外仍报 banned-borderline
  7. 版式隐患 (斜杠误写为反斜杠, \label{eq:...} 位置, 提示框参数个数)
  8. 导言区提示框硬编码标题 (信息项, 需人工确认文风)
  9. 复盘改造硬规则: 真题只标卷别未标教材出处 (exam-source),
     definition 内引入的术语未用 \textbf 标出 (term-bold)
  10. 直陈文体基准 (references/lecture_notes_voice.md): 元话语总起句 (voice-meta, WARN),
      编者复述 / 防御性提醒 / 提示框密度 / 强制分页 (voice-recap, voice-defense,
      tip-density, forced-pagebreak, 均为 INFO). 这些码只用于定位, 清零不等于文体达标;
      既有成稿可 --ignore 放行, 问题仍保留在报告中.

退出码: 有 ERROR 返回 1; --strict 时存在 WARN 也返回 1; 否则返回 0。

用法:
  python lecture_notes_audit.py 讲义.tex
  python lecture_notes_audit.py 讲义.tex --strict --json audit.json
  python lecture_notes_audit.py 讲义.tex --eol lf --quiet
"""

import argparse
import bisect
import json
import re
import sys
from collections import Counter, defaultdict
from pathlib import Path

CONCLUSION_ENVS = ("definition", "theorem", "proposition", "lemma", "corollary")
PROBLEM_ENVS = ("example", "exercise")
ALL_ENVS = ("definition", "theorem", "proposition", "lemma", "corollary",
            "example", "exercise", "solution", "proof", "remark",
            "tabularx", "equation", "align", "gather", "itemize", "enumerate")

# 明确的攻略腔 / 编纂说明体, 命中即错误 (检查范围为 \begin{document} 之后的正文)
BANNED_ERROR = (
    "本讲义", "本稿", "本册", "本节将", "本章将", "编写体例", "勘误",
    "易错点", "记忆要点", "审题技巧", "避坑指南", "避坑", "Pitfalls",
    "拿到题", "高频失分", "考试范围", "自编", "需要注意", "特别注意",
    "以下把", "下列提示", "考试主要", "答题规范", "考试时间", "时间分配",
    "先遮住", "了解即可", "操作模板", "套路", "突破口", "三步走",
    "必须闭卷", "建议", "失分点",
)
# 边界词, 命中给警告, 由使用者按科目判断
# 「必背」已移出边界词表: 期末复习讲义末章章名「必背公式与结论手册」
# 由用户 2026-11-08 明确确认保留; 章名之外的用法在 check_language 里单独警告.
BANNED_WARN = ("本章", "本节", "题型", "解题技巧", "模板")

# 直陈文体基准 (references/lecture_notes_voice.md) 的高置信度定位码.
# 只收「删掉后不改变数学内容」的固定说法, 避免误伤; 词面清零不等于文体达标.
VOICE_META_WARN = (
    "下列两问", "下列三问", "下列四问", "以下两问", "以下三问",
    "两问依次", "三问依次", "两问分别", "三问分别",
)
VOICE_RECAP_INFO = (
    "这也表明", "这也说明", "此判断使用了", "需要作这一修正",
    "满足全部条件", "验证了上述", "由此也满足",
)
VOICE_DEFENSE_INFO = (
    "适用条件与前提", "如何验证", "两边非负, 平方等价",
    "使用题设的非退化条件", "还须由", "还需要由",
)

FULLWIDTH_ERROR = ("；", "：", "（", "）", "“", "”")
FULLWIDTH_WARN = ("、",)

# 斜杠后面直接跟一个多字母 LaTeX 命令名, 几乎必然是把反斜杠误写成斜杠.
# 刻意只收多字母命令: 单字母的 /N, /I, /F, /E, /Z 多为合法商群 / 扩域记号
# (G/N, R/I, E/F, G/Z(G)), 不做整类误报. 带下标的 /Z_p 另由下式捕获.
SUSPECT_SLASH_RE = re.compile(
    r"(?<!\\)/(?:"
    r"infty|alpha|beta|gamma|delta|varepsilon|theta|lambda|sigma|omega|Omega|"
    r"cdots|ldots|vdots|ddots|subseteq|supseteq|leqslant|geqslant|neq|equiv|sim|simeq|approx|propto|"
    r"oplus|otimes|times|cap|cup|land|lor|neg|forall|exists|varnothing|emptyset|"
    r"qquad|quad|to|mapsto|longmapsto|longrightarrow|Rightarrow|Leftrightarrow|"
    r"iso|cong|sum|prod|deg|partial|nabla|sqrt|frac|text|mathrm|mathbf|mathbb|"
    r"overline|underline|bar|hat|tilde|vec|gen|id|chart|Ker|Ima|normal|sgn|bmod|pmod|mid"
    r")\b"
)
# /Z_{pq}, /Q_p 之类: 商记号不会紧跟下标, 属于典型错字.
SUSPECT_SLASH_SUB_RE = re.compile(r"(?<!\\)/(?:Q|Z|R|C|N|F)_")

SOURCE_RE = re.compile(r"教材|作业|试卷|真题|卷|学年|习题|\bP\.?\s*\d+|\b\d{4}--\d{4}\b")
LABEL_RE = re.compile(r"\\label\{([^}]+)\}")
REF_RE = re.compile(r"\\(?:c|C)?ref\{([^}]+)\}|\\eqref\{([^}]+)\}|\\pageref\{([^}]+)\}")

EQUATION_ENVS = ("equation", "equation*", "align", "align*", "alignat", "alignat*",
                 "gather", "gather*", "multline", "multline*", "flalign", "flalign*")


class Issue(object):
    def __init__(self, level, code, message, line=None, detail=None):
        self.level = level          # ERROR / WARN / INFO
        self.code = code
        self.message = message
        self.line = line
        self.detail = detail

    def as_dict(self):
        return {"level": self.level, "code": self.code,
                "message": self.message, "line": self.line,
                "detail": self.detail}


class Auditor(object):
    def __init__(self, path, eol_mode="crlf"):
        self.path = Path(path)
        self.eol_mode = eol_mode
        self.issues = []
        self.stats = {}
        raw = self.path.read_bytes()
        self.raw = raw
        self.bom = raw.startswith(b"\xef\xbb\xbf")
        crlf = raw.count(b"\r\n")
        lf = raw.count(b"\n")
        self.eol = "CRLF" if crlf > 0 else "LF"
        self.stats["bytes"] = len(raw)
        self.stats["crlf"] = crlf
        self.stats["lf"] = lf
        self.stats["bom"] = self.bom
        self.stats["eol"] = self.eol
        try:
            text = raw.decode("utf-8-sig" if self.bom else "utf-8")
        except UnicodeDecodeError as exc:
            raise SystemExit("无法按 UTF-8 解码: %s" % exc)
        self.text = text.replace("\r\n", "\n").replace("\r", "\n")
        self.line_starts = [0]
        for m in re.finditer("\n", self.text):
            self.line_starts.append(m.end())
        self.code = self._mask_comments(self.text)
        bpos = self.code.find(r"\begin{document}")
        self.body_start = bpos if bpos >= 0 else 0
        self.body = self.code[self.body_start:]
        self.preamble = self.code[:self.body_start]

    def line_of(self, pos):
        """绝对偏移量 -> 行号."""
        return bisect.bisect_right(self.line_starts, pos)

    def bl(self, pos):
        """正文 (self.body) 内相对偏移量 -> 行号."""
        return self.line_of(self.body_start + pos)

    def add(self, level, code, message, pos=None, detail=None):
        self.issues.append(Issue(level, code, message,
                                 self.line_of(pos) if pos is not None else None,
                                 detail))

    @staticmethod
    def _mask_comments(text):
        """把 % 注释内容替换为空格, 保持长度与行号不变 (忽略 \\% 转义)."""
        out = list(text)
        for m in re.finditer(r"(?m)(?<!\\)%[^\n]*", text):
            for i in range(m.start(), m.end()):
                out[i] = " "
        return "".join(out)

    def env_ranges(self, name, code=None):
        """返回同名环境的 (起点, 终点) 列表; 假定同类环境不嵌套."""
        code = self.code if code is None else code
        begins = [m.start() for m in re.finditer(r"\\begin\{" + re.escape(name) + r"\}", code)]
        ends = [m.end() for m in re.finditer(r"\\end\{" + re.escape(name) + r"\}", code)]
        if len(begins) != len(ends):
            self.add("ERROR", "env-unbalanced",
                     "环境 %s 的 begin/end 数量不等 (%d/%d)" % (name, len(begins), len(ends)))
        return list(zip(begins, ends))

    @staticmethod
    def optional_arg(code, pos):
        """读取 \begin{env} 之后的可选参数, 支持 [{...}] 与内部嵌套括号."""
        i = pos
        n = len(code)
        while i < n and code[i] in " \t\n":
            i += 1
        if i >= n or code[i] != "[":
            return None, i
        sq, br = 1, 0
        j = i + 1
        buf = []
        while j < n:
            c = code[j]
            if c == "\\" and j + 1 < n:
                buf.append(c)
                buf.append(code[j + 1])
                j += 2
                continue
            if c == "{":
                br += 1
            elif c == "}":
                br = max(0, br - 1)
            elif c == "[" and br == 0:
                sq += 1
            elif c == "]" and br == 0:
                sq -= 1
                if sq == 0:
                    break
            buf.append(c)
            j += 1
        return "".join(buf).strip(), j + 1

    @staticmethod
    def brace_groups(code, pos):
        """读取命令后连续的 {..} 参数组, 返回组内容列表."""
        groups = []
        i = pos
        n = len(code)
        while i < n:
            while i < n and code[i] in " \t\n":
                i += 1
            if i >= n or code[i] != "{":
                break
            j = i + 1
            depth = 1
            while j < n and depth:
                c = code[j]
                if c == "\\" and j + 1 < n:
                    j += 2
                    continue
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                j += 1
            groups.append(code[i + 1:j - 1])
            i = j
        return groups

    def check_encoding(self):
        if self.bom:
            self.add("ERROR", "bom", "文件带 UTF-8 BOM")
        if self.stats["crlf"] and self.stats["lf"] != self.stats["crlf"]:
            self.add("WARN", "eol-mixed", "CRLF 与 LF 混用 (%d/%d)" %
                     (self.stats["crlf"], self.stats["lf"]))
        if self.eol_mode != "any":
            want = "CRLF" if self.eol_mode == "crlf" else "LF"
            if self.eol != want:
                self.add("WARN", "eol", "行尾为 %s, 期望 %s (可用 --eol 调整)" % (self.eol, want))
        try:
            self.raw.decode("ascii")
        except UnicodeDecodeError:
            pass

    def check_environments(self):
        counts = {}
        ranges = {}
        for name in ALL_ENVS:
            r = self.env_ranges(name)
            counts[name] = len(r)
            ranges[name] = r
        self.stats["env_counts"] = counts
        self.stats["conclusion_total"] = sum(counts[e] for e in CONCLUSION_ENVS)
        ex, sol, exe = counts["example"], counts["solution"], counts["exercise"]
        if sol != ex + exe:
            self.add("ERROR", "problem-solution",
                     "solution (%d) 不等于 example (%d) + exercise (%d); "
                     "例题与练习都必须紧跟一份完整解答" % (sol, ex, exe))
        # 每个 example 与 exercise 之后都应紧跟 solution
        sorted_env_begins = []
        for name in CONCLUSION_ENVS + PROBLEM_ENVS + ("solution", "proof"):
            for s, _e in ranges[name]:
                sorted_env_begins.append((s, name))
        sorted_env_begins.sort()
        for name in PROBLEM_ENVS:
            for s, e in ranges[name]:
                nxt = next((item for item in sorted_env_begins if item[0] > e), None)
                if nxt is None or nxt[1] != "solution":
                    self.add("ERROR", "problem-order",
                             "第 %d 行的 %s 之后不是 solution (下一个环境: %s); "
                             "练习不得只在章末给提示" %
                             (self.line_of(s), name, nxt[1] if nxt else "无"), s)
        self.stats["boxed"] = len(re.findall(r"\\boxed\{", self.code))
        self.stats["takeaway"] = len(re.findall(r"\\takeaway\b", self.code)) - \
                                 len(re.findall(r"\\newcommand\{\\takeaway\}", self.code))
        self.stats["examtip"] = len(re.findall(r"\\examtip\b", self.code)) - \
                                len(re.findall(r"\\newcommand\{\\examtip\}", self.code))

    def check_labels(self):
        labels = [m.group(1) for m in LABEL_RE.finditer(self.code)]
        dup = [k for k, v in Counter(labels).items() if v > 1]
        for k in dup:
            self.add("ERROR", "label-duplicate", "重复 label: %s" % k)
        refs = set()
        for m in REF_RE.finditer(self.code):
            key = m.group(1) or m.group(2) or m.group(3)
            for part in key.split(","):
                part = part.strip()
                if part:
                    refs.add(part)
        undefined = sorted(refs - set(labels))
        for k in undefined:
            self.add("ERROR", "ref-undefined", "未定义引用: %s" % k)
        self.stats["labels"] = len(labels)
        self.stats["label_duplicates"] = len(dup)
        self.stats["refs"] = len(refs)
        self.stats["undefined_refs"] = len(undefined)

    def env_optional_args(self):
        """返回 [(起点, 环境名, 可选参数, 终点)], 覆盖所有结论型与题目环境."""
        result = []
        for name in CONCLUSION_ENVS + PROBLEM_ENVS:
            for m in re.finditer(r"\\begin\{" + re.escape(name) + r"\}", self.code):
                arg, _ = self.optional_arg(self.code, m.end())
                end = self.code.find(r"\end{" + name + "}", m.end())
                result.append((m.start(), name, arg, end if end >= 0 else len(self.code)))
        return sorted(result)

    def env_label(self, start, end):
        m = LABEL_RE.search(self.code, start, end)
        return m.group(1) if m else None

    def check_sources(self):
        entries = self.env_optional_args()
        annotated = [x for x in entries if x[2] and SOURCE_RE.search(x[2])]
        problems = [x for x in entries if x[1] in PROBLEM_ENVS]
        problems_annotated = [x for x in problems if x[2] and SOURCE_RE.search(x[2])]
        self.stats["source_annotated"] = len(annotated)
        self.stats["source_envs"] = len(entries)
        self.stats["source_problems"] = len(problems)
        self.stats["source_problems_annotated"] = len(problems_annotated)
        for s, name, arg, _e in problems:
            if not (arg and SOURCE_RE.search(arg)):
                self.add("WARN", "source-missing",
                         "%s 未标注题源 (第 %d 行)" % (name, self.line_of(s)), s)
        # 例 / 练中重复出现的出处字符串
        seen = defaultdict(list)
        for s, name, arg, _e in problems:
            if arg and SOURCE_RE.search(arg):
                key = re.sub(r"\s+", "", arg)
                seen[key].append((self.line_of(s), name))
        dup = {k: v for k, v in seen.items() if len(v) > 1}
        for k, v in dup.items():
            examples = [x for x in v if x[1] == "example"]
            level = "WARN" if len(examples) > 1 else "INFO"
            self.add(level, "source-duplicate",
                     "出处被多处引用 (其中 example %d 处): %s" %
                     (len(examples), k[:70]),
                     detail="%s" % (v,))
        self.stats["source_duplicates"] = len(dup)
        self.stats["source_duplicate_examples"] = sum(
            1 for v in dup.values() if sum(1 for x in v if x[1] == "example") > 1)

    def check_provenance_and_terms(self):
        r"""复盘改造硬规则 (见 references/lecture_notes_revision.md §0).

        1. 真题若源自教材, 卷别与教材出处必须并列; 只写卷别会让课本原题
           看起来像新题, 也无法回教材核对题面. 确无原题的真题应补一个
           概念锚点 (教材 \S X 定义 X.Y), 因此本检查只看有无教材锚点,
           不要求一定有习题号.
        2. definition 与首次引入概念处的术语用 \textbf{} 标出.
        """
        exam_re = re.compile(r"20\d\d\s*[-–—]{1,2}\s*20\d\d")
        book_re = re.compile(r"教材|作业|\bP\.?\s*\d+")
        exam_only = []
        for s, name, arg, _e in self.env_optional_args():
            if arg and exam_re.search(arg) and not book_re.search(arg):
                exam_only.append((s, name, arg[:80]))
        for s, name, arg in exam_only:
            self.add("WARN", "exam-source",
                     "第 %d 行 %s 只标了试卷卷别, 未标教材出处: %s; "
                     "有原题补题号, 无原题补概念锚点, 不得虚构习题号" %
                     (self.line_of(s), name, arg), s)
        self.stats["exam_source_missing"] = len(exam_only)

        ranges = self.env_ranges("definition")
        no_bold = []
        for s, e in ranges:
            body = self.code[s:e]
            nl = body.find("\n")
            body = body[nl + 1:] if nl >= 0 else ""
            if not re.search(r"\\textbf\s*\{", body):
                no_bold.append(s)
        for s in no_bold:
            self.add("WARN", "term-bold",
                     "第 %d 行 definition 正文未见 \\textbf{}, "
                     "本节引入的术语应加粗标出" % self.line_of(s), s)
        self.stats["definition_total"] = len(ranges)
        self.stats["definition_without_bold"] = len(no_bold)

    def check_exercise_solutions(self):
        """每道练习紧跟完整 solution; 全书禁止「练习提示」段."""
        hint_re = re.compile(r"\\section\*\{[^}]*练习提示[^}]*\}")
        hints = list(hint_re.finditer(self.code))
        for m in hints:
            self.add("ERROR", "hint-section",
                     "第 %d 行存在「练习提示」段; 练习必须与例题一样紧跟完整 solution, "
                     "不得把答案或提示集中到章末" % self.line_of(m.start()), m.start())
        self.stats["hint_sections"] = len(hints)
        ranges = self.env_ranges("exercise")
        paired = 0
        for s, e in ranges:
            tail = self.code[e:e + 120]
            if re.match(r"\s*\\begin\{solution\}", tail):
                paired += 1
            else:
                self.add("ERROR", "exercise-solution",
                         "第 %d 行的 exercise 之后未紧跟 solution" %
                         self.line_of(s), s)
        self.stats["exercise_solution_total"] = len(ranges)
        self.stats["exercise_solution_paired"] = paired

    def check_language(self):
        stats = {}
        for w in BANNED_ERROR:
            n = self.body.count(w)
            if n:
                hits = [self.bl(m.start())
                        for m in re.finditer(re.escape(w), self.body)]
                self.add("ERROR", "banned-word", "禁用词「%s」命中 %d 次, 行 %s" %
                         (w, n, hits[:8]))
                stats[w] = n
        for w in BANNED_WARN:
            n = self.body.count(w)
            if n:
                self.add("WARN", "banned-borderline", "边界词「%s」命中 %d 次, 请按科目判断" % (w, n))
                stats[w] = n
        # 「必背」只作为期末复习讲义末章章名放行; 其余用法仍按备考攻略腔警告.
        if "必背" in self.body:
            n_all = self.body.count("必背")
            n_title = sum(t.count("必背") for t in
                          re.findall(r"\\(?:chapter|section)\{([^}]*)\}", self.body))
            if n_all - n_title:
                self.add("WARN", "banned-borderline",
                         "边界词「必背」在章名之外命中 %d 次 (只允许作末章章名)" % (n_all - n_title))
        self.stats["banned_hits"] = stats
        for ch in FULLWIDTH_ERROR:
            n = self.body.count(ch)
            if n:
                self.add("ERROR", "fullwidth", "正文出现全角标点「%s」%d 次" % (ch, n))
        for ch in FULLWIDTH_WARN:
            n = self.body.count(ch)
            if n:
                self.add("WARN", "fullwidth-ideographic-comma",
                         "正文出现顿号「%s」%d 次 (规范允许中文并列词语中保留)" % (ch, n))
        n = self.body.count('"')
        if n:
            self.add("ERROR", "ascii-quote",
                     "正文出现 ASCII 双引号 %d 处, XeLaTeX 中文下会都排成右引号" % n)
        n = len(re.findall(r"\*\*", self.body))
        if n:
            self.add("ERROR", "markdown-bold", "正文出现 Markdown 加粗标记 %d 处" % n)

    def check_layout(self):
        slash_hits = list(SUSPECT_SLASH_RE.finditer(self.body)) + \
                     list(SUSPECT_SLASH_SUB_RE.finditer(self.body))
        for m in sorted(slash_hits, key=lambda x: x.start()):
            snippet = self.body[max(0, m.start() - 45):m.start() + 45].replace("\n", " ")
            self.add("ERROR", "slash-typo",
                     "斜杠命令 %r (第 %d 行) 疑似把反斜杠误写成斜杠" %
                     (m.group(0), self.bl(m.start())),
                     detail=snippet)
        self.stats["slash_typos"] = len(slash_hits)
        # \label{eq:...} 必须位于编号公式环境内
        eq_ranges = []
        for name in EQUATION_ENVS:
            eq_ranges.extend(self.env_ranges(name))
        display_ranges = [(m.start(), m.end()) for m in
                          re.finditer(re.escape("\\[") + r"[\s\S]*?" + re.escape("\\]"), self.code)]
        outside = 0
        for m in re.finditer(r"\\label\{(eq:[^}]+)\}", self.code):
            pos = m.start()
            if any(s <= pos < e for s, e in eq_ranges):
                continue
            outside += 1
            where = "位于 \\[ ... \\] 显示公式中" if any(s <= pos < e for s, e in display_ranges) \
                else "不在编号公式环境内"
            if where.startswith("位于"):
                self.add("ERROR", "eq-label-display",
                         "%s 的 \\label 放在 \\[...\\] 中, cleveref 会串到定理计数器 (第 %d 行)" %
                         (m.group(1), self.line_of(pos)), pos)
            else:
                self.add("WARN", "eq-label-outside",
                         "%s 的 \\label %s (第 %d 行)" %
                         (m.group(1), where, self.line_of(pos)), pos)
        self.stats["eq_labels_outside_numbered_env"] = outside
        self.stats["equation_envs"] = len(eq_ranges)
        # 提示框参数个数
        for cmd in ("takeaway", "examtip"):
            decl = re.search(r"\\(?:re)?newcommand\{\\" + cmd + r"\}\[(\d+)\]", self.code)
            if not decl:
                continue
            arity = int(decl.group(1))
            calls = 0
            mismatch = 0
            for m in re.finditer(r"\\" + cmd + r"(?![a-zA-Z])", self.code):
                prefix = self.code[max(0, m.start() - 20):m.start()]
                if prefix.endswith(r"\newcommand{") or prefix.endswith(r"\renewcommand{"):
                    continue
                calls += 1
                got = len(self.brace_groups(self.code, m.end()))
                if got != arity:
                    mismatch += 1
                    self.add("ERROR", "tip-arity",
                             "\\%s 定义为 %d 参数, 第 %d 行调用传了 %d 个" %
                             (cmd, arity, self.line_of(m.start()), got), m.start())
            self.stats[cmd + "_calls"] = calls
            self.stats[cmd + "_arity_mismatch"] = mismatch
        # 导言区提示框硬编码标题: 文风信息项
        for m in re.finditer(r"\\textbf\{([^}]{0,40})\}", self.preamble):
            label = m.group(1)
            if any(w in label for w in ("考点", "技巧", "易错", "记忆", "提示")):
                self.add("INFO", "tip-label",
                         "导言区提示框标题「%s」会显示在 PDF 中, 请确认符合规范 §3" % label)
        # 章节名 (目录即考纲)
        titles = [m.group(1) for m in re.finditer(r"\\(?:chapter|section)\{([^}]*)\}", self.code)]
        self.stats["chapter_titles"] = [m.group(1) for m in re.finditer(r"\\chapter\{([^}]*)\}", self.code)]
        self.stats["section_count"] = len(titles)
        for m in re.finditer(r"\\(?:chapter|section)\{([^}]*)\}", self.code):
            if re.search(r"本讲义|知识点整理|以下|本章|编写", m.group(1)):
                self.add("WARN", "title-meta",
                         "章节标题含编纂说明体: %s" % m.group(1), m.start())

    def check_voice(self):
        """直陈文体基准 (references/lecture_notes_voice.md §9): 词面只定位, 达标靠连读一章."""
        stats = {}
        for w in VOICE_META_WARN:
            n = self.body.count(w)
            if n:
                hits = [self.bl(m.start())
                        for m in re.finditer(re.escape(w), self.body)]
                self.add("WARN", "voice-meta",
                         "元话语总起句「%s」命中 %d 次, 行 %s; 按 voice §6 改为数学引入句或直接列 enumerate" %
                         (w, n, hits[:8]))
                stats[w] = n
        for w in VOICE_RECAP_INFO:
            n = self.body.count(w)
            if n:
                hits = [self.bl(m.start())
                        for m in re.finditer(re.escape(w), self.body)]
                self.add("INFO", "voice-recap",
                         "编者复述 / 复验「%s」命中 %d 次, 行 %s; 按 voice §2, §4 整句删或前移到该步" %
                         (w, n, hits[:8]))
                stats[w] = n
        n = len(re.findall(r"同一个[^，。；\n]{0,24}解决了[^，。；\n]{0,12}两问", self.body))
        if n:
            self.add("INFO", "voice-recap",
                     "「同一个...解决了...两问」式编者点评命中 %d 次" % n)
            stats["recap-pattern"] = n
        for w in VOICE_DEFENSE_INFO:
            n = self.body.count(w)
            if n:
                self.add("INFO", "voice-defense",
                         "防御性提醒措辞「%s」命中 %d 次; 前提按 voice §4 一次原则处理" % (w, n))
                stats[w] = n
        tips = self.stats.get("takeaway", 0) + self.stats.get("examtip", 0)
        if tips > 5:
            self.add("INFO", "tip-density",
                     "提示框调用 %d 个 (>5); 按 voice §6 默认不用, 逐条评估能否升级为编号结论或删除" % tips)
        secs = self.stats.get("section_count", 0)
        cp = len(re.findall(r"\\clearpage\b", self.body))
        if secs >= 3 and cp >= secs:
            self.add("INFO", "forced-pagebreak",
                     "正文强制分页 %d 处 / 章 %d 个; 按 voice §7 优先连续排版并逐页查孤儿空白页" % (cp, secs))
        self.stats["voice_hits"] = stats

    def run(self):
        self.check_encoding()
        self.check_environments()
        self.check_labels()
        self.check_sources()
        self.check_provenance_and_terms()
        self.check_exercise_solutions()
        self.check_language()
        self.check_layout()
        self.check_voice()
        return self.issues, self.stats

    def report(self, quiet=False):
        c = Counter(i.level for i in self.issues)
        lines = []
        lines.append("=== 期末复习讲义静态验收 ===")
        lines.append("文件: %s" % self.path)
        lines.append("编码: %s%s | 行尾 %s (%d/%d) | %d bytes" %
                     ("UTF-8 ", "带 BOM" if self.bom else "无 BOM", self.eol,
                      self.stats["crlf"], self.stats["lf"], self.stats["bytes"]))
        ec = self.stats["env_counts"]
        lines.append("结构: 结论型环境 %d | example %d / solution %d | exercise %d | proof %d | "
                     "tabularx %d | equation %d | boxed %d" %
                     (self.stats["conclusion_total"], ec["example"], ec["solution"],
                      ec["exercise"], ec["proof"], ec["tabularx"], ec["equation"],
                      self.stats["boxed"]))
        lines.append("引用: label %d | 重复 %d | 引用 %d | 未定义 %d" %
                     (self.stats["labels"], self.stats["label_duplicates"],
                      self.stats["refs"], self.stats["undefined_refs"]))
        lines.append("题源: 环境 %d 中标注 %d | 例题/练习 %d 中标注 %d | 重复出处 %d" %
                     (self.stats["source_envs"], self.stats["source_annotated"],
                      self.stats["source_problems"], self.stats["source_problems_annotated"],
                      self.stats["source_duplicates"]))
        lines.append("练习解答: %d/%d 道 exercise 紧跟 solution | 练习提示段 %d 处 (应为 0)" %
                     (self.stats["exercise_solution_paired"],
                      self.stats["exercise_solution_total"],
                      self.stats["hint_sections"]))
        lines.append("复盘改造: 只标卷别未标教材 %d 处 | definition 未加粗术语 %d/%d" %
                     (self.stats["exam_source_missing"],
                      self.stats["definition_without_bold"],
                      self.stats["definition_total"]))
        lines.append("结论: ERROR %d / WARN %d / INFO %d" %
                     (c["ERROR"], c["WARN"], c["INFO"]))
        lines.append("")
        if not quiet or c["ERROR"] or c["WARN"]:
            for level in ("ERROR", "WARN", "INFO"):
                group = [i for i in self.issues if i.level == level]
                if not group:
                    continue
                if quiet and level == "INFO":
                    continue
                lines.append("--- %s (%d) ---" % (level, len(group)))
                for i in group[:60]:
                    loc = ("L%d " % i.line) if i.line else ""
                    lines.append("  [%s] %s%s%s" %
                                 (i.code, loc, i.message,
                                  ("  | " + i.detail) if i.detail and level != "INFO" else ""))
                if len(group) > 60:
                    lines.append("  ... 另有 %d 条" % (len(group) - 60))
        lines.append("")
        lines.append("语言红线检查范围为 \\begin{document} 之后的正文; "
                     "导言区宏定义中可见的提示框标题以 INFO 列出, 需人工确认.")
        lines.append("本工具不检查编译错误, PDF 断行与数学内容; "
                     "请配合 lecture_notes_build.py 与渲染抽样 (见 lecture_notes_workflow.md §5).")
        return "\n".join(lines)


def main():
    ap = argparse.ArgumentParser(description="期末复习讲义源码层静态验收 (跨科目通用)")
    ap.add_argument("tex", help="待检查的 .tex 文件")
    ap.add_argument("--json", dest="json_out", help="把完整结果写成 JSON")
    ap.add_argument("--strict", action="store_true", help="存在 WARN 时也返回非零退出码")
    ap.add_argument("--ignore", action="append", default=[], metavar="CODE",
                    help="人工复核后放行的检查码, 可重复; 问题仍会出现在报告中")
    ap.add_argument("--quiet", action="store_true", help="只输出汇总与 ERROR/WARN")
    ap.add_argument("--eol", choices=("crlf", "lf", "any"), default="crlf",
                    help="期望的行尾格式 (默认 crlf; Linux 项目可用 lf)")
    args = ap.parse_args()
    if not Path(args.tex).is_file():
        raise SystemExit("文件不存在: %s" % args.tex)
    a = Auditor(args.tex, args.eol)
    issues, stats = a.run()
    print(a.report(args.quiet))
    if args.json_out:
        payload = {"file": str(Path(args.tex).resolve()),
                   "summary": {k: v for k, v in stats.items()
                               if k not in ("env_counts", "chapter_titles", "banned_hits")},
                   "env_counts": stats["env_counts"],
                   "chapter_titles": stats["chapter_titles"],
                   "banned_hits": stats["banned_hits"],
                   "issues": [i.as_dict() for i in issues]}
        Path(args.json_out).write_text(json.dumps(payload, ensure_ascii=False, indent=2),
                                       encoding="utf-8")
        print("JSON 已写入: %s" % args.json_out)
    ignored = set(args.ignore)
    if ignored:
        print("已复核并放行: %s (问题仍列于报告)" % ", ".join(sorted(ignored)))
    active = [i for i in issues if i.code not in ignored]
    c = Counter(i.level for i in active)
    if c["ERROR"] or (args.strict and c["WARN"]):
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
