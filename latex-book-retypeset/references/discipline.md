# 纪律与速查：LaTeX 数学书重排

## 文档类 `gtm96.cls` 速查（Springer GTM 原版式范例）

- 版心 / 字体 / 页眉页脚：Springer GTM 原版式（正文 Times 9.7pt / 行距 12.0pt）。
- 统一计数器：`\newcounter{gtmitem}[section]`，`\thegtmitem = \arabic{section}.\arabic{gtmitem}`。
- 定理样式：`gtmplain`（斜体正文）/ `gtmdefinition`（正体正文），head 形如 `2.7 Theorem.`
- 编号环境：`theorem` `proposition` `lemma` `corollary` `definition` `example` `remark` `claim`。
- 无编号版本：`remark*` `claim*`。
- 编号公式：`gtmeq` 环境（`\refstepcounter{gtmitem}` + `\tag`，**推进计数器**）。
- 习题：`exercises` 环境（enumitem），`\item` 引用写作 `Exercise~N`。
- 运算符宏：`\Real` `\Imag` `\diam` `\dist` `\res` `\cis` `\ann` `\ran` `\id` `\adj` `\eset`。
- 封面：`\makegtmcover`。

## 原书页码映射

`物理页 = 书页 + offset`。GTM96 offset = 15：Book p.1 = Phys 16；p.63(III) = Phys 78；
p.99(IV) = Phys 114。先量出偏移，所有「回原书核对」按物理页定位。

## 文献区排印参数（易漏的细节）

原书**文献区比正文更小更密**：正文 9.7pt / 12.0pt；文献 9.2pt / **10.32pt**（≈0.947× 字号、0.86× 行距）。
`gtmbib` 设 `\fontsize{9.5}{10.3}\selectfont` 实测 9.46pt / 10.3pt，文献 6 页（与原书一致）。
若文献页数对不上，先查字号行距是否照搬了正文。

## 内容来源纪律

- **以原书 PDF 图像为准**，OCR 底稿只用于定位章节边界与条目清单。
- 公式、花体字母、 Claim 编号等一切易错处，必须 `get_pixmap(clip=...)` 渲染原书对应页目视确认。
- 原书自身编号不一致处（外部文献号、跨章旧编号、印刷越界）**保留纯文本，不擅自改写**。

## 工程流水分层

GTM96 的源头闭环：**只改 `tools/make_chNN_secM.py` 生成器 → 片段 → assemble → `chapters/chNN.tex`
→ `_test_chNN.tex` → `main.tex`（3-pass xelatex）**。绝不直接手改 `chapters/*.tex`，
否则下次 assemble 会被覆盖。改内容纪律优先于一切便捷修改。
