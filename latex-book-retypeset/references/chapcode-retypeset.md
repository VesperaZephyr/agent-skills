# 分章页码专著专项（`\chapcode` 版式）

实战来源：Serre《Abelian l-Adic Representations and Elliptic Curves》（A K Peters 1998 重印 =
1968 Benjamin 打字机影印版 + 新增 Special Preface / Supplementary Bibliography）。203 页原书 → 129 页，
前言 + 4 章 + 两套参考文献 + 索引，**每章页码独立起算且带章前缀**，0 错误 / 0 未定义 / 0 重复 label。

这一类原书与 GTM96（单计数器 `gtmitem`、全局连续页码）的**关键差异**：
页码**每章重置为 1 并加章码前缀**（I-1…I-30、II-1…II-42、B-1…B-8、Index-1…Index-3），
前置部分用**小写罗马数字**（v、vii、xiii、xvii…）。自建 cls 须同时处理「分章计数」「章码前缀」
「罗马/阿拉伯切换」「页眉四类约定」「目录页码超链接」五件事。

---

## 1. `\chapcode` 页码机制（cls 核心）

**难点**：kernel 的 `\pagenumbering{roman}` 会**全局重定义** `\thepage`，任何自定义格式都会被它冲掉。
正解是把「打印格式」与「计数器」分离，并在每次 `\pagenumbering` 后重建 `\thepage`/`\theHpage`。

```latex
\newcommand\chapcode{}                         % 当前章码：I/II/III/IV/B/Index，前置为空
\newcommand\serrepagfmt{\arabic{page}}         % 章码为空时用的格式（前置：\romannumeral\c@page）
\newcommand\serrefixpage{%
  \renewcommand\thepage{%
    \ifx\chapcode\empty \serrepagfmt \else \chapcode-\arabic{page}\fi}%
  \ifx\theHpage\undefined
    \newcommand\theHpage{\thepage}%           % 首次：hyperref 未加载，安全
  \else
    \renewcommand\theHpage{\thepage}%         % 后续：锚点目标 == 打印页码
  \fi}
\serrefixpage
```

- **`\theHpage` = 打印页码**（含章码前缀）：这样 `\hyperlink{page.I-3}` 与目录页码一致，
  超链接落点即「所见页码」。若不同步，hyperref 会按 `\thepage` 生成 `page.3` 之类重复目标。
- `\fmroman{n}`：前置切换——`\pagenumbering{roman}` + `\setcounter{page}{n}` + `\serrepagfmt` 改罗马 + `\serrefixpage`。
- `\chapterhead` 内**显式** `\def\chapcode{#1}` 与 `\setcounter{page}{1}`（每章页码从 1 起）。

---

## 2. `\pagestyle{empty}` 泄漏 —— 全书页眉页码丢失（本项目最大坑）

| | |
|---|---|
| 症状 | **全书所有续页**（正文、文献、索引）无 running head、无 folio；只有章/节首页有底部页码 |
| 根因 | `front/titlepages.tex` 第 2 行 `\pagestyle{empty}` 设了**全局**空页样式，之后**从未恢复**。cls 里虽定义了完整的 `fancy` 页眉，但 `\pagestyle` 一直是 `empty` |
| 关键误解 | `\thispagestyle{plain}` **只影响当前页**（首页），对续页无效——所以「首页有页码、续页全空」正是这个坑的指纹 |
| 修法 | 在**每个头宏**里显式恢复 `\pagestyle{...}`：`\chapterhead`→`fancy`、`\fmhead`→`fmfancy`、bib 首页→`fancy`、补充文献→`fmfancy`、索引→`idxfancy` |

```latex
%% \chapterhead 内（\thispagestyle 管首页，\pagestyle 管后续页）
\thispagestyle{plain}%
\pagestyle{fancy}%
```

**排查手法**：用 PyMuPDF 逐页 dump 顶/底文本带，与**原书渲染图**对照——
续页若 `T[]`/`B[]` 全空即命中。见 `scripts/dump_page_heads.py`。

---

## 3. 页眉四类约定（照原书逐类核对）

原书不同区块的页眉规则不同，**不能一套 `fancy` 走天下**。实测（PDF 物理页 → 印刷码）：

