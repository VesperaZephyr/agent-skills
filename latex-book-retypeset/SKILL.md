---
name: latex-book-retypeset
description: 为高保真 LaTeX 数学书重排（re-typeset，非翻译）沉淀工程方法论与坑位时使用本技能：适用于四类原书——① Springer GTM 类西文书（共享 gtmitem 计数器、原生 TikZ、CRLF 无 BOM、xelatex 构建）：PDF 双层 OCR 乱码、编号公式共享计数器错位、Claim 按章编号、overfull 修复、交叉引用补全；② 中文数学书（xeCJK + Fandol + 自建 cls，如徐森林《数学分析》）：TikZ 参数曲线 plot[domain] 解析失败须转 plot[smooth] coordinates、Fandol 缺生僻字须加 SimSun 回退字族、纯 CJK 行 overfull 须用局部 xeCJKsetup{CJKglue} 均匀松排（\hspace 与 fil 皆无效）、密集图标签重叠、\extref 回填、biber 中文书目；③ 分章页码西文专著（自建 cls，如 Serre《Abelian l-Adic Representations》）：\chapcode 分章页码 I-1/II-42/B-5/Index-3、手工编号陈述环境、biblatex sortkey 锁定原书 [1]-[88]、\pagestyle{empty} 泄漏致续页页眉与页码全书丢失、biblatex \addtocategory 末键尾空格吞条、目录页码超链接（\hyperref 到条目 label）；④ 单卷连续页码、小节内裸编号专著（自建 cls，如 Samuel《Algebraic Theory of Numbers》）：陈述/公式按节重启印裸号，Supplement 连续编号；只锁分部起点的 \folio 页码对齐；双模式页眉带 §§ c.s1–c.s2 区间；外部文献 Chapter 号须排除；参考文献 [n] 锚点与正文 \hyperref[bib:n]；习题 \exitem 按章 label（Review Problems 用 R 前缀）；列表条目 (1)(2) 锚点；\hyperref 颜色可能被后置 \hypersetup 覆盖，须像素采样验收；.aux 的 \newlabel 解析与裸引用扫描都必须花括号配对。涵盖硬性纪律、坑位表、交叉引用策略、验收门槛与终检脚本。不适用于 mathtranslation 类纯翻译项目。
metadata:
  agent_created: true
---

# LaTeX 数学书重排（Re-typeset）工程技能

## 目标与范围

把扫描版 / PDF 版数学专著**高保真重排**为可编译、可检索、可跳转的 LaTeX 源码的工程方法论与坑位库。
实战来源：
- **西文**：Conway《A Course in Functional Analysis》GTM 96 全书重排（436 页、11 章 + 3 附录、
  0 编译错误 / 0 死链 / 1606 个内部跳转）。
- **中文**：徐森林、薛春华《数学分析（第一册）》全书重排（551 页、6 章 + 前言 + 参考文献、
  40 个章节源文件、23 幅原生 TikZ、0 错误 / 0 缺字符 / 0 未定义引用 / 0 Overfull / PDF 层 `??` 0）。
- **分章页码西文**：Serre《Abelian l-Adic Representations and Elliptic Curves》全书重排
  （203 页原书 → 129 页，前言 + 4 章 + 两套参考文献 + 索引，**分章页码** I-1/II-42/B-5/Index-3，
  0 错误 / 0 未定义 / 0 重复 label，手工编号陈述环境 + biblatex sortkey 锁定原书编号）。
- **单卷连续页码西文**：Samuel《Algebraic Theory of Numbers》全书重排（原书 110 页正文 → 104 页，
  小节裸编号 `Theorem 1`/`(1)`、参考文献 [1]–[9]、习题按章编号、索引 V.2 链接；
  371 label / 846 内部链接目标 / 922 PDF Link 注释 / 110 Q.E.D.，0 错误 / 0 死链 / 链接颜色实测 (0,0,178)）。

