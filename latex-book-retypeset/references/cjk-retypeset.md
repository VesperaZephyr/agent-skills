# 中文数学书重排专项（xeCJK / Fandol / 原生 TikZ）

实战来源：徐森林、薛春华《数学分析（第一册）》全书重排（6 章 + 前言 + 参考文献，
**551 页**、40 个章节源文件、整章 23 幅 TikZ 图、biber 中文书目 9 条；
终局 0 编译错误 / 0 缺字符 / 0 未定义引用 / 0 Overfull / PDF 层 `??` 0 处）。

本篇是西文（Springer GTM 类）重排之外的**中文书专属坑位**。通用坑位见 `pitfalls.md`。
顺序按「症状 → 根因 → 修法」，与 `pitfalls.md` 风格一致。

---

## 1. TikZ 参数曲线：`plot[domain=…] (\x…)` 会解析失败

| | |
|---|---|
| 症状 | `\fill[pattern=…] plot[domain=0:6.2832,samples=70] (\x - sin(\x r), 1 - cos(\x r)) -- cycle;` 报 `Undefined control sequence` / pgf 解析错；`\draw[domain=…] plot (…)` 同样失败 |
| 根因 | 在 `zhmbook` 这类自建 cls（xeCJK + 定制 tikz 选项）下，`plot` 的 `domain` 传参路径与数学解析组合会崩；实测 `\draw[domain=…]`、`\fill[domain=…]`、`\path[domain=…]` 三种写法**全部失败**，而 `plot[smooth] coordinates{…}` 稳定通过 |
| 修法 | **一律改用 `plot[smooth] coordinates {…}`**：用生成器内的 Python 把曲线数值算成坐标点注入（见 `scripts/gen_tikz_curve.py`）。显式函数 $y=f(x)$ 与参数曲线 $(x(t),y(t))$ 都走这条路 |
| 注意 | 填充闭合要写成 `(起点) -- plot[smooth] coordinates{…} -- (终点) -- cycle`；`samples` 30–60 即可，过密会让 `smooth` 出现抖动 |

实测通过的最小写法：

```latex
\draw[very thick] plot[smooth] coordinates {(0,0) (1,1) (2,0.4) (3,0)};
\fill[pattern=north east lines]
  (0,0) -- plot[smooth] coordinates {(0,0) (1,1) (2,0.4) (3,0)} -- (3,0) -- cycle;
```

---

## 2. 缺字符：Fandol 全字族也不收的汉字（如「暅」U+6685）

| | |
|---|---|
| 症状 | `Missing character: There is no 暅 (U+6685) in font FandolSong-Regular` |
| 根因 | Fandol 宋/楷/黑**全字族**都不收部分生僻字（人名、古算术语高频：祖暅、祖冲之相关） |
| 诊断 | 写一个最小 `.tex`，逐个候选字体试排该字，`grep 'Missing character'` 计数；**不要凭猜测改字** |
| 修法 | 在 cls 中新增一个**回退字族**（不改动原有 `\setCJKmainfont`），正文按需局部切换 |

```latex
% zhmbook.cls：Fandol 缺字回退（SimSun 覆盖 GB2312/GBK 全字集）
\newCJKfontfamily\zmbhan{SimSun}[BoldFont=SimSun]
```
```latex
% 正文：只包裹缺字本身，不影响周围字体
祖{\zmbhan 暅}原理
```

配套纪律：
- 原书印的是生僻字就**照排**，不要替换成形近字或拼音。
- 改完 cls 立刻自检行尾：`CRLF / loneLF=0 / 无 BOM`（cls 属工程源文件，走同一条红线）。
- 每节收尾用 `grep -c 'Missing character' main.log` 断言为 0。

---

## 3. 纯 CJK 行 Overfull：`\hspace` 与 `fil` 都错，正解是局部 `CJKglue`

最难的一类：整行几乎全是汉字 + 少量行内数学，**没有任何可伸缩胶水**，
TeX 找不到可行断点，只能接受 2–3pt 超宽。

**先诊断，再动手**（不要凭感觉加空格）：

```latex
\tracingparagraphs=1
…问题段落…
\par\tracingparagraphs=0
```
编译后从 `main.log` 读 `@firstpass/@secondpass/@thirdpass`：
看每个候选断点的 `badness`、以及是否只有 emergency pass 才可行。
若日志显示「目标断点需要约 30pt 伸缩」→ 说明**必须给全行均匀加伸缩**，任何单点 hack 都救不了。

