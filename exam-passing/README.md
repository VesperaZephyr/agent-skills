# exam-passing / 通用期末考试助教

把「课件解析 → 平时作业 → 期末复习讲义 → 模拟卷」四个环节固定成可执行的规范与工具链。技能内**不含任何课程的教材、考纲或题库**：课程范围、教材 OCR、课件、历年真题一律由当前项目提供，技能只负责解析、撰写规范与验收。

重心是**复习讲义**：写成一本能读下来的书，而不是一份考前清单。以 `SKILL.md` 为准，本文件仅供人读。

> 平台无关 Agent Skill：支持 `SKILL.md` + `references/` + `scripts/` 加载机制的 Agent 均可使用。

---

## 这一版改了什么

上一版把大量「避免踩坑」的禁令和历次复盘堆进必读路径，结果讲义写得畏手畏脚、干瘪生硬，重点也抓不到。2026-11-15 按三条根因做了方向修订：

| 根因 | 旧做法 | 现在 |
|---|---|---|
| **规则过载** | `SKILL.md` 12K 字符, 动笔前要求通读全部 `references/`（含排错表与历次复盘）, 注意力被"别踩坑"占满 | `SKILL.md` 6.5K 只做**加载路由**；`pitfalls` / `revision` 降级为"遇到具体故障才查"；冲突只按一条链裁决：`spec §3 > voice §8 > 其余` |
| **电报体** | 禁用词表与末尾复述正则收录「由此可见」「换句话说」「本章」「建议」等正常学术衔接词, Agent 读到"会被扫"就主动回避 | 从词表移出 9 个正常词, `tail-recap` 正则收窄为只抓机械复述与复验；`spec §3` 明确要求**正常使用中文衔接词** |
| **重点不可见** | 「提示框默认 0 个, 总数不超 5」, 所有命题共用蓝框, `tip-density` 按配额报警 | 核心结论**必须**用 `keyconclusion` 暖色高光框分级标出, **不设配额**；`audit` 改为 `key-emphasis`（INFO 只提示, 不判不达标） |

两类框容易混，务必分清：

- `\idea{}` **思路框**（题干与解答之间的题眼句）：实测效果不好，**已整体移除，不要补回**。
- `keyconclusion` / `\takeaway` **重点结论框与记忆卡**：复习讲义的必备件，**必须配**。

---

## 五项成稿标准

1. **重点一眼可见**。考场要直接调用的定理、公式、判据、重要反例结论用 `keyconclusion`（暖色高光框, 标题 `$\bigstar$ 核心结论`）；一般支撑命题用 `definition` / `proposition` / `lemma` 蓝色常规框, 两类框视觉必须不同。记忆点与适用边界用 `\takeaway{标题}{内容}` / `\examtip{...}` 一句话点透。核心结果 `\boxed{}` 收口, 末章「必背公式与结论手册」按「适用条件—公式/结论」汇总并用 `\cref` 串联。
2. **中文流畅, 直陈不设防**。正常使用「于是」「由此可见」「换句话说」「需要注意的是」「反过来」；引入复杂对象时先说它在刻画什么再落严格符号。证明首段即计算, 退化情形压进括号, 末尾不写编者点评与复验。不写「本讲义按……组织」的编写体例, 不写「记忆要点 / 避坑指南 / 时间分配」等备考管理语言。
3. **题面是引文**。前提与非退化条件、定义句与坐标约定、`(1)(2)(3)` 分问编号、原问法一律照抄, 不合并小问、不改问法；只允许符号转换（箭头向量改 `\vect{}`、全角标点改半角、独立公式改 `\[ \]`）。零元话语与删减判据**对题面一律不适用**。见 `voice.md` §3.3。
4. **题目就地配解**。目录按考点 / 方法命名；同题合并成多问 `example`, 同类题聚拢在同小节；每道 `example` 与 `exercise` 紧跟一份完整 `solution`, 出处写在环境可选参数里, 全书不设章末提示段。
5. **版式与工程**。半角英文标点（中文并列顿号可留）、术语 `\textbf{}`、LaTeX 成对引号；源码 UTF-8 无 BOM + CRLF；XeLaTeX 三轮编译；几何 / 空间类配原生 TikZ 矢量图, 禁用位图；连续排版, 页眉固定文本。

---

## 它要治的五种病

| 症状 | 表现 | 对应机制 |
|---|---|---|
| **题面失真** | 丢了「不共面」这类前提, 删了定义句, 把 (1)(2) 压成一句「证明……及……」 | `spec.md` §3 第 5 条 + `voice.md` §3.3 四类必留成分；**交付前逐题与原卷比结构** |
| **电报体 / 翻译腔** | 段落是「关键词: 公式」, 正常衔接词被当成冗余删光 | `spec.md` §3 第 1 条 + `writing_craft.md` 句群承接 + 衔接词已从静态检查放开 |
| **重点抓不到** | 全书命题共用一种蓝框, 复习时不知道该背哪条 | `spec.md` §3 第 4 条 + `voice.md` §5 / §6 + 模板 `keystyle` |
| **防御式证明** | 章首写方法论, 逐题复验前提, 退化先排除再铺垫, 末尾编者点评 | `voice.md` §3 / §4 前提一次原则 + §9 人工连读一章 |
| **题不对位 / 超出教材** | 同题拆成几道, 练习无解答, 用教材没引入的概念去证教材定理 | `spec.md` §1.1 与 §2.0 / §2.0bis + `audit.py` 的 `source-*` 检查 + `answer_integrity.md` |

