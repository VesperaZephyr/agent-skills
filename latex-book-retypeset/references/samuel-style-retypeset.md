# 单卷连续页码 + 小节裸编号专著专项（Samuel 类）

实战来源：Pierre Samuel, *Algebraic Theory of Numbers*（英译 A. J. Silberger，
Hermann 1967 / W. A. Benjamin 1970），原书 110 页正文；重排后 104 页，
371 个 label、846 个内部链接目标、922 个 PDF Link 注释、110 处 Q.E.D.，
0 错误 / 0 未定义 / 0 重复 label / 0 overfull / PDF `??` 0。

适用特征（与 GTM 类、分章页码类都不同）：

- **全书连续阿拉伯页码**，但原书开本小、正文密（实测 141.7 × 189.2 mm，
  版心 113 × 158 mm，8.5 pt / 9.8 pt）。
- **陈述按节、按关键词各自从 1 起算**，印成裸号：`Theorem 1.`、`Proposition 2 (Transitivity).`。
- **公式按节起算**，印成裸括号号 `(1)`、`(2)`，不带章/节前缀；Supplement 单独连续编号。
- 无图；正文短句多、行内公式密；大量 “Chapter IV, §3, Proposition 1” 式交叉引用。
- 参考文献是**编号 [1]–[9] + 12 条无号评注条目**的混合体；习题按章分块、题号 1B/2B/3A。
- 索引是 “词条 + V.2 式节号” 的极简索引。

---

## 1. 版式测量与页码对齐

先从扫描页量四个数：开本、版心、字号/行距、页眉位置。本书：

```latex
\geometry{paperwidth=141.7mm,paperheight=189.2mm,
  textwidth=113mm,textheight=158mm,
  inner=12.5mm,outer=16.2mm,top=18mm}
```

**不要试图逐页强制对齐原书。** 自然分页 + 字距微调不可能让 104 页逐页等于扫描页，
强行 `\newpage` 只会制造大量半空页。可行做法是**只锁分部起点**：

```latex
\newcommand\folio[1]{%
  \ifnum\value{page}<#1\relax \setcounter{page}{#1}\fi}
```

在每章、Supplement、Exercises、Bibliography、Index 的起始宏里调 `\folio{n}`。
只进不退，避免偶数页/奇数页补偿把页码拉回去。本书实测分部 folio：
13 / 27 / 46 / 53 / 68 / 86 / 94 / 97 / 106 / 108，与原书一致。

页眉照原书双模式，并显示**本节在页内的节号区间**：

- verso：`folio | CHAPTER TITLE | §§ c.s1–c.s2`
- recto：`§§ c.s1–c.s2 | SECTION TITLE | folio`

区间靠 `\pagefirstsec` 记录“本页第一节”，在 `\sechead` 里 `\afterpage{\global\let\pagefirstsec\currentseccode}`，
下一页开头用上一页记录的值做区间起点。`\markboth` 只放节号，不放标题。

---

## 2. 编号模型：裸号 + 按节重启

```latex
\newcounter{theorem}
\counterwithin{theorem}{section}
\renewcommand{\thetheorem}{\arabic{theorem}}
```

每个关键词（theorem / proposition / corollary / lemma / definition / example）
各有一个计数器，全部按 `section` 重启、印裸号。`\chapterhead` 只记
`\chapnum`（阿拉伯）与 `\seclabelprefix`（罗马），不改显示。

**有名字的陈述必须也推进计数器。** 真实 bug：`\begin{proposition}[Transitivity]`
的 wrapper 只在无参时 `\refstepcounter`，结果“Proposition 3”印成 2，后续全部错位。
统一改成：

```latex
\newenvironment{samstatement}[3]{%
  \par\addvspace{0.2\baselineskip}%
  \refstepcounter{#1}%           <- 无论有没有名字都推进
  \noindent{\itshape #2\ \csname the#1\endcsname
    \ifx\\#3\\\else{} (#3)\fi.\ }%
  \itshape\ignorespaces
}{\par\addvspace{0.1\baselineskip}}
```

公式：

```latex
\numberwithin{equation}{section}
\renewcommand{\theequation}{\arabic{equation}}
\renewcommand{\theHequation}{\arabic{equation}}
```

Supplement 内部不调 `\sechead`，所以 equation 计数器不重启，自然得到
连续的 (1)–(12)，与原书一致。**不要**给 Supplement 单独造计数器。

OCR 把 `Definition 1`、`Example 2` 之类排成普通粗体段落时，转成真正的
`definition` / `example` 环境并保留原号（可加可选参数锁号），否则正文里的
“Definition 1”“Example 2” 永远无法链接。转换后必须核对渲染号未变。

---

## 3. 交叉引用补全顺序（针对本书的六轮）

### 3.1 跨章定位语 “Chapter X, §Y”

`Chapter IV, §3` → `\hyperref[sec:4.3]{Chapter IV, §3}`，共 369 处。
难点是**排除外部文献的章号**：

- `[1], Algèbre, Chapter VI, §1` —— Bourbaki 的章，不是本书；
- `[9], Chapter II`、`Chapter V of [9]`、`[1], Chapter VIII, §1, exercises`。

