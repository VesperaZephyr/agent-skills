# 通用期末考试助教 / exam-passing

把「从课件到考卷」的四个环节——课件解析、平时作业、期末复习讲义、模拟卷命制——固定成
可执行的规范与工具链。它**不是题库**，也不生成「七天速成」式的攻略：技能内不含任何课程
的教材索引、考纲或题目；课程名、教材、考试范围、题源一律由当前项目提供。

真正的重点是**复习讲义**。这一部分写得像一本数学书，而不是一份考前清单，具体由三条
互补的规范约束（红线、句法、文体），并由一套静态检查工具守住可机器判定的部分。

> 平台无关 Agent Skill：以 `SKILL.md` 为准，`README.md` 仅供人读。

## 它要治的四种病

让模型写复习讲义，默认产出几乎总是同样四种毛病，本技能逐条对应了机制：

| 症状 | 表现 | 对应机制 |
|---|---|---|
| **清单体** | 把知识切成「标签 + 公式」，配一堆「易错点 / 记忆要点 / 时间分配」 | `lecture_notes_spec.md` §3 语言红线 + `lecture_notes_audit.py` 的禁用词与全角标点检查 |
| **防御式** | 章首写方法论，逐题复验前提，退化先排除再铺垫，末尾加编者点评，提示框复述适用条件 | `lecture_notes_voice.md` 的直陈基准（前提一次原则、结论编号沉淀、末尾不复述） |
| **题不对位** | 同一个题写成好几道，同类题散落各处，练习没有解答，真题不标出处 | `lecture_notes_spec.md` §1.1 两层判据 + `lecture_notes_audit.py` 的 `source-duplicate` / `exam-source` |
| **超出教材** | 用教材没引入的概念去证教材的定理，或把教材没证的结论当已证引用 | `lecture_notes_spec.md` §2.0 / §2.0bis 教材原文优先与课本外工具三档边界 |

前两条决定「像不像一本书」，后两条决定「敢不敢拿去考试」。四者都是**成稿要求**，不是交付
后才发现再返工的补救项。

## 四项能力

| 能力 | 做什么 | 入口 |
|---|---|---|
| **课件解析** | 纯标准库解析 `.pptx`：段落内混排的 OMML 公式、Markdown 表格、按页导出公式截图 | `scripts/extract_pptx.py` |
| **平时作业** | 五环节作答：题目复述 → 前提与符号 → 逐步推导 → 求解计算 → 结果检验；按教材 OCR 检索原题 | `assets/homework_template.tex`、`scripts/homework_helper.py` |
| **复习讲义** | 考点式结构、教材原题配完整解答、三层验收、题源查重 | `references/lecture_notes_spec.md` 及同目录五个配套文件 |
| **模拟卷** | 双向细目表 → 卷面 → 分步评分细则 | `assets/mock_exam_template.tex`、`references/workflow_guide.md` |

## 三条质量线

规范不是一份文件管全部，而是三条各管一段，冲突时按 `voice` §8 裁决：

| 文件 | 管什么 | 性质 |
|---|---|---|
| `lecture_notes_spec.md` | 结构、内容、语言红线、版式、科目适配、验收清单 | **不可让步**：半角标点、零元话语、禁考试管理语言 |
| `writing_craft.md` | 句群承接、伪承接检查、主干搭配、逐命题限定、连续试读 | 正向方法：把句子写顺、把详略定对 |
| `lecture_notes_voice.md` | 证明切入即计算、前提一次、结论编号沉淀、提示框默认不用 | 文体基准：信息组织与详略 |

**合规不等于好读**。静态验收全绿之后仍须按 `voice` §9 连读一章——机器查得出全角标点和
禁用词，查不出「每段都在为没发生的质疑辩解」。

## 讲义规范的六条硬要求

1. **目录即考纲**。章节按考点、方法或研究对象命名，不照抄教材章名；末章固定为「必背公式
   与结论手册」，按「适用条件—公式／结论」编排，开头写明选用顺序。