**合规不等于好读**。静态检查码清零只说明词面没问题；「每段都在为没发生的质疑辩解」和「这一页要背什么」都只能靠人工连读与渲染判断。

---

## 动笔前读什么

| 阶段 | 必读 | 不要读 |
|---|---|---|
| 写讲义 / 续写 / 改造 | `lecture_notes_spec.md`（结构与红线）、`lecture_notes_voice.md`（文体、题面保真、图示）、`writing_craft.md`（句子怎样写顺） | — |
| 含推理的解答 | 另读 `answer_integrity.md` 五条自足性判据 | — |
| 分章迭代 / 三层验收 | `lecture_notes_workflow.md` | — |
| **遇到具体故障才查** | `lecture_notes_pitfalls.md`、`lecture_notes_revision.md` | 动笔前通读这两份会占满注意力, 写出来畏手畏脚 |

规范冲突按一条链裁决：`spec.md §3 红线 > voice.md §8 冲突表 > 其余条款`。半角标点、零元话语、禁考试管理语言三条不让步。

| 文件 | 管什么 |
|---|---|
| `references/lecture_notes_spec.md` | 结构、内容、语言红线、版式、验收清单（**不可让步**） |
| `references/lecture_notes_voice.md` | 直陈文体、前提一次、重点分级、题面是引文、原生矢量图、冲突裁决、人工连读 |
| `references/writing_craft.md` | 句群承接、逐命题限定、连续试读（正向句法方法） |
| `references/answer_integrity.md` | 答案集合完备、条件穷尽、自由度处理、推理可复核（语义层） |
| `references/lecture_notes_workflow.md` | 输入清单、题源台账、分章迭代、三层验收 |
| `references/lecture_notes_pitfalls.md` / `lecture_notes_revision.md` | LaTeX 排错速查 / 既有讲义复盘改造 SOP, **按故障反查** |
| `references/workflow_guide.md` | PPTX、作业、模拟卷三条流程的科目中立细则 |

---

## 四项能力与工具链

| 能力 | 做什么 | 入口 |
|---|---|---|
| 课件解析 | 纯标准库解析 `.pptx`: 段落内混排的 OMML 公式、Markdown 表格、按页导出公式截图 | `scripts/extract_pptx.py` |
| 平时作业 | 题目复述 → 前提与符号 → 逐步推导 → 求解 → 结果检验 | `assets/homework_template.tex`、`scripts/homework_helper.py` |
| 复习讲义 | 考点式结构、原题照抄配完整解答、重点分级、三层验收、题源查重 | 上表规范 + `assets/lecture_notes_template.tex` |
| 模拟卷 | 双向细目表 → 卷面 → 分步骤评分细则 | `assets/mock_exam_template.tex`、`references/workflow_guide.md` |

六个脚本全部**纯 Python 标准库**, 只有 `lecture_notes_build.py` 需要 TeX 环境。

| 脚本 | 作用 | 需要 TeX |
|---|---|---|
| `extract_pptx.py` | 课件大纲、表格、公式截图导出 | 否 |
| `homework_helper.py` | 按教材 OCR 检索课后题并生成作业骨架 | 否 |
| `lecture_notes_scaffold.py` | `init` 骨架 / `backup` 时间戳备份 / `add-chapter` 追加章 | 否 |
| `lecture_notes_audit.py` | 源码层静态验收: 编码行尾、例解配对、label 与引用、题源、语言红线、图示、重点分级 | 否 |
| `lecture_notes_build.py` | 多轮 XeLaTeX、日志解析、`pdftotext` 与渲染抽样 | **是** |
| `source_ledger.py` | 题源台账 `init` / 覆盖率与重复出处 `scan` | 否 |

```bash
# 轻量直出：只有主题、课件或少量题源时，直接建骨架成章，不必被完整流程卡住
python scripts/lecture_notes_scaffold.py init --out 讲义.tex --course "某课程"
python scripts/lecture_notes_audit.py 讲义.tex --strict --ignore fullwidth-ideographic-comma
python scripts/lecture_notes_build.py 讲义.tex --passes 3 --copy-back --render 1,20,40

# 完整工程：先建题源台账，再按 workflow 分章迭代
python scripts/source_ledger.py init --out 题源台账.md --course "某课程"
python scripts/source_ledger.py scan 讲义.tex
```

两点实测提醒：

