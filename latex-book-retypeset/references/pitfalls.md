# 坑位大全：LaTeX 数学书重排

每一个都来自实战踩坑，按「症状 → 根因 → 修法」组织。排错时先对症状，再动手。

---

## 1. PDF 双层文本陷阱（OCR 底稿不可信公式）

| | |
|---|---|
| 症状 | 按 OCR 底稿写出的公式出现 `Jf`（实为 $\mathcal{H}$）、`&i(`（实为 $\mathcal{B}$）、`Yf`、`II A II`（实为 $\|A\|$）等乱码 |
| 根因 | 原书 PDF 内嵌 `HiddenHorzOCR` 的 Type0/CID **隐藏文字层**，`page.get_text()` 把真实正文层与隐藏 OCR 层混排吐出 |
| 修法 | ① `page.get_text('words')` 缩小范围辨认正文层；② **公式必须 `get_pixmap(clip=fitz.Rect(...))` 渲染成 PNG 目视确认**；③ OCR 底稿只用于定位章节边界与条目清单，公式一律回原图核对 |

各章 OCR 错误率：第三章 > 第二章 > 第一章。第三章实测：`q(x)=α` 漏字、`\tilde f(x)=f(x)-if(ix)` 丢符、开映射证明丢下标、漏条件 (iii)、`\|F(\mu)\|_\infty` 写成 `F(\mu)|_\infty`、`v` 与 `\nu` 混用。

---

## 2. 花体字母约定

| | |
|---|---|
| 症状 | 空间名 $\mathcal{H}/\mathcal{K}/\mathcal{L}$ 全部识别成同一个花体字母 |
| 根因 | 第二章起严格区分：$\mathcal{H}$ 源空间、$\mathcal{K}$ 目标空间、$\mathcal{L}$ 第三空间；PaddleOCR 一律识别为 $\mathcal{H}$ |
| 修法 | 回原图确认每个花体字母的实际身份，不要照抄 OCR |

---

## 3. 编号行间公式必须用共享计数器环境

| | |
|---|---|
| 症状 | 编号公式后的所有条目整体前移一格（§6.12 排成 "6.7 Theorem"） |
| 根因 | GTM96 的编号行间公式与定理**共享 `gtmitem` 计数器**。用裸 `\begin{equation}` 不推进计数器，其后编号整体错位 |
| 判定三分类 | ① 左侧有独立粗体号 → `\begin{gtmeq}\label{eq:X}`（推进）；② 左侧空白（号属于所在条目）→ `\begin{equation}\notag\label{eq:X}`（不推进、且不落入 equation 计数器）；③ 裸 `\[ \]` 无 label → 不推进 |
| 注意 | 第二类若写成裸 `equation`（不加 `\notag`）会掉进 equation 计数器，渲染成 "III.2" 章号序号 → **必须加 `\notag`** |

验证手法：编译后正则抽 `(\d+\.\d+)\s?(Theorem|Corollary|…)` 全序列，与原书条目清单逐项对照。

---

## 4. Claim 是否带编号按章而异

| | |
|---|---|
| 症状 | 证明内 "Claim." 的编号与原文不符 |
| 根因 | 第一、二章的 Claim 无编号（`claim*`）；第三、四、九章的 Claim 带编号（`claim`） |
| 修法 | 以原书该章实际形态为准，逐章选择 `claim` 或 `claim*`，不凭语义统一 |

---

## 5. 不要凭语义给段落加环境标签

| | |
|---|---|
| 症状 | 某节所有条目整体顶高一号（"2.2 Remark" 实为裸段落） |
| 根因 | 原书大量段落是**无标签普通正文**；凭直觉包成 `\begin{remark}` 会吃掉编号，顶高后续全部条目 |
| 修法 | 不确定某段有没有标签时，**必须 `get_pixmap` 渲染原书对应页看一眼**；同类风险：把普通说明段误当 `definition` / `example` / `proof` |

---

## 6. `$*$-xxx` 断词 + `\linebreak` 吞空格

| | |
|---|---|
| 症状 | `$*$-homomorphism` 行尾 overfull；`\linebreak[0]` 后断点失效 |
| 根因 | ① `$*$-单词` 是数学盒子 + 显式连字符，TeX 连字模式不在后续单词插软连字符；② `\linebreak[0]` 末尾的 `\ignorespaces` 吞掉源码普通空格，使惩罚点 + 后继胶水不成立 |
| 修法 | ① 手写断词点 `$*$-homo\-mor\-phism`（输出无差异）；② `\linebreak[3]\ actually`（强制断点用 `\linebreak[4]` = −10000，且紧跟 `\ ` 控制空格） |

---

## 7. overfull \hbox 修复方法论

**先量测探针，再动源码。**（探针必须每个取值写独立文件，否则循环内互相覆盖得假数据。）
试编 `emergencystretch` = 0/1/2/3em：若 overfull 数与最大值都不变 → 根因是**不可断行长数学串**，不是断行容差 → **不要改 cls 容差参数**，改源码。

