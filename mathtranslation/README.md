# MathTranslation — 数学书中文 LaTeX 翻译与审校 Agent Skill

一个平台无关的严谨数学翻译技能：把数学书籍、论文、讲义或已有 LaTeX 项目
译为**可编译、可核对、可维护**的中文 LaTeX，并支持对照原书复核与修复现有译稿。

它不绑定任何模型、厂商或 Agent 框架。只要能读 Markdown 指令、能访问项目文件、
能执行 Python / XeLaTeX，就能用。

本项目的组织方式参考
[MathTranslations 数学翻译指南](https://mathtranslations.org/guide/)，
并经 MathTranslations 创始人及版权所有者授权，内置 MIT 许可的模板与 logo。
在线术语表保持外部引用，不在仓库内固定可能过期的数据。

---

## 能力总览

| 能力 | 说明 | 入口 |
|---|---|---|
| 翻译 | 以出版 PDF 为内容权威，保留定理/证明/公式/标签/引用/脚注/图表/层级 | `SKILL.md` → `references/workflow.md` |
| 审校与修复 | 中文、数学、编译版面三路分离校对；全稿证据驱动复核 | `references/review-checklist.md`、`references/forensic-review.md` |
| 编译与可视化验证 | `xelatex + biber + texindy` 五步构建，并从渲染 PDF 证明正确 | `references/build-verify.md`、`scripts/build_and_check.py` |
| 交叉引用 | `定理 3.4` / `(2.3)` / `见 3.25` / 索引页码 → `\ref` / `\eqref` / `\hyperpage` | `references/hardref.md`、`references/hardref-completeness.md` |
| 模板迁移 | 旧 ctexart 单文件模板 → `mathtranslation.cls` v3.1（ctexbook） | `references/cls-v31-upgrade.md` |
| 术语治理 | 已确定译名表（含人名对照）+ 疑点与命名边界 | `references/confirmed-terminology.md`、`references/terminology-exceptions.md` |
| 交换图 | 一律 `tikz-cd` 重绘，含逐边规格与独立复核 | `references/diagram-practice.md` |
| 插图 | 矢量优先、TikZ 重绘、最终页可读性判据 | `references/illustrations.md`、`references/figure-capture.md` |
| 法语文献 | 法语逻辑构造、前言/简历边界（résumé/préface 与译者新写前言的区分）、多卷术语对账 | `references/french-mathematics.md`、`references/french-calibration.json` |
| 独立审阅 | 译者/审阅者上下文隔离，避免自审闭环 | `references/independent-review.md` |

---

## 快速开始

### 安装

```bash
git clone git@github.com:VesperaZephyr/agent-skills.git
# 或
git clone https://github.com/VesperaZephyr/agent-skills.git
```

仓库内 `mathtranslation/` 即本技能目录。

### 接入方式

1. 把 `mathtranslation/` 复制到该 Agent 的 skills / rules / instructions 目录；
2. 在 Agent 配置中把本目录或 `SKILL.md` 注册为一个 skill；
3. 或在任务里直接要求 Agent 先读 `mathtranslation/SKILL.md`。

`agents/openai.yaml` 只是 OpenAI/Codex 客户端的可选界面元数据，其他 Agent 可以忽略。

### 调用示例

支持 `$skill-name` 语法的 Agent：

```text
使用 $mathtranslation 把这篇数学论文翻译成中文 LaTeX，并编译校对。
所有交换图、态射图和适合节点箭头表达的数学图必须使用 tikzcd 重绘，
不得使用截图代替。
```

不支持该语法的 Agent：

```text
请先读取 mathtranslation/SKILL.md，并严格按照其中的工作流，
把这篇数学论文翻译成中文 LaTeX，完成编译与校对。
```

审校已有译本：

```text
使用 $mathtranslation 对照原始 PDF 复核这个中文 LaTeX 项目，
修复引用、术语和排版问题，并给出证据说明哪些部分已真正逐句核对。
```

只做交叉引用补全：

```text
使用 $mathtranslation 把本项目里残留的硬编码编号引用
（定理 3.4、式 (2.3)、见 3.25、索引页码）全部转成可点击交叉引用，
并用 scripts/audit_bare_references.py 盘点后再逐条分类。
```

新建译本时只需提供：原书 PDF、MinerU Markdown、提取出的图片；
模板与 logo 从 `assets/` 复制，不要改动 `assets/` 内的母本。

---

## 核心纪律（红线）

- **内容权威是出版 PDF**，源 TeX 只用来恢复标记、减少转录错误；两者冲突时以 PDF 为准。
- 不擅自"修正"疑似原书错误：默认原样保留并记录，只在用户要求或有可靠证据时改。
- **不硬编码编号**：不得在正文手写定理/公式/章节/图/表/页码，一律 `\ref` 系命令。
- **不虚构**：缺的证明步骤、引用、定义、标签、图表一律标注未解决，不补写。
- 编译红线：**0 错误 / 0 未定义引用 / 0 缺字符 / 0 新增 overfull**。
- 编号正确性必须**从渲染 PDF 文本实抽**验证，不能只看退出码。
- 交换图、态射图、交换方块一律 `tikzcd` 重绘，**禁止截图代替**。
- 编译通过 ≠ 数学正确；脚本全绿 ≠ 覆盖完整。

---

## 工作流与参考文档

| 阶段 | 要做的事 | 对应文档 |
|---|---|---|
| 1. 建立事实基准 | 盘点 PDF / TeX / 文献 / 图 / 字体 / 模板 / 已有译文 | `SKILL.md`「Establish The Source Of Truth」 |
| 2. 准备项目 | 决定模板路线、建术语表、确定分章方式 | `references/workflow.md`、`references/mathtranslations-template.md` |
| 3. 译名对齐 | 查已定译名与例外，避免跨章漂移 | `references/confirmed-terminology.md`、`references/terminology-exceptions.md` |
| 4. 翻译 / 独立复核 | 译者与审阅者上下文隔离，各自独立清单 | `references/independent-review.md` |
| 5. 编译与渲染验证 | 五步构建 + PDF 逐页比对 + 编号实抽 | `references/build-verify.md` |
| 6. 交叉引用收敛 | 盘点 → 分类 → 转换 → 验证锚点 | `references/hardref.md`、`references/hardref-completeness.md` |
| 7. 完工审查 | 对照清单逐项确认，区分"已审/已修/已验证" | `references/review-checklist.md`、`references/forensic-review.md` |

法语文献在第 3、4 阶段前先读 `references/french-mathematics.md`：先盘点前言、简历、原作者
préface 与译者新写前言的边界，多卷项目按数学含义对账术语并保留未决项。
插图与交换图在动笔绘图前读 `references/diagram-practice.md` /
`references/illustrations.md` / `references/figure-capture.md`。

---

## 目录结构

```text
mathtranslation/
├── SKILL.md                         技能主文件（Agent 首先读这个）
├── README.md
├── LICENSE                          MIT
├── NOTICE.md
├── .gitattributes
├── .gitignore
├── agents/
│   └── openai.yaml                  可选：OpenAI/Codex 界面元数据
├── assets/
│   ├── mathtranslations-translation-template.tex   旧版单文件 ctexart 模板（legacy）
│   └── logo.pdf                     封面 logo（mathtranslation.cls 亦使用）
├── references/
│   ├── workflow.md                  新译本分阶段工作流
│   ├── latex-quality.md             TeX 编辑 / OCR / 引用修复质量规则
│   ├── mathtranslations-template.md mathtranslation.cls v3.x 模板说明（主路径）
│   ├── review-checklist.md          完工前审查清单
│   ├── forensic-review.md           全稿证据驱动审校标准
│   ├── independent-review.md        译者/审阅者上下文隔离与交接
│   ├── confirmed-terminology.md     已确定译名（含人名对照，约 2200 行）
│   ├── terminology-exceptions.md    术语疑点与命名边界
│   ├── build-verify.md              五步构建 + 渲染级验证完整配方
│   ├── hardref.md                   硬编码引用 → 可点击（cls 路径）
│   ├── hardref-completeness.md      引用完整性：防「编译通过但普遍漏链」
│   ├── cls-v31-upgrade.md           旧模板 → cls v3.1 迁移与回归审计
│   ├── diagram-practice.md          交换图规格、练习与独立复核
│   ├── illustrations.md             数学插图：来源保真与最终页可读性
│   ├── figure-capture.md            PDF 裁切 / 截图 / TikZ 重绘实操
│   ├── french-mathematics.md        法语数学文献翻译与校准
│   └── french-calibration.json      法语校准样例（源定位、可回归）
├── scripts/
│   ├── audit_latex.py               确定性审计（标签/引用/资源/模板 profile）
│   ├── build_and_check.py           五步构建驱动 + 结论报告
│   ├── audit_bare_references.py     裸编号引用盘点（只盘点，不改写）
│   ├── convert_hardrefs.py          cls 路径硬引用转换（dry-run / --apply）
│   ├── convert_bare_refs.py         book 类裸编号转换（dry-run / --go）
│   └── capture_pdf_region.py        PDF 区域导出 PDF+PNG+来源信息
└── tests/
    └── test_audit_latex.py          审计脚本单元测试
```

---

## 脚本参考

| 脚本 | 用途 | 是否写盘 |
|---|---|---|
| `scripts/audit_latex.py` | 确定性审计（标签 / 引用 / 资源 / 模板 profile） | 只读 |
| `scripts/build_and_check.py` | 五步构建 + 结论 | 只写 `_build_report.txt` |
| `scripts/audit_bare_references.py` | 裸编号引用盘点 | 只写 JSON 清单 |
| `scripts/convert_hardrefs.py` | cls 路径硬引用转换 | 默认 dry-run，`--apply` 写盘 |
| `scripts/convert_bare_refs.py` | book 类裸编号转换 | 默认 dry-run，`--go` 写盘 |
| `scripts/capture_pdf_region.py` | PDF 区域导出 + 来源信息 | 直接产出 PDF / PNG |

### `audit_latex.py` — 确定性审计

```bash
python scripts/audit_latex.py path/to/project
python scripts/audit_latex.py path/to/project --strict
python scripts/audit_latex.py path/to/project --profile mathtranslations --strict
```

检查重复标签、未定义引用、缺失资源、模板漂移、连续展示公式、全角弯引号、
手写编号列表、编译日志异常等。确定性错误返回非零；`--strict` 让警告也返回非零（适合 CI）。

`--profile mathtranslations` 额外检查：XeLaTeX 配置、模板元信息、字体与链接设置、
术语键、长证明配对、句末标点、行间公式环境、引号写法、列表环境、最终术语索引，
以及 `\makecover` / `\makecontents` / `\makebibliography` 调用与 biblatex 是否重复加载。

### `build_and_check.py` — 五步构建与结论

```bash
python scripts/build_and_check.py path/to/project   # 默认当前目录，须含 main.tex
```

执行 `xelatex → biber → xelatex → texindy(C locale) → xelatex`，
统计全部错误模式，写入 `_build_report.txt`，任何计数非零即退出非零。
**不传 `-output-directory`**（非 ASCII 路径下会失败），改为切换 cwd。

判读要点：看 build3（最后一轮）而非 build1；`-file-line-error` 让 `^! ` 单独不够，
要同时统计 `.tex:<行>:` 形式。

### `audit_bare_references.py` — 裸编号引用盘点

```bash
python scripts/audit_bare_references.py main.tex chapters/*.tex --output bare_refs.json
```

只产出候选清单（含 `(15)`、小数、列表、罗马数字章号、页码），**不改写源码**。
清单必须逐条分类后才能交给转换脚本；链接数增加不等于覆盖完整。

### `convert_hardrefs.py` — cls 路径转换

在脚本顶部按项目填写 `ROOT` / `PARTS` / 附录分段等常量后运行。
默认 dry-run，打印拟替换项；加 `--apply` 才写盘。

转换成立的条件是**唯一候选标签**同时满足：章节作用域正确 + 打印编号与 `main.aux`
一致 + 对象类型匹配。编号→标签映射必须从 `main.aux` 导出，不得手写。

### `convert_bare_refs.py` — book 类路径转换

适用于定理类环境共用一个计数器、标签形如 `thm:iv.4.1` 的书籍类（AJbook / ctexbook）。
需要在脚本顶部填 `BASE` / `FILES` / `CHAP_OF` / `HAND` / `EXACT`。默认 dry-run，`--go` 写盘。
无标签的手工编号项走 `\phantomsection\hypertarget` + `\hyperlink`，不要加 `\label`。

### `capture_pdf_region.py` — 区域导出

```bash
python scripts/capture_pdf_region.py book.pdf --page 42 --bbox 80 120 500 640 \
    --out figs/fig-3-1 --dpi 200
```

按物理页（1 起）或审阅过的 bbox 导出 PDF + PNG 及 provenance。
**生成了文件不等于做过视觉确认**，导出状态与审阅状态要分开记录。

---

## 术语约定（摘要）

- 中文行文写 **Abel 群 / Abel 范畴 / Abel 簇**，不写 Abelian 群或阿贝尔群；
  英文列、英文引文与文献标题保留 `abelian group/category/variety` 原形。
- 以下固定用姓氏形式：Lie 群／Lie 代数、Galois 群、Noether 环、Boole 代数、
  Euclid 空间、Riemann 度量、Banach 空间、Hilbert 空间、Lebesgue 积分、Fourier 变换。
- 人名译名（如「尼尔斯·亨里克·阿贝尔」）只用于传记/人名语境，不改变 `Abel 群`。
- 未在表内的术语不强行统一；先提出具体疑点，不把不确定的译法静默提升为定案。
- 用户当轮的显式指令优先于以上默认。

完整表在 `references/confirmed-terminology.md`，边界与未决项在
`references/terminology-exceptions.md`。

---

## 排版与图表约定

- 行间公式统一 `align` / `aligned` / `align*`；不得并排放多个 `\[ \]`。
- 有序列表用 `enumerate`，不手写编号。
- 中文双引号用 TeX 连字：开引号两个反引号，闭引号两个直撇号；不用 Unicode 弯引号。
- 图：`\begin{figure}[htbp] \centering ... \caption{...} \label{fig:...} \end{figure}`，
  `\caption` 必须在 `\label` 之前；`\caption` 内不得手写「图 3.1:」。
- 宽度优先用 `\linewidth` 比例，按最终标签字号、纵横比与可用页高决定，不强套固定区间。
- **不使用 `wrapfigure`**：中文（xeCJK）下环绕图会破坏行间公式、标题缩进并造成
  overfull；一律改为独立居中图，或并排 `minipage` + `\captionof`。
- 矢量清晰的原图优先裁切 PDF 复用；重绘用原生 TikZ/PGFPlots；
  **400 DPI PNG 是位图，不是无损矢量化**。
- 编辑 TeX、处理 OCR 歧义记号、修复引用结构时，先读
  `references/latex-quality.md`。

---

## 与 `mathtranslation.cls` 的关系

当前书籍项目实际使用的模板是 **`mathtranslation.cls`**（基于 ctexbook 的类文件，
由用户维护，**不在本仓库内捆绑**），与 `assets/` 里那份单文件 ctexart 模板同源但不同线。

- `references/mathtranslations-template.md` 以 `mathtranslation.cls` v3.x 为主路径，
  单文件 ctexart 模板仅作历史参考。
- 使用该类时按其公开接口：`\makecover`、`\frontmatter`、`\makecontents`、
  `\makebibliography`、`\printterminology`；构建用项目自带的 `tools/build.sh full`
  （xelatex ×2 → biber → xelatex ×2）。
- biblatex 由类文件按 `BibStyle` / `BibFile` 选项加载，因此只调 `\addbibresource`，
  **不要**再 `\usepackage{biblatex}`。
- `assets/` 中仍保留 `mathtranslations-translation-template.tex` 与 `logo.pdf`
  （封面 logo 仍被 `mathtranslation.cls` 使用）。

---

## 来源与边界

工作流依据 MathTranslations 公开指南整理，表述与实现独立完成。在线指南、术语资源与
模板可能更新，实际项目应以[指南页面](https://mathtranslations.org/guide/)当前版本为准。

模板配置核对过官方 `mathtranslations-translation-template.zip`（2026-08-23 版；
旧名 `MathTranslations-Template.c9598d4a8d56.zip` 为同一模板的早期发布）的实际 TeX
与示例 PDF。模板 TeX 与 logo 经版权所有者授权，作为本仓库 MIT 内容公开；
编译示例 PDF 未打包，因为运行技能不需要它。

**这个技能不替代领域知识与人工判断。** 编译成功、脚本全绿、清单打勾，
都不能证明数学内容正确、覆盖完整或链接指向正确目标；编号与引用必须从渲染 PDF 抽验。

---

## License

本仓库内容（含 `assets/mathtranslations-translation-template.tex` 与 `assets/logo.pdf`）
采用 MIT License。在线术语数据与原始数学作品仍受各自许可与版权约束。