| 区块 | 偶页（verso，左页） | 奇页（recto，右页） | 页样式 |
|---|---|---|---|
| **正文各章** | `I-2` 　 `ABELIAN l-ADIC REPRESENTATIONS`（外侧页码 + 内侧书名） | `l-ADIC REPRESENTATIONS` 　 `I-3`（内侧章短题 + 外侧页码） | `fancy` |
| **前置部分** | `vi` 　 `SPECIAL PREFACE` | `INTRODUCTION` 　 `xv` | `fmfancy`（**节名取代书名**） |
| **正参考文献** | `B-2` 　 `ABELIAN l-ADIC REPRESENTATIONS` | `BIBLIOGRAPHY` 　 `B-3` | `fancy` |
| **补充参考文献** | `B-6` 　 `Supplementary Bibliography` | `Supplementary Bibliography` 　 `B-7` | `fmfancy`（**混合大小写**，照原书） |
| **索引** | `Index-2` | `Index-3` | `idxfancy`（**两侧仅外侧裸页码**，无其他页眉） |

三种续页样式（cls）：

```latex
\fancypagestyle{fancy}{%        正文 / 正参考文献（cls 默认）
  \fancyhead[LE]{\normalfont\small\thepage}          % 偶页外侧：页码
  \fancyhead[RE]{\normalfont\small\bktitle}          % 偶页内侧：书名
  \fancyhead[LO]{\normalfont\small\capsshorttitle}   % 奇页内侧：章短题
  \fancyhead[RO]{\normalfont\small\thepage}}         % 奇页外侧：页码
\fancypagestyle{fmfancy}{%      前置 / 补充文献（节名取代书名，几何同 fancy）
  \fancyhead[LE]{\normalfont\small\thepage}
  \fancyhead[RE]{\normalfont\small\capsshorttitle}
  \fancyhead[LO]{\normalfont\small\capsshorttitle}
  \fancyhead[RO]{\normalfont\small\thepage}}
\fancypagestyle{idxfancy}{%     索引（仅外侧裸页码）
  \fancyhead[LE]{\normalfont\small\thepage}
  \fancyhead[RO]{\normalfont\small\thepage}}
```

- `capsshorttitle` 由各头宏 `\renewcommand` 就地改写（章短题 / 节名 / `BIBLIOGRAPHY` / `Supplementary Bibliography`）。
- **首页**（章/前置/文献/索引）无页眉、底部居中裸页码：用 `\fancypagestyle{plain}`/`{fmplain}` 把 folio 放 `\fancyfoot[C]`。
- 独立页（如 Contents，不走 `\fmhead`）须**自己**设 `\capsshorttitle` 与 `\pagestyle{fmfancy}`，
  否则会继承上一节的 running head（实测：Contents 页会错误显示 "VITA"）。

**个别例外照原书保留**：原书 ch.IV 首页恰好缺 folio（I–III 章首页都有居中 "1"）。
这种**孤立个例**可统一补足并记录，不必复刻——但要在 STATE.md 写明，便于日后核对。

---

## 4. 前置 folio「只进不退」

原书前置各部分 folio 有跳跃（specpref=v、preface=vii、vita=viii、contents=ix、introduction=xiii、notations=xvii）。
若每次 `\clearpage` 都强制 `\setcounter{page}{目标}`，当我们的排版比原书**长**时会把 folio 往回拨、打印两次。

```latex
%% \fmhead[folio#]{Heading}{Title}{anchor}{RUNHEAD}
\newcommand\fmhead[5][]{%
  \clearpage
  \ifx\\#1\\\else\ifnum\value{page}<#1\relax\setcounter{page}{#1}\fi\fi  % 只在目标 > 当前时 bump
  \renewcommand\capsshorttitle{#5}%
  \thispagestyle{fmplain}%
  \pagestyle{fmfancy}%
  ...}
```

---

## 5. 手工编号陈述环境（原书编号 ≠ 自动计数器）

原书陈述（THEOREM / PROPOSITION / COROLLARY / LEMMA / DEFINITION）**手工编号**：有号与无号混排、
常**重新起数**（同一节内 LEMMA 1、2，下一节又从 1 起）。用 LaTeX 自动计数器必然对不上。

正解：**手工编号参数 + 隐藏锚点计数器**——编号文本由调用方给定（照抄原书），
另用一个隐藏 `stmt` 计数器只为 mint 唯一 hyperref 锚点。

```latex
\newcounter{stmt}% 隐藏计数器，仅为唯一锚点
\newenvironment{stmt}[2]{%
  \par\addvspace{1.15\baselineskip}%
  \refstepcounter{stmt}%                                   % 推进隐藏计数器
  \ifx\\#2\\\else\protected@edef\@currentlabel{#2}\fi%     % 有号则 \ref 打印原书号
  \noindent
  {\bfseries #1\ifx\\#2\\\else\ #2\fi\/\textbf{~---}\hspace{0.55em}\itshape}%
  \ignorespaces
}{\par\addvspace{0.45\baselineskip}}
\newenvironment{theorem}[1][]{\begin{stmt}{THEOREM}{#1}}{\end{stmt}}
\newenvironment{lemma}[1][]{\begin{stmt}{LEMMA}{#1}}{\end{stmt}}
%% 用法：\begin{lemma}[1]\label{lem:IV.3.2.1} ... \end{lemma}
%%       \begin{stmt}{MAIN LEMMA}{}  ... \end{stmt}   % 原书无号
```

