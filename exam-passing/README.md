# exam-passing / 理工科期末考试助教

把「课件解析 → 平时作业 → 期末复习讲义 → 模拟卷」四个环节固定成可执行的规范与工具链。面向高校理工科期末备考（重点为数学、大学物理与推导类工科课程）。技能内**不含任何课程的教材、考纲或题库**：课程范围、教材 OCR、课件、历年真题一律由当前项目提供，技能只负责解析、撰写规范与验收。

重心是**复习讲义**：写成一本能读下来的书，而不是一份考前清单。以 `SKILL.md` 为准，本文件仅供人读。

> 平台无关 Agent Skill：支持 `SKILL.md` + `references/` + `scripts/` 加载机制的 Agent 均可使用。

---

## 这一版改了什么

2026-11-28 从跨科目通用版升级为**理工科定向版**，并补上两道机器验收关卡。

| 维度 | 上一版 | 现在 |
|---|---|---|
| **适用范围** | 任意高校课程 | 数学、大学物理、力学、电磁学、信号/控制/电路等推导与建模类课程；章名按考点/方法/物理模型命名 |
| **重点分级** | 核心结论必须高亮，但**不设配额**，容易满页暖色框 | 由**真题频次与枢纽作用**定级；每节 1–2 个高光，全篇 `keyconclusion` 占结论型环境 **≤ 45%**（`key-dilution` 检测） |
| **叙述动机** | 只强调「首段即计算」，容易被写成「天降神兵」 | 新增 `voice.md` §3.1：关键构造/换元/高斯面/参考系前用**半句话点出动机**，与防御性铺垫明确区分 |
| **题源台账** | 只记出处与覆盖率 | 新增「考点真题频次与重点分级」表，连续两年同位置题型独立成节；回忆版真题数据一律标「待核」 |
| **验收工具** | 静态审计 + 编译 + 视觉 | 前置 `normalize_tex.py`（标点/引号/行尾归一化），后置 `check_problem_fidelity.py`（题面汉字覆盖率 ≥ 0.95） |
| **文档布局** | `writing_craft.md` 为必读正向方法 | 其核心内容并入 `voice.md` §4.2 / §9，原件降为指针，**减少一份必读上下文** |

两类框容易混，务必分清：

- `\idea{}` **思路框**：实测效果不好，**已整体移除，不要补回**。动机改在推导首句的自然叙述中点出。
- `keyconclusion` / `\takeaway` / `\examtip` **重点结论框与记忆卡**：复习讲义的必备件，**必须配**。

---

## 五项成稿标准

1. **重点一眼可见，且由真题权重驱动**。按历年真题频次与考法画像定级：高频定理、物理定律、核心公式、判据与高区分度反例用 `keyconclusion`（暖色高光框，标题 `$\bigstar$ 核心结论`）；一般支撑命题用 `definition` / `proposition` / `lemma` 蓝色常规框。每节 1–2 个高光、全篇占比 ≤ 45%。记忆点与易混边界用 `\takeaway{具体标题}{内容}` / `\examtip{具体标题}{内容}` 一句话点透。核心结果 `\boxed{}` 收口，末章设「必背公式与结论手册」，开头配「题干特征 → 核心工具 → `\cref`」速查路由表。
2. **中文流畅、直陈不设防、关键构造点出动机**。正常使用「于是」「由此可见」「换句话说」「需要注意的是」「反过来」；引入复杂对象或物理模型先讲它在刻画什么再落符号。证明/求解首段直接切入计算或建立物理方程，退化与零情形压进括号；遇到非显然的辅助函数、换元、高斯面/积分路径或参考系选取，用**半句自然语言点出动机**。末尾不写编者点评、复述与复验。禁零元话语与备考管理语言。
3. **题面是引文**。前提、定义/物理条件句、坐标约定、`(1)(2)(3)` 分问编号、原问法一律照抄，不合并小问、不改问法；只允许排版符号转换（箭头向量改 `\vect{}`、全角标点改半角）。零元话语与删减判据**对题面一律不适用**。见 `voice.md` §3.3。
4. **题目就地配解**。目录按考点 / 方法 / 物理模型命名；同题合并成多问 `example`，同类题聚拢在同小节并配换参数变式 `exercise`；每道 `example` 与 `exercise` 紧跟一份完整 `solution`，出处写在环境可选参数里。
5. **版式与工程**。交付前经 `normalize_tex.py` 统一半角英文标点（顿号可留）、LaTeX 成对引号；源码 UTF-8 无 BOM + CRLF；XeLaTeX 三轮编译；几何与物理类（受力图、场线、光路、相图）配原生 TikZ/pgfplots 矢量图，禁用位图；连续排版，页眉固定文本。