2. **题目编排分两层**。题干相同、或同一实例的不同问法，属**同一个题**，删重复、合并成
   一道多问递进的例题，出处并列；差别只在数据而方法相同的，属**同类题**，不合并，按方法
   聚在同一小节相邻对照。判据只看「差别在表述还是数据」，不能用「方法相同」当合并理由。
3. **教材原文优先**。陈述照抄教材骨架（量词、限定条件、并列条款齐全）；证明只用教材用过
   的工具，在教材里出现 0 次的概念不得作为证明依据；教材有证明而讲义只给陈述的必须补；
   每条结论在标题标出教材编号。「内容正确」不等于「忠于原书」。
4. **例练就地配解**。每道 `exercise` 紧跟一份与例题同等规格的完整 `solution`，全书不设
   章末提示段；结论型习题（判定、性质、等价刻画）直接写成正文命题并标注题源。
5. **术语加粗，教材外内容降级**。`definition` 与首次引入处用 `\textbf{}`；教材没有的命名
   或更一般观点只进 `remark`，不占结论编号。
6. **真题双标注**。卷别与教材原题号／定理号并列；确无原题的写概念锚点，不虚构习题号。

## 工具链

六个脚本，全部**纯 Python 标准库**，不依赖第三方包；其中 `lecture_notes_audit.py` 与
`source_ledger.py` 共用同一套 `.tex` 解析核心，题源统计口径一致。

| 脚本 | 作用 | 是否需要 TeX |
|---|---|---|
| `extract_pptx.py` | 解析课件，导出大纲、表格与公式截图 | 否 |
| `homework_helper.py` | 按教材 OCR 检索课后题，生成作业骨架 | 否 |
| `lecture_notes_scaffold.py` | `init` 建讲义骨架、`backup` 时间戳备份、`add-chapter` 追加章 | 否 |
| `lecture_notes_audit.py` | 源码层静态验收（编码、例解配对、label、题源、红线、文体检查码） | 否 |
| `lecture_notes_build.py` | 多轮 XeLaTeX 编译、日志解析、`pdftotext` 与渲染抽样 | **是** |
| `source_ledger.py` | `init` 建题源台账、`scan` 统计标注覆盖率与重复出处 | 否 |

```bash
# 1 建题源台账
python scripts/source_ledger.py init --out 题源台账.md --course "某课程"

# 2 建讲义骨架（产出恒为 UTF-8 无 BOM + CRLF）
python scripts/lecture_notes_scaffold.py init --out 讲义.tex --course "某课程" --author "某某"

# 3 每章迭代：备份 -> 追加章骨架 -> 编译 -> 验收
python scripts/lecture_notes_scaffold.py backup 讲义.tex
python scripts/lecture_notes_scaffold.py add-chapter 讲义.tex --title "某考点" --sections "方法一,方法二"
python scripts/lecture_notes_build.py 讲义.tex --workdir /tmp/build --passes 3 --copy-back --render 1,20,40
python scripts/lecture_notes_audit.py 讲义.tex --strict

# 4 题源查重
python scripts/source_ledger.py scan 讲义.tex
```

`--workdir` 建议给一个 ASCII 路径：在 Windows 中文目录下直接跑 XeLaTeX，日志会报成功而 PDF
落到乱码文件名，是这套工具最先要绕开的坑。

## 三层验收

| 层 | 查什么 | 工具 |
|---|---|---|
| **源码** | 编码与行尾、`example`/`exercise` 与 `solution` 配对、label 与引用、题源标注覆盖与重复、禁用词、全角标点、斜杠错字、术语加粗、真题双标注 | `lecture_notes_audit.py --strict` |
| **日志** | 每轮 error / warning / undefined reference / Overfull / Underfull / Missing character / 页数 | `lecture_notes_build.py` |
| **视觉** | `pdftotext` 残留的 `??` 与字面斜杠命令；题框跨页、公式溢出、孤行 | `--render` + 逐页看图 |

三层的分工在 `lecture_notes_workflow.md` §5。**日志全绿不等于合格**：编译零警告而 PDF 是
错的那一类，只查日志与文本永远查不出来，必须渲染抽样页。

## 目录结构