- 适用：**原书重排（不翻译）**。三条路线：① Springer GTM 类单计数器版式（`gtmitem` 共享计数器，
  编号 `\thesection.\arabic{gtmitem}`）；② 中文书自建 cls（xeCJK + Fandol，按章分文件 + 生成器落盘）；
  ③ 分章页码专著自建 cls（`\chapcode` + 重定义 `\thepage`，手工编号陈述环境）；
  ④ 单卷连续页码、小节裸编号专著自建 cls（按关键词分计数器 + 按节重启、只锁分部起点的 `\folio`）。
  图形按下文「普通数学插图」分流：可编辑重绘用原生 TikZ；保真复用可保留原书矢量 PDF。
- 不适用：mathtranslation 类**纯翻译**项目（属 `mathtranslation` 技能）。

## 何时使用

- 用户说「重排某书」「把 PDF 排成 LaTeX」「补交叉引用」「修 overfull」「公式编号错位」「OCR 乱码」。
- 接手一个重排项目，需要先建立纪律红线再动手。
- 编译出现 `multiply defined` / `undefined references` / 编号错位 / 大量 overfull。

## 硬性纪律（红线，动手前确认）

| 项 | 要求 |
|---|---|
| 行尾 | **CRLF**，**UTF-8 无 BOM**（`.tex/.cls/.py` 全部） |
| 构建 | `xelatex -interaction=batchmode main.tex` × 3（改 label 后清 aux × 4） |
| 质量红线 | 0 编译错误、0 未定义引用、0 缺字符、新增章节 0 overfull |
| 内容来源 | **以原书 PDF 图像为准**，OCR 仅作检索索引 |
| 改内容 | 只改生成器（`make_chNN_secM.py`）→ assemble；绝不直接编辑 `chapters/*.tex` |
| 编号 | 先按原书选路线：GTM 用 `gtmitem` 共享计数器；手工编号专著或试卷可用原始显示号 + 隐藏锚点计数器。不得为连续性擅改原号 |
| 公式 | 未编号行间公式用裸 `\[\]` / `align*`，或 `equation\notag`；**严禁**给它们编号 |
| 图形 | 重绘优先原生 TikZ/PGFPlots；原书有可靠矢量图时可直接保留矢量 PDF。禁止把矢量图先转 PNG 再声称无损；原书本身的位图须记录原始限制 |

## 原书页码映射

`物理页 = 书页 + offset`（GTM96 offset = 15）。先量出偏移，后续所有「回原书核对」都按物理页定位。

## 普通数学插图：保真、可读与逐图验收

本节适用于曲线、曲面、向量场、坐标网格、定向/边界、分面几何图等；
交换图继续执行下一节的逐边审计。使用两技能共用的
[插图修复流程](../mathtranslation/references/illustrations.md)，不要机械套用某一本书的裁框或缩放比例。

先独立盘点原书与实际构建链中的图，再建逐图台账，记录物理页/裁框、图号、
所有子图、标签、箭头/定向、源资产、最终 PDF 页与验证证据。相同数量或相同文件名
不能排除「错图替代了正确图」；核对相邻图，尤其同页多图及左右侧排图注。

优先保留原书可靠的矢量内容；需中文化、统一字体或修复几何时用原生 TikZ/PGFPlots
重绘。重绘前列出可见数学事实：坐标/曲线关系、向量端点、水平集条数与数值、
定向、边界符号、遮挡和投影。不得为美观改变这些事实。复杂曲面与场图不应退化成
含义相近的示意图。重新排布子图须保留阅读顺序、比例意义与连接关系。

400 DPI 渲染只是位图；真正矢量复用须保留 PDF 路径/字形/透明度，并复查输出。
绘图包给出的路径包围框可能含曲线控制点或受内部裁切约束，既不能盲目取并集，
也不能把它与裁框相交直接当成截断证据。自动裁图只生成候选；必须目视核对
完整原页、候选图、最终书页。保留细箭头、远处标签、子图标号与适当安全边。

