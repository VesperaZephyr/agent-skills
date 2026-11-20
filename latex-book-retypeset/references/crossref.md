# 交叉引用补全：七轮递进策略

实战来源：Conway GTM 96 全书（436 页）。最终：1828 label 全局 0 重复、\ref/\eqref 1492 处、
PDF 内部跳转 1606 个、4 遍编译 0 错。坑位 A–E 见 `pitfalls.md` §8。

---

## 0. 开工前审计

1. 跑 `scripts/audit_text_refs.py` 扫全部章节，得「尚未 \ref 化的硬编码引用」清单，按
   `文件:行号 + 建议类型` 归类，作为各轮输入。
2. 编译一次，收集 `main.log` 的 `multiply defined` 清单（GTM96 实测 60 处）。
3. 确认计数器模型（共享 `gtmitem` 还是每环境独立），决定公式环境写法。

---

## 1. 规范化 label 命名（消除 multiply defined）

**根因**：早期章节 label 用 `kind:s.i`（无章号），同名 label 跨章重复（`def:1.1` 在四章各定义一次）。
**修法**：补章号前缀 → `kind:c.s.i`（thm/prop/lem/cor/def/ex/clm/eq : 章.节.项）；同步改写
对应 `\ref`/`\eqref`。结果：label 全局 **0 重复、0 未定义**。

附加 label：`sec:c.s`（一节一标题）、`exercise:c.s.i`（一节一题）。

---

## 2. 补缺失的 section / exercise label

- 节标题补 `sec:c.s`（Ch VII–X 原本已有，其余需补，共 58 个）。
- 习题 814 个 `exercise:c.s.i`：
  - 跨章 `Exercise~IV.1.16` → 直接匹配 `exercise:4.1.16`；
  - 章内裸编号 `Exercise N` → 用「引用点所属 \section」定位（唯一确定）；
  - 带节号提示 `Exercise~17 of Section~\ref{sec:4.1}` → 单独解析（round7）。
- 用 `scripts/rebuild_exercise_labels.py`（dry-run → 核对 → --apply）。

---

## 3. 正文纯文本引用 → \ref（七轮递进）

| 轮 | 类型 | 数量（实测） |
|---|---|---|
| round1 | 跨章 stmt / paren / sec / ex（含罗马前缀） | 320 |
| round2 | 章内括号 `(1.5)` / `\textup{(C.2)}`，不限 eq 类型 | 54 |
| round3 | `Section N` / `Exercise N` 跨章三段式 | 43 |
| round4 | 章内裸编号 `Exercise N`（按当前节定位） | 178 |
| round5 | 章内裸编号 `Lemma 1.4` 类 | 3 |
| round7 | `Exercise N of Section~\ref{}` | 2 |
| 追加 | 条目类型修正（Lemma→Proposition IV.3.2、Proposition→Theorem II.2.19、Example 2.11→2.2） | 3 |

**净效果**：\ref/\eqref 863 → 1492；PDF 内部跳转 515 → 1606。

每轮：抽匹配 → 生成「原文 → 替换后」映射表 → 抽看 5–10 条确认规则 → 批量替换 → 编译 1 遍查 `undefined`。
跨章引用务必带章号；章内裸编号靠「当前 \section」反查。

---

## 4. 条目类型修正（安全链接前提）

引用文字类型可能与我方 label 类型不符，但**内容一致**时可安全链接：
`Lemma IV.3.2` 实为 Proposition → `prop:4.3.2`；`Proposition II.2.19` 实为 Theorem → `thm:2.2.19`；
`Example 2.11` 实为 `Example 2.2` → `ex:2.2`。判定：回原书渲染该页核对条目标题与编号。

---

## 5. 保留为纯文本的 7 处（原书自身问题，不得改写）