判定规则（按优先级）：

1. 同一句里 `[n]` 出现在 `Chapter` 之前且距离最近 → 外部；
2. `Chapter` 后紧跟 `of [n]` → 外部；
3. 前面出现过 `\emph{Algèbre}` / `\emph{Algèbre commutative}` → 外部。

脚本先把 `\divhead{Chapter X}`（习题分组标题）用哨兵保护，再替换正文；
跳过注释行；每次替换后重编译，`undefined` 必须保持 0。

### 3.2 陈述号 “Type N” 与倒装 “N of §M”

- 正向：`§3, Lemma 1` → `\hyperref[sec:1.3]{§3}, \hyperref[lem:I.3.1]{Lemma 1}`；
- 倒装：`Lemma 1, §3, Chapter I` → `\hyperref[lem:I.3.1]{Lemma 1}, \hyperref[sec:1.3]{§3, Chapter I}`。
  倒装语序常被只认 “§…, Type N” 的脚本漏掉，收尾时要单独扫一遍。

### 3.3 索引

索引条目本身不是引用，但节号可以链：

```latex
ramified, cf.\ \hyperref[fm:supplement]{the Supplement}
ideal, discriminant II.7 and V.4     % 每个 X.Y 换成 \hyperref[sec:X.Y]{X.Y}
```

`multicols` 内链接正常工作。索引开头的 “The notation V.2 stands for Chapter V, §2”
是记号说明，保持纯文本。

### 3.4 参考文献 [n]

编号条目加锚点，正文方括号包链接：

```latex
\item[\textbf{[1]}] \phantomsection\label{bib:1}N.\thinspace BOURBAKI, ...
```

```latex
... see \hyperref[bib:1]{[1]}, Chapter VIII, §1 ...
```

要点：

- 用 `\hyperref[bib:n]{[n]}` 而不是 `\ref{bib:n}`，显示文本锁定为印刷的 `[1]`；
- `\phantomsection` 必须紧跟在 `\item[...]` 之后；放在 list 外会继承上一个计数器；
- 无号评注条目（Artin、Hasse…）不编号、不加锚点，正文也不引用它们；
- 外部著作自身的章号保持纯文本（见 3.1）。

### 3.5 习题

```latex
\newcounter{exno}
\newcommand{\exchap}[1]{\def\exprefix{#1}\setcounter{exno}{0}}
\newcommand{\exitem}[1]{\par\medskip\refstepcounter{exno}%
  \noindent{\bfseries #1.}\label{exer:\exprefix.\arabic{exno}}\quad}
```

每章 `\divhead{Chapter X}` 前放 `\exchap{X}`；Review Problems 的三组各用
`\exchap{R1}` / `R2` / `R3`，否则题号 1–6 会与第 VI 章的 `exer:VI.1…` 撞车，
产生 **duplicate label**（这条很容易在“全部改完”之后才暴露）。

正文引用按“引用点所属章”解析：`Exercise 3` 在第 V 章习题里 → `exer:V.3`；
`exercise 8 of Chapter V` → 明确跨章；`Reformulate exercise 2` 在 Chapter VI
的 3B 里 → 指的是 Chapter VI 的 2B，不是它自己的第 2 题。**逐条看语义，不能按
“最近一个 exercise”盲配。**

### 3.6 列表条目 (1)(2)

`Proposition 1` 下面常跟 `(1) … (2) …`，正文写 “Proposition 1, (2)”。
给条目加 label：

```latex
\item\label{prop:V.1.1.2} The mapping ...
```

链接仍写 `\hyperref[prop:V.1.1.2]{(2)}`：enumerate 的 `\ref` 只给 `2`（无括号），
而原书印刷是 `(2)`。

### 3.7 原书笔误

本书第 IV 章 §6 印 “(§4, Proposition 2)”，但 §4 只有 Proposition 1。
处理原则：**保留原印刷文字**（不改字），把链接指向真实目标 `prop:IV.4.1`，
并在 `STATE.md` 记录“原书笔误 + 链接目标”。这样既不篡改原文，又保证可跳转。

---

## 4. 裸引用审计的两个致命细节

### 4.1 屏蔽必须覆盖整个 `\hyperref[...]{...}`

只把 `\hyperref[lem:III.3.1]{` 前缀换成空格，链接**文字**仍留在掩码里，
于是已链接的 “Lemma 1” 会被当成裸引用，产出几十条假阳性。必须做花括号配对，
把命令连同显示文本整段抹掉：

```python
def mask_hyperref(s):
    out = list(s); i = 0
    while True:
        p = s.find(chr(92) + 'hyperref[', i)
        if p < 0: break
        q = s.find(']', p); r = s.find('{', q); depth = 0; j = r
        while j < len(s):
            if s[j] == '{': depth += 1
            elif s[j] == '}':
                depth -= 1
                if depth == 0: break
            j += 1
        for k in range(p, j + 1): out[k] = ' '
        i = j + 1
    return ''.join(out)
```