图幅由最终字号与页面空间决定，不设全书统一宽度下限/上限；宽度使用局部
`\linewidth`，保持纵横比。密集分图可放大或重排，不能靠裁掉边缘/标签来缩小。
全书交付须逐图有最终页对应关系；编译通过、256 个图号对应 256 个文件、
像素相似度高，都分别不能代替内容、覆盖率和目视验收。

## 交换图与箭头保真审校

本节专指由节点和态射组成的交换图、正合列网格、拉回/推出图等；普通几何插图、曲线图和公式矩阵仍按各自规则处理。绘制或审校时使用 `tikzcd`，不要默认用 `array` 拼箭头图。发现旧稿时不能只搜 `tikzcd`：运行配套审计技能的 `scripts/inventory_diagrams.py`，覆盖所有实际参与构建的源文件、输入文件、脚注/附录和宏定义；候选逐项分类为交换图、公式/表格、待展开宏或未决。`array/aligned/matrix/CD/xymatrix` 中的箭头图同样纳入，普通矩阵不因含矩阵环境而机械迁移。

逐图分别从原书 PDF 与重排稿建立节点网格和边清单，再逐边比较：起点、终点、箭头头端、单射钩端、双头/等号/无头线、实虚线、标签及侧别、空节点与零行列。`r/l/u/d` 是几何位移，不能代替对映射方向的判断；检查显式 `from/to`、反向箭头选项、命名节点及实际展开后的宏。单射必须在最终 PDF 中确实显示钩，满射显示双头。`hook'` 只换钩所在侧，不会反转箭头；标签中的 `\hookrightarrow` 也不会改变边样式。检查局部选项与 `\tikzcdset`、`every arrow/.style`、自定义宏的叠加顺序，后续 `rightarrow` 等设置可能抹掉前面的 `hook`。编译成功及源码里出现 `hook` 都不能代替端部核对。

以原书出版版图像确定节点和箭头的可见事实；原始 TeX、OCR、数学语义只作辅助证据。分别映射原书和重排稿物理页，不用定理/证明的页码直接推定图所在页。先看整图结构，再放大检查钩、双头、箭头端点及裁切；同时检查孤立小样和最终书页。

若无法直接查看图像，先确认本地图片路径和查看工具，再重试一次；路径/工具错误不等同于模型没有视觉能力。仍无法目视时，按配套技能的[无视觉核验流程](../latex-array-diagram-audit/references/no-vision-verification.md)：从源码按顶层 `&`/`\\` 展开网格（保留空节点并处理嵌套宏），核对边方向和生效样式；在已确认的 PDF 裁剪区域检查文字跨度与矢量路径/字形，区分源码拓扑、PDF 几何和直接目视三类证据。PDF 没提取到箭头头笔画不能证明原图没有箭头。保留无法确认的具体图、边、行号、原书页/裁剪位置；这些细节必须标为未决，不能用编译通过或 OCR 的 `→` 代替视觉验收。

## 关键坑位速查

完整表见 `references/pitfalls.md`。最高频：

- **PDF 双层文本陷阱**：原书内嵌 `HiddenHorzOCR` 隐藏文字层，`get_text()` 混排吐乱码
 （`Jf`=ℋ、`&i(`=ℬ）。公式必须 `get_pixmap` 渲染目视确认。
- **编号公式共享计数器**：编号行间公式用 `gtmeq`（推进计数器）；左侧空白的号用 `equation\notag`
  （不推进）。裸 `equation` 会掉进 equation 计数器渲染成章号。
- **Claim 按章编号**：第一/二章 `claim*` 无号，第三/四/九章 `claim` 带号。
- **不要凭语义加环境标签**：原书大量裸段落，误包 `remark` 会吃掉编号、顶高后续全部条目。
- **交叉引用 A–E**（详见 `references/crossref.md`）：`\item` 前 `\gtmtarget` 错位、习题块两种写法、
  正则 `\\S` 误伤、批量补空格二次替换 + 陈旧 .aux 假错误、补零章号 / 空 `\ref{}`。
