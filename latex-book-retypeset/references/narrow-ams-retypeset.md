# 极限窄版心数学专著专项（Katz & Mazur / AMS 路线）

实战来源：Nicholas M. Katz & Barry Mazur, *Arithmetic Moduli of Elliptic Curves* (Annals of Mathematics Studies No. 108, Princeton University Press, 1985)。全书重排成品 **518 页**（14 章 + 前言 + 校样附注 Notes Added in Proof + 52 篇参考文献 References）。在极限窄版心（100.5 mm）下达成 **0 Errors, 0 Overfull \hbox (0.0pt), 0 Undefined refs, 0 Undefined citations** 全绿灯工业级验收标准。

---

## 1. 版式几何与极限窄版心约束

AMS 系列与普林斯顿专著的一大显著特征是**极限窄版心**：

| 几何参数 | 数值 | 换算 / 影响 |
|---|---|---|
| **成品页面** | 130.5 × 195.4 mm | 便携学术小开本 |
| **版心尺寸** | 100.5 × 150 mm | 正文可用宽度 `\linewidth = 285.95pt`（仅约 40 个西文字符宽） |
| **公式编号** | `leqno`（左置编号） | 行间公式左侧被编号占据约 35–45pt，右侧实际剩余不足 240pt |
| **页眉字号** | `\scriptsize` | 双页页眉，偶页书名全大写，奇页章名全大写 |
| **页码映射** | `物理页 = 书页 + 11` | 实际印刷书页与原书扫描件对应稳定 |

由于 `\linewidth` 仅 285.95pt，任何稍长的分式、多重上标、欧拉示性数式或直和式极易产生 10–50pt 的 Overfull \hbox。必须依赖系统化的排版模式，禁止盲目依靠增大容差（如 `emergencystretch`）。

---

## 2. 联合递增编号体系 (`kmitem`)

原书采用 20 世纪 80 年代 Grothendieck 学派专著典型的**段落与定理联合编号**：

1. **统一计数器 `kmitem`**：
   段落条目形如 `(1.3.1)`，与同节内的 `Theorem 1.3.2`、`Lemma 1.3.3`、`Proposition 1.3.4` 共用一条单调递增计数器。
   ```latex
   \newcounter{kmitem}[section]
   \renewcommand{\thekmitem}{\thesection.\arabic{kmitem}}
   ```
2. **定理样式与字体**：
   - 定理类（`theorem`, `lemma`, `keylemma`, `proposition`, `corollary`）：正文斜体（`\theoremstyle{kmplain}`）；
   - 定义说明类（`definition`, `caution`, `remark`, `example`）：正文正体（`\theoremstyle{kmdef}`）；
   - 证明环境（`proof`）：正体，证毕符号统一右对齐 `\square`（`\qedsymbol = \ensuremath{\square}`），公式结尾必须使用 `\qedhere` 避免证毕框掉落至次行。
3. **行间公式二级分层编号**：
   行间公式属于某一条目下的子公式时，形如 `(1.3.1.1)`。使用 `chngcntr` 宏包实现条目出现即清零：
   ```latex
   \counterwithin*{equation}{kmitem}
   \renewcommand{\theequation}{\thekmitem.\arabic{equation}}
   ```
4. **特殊编号处理**：
   - 附录或特殊性质（如 Ch.8 的 `(T.1)`–`(T.4)`、Ch.10 的 `10.9.3` 跨节号）：使用 `\refstepcounter{kmitem}\tag{...}` 或临时覆盖 `\thekmitem`；
   - 无编号定理（如 Notes Added in Proof）：定义独立的无编号环境 `\newtheorem*{theorem*}{Theorem}` 与 `\newtheorem*{proposition*}{Proposition}`，杜绝编号计数器被污染。

---

## 3. 窄版心数学排版五大设计模式

| 模式名称 | 核心应用场景 | 语法实现与避坑要诀 |
|---|---|---|
| **对齐断行律** (*Aligned Split*) | 欧拉示性数长公式、复杂减法求和式（如 §14.5.12b） | 首行保留求和算子与首项欧拉示性数；次行大幅缩进，二元减号运算符置于行首并与外层大括号形成视觉对称：<br>`\begin{equation*}`<br>`\begin{aligned}`<br>`&\sum_{a+b=n} \phi(p^{\min(a,b)}) \\`<br>`&\quad \times \left[ \begin{aligned}`<br>`&\chi\bigl((X_s(a,b) - CX_s(a,b) - \mathrm{SS}(X_s(a,b)))/H(v)\bigr) \\`<br>`&\quad - \chi(\text{''} / H(v-1))`<br>`\end{aligned} \right] .`<br>`\end{aligned}`<br>`\end{equation*}` |
| **外层缩放律** (*Outer Resizebox*) | 超宽汇总表格（如 §8.5.4 分类表、Table 14.5.7.9~12 群作用分析表） | `\resizebox{\linewidth}{!}{ \begin{tabular}... \end{tabular}% }` **必须作为最外层容器**完整包裹表格；尾部花括号紧跟 `%`，杜绝多余空格令牌诱发 `Misplaced \noalign` 编译崩溃。 |
| **紧凑阶梯律** (*Compact TikZ-cd*) | 密集纤维代数图、多层交换图（如 §8.11, §9.3） | **严禁在 tikzcd 外部包裹 resizebox**（`&` catcode 冲突导致致命错误）；改用内部紧凑控制：`[column sep=0.3em, row sep=1.2em, font=\scriptsize]` 梯级降级化解宽度压力。 |
| **蛇引理贝塞尔回环律** (*Snake Bezier*) | 跨行长正合列与蛇引理弯折连接箭头（如 §14.6.3） | 使用原生 TikZ 贝塞尔弯曲：首行末尾向右向下平滑出环，次行首端向左向上平滑入环，在窄版心内流线型换行：<br>`\draw (C.east) to[out=0, in=0, looseness=2] ++(0, -0.6) -- ([yshift=0.6cm]D.west);`<br>`\draw[->] ([yshift=0.6cm]D.west) to[out=180, in=180, looseness=2] (D.west);` |
| **直和下标堆叠律** (*Substack Sizing*) | 多重求和/直和下标（如 §13.12, §14.6） | 行间公式使用 `\bigoplus_{\substack{a+b=n \\ u \in (\mathbb{Z}/p^{\min(a,b)}\mathbb{Z})^\times}}` 纵向折叠；表格与矩阵内搭配 `\small` 与 `\arraystretch` 控制行高与间距。 |