按章独立测量：`_ovf_chNN.tex` 单独编译得该章 overfull 与行号（从 `main.log` 按行号区间反推章节不可靠，行数会漂移）。

有效手段（按优先级）：① 超长行内数学 / 长 `\text{}` 提成独立 `\[ \]` / `align*`；② 一行 `align` 拆 2–3 行；③ `exercises` 环境（版心更窄）里把长公式移出正文；④ **改写句子给出额外断点**（要在不可断词之前造断点，不是简单重新折行）；⑤ 缩到 < 3pt 后接受（Springer 原书本身也有这类噪声）。

⚠️ **单纯源码重新折行对不可断数学串无效**：`\text{...}` 整串是盒子，源码换行不改宽度。

---

## 8. 交叉引用工程的坑（A–E）

| 坑 | 症状 | 根因 | 修法 |
|---|---|---|---|
| **A** | 习题 label 与自动编号错位（引用跳号） | `\item` 前同行有 `\gtmtarget{ixNNN}`，用 `^\s*\item` 行首锚定会跳过这些题 | 改用「块内深度 + 顺序计数」；label 插在 `\gtmtarget` 与 `\item` 之间 |
| **B** | 整节习题无 label | 除 `exercises` 环境外，还可能是 `\par\vspace{...}\noindent{...Exercises}...\begin{enumerate}` 手工展开 | 两种块形式都识别（Ch IX §2 整节 23 题因此漏） |
| **C** | 匹配到 `= 1` / `q 0` 无关字符 | 正则 `'\\S'` 是「非空白字符」而非 Section 符号 | 写 `re.escape('\\' + 'S')` |
| **D** | 批量补空格后重复引用 + 假错误 | `}~\ref{X}` 全局替换二次生效；陈旧 `.aux` 让正确源码也报 `Extra \else` | 先去重复再**清空 `main.aux/out/toc` 重编 4 遍** |
| **E** | `undefined` 指向 `exercise:02.1.13` / 空 `\ref{}` | 章号格式化产生前导零；批量替换误伤产生空 ref | 正则去前导零；终验专门扫空 `\ref{}` 与 `0\d` 章号 |

---

## 9. Ch IX 专项坑（长不等式 / 强制断点）

| 症状 | 根因 | 修法 |
|---|---|---|
| 强制断点无效，overflow 数值一模一样 | `\linebreak[0]` 只 penalty 0 | 改 `\linebreak[4]`（−10000）；断点落在不可断数学串**之前** |
| 段落全是长不等式，overflow 40+pt，`\allowbreak` 无效 | 断行容差不足（非不可断） | 局部 `\begingroup\emergencystretch=1em … \par\endgroup` |
| `\text{长句}` → 70pt 不可断盒子 | `\text{}` 整体成盒 | 把文字挪出数学：`$\{…\}$ is a polynomial in $z$`（字形不变但可断） |
| `\tag{\thegtmitem^{*}}` → Missing $ inserted | `\tag` 参数在文本模式 | `\tag{\thegtmitem\textsuperscript{*}}`（且不推进计数器） |
| 生成器 SyntaxError / invalid escape | `\mathscr{S}''''` 四个撇号闭合了 `r'''…'''` | 改用 `r"""…"""` |
| 习题前有导语段 → "missing \item" | cls 的 `exercises` 内直接是 enumerate | 生成器内手写 heading + 导语 + `enumerate[label=\arabic*., leftmargin=* …]` |

---

## 10. 中文书（xeCJK）专属坑 → 见 `cjk-retypeset.md`

上表 1–9 全部来自西文书（GTM96）。中文书重排另有一整类坑，**不要拿西文经验硬套**：

| 症状 | 与西文书的关键差异 | 修法摘要 |
|---|---|---|
| `\draw[domain=…] plot (\x,…)` 解析失败 | 西文书无此问题；xeCJK 自建 cls 下三种写法全崩 | 改 `plot[smooth] coordinates{…}`，Python 算坐标 |
| `Missing character … FandolSong` | 西文缺字符极少；中文生僻字（人名/古算术语）高频 | cls 加 SimSun 回退字族，局部包裹 |
| 纯 CJK 行 2–3pt Overfull | 西文可用断字/连字符；**汉字无连字符、无伸缩** | `\tracingparagraphs` 诊断 → 局部 `CJKglue` 均匀松排（`\hspace`/`fil` 均错） |
| 图标签重叠（`$2n$`/`$2n+1$`） | 数学标签宽度远大于数字刻度 | 错落下沉或斜引线 |
| 末尾空白页 | 西文 `openright` 常见；中文 cls 是 `openany` 却仍出现 | 查 `\makebibliography` 内 `\cleardoublepage`，奇偶合原书即预期 |

完整 15 条（含 `\extref` 回填、`\xlongequal[下]{上}`、子文件 `\section`、`memory exhausted`、
shell 反斜杠剥层、biber 跨册复制残留、底料漏题、单一落盘出口）见 `references/cjk-retypeset.md`。
