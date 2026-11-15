---
name: exam-passing
description: 面向任意高校期末考试的通用学业助教技能。支持 PPTX 课件解析、平时作业规范解答、期末复习讲义体系化编写（考点式目录、流畅中文直陈叙述、核心结论醒目标注、原题照抄配完整解答、必背公式手册收口，配骨架/编译/静态验收/题源脚本）、期末模拟卷与评分细则设计。适用于数学、物理、计算机、经管、工科等各类课程。
agent_created: true
license: CC-BY-4.0
---

# Exam-Passing 通用期末考试助教技能

`exam-passing` 面向任意高校课程的期末备考，提供从课件解析、平时作业求解，到期末复习讲义编写与模拟卷命制的工具链。课程范围、教材、课件与真题一律由当前项目提供，技能不绑定任何教材或课程。

---

## 动笔前读什么

| 阶段 | 必读 | 不要读 |
| :--- | :--- | :--- |
| 写讲义 / 续写 / 改造 | `references/lecture_notes_spec.md`（结构与红线）、`references/lecture_notes_voice.md`（文体与详略）、`references/writing_craft.md`（句子怎样写顺） | — |
| 含推理的解答 | 另读 `references/answer_integrity.md` 五条判据 | — |
| 分章迭代 / 三层验收 | `references/lecture_notes_workflow.md` | — |
| **遇到具体故障才查** | `references/lecture_notes_pitfalls.md`、`references/lecture_notes_revision.md` | 动笔前不要通读：这两份是排错索引与历次复盘，先读完会让注意力全被「别踩坑」占满，写出来畏手畏脚 |

规范之间冲突时只按一条链裁决：**spec §3 红线 > voice §8 冲突表 > 其余条款**。半角标点、零元话语、禁考试管理语言三条不让步。

---

## 讲义五条核心标准

1. **重点必须一眼可见**（复习讲义与普通教材的区别）:
   - 考场要直接调用或记忆的定理、公式、判据、重要反例结论，用 `keyconclusion` 环境（暖色高光框，标题 `$\bigstar$ 核心结论`）标出；一般支撑命题用 `definition` / `proposition` / `lemma`（蓝色常规框）。**两类框必须视觉不同**，否则扫读时抓不到要记什么。
   - 记忆点与适用边界用 `\takeaway{标题}{内容}` 或 `\examtip{...}` 一句话点透，标题具体，不复述题设前提、不写「如何验证」。
   - 核心结果用 `\boxed{}` 收口；末章设「必背公式与结论手册」按「适用条件—公式/结论」汇总，用 `\cref` 串联编号结论。
2. **中文流畅、直陈不设防**:
   - **正常使用**「于是」「由此可见」「换句话说」「需要注意的是」「反过来」等中文学术衔接词；引入复杂对象时先讲一两句它在刻画什么，再落严格符号。不写「关键词: 公式」电报体，也不为追求简短把必要的过渡删成翻译腔。
   - 证明首段即计算，退化与零情形压进括号；解答末尾不写编者点评、复述与复验；前提按一次原则写在结论陈述里。
   - 不写编者说明书腔（「本讲义按……」「下列三问依次……」），不写备考管理语言（「先遮住答案」「时间分配」「避坑指南」）。
   - **题面是引文，不受任何删减判据约束**：前提与定义句、坐标约定、`(1)(2)(3)` 分问编号、原问法一律照抄，只做符号转换（箭头向量改 `\vect{}`、全角标点改半角）。细节见 `voice.md` §3.3。
3. **结构与题目**: 目录即考纲（按考点/方法命名）；同题合并成多问 `example`，同类题聚拢在同小节并配变式 `exercise`；**每道 `example` 与 `exercise` 必须紧跟完整 `solution`**，出处写在可选参数里。
4. **版式与工程**: 半角英文标点（顿号可留）、`\textbf{}` 强调、LaTeX 成对引号；UTF-8 无 BOM + CRLF；XeLaTeX 3 轮；几何类配原生 TikZ 矢量图（禁用位图）；连续排版，不强制每章 `\clearpage`；页眉固定文本。
5. **交付验收**:
   ```bash
   python scripts/lecture_notes_audit.py "<讲义.tex>" --strict
   python scripts/lecture_notes_build.py "<讲义.tex>" --passes 3 --copy-back
   ```
   词面检查码只用于定位，清零不等于好读；另按 `voice.md` §9 连读一章，逐张渲染图与高亮框，确认无 `??`、无溢出、无缺字符。

**思路框 `\idea{}` 已于 2026-11-11 整体移除，不要补回。** 重点结论框与思路框是两类东西，前者必须配，后者禁用。

---

## 工作流

| 场景 | 动作 |
| :--- | :--- |
| PPTX 课件 | `python scripts/extract_pptx.py <课件.pptx> -o <输出.md> --media <图片目录>`；公式常为图片，导出后须识图补充 |
| 平时作业 | 按「题目复述 → 前提与符号 → 逐步推导 → 求解 → 结果检验」组织，套 `assets/homework_template.tex` |
| 讲义（轻量直出） | 只有主题 / 课件 / 少量题源时：`lecture_notes_scaffold.py init` 生成骨架，按上节五条直接成章，再跑 audit 与 build。**不要被繁琐流程卡死直出** |
| 讲义（完整工程） | 有全书 OCR + 历年真题 + 多章迭代时：先建 `source_ledger.py` 题源台账，再按 `lecture_notes_workflow.md` 分章迭代、三层验收 |
| 模拟卷 | 先确认范围 / 题型 / 题量 / 分值 / 时长 → 双向细目表 → `assets/mock_exam_template.tex` → 分步骤评分细则 |

---

## 资源清单

| 路径 | 用途 |
| :--- | :--- |
| `references/lecture_notes_spec.md` | 结构、内容、语言红线、版式、验收清单 |
| `references/lecture_notes_voice.md` | 直陈文体基准、题面是引文、原生矢量图、冲突裁决、人工连读 |
| `references/writing_craft.md` | 句群承接、逐命题限定、连续试读 |
| `references/answer_integrity.md` | 论证自足五条判据 |
| `references/lecture_notes_workflow.md` | 分章迭代与三层验收 |
| `references/lecture_notes_pitfalls.md` / `lecture_notes_revision.md` | **排错索引 / 历次复盘，遇到故障才查** |
| `references/workflow_guide.md` | PPTX、作业、模拟卷流程 |
| `assets/lecture_notes_template.tex` | 讲义骨架（含 keyconclusion 高光框与 aliascnt 写法） |
| `scripts/lecture_notes_audit.py` | 源码层静态验收（编码行尾、例解配对、题源、红线、图示） |
| `scripts/lecture_notes_build.py` / `scaffold.py` / `source_ledger.py` | 多轮编译、骨架生成、题源台账 |