---

## 它要治的五种病

| 症状 | 表现 | 对应机制 |
|---|---|---|
| **题面失真** | 丢了「不共面」「光滑无摩擦」这类前提，删了定义句，把 (1)(2) 压成一句 | `spec.md` §2 + `voice.md` §3.3 四类必留成分 + `check_problem_fidelity.py` 覆盖率比对 |
| **电报体 / 翻译腔** | 段落是「关键词: 公式」，正常衔接词被当成冗余删光 | `voice.md` §4.2 句群承接与公式参与承接 + `audit.py` 的 `telegraphic-list` 检测 |
| **重点抓不到 / 泛滥** | 全书命题共用一种蓝框，或满页暖色高光 | `spec.md` §1.2 真题权重分级 + `voice.md` §5 + `audit.py` 的 `key-dilution`（≤45%） |
| **防御式证明 / 天降神兵** | 章首写方法论、逐题复验前提，或关键构造毫无来由 | `voice.md` §3.1 动机半句 + §4 前提一次原则 + §9 人工连读 |
| **题不对位 / 超出教材** | 同题拆成几道，练习无解答，回忆版真题按「答案漂亮」反推 | `spec.md` §1.1 / §2 + `audit.py` 的 `source-*` 检查 + `answer_integrity.md` |

**合规不等于好读**。静态检查码清零只说明词面没问题；「这一段是不是在解释动机」「这一页到底要背哪条」「这张受力图会不会误导」只能靠人工连读与逐张渲染判断。

---

## 动笔前读什么

| 阶段 | 必读 | 不要读 |
|---|---|---|
| 写讲义 / 续写 / 改造 | `lecture_notes_spec.md`（结构、重点分级与红线）、`lecture_notes_voice.md`（直陈文体、一句话动机与流畅叙述） | — |
| 含推理 / 建模的解答 | 另读 `answer_integrity.md` 五条判据 | — |
| 分章迭代 / 多源整合 | `lecture_notes_workflow.md` | — |
| **遇到具体故障才查** | `lecture_notes_pitfalls.md`、`lecture_notes_revision.md` | 动笔前通读这两份会分散注意力、写成防御腔 |

规范冲突按一条链裁决：`spec.md §3 红线 > voice.md §8 冲突表 > 其余条款`。半角标点、零元话语、禁考试管理语言三条不让步（半角标点可先自然写中文，交付前由 `normalize_tex.py` 自动归一化）。

| 文件 | 管什么 |
|---|---|
| `references/lecture_notes_spec.md` | 结构、真题权重分级、内容忠实度、语言红线、理工科适配、验收清单（**不可让步**） |
| `references/lecture_notes_voice.md` | 直陈文体、一句话动机、句群承接、题面保真、原生矢量图、冲突裁决、人工连读 |
| `references/writing_craft.md` | 已并入 `voice.md` 的指针，无需单独加载 |
| `references/answer_integrity.md` | 论证与求解自足五条判据（含数理/物理/工科映射） |
| `references/lecture_notes_workflow.md` | 多源资料整合、分章迭代与三层验收 |
| `references/lecture_notes_pitfalls.md` / `lecture_notes_revision.md` | LaTeX 排错速查 / 既有讲义复盘改造 SOP, **按故障反查** |
| `references/workflow_guide.md` | PPTX、作业、模拟卷三条流程细则 |

---

## 四项能力与工具链

| 能力 | 做什么 | 入口 |
|---|---|---|
| 课件解析 | 纯标准库解析 `.pptx`: 段落内混排的 OMML 公式、Markdown 表格、按页导出公式截图 | `scripts/extract_pptx.py` |
| 平时作业 | 题目复述 → 前提/模型与符号 → 逐步推导 → 求解 → 量纲/极限/结果检验 | `assets/homework_template.tex`、`scripts/homework_helper.py` |
| 复习讲义 | 考点式结构、真题权重分级、原题照抄配完整解答、三层验收 | 上表规范 + `assets/lecture_notes_template.tex` |
| 模拟卷 | 双向细目表 → 卷面 → 分步骤评分细则 | `assets/mock_exam_template.tex`、`references/workflow_guide.md` |