- **`\pagestyle{empty}` 泄漏（全书页眉页码丢失）**：扉页文件设 `\pagestyle{empty}` 却从不恢复，
  致**全书所有续页无页眉无页码**。`\thispagestyle` 只影响首页，须在章/前置/文献/索引各头宏里
  显式 `\pagestyle{fancy}` 恢复（详见下文「分章页码专著专项」）。

## 分章页码专著专项（`\chapcode` 版式）

Serre 类原书**每章页码独立起算**且带章前缀（I-1…I-30、II-1…II-42、B-1…B-8、Index-1…Index-3），
自建 cls 比 GTM 共享计数器路线多一整类坑，完整版见 `references/chapcode-retypeset.md`。最高频五条：

| 症状 | 正解 |
|---|---|
| 全书续页无页眉无页码 | `front/titlepages.tex` 的 `\pagestyle{empty}` 泄漏；在每个头宏（`\chapterhead`/`\fmhead`/bib/index）内显式 `\pagestyle{...}` 恢复，**不能只靠 `\thispagestyle`**（只管首页） |
| 页码格式被 `\pagenumbering` 重置 | kernel `\pagenumbering{roman}` 重定义 `\thepage`；须把「打印格式」与「计数」分离，每次 `\pagenumbering` 后重建 `\thepage`/`\theHpage`（后者 = 打印页码，使锚点与页码一致） |
| 前置 folio 反复跳页 / 打印两次 | `\fmhead[folio#]` 只在目标 folio **>** 当前值时才 bump（只进不退），避免向前跳页 |
| 陈述编号与原书不符 | 原书**手工编号**（有号/无号混排、常重新起数）：用「手工编号参数 + 隐藏锚点计数器」，`\begin{stmt}{LEMMA}{3}`，无号则第二参空 |
| biblatex 编号打乱原书顺序 | 自定义排序模板 + 每条 `sortkey` 字段，把 `refnumber` 锁死原书 [1]–[88] |
| 分 category 打印**恰好丢每条 category 的末条** | `\addtocategory` 的**收尾 `}` 另起一行** → TeX 把换行读成空格，末键变 `xxx␠`，biblatex 记进 `.aux` 后匹配不到条目。修：末键行尾加 `%` 吞换行。**先查 `.aux` 的 `\abx@aux@category{...}` 有无尾空格**（`defernumbers=true` 修不了） |
| 目录页码是死链 | hyperref 部分页不生成 `page.<folio>` 目标；改用 `\hyperref[<条目自己的 label>]`（章 `chap:I`/节 `sec:I.2`/文献 `bib:main`），`\@ifundefined{r@…}` 兜底回退 `\hyperlink{page.<folio>}` |

分章页码书的**页眉四类约定**（照原书逐类核对，`references/chapcode-retypeset.md` 有完整表）：
正文各章（偶页书名/奇页章短题）、前置部分（节名取代书名）、正/补充参考文献、索引（两侧仅外侧裸页码）。

## 小节裸编号专著专项（Samuel 类）

单卷、连续阿拉伯页码、陈述**按关键词分计数器并按节重启印裸号**、公式按节重启印 `(1)`、
参考文献 `[n]`、习题按章编号的书，完整版见 `references/samuel-style-retypeset.md`。最高频九条：