三级方案实测对比：

| 方案 | 结果 |
|---|---|
| `\hspace{0pt plus 3pt}`（有限伸缩） | ❌ 无效，overfull 数值纹丝不动（伸缩量不够，badness 仍超限） |
| `\hspace{0pt plus 1fil}`（fil 级） | ❌ 数值清零但产生 **86pt 巨隙**（全部伸缩集中到一处，视觉灾难） |
| `\hspace{0pt plus 20pt}`（较大有限值） | ❌ 清零但空隙肉眼可见 |
| **局部 `\xeCJKsetup{CJKglue={\hskip 0pt plus 1pt}}`** | ✅ **正解**：每个 CJK 字间隙各摊 +1pt 伸缩，30pt 缺口由 ~30 个字间隙均摊，单处仅约 0.7pt，视觉无感 |

```latex
\begingroup\xeCJKsetup{CJKglue={\hskip 0pt plus 1pt}}
…这一段（含纯 CJK 长行）…
\endgroup
```

配套心法：
- 用 `\begingroup … \endgroup` **严格限定作用域**，切勿全局改（会悄悄改变全行距观感）。
- 修完**必须目视渲染核验**（`get_pixmap` 裁切该段），确认既无巨隙、断行位置也与原书一致。
- 原书若是**绕图窄栏**排版，全宽版式下原断点不可复现是正常的——目标是「断行落在语义合理处且无隙」，不必强求逐字对齐。

---

## 4. TikZ 标签重叠（密集刻度）

| | |
|---|---|
| 症状 | x 轴右侧 `2n` / `2n+1` / `2n+2` 三个标签挤成一坨；或图底 `n±1/(2^n n)` 与 `n` 互压 |
| 根因 | 标签等宽排列，间距不足；`\node[below]` 全部锚在同一 y 上 |
| 修法（照原书） | ① **错落**：让中间标签下沉一行（`yshift=-0.45`），两侧保持；② **斜引线**：标签左右外移，用 `\draw[thin] (标签) -- (锚点)` 斜引到轴上。两种原书都有使用，看原书形态选 |
| 复检 | 高倍裁切（dpi 300+）渲染核对；不要只看整页缩略图 |

---

## 5. `minipage[t]` 并排 TikZ 的基线错位

| | |
|---|---|
| 症状 | 左 `minipage` 放 `gather*`/`align`、右 `minipage` 放 TikZ，两者呈**对角堆叠**（图整体下沉） |
| 根因 | TikZ picture 的默认基线在 bounding box **底边**，与公式首行基线不平齐 |
| 修法 | `\begin{tikzpicture}[…, baseline=(current bounding box.north)]` |

---

## 6. `\extref` 是临时态，必须回填

| | |
|---|---|
| 症状 | 全书完成后仍有 `\extref{6.3.2}` 这类纯文本引用（不可点击、不会随编号变化） |
| 根因 | 写第 N 章时第 M 章（M>N）尚未落盘，用 `\extref`（= `\textup{}`）占位防 `??` |
| 修法 | **目标章节落盘后立刻回填**为 `类别词~\ref{kind:X.Y.Z}`；回填**必须改生成器源头**再重新落盘，绝不直接改 `.tex`（会被下次生成覆盖） |
| 类别词纪律 | 本册引用一律带类别词：`定理~\ref{thm:…}`、`定义~\ref{def:…}`、`例~\ref{ex:…}`、`图~\ref{fig:…}`、`注~\ref{rem:…}`、`推论~\ref{cor:…}` |
| 回填后验证 | 在 PDF 文本层正则搜 `定理\s*6\.3\.2` 等，确认落点页码合理且全部解析为编号（不再显示原文） |

---

## 7. `\xlongequal[下]{上}` 的下标注记不可包 `\text{}`

| | |
|---|---|
| 症状 | 双行标注的下标处报一连串级联错误 |
| 根因 | 下标注记处于数学模式，包 `\text{}` 会切到文本模式引发级联；**上标注记**已被 cls 自动包 `\text{\small …}`，所以上标写纯数学要**自套 `$…$`** |
| 修法 | `\xlongequal[{\exists\xi\in[a,b]}]{\text{积分第一中值定理}}`；上标写数学时：`\xlongequal{$t=\frac{\pi}{2}-x$}` |