同时屏蔽：`$...$`、`\[...\]`（**必须 `re.S`**，否则跨行行间公式漏屏蔽）、
`equation` 环境、`\pdfbookmark[n]`、`\newcommand{...}[n]`。本书第一版漏了 `re.S`，
把 `\operatorname{Tr}(1)` 报成 “公式 (1) 未链接”。

### 4.2 `.aux` 的 `\newlabel` 必须花括号配对解析

```latex
\newlabel{fact:II.A.1}{{{{1.}}}{43}{}{Item.24}{}}
\newlabel{prop:V.1.1.2}{{{{(2)}}}{68}{}{Item.41}{}}
\newlabel{bib:1}{{6}{106}{}{section*.72}{}}
```

- enumerate item 的 label 值有**双重花括号**（`{{(1)}}`）；
- `\phantomsection` 后的 `bib:` label 值会**继承上一个计数器**（这里是 `6`），
  反正只用 `\hyperref`，值无意义；
- 用 `\{\{([^{}]*)\}\{([^{}]*)\}` 解析会直接失败，把存在的 label 误报为缺失。

正确写法：从 `\newlabel` 后第一个 `{` 开始做配平，先取 key，再取 value。

### 4.3 PDF 链接坐标是自下而上的

`page.get_links()[i]['to'].y` 用的是 PDF 用户空间（原点左下），而
`get_text('words')` 的 y 是自上而下。比较“锚点是否落在 [1] 那一行”时必须换算
`y_text = page_height - y_link`，否则会把正确锚点误判为错位（本书曾据此误修一次）。

---

## 5. hyperref 颜色

类文件里可能残留：

```latex
\hypersetup{colorlinks=true,linkcolor=red,citecolor=blue,urlcolor=pink}
```

或后置一条 `\hypersetup{hidelinks}` 把前面全部覆盖。**同一文档多处
`\hypersetup`，后写者生效**，颜色设置要放在最后一次。推荐统一：

```latex
\hypersetup{colorlinks=true,
  linkcolor=blue!70!black,citecolor=blue!70!black,urlcolor=blue!70!black}
```

验收不要只看源码：渲染 300 dpi，取每个 Link 矩形内的非白像素做颜色直方图，
`blue!70!black` 应得到 `(0, 0, 178)`。本书第一次交付时源码写着 colorlinks，
实际 PDF 是纯红 `(255,0,0)`，像素采样才发现。

---

## 6. 构建

类里用了 `fontspec`，因此**不能用 pdflatex**：

```
! Package fontspec Error: The fontspec package requires either XeTeX or LuaTeX.
```

本机（TeX Live 2026，Windows/Git Bash）直接用：

```bash
lualatex -interaction=nonstopmode main.tex
lualatex -interaction=nonstopmode main.tex
```

改 label / 大批量替换后清 `main.aux main.toc main.out` 再编 3 遍。
`latexmk` 若残留旧 fdb 仍会拉 pdflatex，本项目最终改为直接调 lualatex。

**Git Bash + heredoc 的转义坑**：在本环境用 heredoc 写 Python 时，
`\\` 会被折叠成 `\`，导致 `\b`、`\l`、`\q` 之类变成非法转义、正则报
`unbalanced parenthesis`。写生成脚本一律用 Write 工具落盘；必须内联时用
`chr(92)` 拼反斜杠，不要依赖 heredoc 的引号形式。

---

## 7. 验收（本书实测值）

| 指标 | 本书结果 | 检查方式 |
|---|---|---|
| 页数 | 104（原书正文 110，含前置差异） | `page_count` |
| 编译 | 2 遍 exit=0，0 error / 0 warning | `grep -c '^!' main.log` |
| 未定义 / 重复 | 0 / 0 | log + aux 审计 |
| overfull | 0 | `grep Overfull main.log` |
| PDF `??` | 0 | 全文 `get_text().count('??')` |
| Q.E.D. | 110（= 110 个 proof 环境） | 全文计数 |
| label | 371（282 陈述/节/公式 + 45 exer + 9 bib + 5 fact + 其余） | aux 解析 |
| 内部链接目标 | 846，缺失 0 | `scripts/audit_internal_links.py` |
| PDF Link 注释 | 922 | `get_links()` 求和 |
| 链接颜色 | `(0,0,178)` | 300 dpi 像素直方图 |
| 分部页码 | 13/27/46/53/68/86/94/97/106/108 | `\folio` 起点 |

---

## 8. 与另外两条路线的差异速记

| 维度 | GTM 类 | 分章页码类 | 本书（Samuel 类） |
|---|---|---|---|
| 页码 | 全书连续 | 每章 I-1/II-42 | 全书连续 + 只锁分部起点 |
| 陈述号 | 共享 `gtmitem`，`c.s.i` | 手工号 + 隐藏锚点 | 每关键词独立计数器，按节重启、裸号 |
| 公式号 | 共享计数器，`2.1` | 手工/原始号 | 按节重启、裸 `(1)` |
| 交叉引用重点 | 七轮递进 | 目录 `page.*` 死链 | 外部文献排除 + 参考文献 + 习题 + 条目 |
| 颜色 | 可选 | 可选 | 必须像素验收（多 `\hypersetup` 覆盖） |