- `audit.py` 默认期望讲义为 CRLF；Linux 项目可加 `--eol lf`。仓库本身由 `.gitattributes` 统一为 LF 存储, 与讲义产物的行尾要求是两回事。
- `--strict` 遇 WARN 即返回非零。顿号「、」在中文并列词语里规范允许, 但会被记为 `fullwidth-ideographic-comma` WARN, 人工复核后用 `--ignore` 显式放行（问题仍留在报告中）。
- Windows 中文目录下直接跑 XeLaTeX, 日志会报成功而 PDF 落到乱码文件名；`--workdir` 建议给 ASCII 路径。

---

## 三层验收

| 层 | 查什么 | 工具 |
|---|---|---|
| **源码** | 编码与行尾、`example`/`exercise` 与 `solution` 配对、label 与引用、题源标注与重复、语言红线、全角标点、图示与位图、重点分级提示 | `lecture_notes_audit.py --strict` |
| **日志** | 每轮 error / warning / undefined reference / Overfull / Underfull / Missing character / 页数 | `lecture_notes_build.py` |
| **视觉** | `pdftotext` 残留 `??`、字面斜杠命令；题框跨页、公式溢出、孤行、高光框星号、示意图是否误导 | `--render` + 逐页看图 |

**日志全绿不等于合格**。`audit.py` 只查可机器判定的部分：合并小问时字数几乎不减, 任何词面统计都查不出题面改写；星号缺字符、二维投影画错、段落读起来像说明书, 也都必须渲染与连读才能发现。

当前验收口径：模板两遍 XeLaTeX 0 error / 0 warning / 0 Overfull / 0 Underfull / **0 缺字符**；`keyconclusion` 用 `$\bigstar$` 而非字面 `★`（后者在 lmroman 下会缺字符）。

---

## 目录结构

```text
exam-passing/
├── SKILL.md                      技能入口: 加载路由 + 五项核心标准
├── README.md                     本文件（人读）
├── references/
│   ├── lecture_notes_spec.md      结构 / 内容 / 语言红线 / 版式 / 验收
│   ├── lecture_notes_voice.md     直陈文体 / 题面是引文 / 重点分级 / 图示 / 连读
│   ├── writing_craft.md           中文句群与连续试读
│   ├── answer_integrity.md        论证自足五条判据
│   ├── lecture_notes_workflow.md  分章迭代与三层验收
│   ├── lecture_notes_pitfalls.md  LaTeX 排错速查（按故障反查）
│   ├── lecture_notes_revision.md  既有讲义复盘改造 SOP（按故障反查）
│   └── workflow_guide.md          课件 / 作业 / 模拟卷细则
├── scripts/
│   ├── extract_pptx.py            PPTX 解析（zipfile + ElementTree）
│   ├── homework_helper.py         教材检索 + 作业骨架
│   ├── lecture_notes_scaffold.py  init / backup / add-chapter
│   ├── lecture_notes_audit.py     源码层静态验收
│   ├── lecture_notes_build.py     编译与 PDF 验收
│   └── source_ledger.py           题源台账 init / scan
└── assets/
    ├── lecture_notes_template.tex 讲义骨架（含 keyconclusion 高光框、aliascnt、TikZ 色板）
    ├── homework_template.tex      作业解答模板（五环节）
    ├── mock_exam_template.tex     模拟卷空白卷面
    └── source_ledger_template.md  题源台账模板
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
使用 $exam-passing 写一份期末复习讲义：题面逐字照抄原卷，核心结论用高光框标出，
练习就地配完整解答。
```

```text
使用 $exam-passing 验收这份讲义，按源码、日志、视觉三层查，报告要能定位到行。
```

---

## 已验证产出（规模参考）

| 对象 | 结果 |
|---|---|
| 一份 39 页几何类复习讲义 | 20 例题 + 31 练习 + 51 解答 + 11 张原生 TikZ 图；49 道真题题面与原卷汉字覆盖率中位数 1.000；三轮 XeLaTeX 0 error / 0 warning / 0 Overfull / 0 未定义引用；静态验收 ERROR 0（顿号 WARN 按规范放行, INFO 1 为重点分级提示） |
| 技能自带模板 | 3 页, 编译全 0；单独做 `keyconclusion` 渲染探针, 星号完整显示、0 缺字符 |
| 静态检查回归 | 含全部正常衔接词的负例文本, 修订前 16 ERROR, 修订后 0 ERROR |

数据只用于说明规模与验收口径, 技能本身不绑定任何课程。

---

## 边界

- **不内置课程内容**。教材 OCR、作业、真题、课件都由项目提供；教材对齐依赖 OCR 完整度。
- **`audit.py` 是清单, 不是合格证**。题面是否被改写、文字是否好读、图形是否误导, 只能人工比对与逐张渲染。
- **编译层需要 TeX 环境**：XeLaTeX + ctex + tcolorbox + cleveref。只做静态验收与题源扫描不需要 TeX。
- **两套规范相互独立**。作业的五环节（逐条写边界、结果检验）不适用于讲义解答, 反之亦然。
- **思路框禁用**。`\idea{}` 已从跨科目规范整体移除, 旧稿残留只提示删除, 不要迁移或补回。

---

## 许可

本技能采用 [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) 许可, 与仓库根 `LICENSE` 一致。转载、改写、商用均可, 请保留出处与作者署名。