带撇 / 双撇编号（`6.5.3′`、`6.5.3″`）用 cls 的 `theoremp` / `theorempp` / `corollaryp` 环境，
label 写作 `thm:6.5.3p`。

---

## 8. 子文件必须自带 `\section`

生成器初版漏写 `\section{…}` 时，整节内容会被排进**前一节编号下**，且页眉节名错误。
落盘后必须核对页眉节名与 PDF 书签层级。

---

## 9. `xelatex` 报 `fatal: memory exhausted`

| | |
|---|---|
| 症状 | exit=1，日志无 `Output written`，`main.pdf` 仍是旧时间戳 |
| 根因 | **瞬时系统内存压力**，不是源码问题 |
| 修法 | 直接重跑；**诊断顺序：先看日志尾部有没有这行，再决定要不要查源码**——不要一上来就怀疑刚落盘的 `.tex` |

---

## 10. 正文中间突然出现空白页

| | |
|---|---|
| 症状 | 全书唯一一处空白页出现在正文末尾（p550），cls 明明是 `openany` |
| 根因 | `\makebibliography`（cls 内）含显式 `\cleardoublepage`，参考文献强制起于**奇数右页** |
| 判定 | 若与原书印刷页奇偶一致（原书参考文献起于印刷页 449 = 奇数）→ **预期版式，不是缺陷**，不要改 |
| 排查法 | 先 `grep -n 'cleardoublepage' cls main.tex`，再比对原书该处页码奇偶 |

---

## 11. biber 中文书目：跨册工程复制残留

| | |
|---|---|
| 症状 | `refs.bib` 头注释写着「《数学分析》（**第二**册）…第 412 页」，而本册是**第一**册、参考文献在印刷页 449 |
| 根因 | 从姊妹册工程复制 `.bib` 时只改条目没改头注释 |
| 修法 | 交付前核对：书名/册次、原书印刷页与物理页映射、条目数；条目顺序用 `BibSorting=none` 锁定为原书顺序，**不得重排** |
| 输出方式 | 原书正文无引用角标时，用 `\nocite{*}` 令 biber 全量输出 |

---

## 12. 底料（OCR 的 md）不可全信：跨页截断会漏题

底料抽取在跨页截断处**漏题**是常态（实测：复习题底料记录到 24 题，原书实为 27 题）。
落盘前必须**对照原书影印页逐题点数**，而不只是信底料行数。
其它高频 OCR 错误：导数极限自变量 $x\to0$ 误识为 $n\to\infty$、`\int` 上下限错位、指数 `!!!` 爆炸、
`\operatorname` 误码、全角标点残留。

---

## 13. 工程侧：shell heredoc 会剥掉一层反斜杠

| | |
|---|---|
| 症状 | Bash 内联 `python - <<'PYEOF'` 中写 `'\\backslash'`，到 Python 手里只剩 `'\backslash'`；`SyntaxWarning: invalid escape sequence`，精确字符串匹配失败 |
| 根因 | shell shim 对内联脚本剥掉一层反斜杠 |
| 修法 | **凡是含反斜杠字面量的文本处理**（LaTeX 宏名、Windows 路径、正则），一律用 Write 工具落 `.py` 脚本文件再执行，不要走内联 heredoc |

---

## 14. 题块与插图规范（中文书）

- 复习题 / 练习题统一用 `\begin{exblock}{复习题 N}` 容器；大题直接 `\item`，子问 `\begin{enumerate}[label=(\arabic*)]`。
- 原书多列排版的题组，本工程统一**单列**（cls 未载 `multicol`，与既有章节保持一致）。
- **图题注不得手写编号**，一律 `\caption{}\label{fig:X.Y.Z}`，正文用 `(图~\ref{fig:X.Y.Z})` 引用。
- 图形一律**原生 TikZ**，禁用位图；阴影区用 `pattern=dots` / `north east lines`（cls 已载 `patterns` 库）。
- 单节插图可达 20+ 幅——生成器按 `fig:X.Y.N` 顺序编号，落盘后跑结构脚本断言 label 序列 `1..N` 无缺口。

---

## 15. 单一落盘出口

所有生成器统一 `from _texout import write_tex` 落盘：自动清洗 display 数学环境内部空行（杜绝 amsmath 级联报错）、
折叠多余空行、写 CRLF 无 BOM，并打印 `bytes / blank_in_display_removed / BOM / CRCRLF`。
**任何新生成器都必须走这个出口**，不要各自写 `open(...).write()`。