```text
exam-passing/
├── SKILL.md
├── references/
│   ├── lecture_notes_spec.md       讲义撰写规范（结构/内容/语言/版式/科目适配/验收）
│   ├── lecture_notes_workflow.md   工程流程（输入清单、台账、分章九步、三层验收、失败模式）
│   ├── lecture_notes_revision.md   既有讲义复盘改造 SOP（九类反馈的判据与动作）
│   ├── lecture_notes_pitfalls.md   LaTeX 排错速查（按症状反查根因，19 类）
│   ├── lecture_notes_voice.md      直陈文体基准（防御式写法的症状与改写）
│   ├── writing_craft.md            中文叙述体写作方法（句群、限定、校对、试读）
│   └── workflow_guide.md           四条工作流的科目中立细则
├── scripts/
│   ├── extract_pptx.py             PPTX 解析（zipfile + ElementTree）
│   ├── homework_helper.py          教材检索 + 作业骨架
│   ├── lecture_notes_scaffold.py   init / backup / add-chapter
│   ├── lecture_notes_audit.py      源码层静态验收
│   ├── lecture_notes_build.py      编译与 PDF 验收
│   └── source_ledger.py            题源台账 init / scan
└── assets/
    ├── lecture_notes_template.tex  讲义骨架（tcolorbox 包装 amsthm、自定义 solution）
    ├── homework_template.tex       作业解答模板（五环节）
    ├── mock_exam_template.tex      模拟卷空白卷面
    └── source_ledger_template.md   题源台账模板
```

## 安装与调用

仓库内 `exam-passing/` 即技能目录，整个复制到 Agent 的技能路径即可：

```bash
git clone https://github.com/VesperaZephyr/agent-skills.git
cp -r agent-skills/exam-passing ~/.workbuddy/skills/     # WorkBuddy
```

其它支持「`SKILL.md` + `references/` + `scripts/`」加载机制的 Agent，放到各自的 skills
目录；也可以直接让模型先读 `exam-passing/SKILL.md`。支持 `$skill` 语法时用
`$exam-passing`。

```text
使用 $exam-passing 解析这三个课件，与本项目教材对照，列出考点与教师补充的结论。
```

```text
使用 $exam-passing 写一份期末复习讲义：先建题源台账，再按章迭代；
题目必须标出处，练习就地配完整解答。
```

```text
使用 $exam-passing 验收这份讲义，按源码、日志、视觉三层查，报告要能定位到行。
```

## 修订而不是重写

已有讲义没达到规范时，技能不主张推倒重来。`lecture_notes_revision.md` 按反馈类型给出
判据与动作：先做三项盘点（环境清单、题干清单、争议术语在教材中的出现次数），再分文本、
结构、收尾三层改造，最后四层验收并回写台账。搬动或删除环境前先备份，改完复查全部交叉
引用——删掉一个重复块，可能让保留块与紧邻命题变成同一结论，这类新邻接问题必须渲染确认。

## 规模参考

以 2026 年秋季一门抽象代数课的复习讲义为例（仅作规模参考，与技能绑定无关）：91 页，
159 个结论型环境全部带教材锚点，71 份解答（36 例题 + 35 练习），113 段证明，308 个 label
无重复无未定义，`lecture_notes_audit.py --strict` 报告 0 error / 0 warning（余两条 INFO 仅作定位提示）。

## 边界

- **不内置课程内容**。没有教材索引、考纲、题库；教材 OCR、作业、真题、课件都来自项目。
- **教材对齐依赖 OCR 质量**。用「教材里出现 0 次」判定概念越界，前提是 OCR 完整；OCR 缺页
  会让判据失真，须先核对文本层。
- **`lecture_notes_audit.py` 只查可机器判定的部分**。它给的是清单与定位，不是合格证。
- **编译层需要 TeX 环境**：XeLaTeX + ctex + tcolorbox + cleveref。只做静态验收与题源扫描
  时不需要 TeX。
- **讲义规范只约束讲义**。作业的五环节（逐条写边界、结果检验）不适用于讲义解答，反之
  亦然；两套规范相互独立。

## 许可

本技能采用 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) 许可，与仓库根
`LICENSE` 一致。转载、改写、商用均可，请保留出处与作者署名。