| 位置 | 原文 | 判定依据 |
|---|---|---|
| appC | `(12.36)` | 外部文献 Hewitt–Stromberg 的定理号 |
| ch07 | `(V.6)` / `(V.7)` | 原书跨章公式旧编号体系，无对应 label |
| ch09 | `Corollary V.1.4` | 原书印刷如此；我方 `thm:5.1.4` 是 Theorem（类型不符），已回退 |
| ch09 | `Example 20.17` | 外部文献 Hewitt–Stromberg |
| ch09 | `Exercise XI.3.14` | 原书 XI.3 仅 8 题，无第 14 题 |
| ch11 | `Exercise IV.1.24` | 同上（已核实 `exercise:4.1.24` 存在但原书该处编号越界） |

纪律：**原书自身编号不一致处不擅自改写**，保留纯文本，写审计脚本确认数量稳定。

---

## 6. 习题 label 重建算法（安全模板）

见 `scripts/rebuild_exercise_labels.py`。核心：

1. **跟踪当前节**：扫描 `\label{sec:(\d+\.\d+)}` 记录当前 `c.s`（避免解析 LaTeX 计数器）。
2. **识别习题块**：`exercises` 环境；或前文含 `Exercises` 的 `\begin{enumerate}`（含
   `\noindent{...Exercises...}` 手工展开形态，坑 B）。
3. **计数规则**：块内深度 + 顺序计数，只给习题块自身 enumerate 深度的 `\item` 派发 label；
   嵌套 enumerate（子题 a/b/c）跳过。
4. **同行锚点**：`\item` 前同行有 `\gtmtarget{ixNNN}` → 插入为
   `\gtmtarget{ixNNN}\label{exercise:c.s.i}\item`（坑 A）。
5. **默认 dry-run**：打印 `file:line  exercise:c.s.i`；`--apply` 才写备份 + 改后副本。

---

## 7. 单卷裸编号书的三类额外对象

GTM 类之外，连续页码、小节内裸编号的专著（Samuel 类）还要补三类引用，详见
[`samuel-style-retypeset.md`](samuel-style-retypeset.md)：

1. **参考文献 [n]**：条目行 `\item[\textbf{[n]}] \phantomsection\label{bib:n}`，
   正文 `\hyperref[bib:n]{[n]}`（固定显示文本，不用 `\ref`）；外部著作自身的 Chapter 号保持纯文本。
2. **按章习题号**：`\exitem` 内 `\refstepcounter{exno}` + `\label{exer:章.n}`；
   每章 `\exchap` 重置，Review Problems 用 `R1/R2/R3` 前缀防重号。
3. **陈述内列表条目 (1)(2)**：`\item\label{prop:c.s.i}`；正文仍写
   `\hyperref[...]{(1)}`，因为 enumerate 的 `\ref` 不带括号。

另：裸引用扫描必须整段屏蔽 `\hyperref[...]{...}`（花括号配平），
否则已链接的 “Lemma 1” 会被全部误报为裸引用。

---

## 8. 裸编号书（Iversen 类）的链接化坑位与工具

小节裸编号、正文以「裸 sec.item」引用为主的书（无关键词、无括号），audit_text_refs.py
的规则表**不覆盖主引用体例**（其 stmt/eq 规则只抓带关键词的引用）。此类书的链接化：

1. **label 键清单驱动**：从 aux/chapters 提取全部 label 键（kind:C.S.I），建
   「裸编号 → label」映射；候选裸编号只在键清单命中时才替换——小数、坐标、
   单位（1.8em）、外部文献号天然被排除。
2. **尾随断言**：`(?![.\dA-Za-z])` 会系统性漏掉**句号结尾**的引用
   （"by Lemma 3.3."）——正解 `(?!\.?\d)(?![A-Za-z])`（挡小数续接与单位，放行孤立句号）。
   前缀断言照旧挡 `.` 与字母。
3. **tikz 几何整段屏蔽**：`\draw/\path/\node/\coordinate/\fill` 语句内的
   `ellipse (3.0 and 2.1)`、坐标 `(1.7,0.35)`、`at (-1.7,...)` 会恰好命中 label 键
   （Iversen 项目实测把椭圆半轴链到了 def:III.2.1）。链接器必须把
   `\+(?:draw|path|node|coordinate|fill|shade|clip)\b[^;]*;`（re.S）整段作为保护分支。
   注意 \draw 语句可跨行且含 `{}`，屏蔽须到最近的 `;`。