- **纪律**：原书无号的陈述**保持无号**（不要「顺手」补号）；原书有号的**照抄**其号（哪怕与自动序不符）。
- 风险：编号可能被误删。本项目曾把「MAIN LEMMA / LEMMA 1…6」压平成无号 LEMMA，
  致正文引用「lemma 3」悬空——**恢复编号后**再逐一超链接正文引用。
- 回归验证：加/去编号后 overfull 计数应**不变**（本项目均为 33，确认编号非 overfull 来源）。

---

## 6. biblatex sortkey 锁定原书编号

原书文献 [1]–[78] + 补充 [79]–。biblatex 默认按字母/年代排序会**打乱原书编号**。
正解：自定义排序模板 + 每条 `sortkey` 字段：

```latex
\DeclareSortingTemplate{serre}{%
  \sort{\field{sortkey}}}                    % 按 sortkey 排序
%% 每条：@book{...  sortkey = {001}, ...}    % 001…078 锁定原书序
```

配合 `labelnumber=true`，`refnumber` 即原书号。`\nocite{*}` + `category=main`/`supp` 分两套文献区。

### 6.1 分 category 打印掉条 —— 尾空格吞掉末键（隐蔽坑）

| | |
|---|---|
| 症状 | `\printbibliography[category=main]` 恰好**丢每个 category 的最后一条**（本项目 [46] H. WEYL、[88] ZARHIN-weights 从 PDF 消失；`.bbl` 里 88 条齐全，只是没排出来） |
| 根因 | `\addtocategory{main}{a,b,c,…,\<末键>\n}` 中**收尾 `}` 另起一行**，TeX 把行末换行读成**空格**，末键变成 `weyl-gleichv␠`（带尾空格）。biblatex 原样写进 `.aux`：`\abx@aux@category{main}{weyl-gleichv }`；带空格的键匹配不到真实 entry key，被 `category=` 过滤剔除 |
| 指纹 | 丢的**永远是该 category 块的最后一个键**；且只有「块尾键在独立一行、`}` 又另起一行」时才中招（键与 `}` 同行的块不中） |
| 修法 | 末键行尾加 `%` 吞掉换行：`…,weyl-gleichv%` 然后下一行 `}` |
| 验证 | 检查 `.aux` 的 `\abx@aux@category{...}` 有无尾空格；或直接断言 PDF 里 `[1]`–`[N]` 全出现 |

```latex
\addtocategory{main}{
  artin-collected,artin-tate-cft,...
  weil-cm,weil-adeles,weil-bnt,weil-dirichlet,weyl-gleichv%   ← % 吞掉行末换行
}
```

**排查陷阱**：此坑与 `\bibsetup`、自定义 `bibenvironment`、driver 个数**都无关**——把这些逐个注释掉，
症状不变（本项目曾误判为「列表收尾」问题，绕了几圈）。正解是**先看 `.aux` 的 category 键有没有尾空格**。
最小复现：把真实 preamble + 最小 body 单独建一个 `_probe.tex`，`\printbibliography` 各 category 一次，
对比「加/不加 `%`」的差异（本项目 `_min5` 丢 [46,88]，末键补 `%` 后全出）。

**注意**：`defernumbers=true` 不能修此坑（实测反而把 [87] 也一起丢了），别被 biblatex 的
"Split bibliography detected … consider defernumbers=true" 警告带偏——那警告是另一回事。

---

## 7. 目录页码超链接（「页码要带交叉引用」）

原书目录每行右侧是**页码**（如 `I-2`、`B-3`、`Index-2`）。要让它可点击。
**两种方案，优先用方案 B**：

```latex
%% 方案 A（早期）：页码文本 -> hyperref 的 per-page 命名目标 "page.<folio>"
\newcommand{\hyperpage@serre}[1]{%
  \ifx\\#1\\\else\hyperlink{page.#1}{#1}\fi}
```

- 方案 A 依赖 `\theHpage` 与打印 folio 一致（第 1 节已保证）。**但 hyperref 在部分页面不生成
  `page.<folio>` 目标**（本项目实测 II-9、III-22、III-26、IV-14、IV-28 等页缺失），
  于是这些目录页码成了**死链**。