八个脚本全部**纯 Python 标准库**，只有 `lecture_notes_build.py` 需要 TeX 环境。

| 脚本 | 作用 | 需要 TeX |
|---|---|---|
| `extract_pptx.py` | 课件大纲、表格、公式截图导出 | 否 |
| `homework_helper.py` | 按教材 OCR 检索课后题并生成作业骨架 | 否 |
| `lecture_notes_scaffold.py` | `init` 骨架 / `backup` 时间戳备份 / `add-chapter` 追加章 | 否 |
| `normalize_tex.py` | 正文半角标点与成对引号归一化、去 BOM、统一 CRLF，`--in-place` 前自动备份 | 否 |
| `check_problem_fidelity.py` | 题面汉字/数字覆盖率与原卷比对（默认阈值 0.95），支持 JSON 报告 | 否 |
| `lecture_notes_audit.py` | 源码层静态验收: 编码行尾、例解配对、label 与引用、题源、语言红线、重点密度、电报体、图示 | 否 |
| `lecture_notes_build.py` | 多轮 XeLaTeX、日志解析、`pdftotext` 与渲染抽样 | **是** |
| `source_ledger.py` | 题源台账 `init` / 覆盖率与重复出处 `scan` | 否 |

```bash
# 轻量直出：只有主题、课件或少量题源时，直接建骨架成章
python scripts/lecture_notes_scaffold.py init --out 讲义.tex --course "某课程"
python scripts/normalize_tex.py 讲义.tex --in-place
python scripts/lecture_notes_audit.py 讲义.tex --strict --ignore fullwidth-ideographic-comma
python scripts/lecture_notes_build.py 讲义.tex --passes 3 --copy-back --render 1,20,40

# 完整工程：先建题源台账，再按 workflow 分章迭代
python scripts/source_ledger.py init --out 题源台账.md --course "某课程"
python scripts/source_ledger.py scan 讲义.tex

# 题面保真抽核（题源可为教材 OCR、真题文本）
python scripts/check_problem_fidelity.py 讲义.tex --source 原卷.txt --json fidelity.json
```

三点实测提醒：

- `audit.py` 默认期望讲义为 CRLF；Linux 项目可加 `--eol lf`。仓库本身由 `.gitattributes` 统一为 LF 存储，与讲义产物的行尾要求是两回事。
- `--strict` 遇 WARN 即返回非零。顿号「、」在中文并列词语里规范允许，但会被记为 `fullwidth-ideographic-comma` WARN，人工复核后用 `--ignore` 显式放行（问题仍留在报告中）。
- Windows 中文目录下直接跑 XeLaTeX，日志会报成功而 PDF 落到乱码文件名；`--workdir` 建议给 ASCII 路径。

---

## 三层验收

| 层 | 查什么 | 工具 |
|---|---|---|
| **源码** | 编码与行尾、`example`/`exercise` 与 `solution` 配对、题源标注、语言红线、全角标点、重点密度、电报体、图示与位图 | `normalize_tex.py` + `lecture_notes_audit.py --strict` |
| **日志** | 每轮 error / warning / undefined reference / Overfull / Underfull / Missing character / 页数 | `lecture_notes_build.py` |
| **视觉 + 题面** | `pdftotext` 残留 `??`；题框跨页、公式溢出、高光框星号、示意图是否误导；题面汉字覆盖率与原卷一致 | `--render` + 逐页看图 + `check_problem_fidelity.py` |

**日志全绿不等于合格**。`audit.py` 只查可机器判定的部分；星号缺字符、二维投影画错、段落读起来像说明书、题面被悄悄改写，都必须渲染、比对与连读才能发现。

当前验收口径：模板三轮 XeLaTeX 0 error / 0 warning / 0 Overfull / 0 Underfull / **0 缺字符**；`keyconclusion` 用 `$\bigstar$` 而非字面 `★`（后者在 lmroman 下会缺字符）。

---

## 目录结构