| 症状 | 正解 |
|---|---|
| 有名字的陈述后编号错位（Proposition 3 印成 2） | statement 包装器必须**无条件** `\refstepcounter`，可选参数只负责打印名字 |
| 逐页对不上扫描页 | 不要逐页强排；只在章/Supplement/Exercises/Bib/Index 起点调 `\folio{n}`（只进不退） |
| 页眉要显示本节在页内的节号区间 | `\pagefirstsec` + `\afterpage` 记上一页第一节；verso `folio｜章名｜§§ c.a–c.b`，recto 反向 |
| 外部文献章号被误链（`[1], Algèbre, Chapter VI`、`Chapter V of [9]`） | 按 `[n]` 与 `Chapter` 的近邻、`of [n]`、`\emph{Algèbre}` 三条规则排除，先保护 `\divhead{Chapter X}` |
| 参考文献 `[n]` 点不动 | `\item[\textbf{[n]}] \phantomsection\label{bib:n}`；正文 `\hyperref[bib:n]{[n]}`（显示文本锁死） |
| 习题引用链不上 | `\exitem` 内 `\refstepcounter{exno}` + `\label{exer:章.n}`；每章 `\exchap{X}` 重置；Review Problems 用 `R1/R2/R3` 防与末章重号 |
| 列表条目 `(1)(2)` 无锚点 | `\item\label{prop:c.s.i}`；正文仍写 `\hyperref[...]{(1)}`，因 enumerate 的 `\ref` 不带括号 |
| 裸引用审计满屏假阳性 | 必须**整段**屏蔽 `\hyperref[...]{...}`（花括号配平）；`\[...\]` 屏蔽要 `re.S` |
| `.aux` 报 label 不存在 / 颜色源码与 PDF 不符 | `\newlabel` 用配平解析（条目值形如 `{{(1)}}`）；颜色用 300 dpi 采样 Link 矩形断言 `(0,0,178)` |

构建：cls 用了 `fontspec` 时 `pdflatex` 必失败（`fontspec requires XeTeX or LuaTeX`），
用 `lualatex`/`xelatex`；`latexmk` 残留 fdb 仍可能拉 pdflatex，必要时直接调用。

## 中文书（xeCJK）专项

中文数学书重排有一整类西文书遇不到的坑，完整版见 `references/cjk-retypeset.md`。最高频五条：

| 症状 | 正解 |
|---|---|
| TikZ `\draw/\fill/\path[domain=…] plot (…)` 解析失败 | 改 `plot[smooth] coordinates{…}`，坐标由 `scripts/gen_tikz_curve.py` 在 Python 里算好注入 |
| `Missing character: … (U+6685) in font FandolSong` | Fandol 全字族缺生僻字；cls 加 `\newCJKfontfamily\zmbhan{SimSun}` 回退族，正文 `祖{\zmbhan 暅}` |
| 纯 CJK 行 2–3pt Overfull，`\hspace{0pt plus 3pt}` 无效、`plus 1fil` 出巨隙 | `\tracingparagraphs` 先诊断；正解是局部 `\begingroup\xeCJKsetup{CJKglue={\hskip 0pt plus 1pt}}…\endgroup` 均匀松排 |
| 密集刻度标签重叠（`2n` / `2n+1` / `2n+2`） | 照原书用「错落下沉」或「斜引线」两种布局，勿硬挤一行 |
| 全书出现 `\extref{6.3.2}` 纯文本引用 | 目标章节落盘后**回填**为 `定理~\ref{thm:6.3.2}`，且**只改生成器源头**再重新落盘 |

中文书另有三条易误判为缺陷的「正常现象」：
`xelatex fatal: memory exhausted`（瞬时内存压力，重跑即过）、
正文末尾空白页（`\makebibliography` 内 `\cleardoublepage`，与原书奇偶一致即预期版式）、
底料 OCR 跨页截断漏题（须对照影印页逐题点数）。

## 交叉引用补全（七轮递进）

正文硬编码引用（Theorem X.Y / (2.3) / Exercise N / Section N）→ 超链接 `\ref/\eqref` 的完整策略，
见 `references/crossref.md`：先规范化 label 命名（`kind:c.s.i`）、补 `sec:`/`exercise:` label，
再跨章 → 章内括号 → 章内裸编号逐轮转换，每轮编译验证。