```latex
%% 方案 B（推荐）：页码文本 -> 该条自己的 section label（\hyperref）
%% toc 行宏带第 4 参 = label：\addtocontents{toc}{\string\chlc{Chapter I}{...}{\thepage}{chap:I}}
\newcommand{\hyperpage@serre}[2]{%
  \ifx\\#1\\\else
    \@ifundefined{r@#2}{\hyperlink{page.#1}{#1}}{\hyperref[#2]{#1}}%   % 有 label 用之，否则回退 A
  \fi}
```

- 方案 B 把目录行绑到**条目自己的 `\label`**（章 `chap:I`、节 `sec:I.2`、前置 `fm:preface`、
  文献 `bib:main`），落点稳定，不再依赖 per-page 目标是否存在；`\@ifundefined{r@#2}` 兜底回退方案 A，
  保证任何一行都不会渲染成 `??`。
- 代价：改 toc 行宏签名（多一个 label 参）后**必须删旧 `main.toc`** 再重建，否则旧 2/3 参条目会报
  `Missing \endcsname inserted`（本项目踩过）。
- 验证：`python -c` 用 PyMuPDF `get_links()` 遍历目录页，确认 `LINK_GOTO`/`LINK_NAMED` 且
  `page` 目标非负（未解析）；本项目 98 条链接 0 未解析。
- 目录页**不写** dot leader（原书无点线）。

---

## 8. 交叉引用：裸编号 → `\ref`（打印文本不变，只加超链接）

原书正文大量裸数字互引（`cf. 3.1`、`chap. I, 1.2`）。转换原则：
**`\ref` 打印的文本与原硬编码数字完全相同**（因 `\@currentlabel` 被设为原书编号），
所以转换**不改变可见输出**，只增加可点击链接。

- 节头宏自动 mint `\label{sec:\chapcode.#1}`：`\sechead{2}{...}` → `\ref{sec:I.2}` 打印 "2"。
- 陈述：`\label{lem:IV.3.4.5}` → 正文 `lemma~\ref{lem:IV.3.4.5}`。
- **保留原书自身的不一致**（不静默"修正"）：本项目三例——
  ① ch2_s3 的 `[47]`（原书 [1]–[46] 连续，[47] 在 1968 原版即未定义）；
  ② ch4_s2 的 "the theorem in section 4"（第 IV 章仅 §§1–3，实指 2.2）；
  ③ 索引两处错印（Γ_E : IV.A.3、Tate's elliptic curves : IV.A.1:1）——照印，但**链接指向正确节号**。

---

## 9. 终检清单（本项目实测）

```bash
xelatex -interaction=nonstopmode main.tex && biber main && xelatex main.tex && xelatex main.tex
```

| 指标 | 合格线 | 本项目实测 |
|---|---|---|
| 4 遍 exit | 全 0 | 0/0/0/0 |
| errors | 0 | 0 |
| undefined ref/citation | 0 | 0 |
| multiply defined label | 0 | 0 |
| PDF 层 `??` | 0 | 0 |
| overfull | 持平未新增 | 33（既有长公式行） |
| 页眉/页码 | 逐页符合四类约定 | 129 页全通过 |
| 目录页码超链接 | 全部解析 | 98 条，0 未解析 |
| 参考文献完整性 | `[1]`–`[N]` 全出现 | 88/88（修复 category 尾空格后） |

---

## 10. 复用清单（下次遇到分章页码书）

1. 先量原书**页码体系**：是否分章重置、是否带章前缀、前置用罗马还是阿拉伯、各区块起始 folio。
2. cls 里写 `\chapcode` + `serrepagfmt` + `serrefixpage`（打印格式与计数分离）。
3. 页眉**逐区块**核对原书（正文/前置/文献/索引四类），写对应 `\fancypagestyle`。
4. **务必检查 `\pagestyle{empty}` 泄漏**：扉页文件设了就一定要在首个头宏恢复。
5. 陈述编号照抄原书（手工编号参数 + 隐藏锚点计数器）。
6. biblatex 用 `sortkey` 锁编号；`\addtocategory` 的**末键行尾加 `%`**（否则尾空格吞掉末条）。
7. 目录页码用 `\hyperref[<条目 label>]`（回退 `\hyperlink{page.<folio>}`），并保证 `\theHpage` 与打印页码一致。
8. 交付前跑 `scripts/dump_page_heads.py` 逐页验证页眉/页码，并断言 PDF 里 `[1]`–`[N]` 全出现。