```text
exam-passing/
├── SKILL.md                      技能入口: 加载路由 + 五项核心标准
├── README.md                     本文件（人读）
├── references/
│   ├── lecture_notes_spec.md      结构 / 真题权重分级 / 内容忠实 / 理工科适配 / 验收
│   ├── lecture_notes_voice.md     直陈文体 / 一句话动机 / 题面保真 / 矢量图 / 连读
│   ├── writing_craft.md           已并入 voice.md 的指针
│   ├── answer_integrity.md        论证自足五条判据
│   ├── lecture_notes_workflow.md  分章迭代与三层验收
│   ├── lecture_notes_pitfalls.md  LaTeX 排错速查（按故障反查）
│   ├── lecture_notes_revision.md  既有讲义复盘改造 SOP（按故障反查）
│   └── workflow_guide.md          课件 / 作业 / 模拟卷细则
├── scripts/
│   ├── extract_pptx.py            PPTX 解析（zipfile + ElementTree）
│   ├── homework_helper.py         教材检索 + 作业骨架
│   ├── lecture_notes_scaffold.py  init / backup / add-chapter
│   ├── normalize_tex.py           标点与引号归一化、编码/行尾后处理
│   ├── check_problem_fidelity.py  题面覆盖率机械比对
│   ├── lecture_notes_audit.py     源码层静态验收
│   ├── lecture_notes_build.py     编译与 PDF 验收
│   └── source_ledger.py           题源台账 init / scan
└── assets/
    ├── lecture_notes_template.tex 讲义骨架（高光框、takeaway/examtip、路由表、aliascnt、TikZ）
    ├── homework_template.tex      作业解答模板（五环节）
    ├── mock_exam_template.tex     模拟卷空白卷面
    └── source_ledger_template.md  题源台账模板（含真题频次与重点分级表）
```

---

## 安装与调用

```bash
git clone https://github.com/VesperaZephyr/agent-skills.git
cp -r agent-skills/exam-passing ~/.workbuddy/skills/     # WorkBuddy
```

只取一个技能、不下载整仓历史：

```bash
git clone --filter=blob:none --sparse https://github.com/VesperaZephyr/agent-skills.git
cd agent-skills && git sparse-checkout set exam-passing
```

放入对应 Agent 的 skills 目录即可；也可以直接让模型先读 `exam-passing/SKILL.md`。支持 `$skill` 语法时用 `$exam-passing`。

```text
使用 $exam-passing 解析这三个课件，与本项目教材对照，列出考点与教师补充的结论。
```

```text
使用 $exam-passing 写一份大学物理期末复习讲义：按真题频次分级重点，题面逐字照抄原卷，
高斯面的选取点出动机，练习就地配完整解答。
```

```text
使用 $exam-passing 验收这份讲义：先归一化标点，再按源码、日志、视觉三层查，
并抽核题面覆盖率，报告要能定位到行。
```

---

## 已验证产出（规模参考）

| 对象 | 结果 |
|---|---|
| 一份 39 页几何类复习讲义 | 20 例题 + 31 练习 + 51 解答 + 11 张原生 TikZ 图；49 道真题题面与原卷汉字覆盖率中位数 1.000；三轮 XeLaTeX 0 error / 0 warning / 0 Overfull / 0 未定义引用；静态验收 ERROR 0 |
| 技能自带模板 | 3 页, 编译全 0；单独做 `keyconclusion` 渲染探针, 星号完整显示、0 缺字符 |
| 静态检查回归 | 含全部正常衔接词的负例文本, 修订前 16 ERROR, 修订后 0 ERROR |

数据只用于说明规模与验收口径，技能本身不绑定任何课程。

---

## 边界

- **不内置课程内容**。教材 OCR、作业、真题、课件都由项目提供；教材对齐依赖 OCR 完整度。
- **`audit.py` 是清单，不是合格证**。题面是否被改写、文字是否好读、图形是否误导，只能人工比对与逐张渲染。
- **编译层需要 TeX 环境**：XeLaTeX + ctex + tcolorbox + cleveref。只做静态验收与题源扫描不需要 TeX。
- **两套规范相互独立**。作业的五环节（逐条写边界、结果检验）不适用于讲义解答，反之亦然。
- **思路框禁用**。`\idea{}` 已整体移除，旧稿残留只提示删除，不要迁移或补回；构造动机写进推导首句的自然叙述。
- **回忆版真题须先核**。矩阵元素、系数、初值、物理参量一律先标「待核」，经用户确认后再写入，严禁按「答案是否漂亮」反推题面。

---

## 许可

本技能采用 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) 许可，与仓库根 `LICENSE` 一致。转载、改写、商用均可，请保留出处与作者署名。