4. **文本 diff 查不出错链**：`\ref` 替换按设计保文本（\ref{def:III.2.1} 印 2.1 与
   原字面相同）——「对比 PDF 文本」对错目标无效。pgf 里拒收 \ref 会报错是运气；
   正解是几何屏蔽 + 编译 + 每轮「链接注释枚举 + 语义抽查」。
5. **前缀必须取文件原样字节**：批量替换的匹配前缀要含 `$X$`、`\textbf{...}` 等
   包装（语义等价的纯文本匹配不到，或匹配到错误位置）。
6. **CRLF**：生成器 CRLF 落盘时，替换模式一律 `(?:\r?\n)`；事后全库行尾再规范。

### label 名 ↔ 渲染号一致性核对（漏排/跳号/漂移的抓手）

手工编号书的 label 按原书编号命名（prop:IV.4.20）。**label 名尾号 ≠ 渲染号**即缺陷：
正文漏排一条（后续全部前移）、跳号未实现（后续全部后移）、计数器多步/少步。
用 `scripts/audit_label_numbers.py main.aux`（exit=1 on mismatch）：
- Iversen 项目实测抓出三簇：IV.8 偏 +1（4 处）、XI.2 偏 +2（6 处）、XI.3 偏 −1（6 处），
  并顺带抓出 IV.4 **漏排整条 Proposition 4.20**（书 225）——漏排本身任何 label 工具
  都看不见，但跳号错位是它的可观测信号。
- 每处错位需回原书渲染页裁决：label 名错（改名+改引用）、计数器多步/少步
  （删/补 \refstepcounter），或原书自身跳号（照录 + \addtocounter）。
- 打印的「name implies」是 label 名的数字尾段；name 含非数字段（IV.8 的章段）时
  对齐段数取 min(len(name), len(rendered))，逐一人工裁决。

### 实测裁决记录（Iversen 三簇，2026-11-21）

audit_label_numbers.py 首跑 16 处错位，逐簇回原书渲染页裁决，三种情形各得一例：

1. **计数器多步（IV.8，+1）**：Definition 8.1 环境内嵌 `iveq`（def 计一步、
   iveq 又计一步）。实测书 249：定义内公式**无页边号**。修法=内嵌公式改
   `\[...\]`，外层 label 名本来就对（8.2/8.3/8.4），无需改名。
2. **原书自身特殊编号（XI.2，+2）**：实测书 436/437：原书印页边号
   **2.6°、2.7°**（对偶式重复编号，随后正常回到 2.8）。修法=照录：
   `\begingroup\addtocounter{ivitem}{-2}\renewcommand{\theivitem}{...$^{\circ}$}`
   使两式印 2.6°/2.7°，同时 `\theHivitem` 局部改唯一串（11.2.6o/11.2.7o）
   防锚冲突；group 结束后计数器自然落在 7，后续 2.8 起全对。
3. **计数器少步（XI.3，−1）**：实测书 442：**Functoriality 3.4.** 是带编号
   陈述（名前号后），转录误排成普通 `\textbf{...}` 段落——不 \refstepcounter。
   修法=改 `stmt[Functoriality]{}` 环境（正文入环境、证明在外），渲染 3.4 ✓。

裁决要点：**错位方向即诊断线索**——rendered = name+k 为多步（找误编号的
环境/内嵌 display），rendered = name−k 为少步（找被降级为普通段落的编号
陈述），跨过错位点的书页边号序列对照即可定型。label 键名在多步情形往往
本来就对（勿盲目改名）；少步情形须补建缺的 label（stmt:XI.3.4）。

修复后复跑：926 compared, 0 mismatches；链接 1120 不变；357 页 0/0/0。