单卷裸编号书另有三类 `crossref.md` 未覆盖的对象：**参考文献 [n]**（锚在条目行、正文用
`\hyperref[bib:n]{[n]}`）、**按章习题号**（`exer:c.n`，Review Problems 另用 R 前缀）、
**陈述内列表条目 (1)(2)**（`\item\label{...}`）。另有两类必须保留纯文本：外部著作自身的
Chapter 号、原书笔误（如 “§4, Proposition 2” 而该节只有 Proposition 1——保留印刷字，
链接指向真实目标并记入 `STATE.md`）。详见 `references/samuel-style-retypeset.md`。

## 配套审计技能（已安装，按需调用）

- `latex-eq-numbering-audit` — 编号公式与原书逐项核对
- `latex-display-layout-audit` — 行间公式版式（over-wrap / 假对齐）
- `latex-footnote-fidelity-audit` — 脚注是否全部落地
- `latex-ocr-math-defect-audit` — OCR 静默毁坏的数学
- [交换图审计技能](../latex-array-diagram-audit/SKILL.md) — 旧式图候选盘点、逐边方向/钩/双头核验、样式覆盖检查与无视觉证据流程
- `latex-bookmark-anchor-audit` — PDF 书签锚点
- `mathtranslation` — xelatex/biber 编译与视觉验证（references/build-verify.md）

## 验收门槛

见 `references/verification.md`：清 aux 后 4 遍 exit=0；0 错误 / 0 重复 / 0 未定义 / 0 死链；
习题编号逐节连续；CRLF/BOM 合规；原书自身编号不一致处保留纯文本并审计数量。

中文书额外三项（用 `scripts/verify_cjk_book.py main.pdf --log main.log --bib-page N` 一次跑完）：
PDF 文本层 `??` 0 处、`Missing character` 0 处、回填后的引用在 PDF 中确实解析为编号（而非原文）。

分章页码书额外一项：用 `scripts/dump_page_heads.py main.pdf` 逐页 dump 顶/底文本带，
断言**每一续页**都有页眉与页码、**每一首页**无页眉而底部居中裸页码，且页码格式（I-2 / B-5 / Index-3 / 罗马数字）正确。
目录页码超链接另用 `--check-toc-links` 断言 `page.*` 命名目标全部解析。

单卷裸编号书额外两项：`scripts/audit_internal_links.py` 断言全部 `\ref/\eqref/\pageref/\hyperref`
目标 0 缺失（不要只查 `\ref`）；`scripts/check_link_color.py main.pdf --expect 0,0,178` 用像素采样
断言链接颜色（源码里的 `colorlinks` 不算证据）。裸引用扫描用 `scripts/audit_bare_xrefs.py`，
残留项必须逐条判定是「列表标号/外部文献」而不是引用。

## 关键脚本

- `scripts/audit_text_refs.py`：扫描 `.tex` 列出尚未 `\ref` 化的硬编码引用（开工清单，不改文件）。
- `scripts/rebuild_exercise_labels.py`：安全重建 `exercise:c.s.i`（默认 dry-run，正确处理同行
  `\gtmtarget` 与手工习题块）。
- `scripts/gen_tikz_curve.py`：xeCJK cls 下 `plot[domain=…]` 不可用，用它把参数 / 笛卡尔 / 极坐标
  曲线算成 `plot[smooth] coordinates{…}` 字面量（`--wrap` 直接输出完整 `\draw`）。
- `scripts/verify_cjk_book.py`：全书终检器（`??` 残留 / 书签条数 / 回填引用落点 / 参考文献条目 /
  缺字符），任一硬门槛不过即 exit=1；交付前必跑。
- `scripts/dump_page_heads.py`：分章页码书页眉/页码终检器。逐页 dump 顶/底文本带，报告每页的
  running head 与 folio；`--check-toc-links` 另断言目录 `page.*` 命名目标全部解析。