---

## 4. TikZ / TikZ-cd 容器红线与图形避坑

1. **绝对禁令：禁止在 `tikzcd` 外层套 `\resizebox`**：
   - 根因：`tikzcd` 环境内使用 `&` 作为列分隔符，TeX 会在展开 `\resizebox` 的参数时将 `&` 的 catcode 固定为 12（other）或 4（alignment tab），导致 `tikzcd` 无法重置 catcode，报出致命错误 `Single ampersand used with wrong catcode`。
   - 正解：通过内部参数 `column sep`、`row sep` 与 `font` 进行版面紧凑化。
2. **绝对禁令：禁止在 `tikzcd` 单元格内嵌套 `tikzpicture`**：
   - 根因：路径构建上下文冲突，引发 `Giving up on this path` 崩溃。
   - 正解：单元格内的小双箭头、小符号改用纯数学构造，例如双箭头宏：
     ```latex
     \newcommand{\kmdual}{\mathrel{\overset{\pi}{\longrightarrow}\limits_{\underset{\lambda}{\longleftarrow}}}}
     ```
3. **原生 TikZ 跨行图外层缩放可行性**：
   - 与 `tikzcd` 不同，普通的 `tikzpicture` **完全支持**外层套 `\resizebox{\linewidth}{!}{...}`，前提是使用独立的 `\node` 坐标与贝塞尔 `to[...]` 路径。

---

## 5. 附录、校样后记与书签定位规范

1. **校样附注《Notes Added in Proof》独立成章**：
   - 正文结束后的后记说明，不可当作正文章节给章号；
   - 启用 `\backmatter`，使用 `\chapter*{Notes Added in Proof}`；
   - 环境使用无编号的 `theorem*` / `proposition*`，避免编号序列发生扰动。
2. **未编号章节的书签与目录锚点漂移（最关键避坑）**：
   - **症状**：点击 PDF 书签中的 "Notes Added in Proof" 或 "References"，阅读器跳转到了上一章最后一页末尾，而不是当前页顶端！
   - **根因**：直接调用 `\addcontentsline{toc}{chapter}{...}` 时，若上一章刚结束且当前页尚未输出任何可视垂直盒子，TeX 锚点 `\phantomsection` 仍吸附在上一个页面的底部。
   - **铁律修法**：所有未编号章节头必须强制先分页、后布锚点、再写入目录项：
     ```latex
     \clearpage
     \phantomsection
     \addcontentsline{toc}{chapter}{References}
     \printbibliography[heading=none]
     ```
3. **参考文献独立的顶级书签**：
   - 参考文献作为与正文大章同级的终审部分，在目录（TOC）与 PDF 书签中必须拥有**独立的一级条目**；
   - 书签名称与目录文本严格一致，指向参考文献首页顶端。
4. **biblatex 自定义 shorthand 避免重复缩写**：
   - 在 `.bib` 中为文献配置了 `shorthand = {Katz 1}` 时，`\cite` 命令会自动打印该 shorthand；
   - 正文中书写 `\cite[Theorem 2.1]{katz1}` 即可，**绝对不要**在 postnote 中重复写 `\cite[Katz 1, Theorem 2.1]{katz1}`，否则会输出难看的冗余重复 "Katz 1, Katz 1, Theorem 2.1"。

---

## 6. 自动化构建与 4-Pass 审计流水线

为确保上千个定理编号、二级公式编号与 52 篇参考文献在极限窄版心下绝对准确，构建链必须实行全自动化扫描验收：

```python
# tools/audit_log.py 核心架构
run_pass("xelatex -interaction=nonstopmode main.tex")
run_pass("biber main")
run_pass("xelatex -interaction=nonstopmode main.tex")
run_pass("xelatex -interaction=nonstopmode main.tex")

# 严苛扫描四项红线：
assert len(errors) == 0, "LaTeX errors detected"
assert len(undef_refs) == 0, "Undefined references detected"
assert len(undef_cits) == 0, "Undefined citations detected"
assert len(overfulls) == 0, "Overfull \\hbox detected"
```

凡改动 `.cls` 宏定义或目录结构后，必须执行 `rm -f main.toc` 再跑 4-Pass 构建，杜绝旧格式导致第一遍崩溃。
