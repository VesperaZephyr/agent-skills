---
name: exam-passing
description: 面向理工科高校期末考试（重点面向数学、大学物理与推导类工科课程）的通用学业助教技能。支持 PPTX 课件解析、平时作业规范解答、期末复习讲义体系化编写（真题频次驱动重点分级、流畅中文直陈叙述与一句话动机、原题照抄配完整解答、必背公式与题干路由手册收口，配骨架/标点归一化/编译/静态验收/题源与题面保真脚本）、期末模拟卷与评分细则设计。
agent_created: true
license: CC-BY-4.0
---

# Exam-Passing 理工科期末考试助教技能

`exam-passing` 面向高校理工科期末备考（特别是数学、大学物理与推导类工科课程），提供从多源资料整合、平时作业求解，到期末复习讲义编写与模拟卷命制的工具链。课程范围、教材、课件与真题一律由当前项目提供，技能不绑定任何教材或课程。

---

## 动笔前读什么

| 阶段 | 必读 | 不要读 |
| :--- | :--- | :--- |
| 写讲义 / 续写 / 改造 | `references/lecture_notes_spec.md`（结构、重点分级与红线）、`references/lecture_notes_voice.md`（直陈文体、一句话动机与流畅叙述） | — |
| 含推理 / 建模的解答 | 另读 `references/answer_integrity.md` 五条判据 | — |
| 分章迭代 / 多源整合 | `references/lecture_notes_workflow.md` | — |
| **遇到具体故障才查** | `references/lecture_notes_pitfalls.md`、`references/lecture_notes_revision.md` | 动笔前不要通读：这两份是排错索引与复盘记录，先读完会分散注意力、写成防御腔 |

规范冲突裁决链：**spec §3 红线 > voice §8 冲突表 > 其余条款**。半角标点、零元话语、禁考试管理语言三条不让步（半角标点可先自然写中文，交付前由 `scripts/normalize_tex.py` 自动归一化）。

---

## 讲义五条核心标准

1. **重点一眼可见，且由真题权重驱动**:
   - 按历年真题频次与考法画像决定重点：高频调用的定理、物理定律、核心公式、判据与高区分度反例，用 `keyconclusion` 暖色高光框（标题 `$\bigstar$ 核心结论`）标出；一般支撑命题用 `definition` / `proposition` / `lemma` 蓝色常规框。**控制高光密度（每节 1–2 个，全篇核心结论占比不超过 45%）**，防止全篇高亮等于没重点。
   - 记忆点、适用近似与易混边界用 `\takeaway{具体标题}{内容}` 或 `\examtip{具体标题}{内容}` 一句话点透；不复述题设前提，不写「适用条件与关键前提」「如何验证」。
   - 核心结果用 `\boxed{}` 收口；末章设「必背公式与结论手册」，开头配一张「题干特征 → 核心工具 → `\cref`」速查路由表，正文按「适用条件—公式/结论」汇总。
2. **中文流畅、直陈不设防、关键构造点出动机**:
   - **正常使用**「于是」「由此可见」「换句话说」「需要注意的是」「反过来」等中文学术衔接词；引入复杂对象或物理模型时，先用一两句讲清它在刻画什么，再落严格符号。禁止「关键词: 公式」电报体。
   - **区分防御性铺垫与一句话动机**：证明/求解首段直接切入计算或建立物理方程，退化与零情形压进括号；但遇到非显然的辅助函数、换元、高斯面/积分路径或参考系选取时，用**半句自然数学/物理语言点出构造动机**，避免“天降神兵”。解答末尾不写编者点评、复述与复验。
   - 零元话语（「本讲义按……」「下列三问依次……」），禁考试管理语言（「先遮住答案」「时间分配」「避坑指南」）。
   - **题面是引文，不受删减判据约束**：前提与定义句、坐标/物理条件约定、`(1)(2)(3)` 分问编号、原问法一律照抄，只做排版符号转换（见 `voice.md` §3.3）。