- `scripts/audit_internal_links.py`：把 `\ref/\eqref/\pageref/\hyperref[...]` 全部对 `main.aux`
  核验（`\newlabel` 花括号配平；自动跳过 `work/bak/render/build` 备份目录），有缺失即 exit=1。
- `scripts/audit_bare_xrefs.py`：先整段屏蔽已链接文本、数学、`\item[...]`/`\pdfbookmark[...]`
  等可选参数，再枚举裸 `Theorem 3` / `(4)` / `[3]` / `exercise 8`，输出 STMT/PAREN/FORM/BIB/EXERC 计数。
- `scripts/check_link_color.py`：渲染 PDF、对每个 Link 矩形做非白像素直方图，断言链接文字颜色；
  `--expect 0,0,178` 对应 `blue!70!black`，防 `\hypersetup` 后写覆盖。

## Resources

- `references/discipline.md` — 文档类 / 计数器速查、页码映射、文献区排印参数
- `references/pitfalls.md` — 西文书全部坑位（OCR / 编号公式 / Claim / 环境标签 / overfull / 交叉引用 A–E）
- `references/cjk-retypeset.md` — **中文书专项**（TikZ 曲线 / 缺字回退 / CJKglue 松排 / 标签重叠 / extref 回填 / memory exhausted / biber 书目 / 单一落盘出口）
- `references/chapcode-retypeset.md` — **分章页码专著专项**（`\chapcode` 页码机制 / `\pagestyle{empty}` 泄漏 / 四类页眉约定 / 手工编号陈述 / biblatex sortkey 锁定 / 目录页码超链接）
- `references/samuel-style-retypeset.md` — **单卷裸编号专著专项**（按关键词/按节重启编号、`\folio` 只锁分部起点、页眉节号区间、外部文献章号排除、`bib:n` 与 `exer:` 锚点、列表条目引用、`.aux` 配平解析、链接颜色像素验收）
- `references/crossref.md` — 交叉引用七轮补全策略 + 习题重建算法 + 保留纯文本清单
- `references/verification.md` — 构建命令、验收清单、CRLF/BOM 检查
- `scripts/audit_text_refs.py` — 硬编码引用扫描器
- `scripts/rebuild_exercise_labels.py` — 习题 label 安全重建器
- `scripts/gen_tikz_curve.py` — 参数/笛卡尔/极坐标曲线 → `plot[smooth] coordinates{…}` 片段
- `scripts/verify_cjk_book.py` — 全书终检（PDF 层 `??` / 书签 / 回填引用落点 / 参考文献条目 / 缺字符）
- `scripts/dump_page_heads.py` — 分章页码书页眉/页码 + 目录页码超链接终检器
- `scripts/audit_internal_links.py` — 全部内部链接目标（`\ref/\eqref/\pageref/\hyperref`）对 aux 核验
- `scripts/audit_bare_xrefs.py` — 屏蔽已链接文本后的裸引用枚举（STMT/PAREN/FORM/BIB/EXERC）
- `scripts/check_link_color.py` — PDF Link 矩形像素采样，断言链接颜色（默认 `0,0,178`）

## 中文回忆版试卷合集

多校多年试卷、各卷独立题号与分值、重排同时审题时，读取 [回忆版试卷专项](references/recalled-exams.md)。必须分开识别错误与原题错误，检查被 OCR 丢弃的页眉页脚是否藏着题号；未完成逐题证明时不将首轮初筛写作全题已证正确。

## 有界并行与页级 OCR 来源

全书任务需要缩小单个代理上下文时，参阅[有界子代理、OCR页级来源与索引映射](references/parallel-retypeset.md)。包含文件所有权、代理中断交接、修订表查重、数学字体与陈述范围、PDF 哈希绑定验收，以及 Ahlfors 底稿中跨页段落搬移、分卷局部页号重启、一块多图、索引语义分组终审、疑点定案、脚注跨页复核和编辑性校勘留痕的已验证方法。