3. **结构与题目**: 目录即考纲（按考点/方法/物理模型命名）；同一个题合并成多问 `example`，同类题聚拢在同小节并配换参数变式 `exercise`；**每道 `example` 与 `exercise` 必须紧跟完整 `solution`**，出处写在可选参数里。
4. **版式与工程**: 最终稿统一半角英文标点（顿号可留）、`\textbf{}` 强调、LaTeX 成对引号；UTF-8 无 BOM + CRLF；XeLaTeX 3 轮；几何与物理类（受力图、场线、光路、相图）配原生 TikZ 矢量图（禁用位图）；连续排版，不强制每章 `\clearpage`；页眉固定文本。
5. **交付验收**:
   ```bash
   python scripts/normalize_tex.py "<讲义.tex>" --in-place
   python scripts/lecture_notes_audit.py "<讲义.tex>" --strict
   python scripts/lecture_notes_build.py "<讲义.tex>" --passes 3 --copy-back
   ```
   静态检查清零不等于好读；另按 `voice.md` §9 连读一章，用 `check_problem_fidelity.py` 抽核题面，并逐张渲染图与高亮框，确认无 `??`、无溢出、无缺字符。

**思路框 `\idea{}` 已整体移除，不要补回。** 动机融在解答首句的自然叙述中，不用独立色块；重点结论框与思路框是两类东西，前者必须配，后者禁用。

---

## 工作流

| 场景 | 动作 |
| :--- | :--- |
| PPTX 课件 | `python scripts/extract_pptx.py <课件.pptx> -o <输出.md> --media <图片目录>`；公式与示意常为图片，导出后须识图补充 |
| 平时作业 | 按「题目复述 → 前提/模型与符号 → 逐步推导 → 求解 → 量纲/极限/结果检验」组织，套 `assets/homework_template.tex` |
| 讲义（轻量直出） | 只有主题 / 课件 / 少量题源时：`lecture_notes_scaffold.py init` 生成骨架，按上节五条直接成章，再跑 normalize + audit + build。**不要被繁琐流程卡死直出** |
| 讲义（完整工程） | 有全书 OCR + 历年真题 + 多章迭代时：先建 `source_ledger.py` 题源台账（含真题频次与重点分级），再按 `lecture_notes_workflow.md` 分章迭代、三层验收 |
| 模拟卷 | 先确认范围 / 题型 / 题量 / 分值 / 时长 → 双向细目表 → `assets/mock_exam_template.tex` → 分步骤评分细则 |

---

## 资源清单

| 路径 | 用途 |
| :--- | :--- |
| `references/lecture_notes_spec.md` | 结构、重点分级、内容忠实度、语言红线、理工科适配、验收清单 |
| `references/lecture_notes_voice.md` | 直陈文体、一句话动机、句群承接、题面保真、原生矢量图、冲突裁决、人工连读 |
| `references/answer_integrity.md` | 论证与求解自足五条判据（含数理/物理/工科映射） |
| `references/lecture_notes_workflow.md` | 多源资料整合、分章迭代与三层验收 |
| `references/lecture_notes_pitfalls.md` / `lecture_notes_revision.md` | **排错索引 / 复盘改造 SOP，遇到故障才查** |
| `references/workflow_guide.md` | PPTX、作业、模拟卷流程 |
| `assets/lecture_notes_template.tex` | 讲义骨架（含 `keyconclusion` 高光框、`\takeaway`/`\examtip`、路由表与 `aliascnt`） |
| `assets/source_ledger_template.md` | 题源台账模板（含真题频次与重点分级表） |
| `scripts/normalize_tex.py` | 标点半角化、引号规范化与编码/行尾后处理 |
| `scripts/lecture_notes_audit.py` | 源码层静态验收（编码、例解配对、题源、红线、重点密度、电报体与图示） |
| `scripts/check_problem_fidelity.py` | 讲义题面与原卷/原书的字符覆盖率机械比对 |
| `scripts/lecture_notes_build.py` / `scaffold.py` / `source_ledger.py` | 多轮编译、骨架生成、题源台账 |
