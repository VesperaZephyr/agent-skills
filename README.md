# agent-skills

一组面向**数学文档处理**与**课程备考**的 Agent 技能。每个目录是一个独立技能，遵循通用约定
`SKILL.md` + `references/` + `scripts/`，不绑定任何特定的 Agent 运行时——WorkBuddy、Codex、
Claude Code 或任何支持该加载机制的 Agent 都能直接用。

这里放的是**方法论 + 可执行工具**，不是提示词合集。每个技能都带着自己的验收门槛、坑位表
和脚本，且这些内容来自实际交付中踩过的错，不是凭想象罗列的最佳实践。

## 技能清单

### 一、数学书 LaTeX：重排 / 翻译 / 审计

对数学专著做高保真重排与中文翻译，并配套一组「对照原书逐页核对」的专项审计技能。两个主控
技能（重排、翻译）之下挂多个审计子技能，构成闭环。

| 技能 | 做什么 | 典型触发 |
|---|---|---|
| **`latex-book-retypeset`** | 数学书**重排**（re-typeset，不翻译）：GTM 类西文书、中文书、分章页码专著、单卷裸编号专著四类原书的工程方法与坑位库 | 「重排这本书」「把 PDF 排成 LaTeX」「修 overfull」「补交叉引用」 |
| **`mathtranslation`** | 数学书 / 论文 / 讲义的中文 LaTeX **翻译与审校**：以原书 PDF 为内容权威，含编译可视化验证与硬编码引用转链接 | 「翻译这本书」「审校译稿」「修译稿的引用」 |
| **`latex-eq-numbering-audit`** | 对照原书逐节核对**公式编号**并直接修复：标签与渲染号矛盾、编号公式被压成行内、罗马数字误成阿拉伯数字 | 「公式编号与原书不一致」 |
| **`latex-display-layout-audit`** | 修正**行间公式的怪异版面**且不动任何编号：过拆、假对齐、嵌套显示环境、连续单行堆叠 | 「公式被拆得太碎」「对齐方式不对」 |
| **`latex-footnote-fidelity-audit`** | 确保 OCR 记录的**每个脚注都落到 PDF 上**：怪异脚注记号、正文缺失、位置异常、连带丢失的索引条目 | 「脚注丢了」「脚注号不对」 |
| **`latex-ocr-math-defect-audit`** | 修 OCR 在抵达 LaTeX **之前**就破坏的数学：积分被吞进指数、积分域下标丢失、集合括号错位、微分跑到数学环境外 | 「OCR 把公式弄错了」 |
| **`latex-array-diagram-audit`** | 绘制与审校交换图、态射图、正合列网格（`tikzcd`），含藏在 `array`/`matrix` 里的图 | 「交换图不对」「画个交换图」 |
| **`latex-bookmark-anchor-audit`** | 修 LaTeX 文档的**书签与目录超链点错位置**：星号标题无锚点、`\phantomsection` 顺序偏移、`.toc` 借用锚点 | 「书签跳错页」「目录点进去不对」 |
| **`latex-translation-fidelity-audit`** | 译稿**保真度三段审查**：结构性缺失 → 模式扫描（算子宏、哥特字母、残留英文）→ 原书 PDF ↔ OCR ↔ 译稿逐段比对 | 「检查译文有没有漏译」 |

### 二、PDF 处理

| 技能 | 做什么 | 典型触发 |
|---|---|---|
| **`pdf`** | 通用 PDF 读写、渲染与验证，含可填表单（AcroForm）的字段提取与填写 | 「读这个 PDF」「生成一份 PDF」「填表单」 |
| **`pdf-image-text-extractor`** | 从图片或 PDF 提取文字，**零额外依赖**：扫描页渲染成图交视觉识别，表格用 `find_tables` 结构化 | 「提取这个 PDF 的文字」「识别这张图」 |
| **`pdf-scanned-ocr-bookmark`** | 给纯扫描（无文字层）PDF 加**可搜索隐藏文本层**（离线 OCR），并据识别文本重建书签树 | 「扫描件不能搜索」「批量 OCR 加目录」 |
| **`math-pdf-bookmark`** | 批量给数学 PDF 加**精确书签**：跳到标题的 y 坐标而非页顶；有文字层走 span 几何，纯扫描走 OCR | 「给这个文件夹的 PDF 加书签」 |

### 三、学业与备考

| 技能 | 做什么 | 典型触发 |
|---|---|---|
| **`exam-passing`** | 通用期末考试助教：课件解析 → 平时作业规范作答 → 期末复习讲义体系化编写 → 模拟卷与评分细则；内含跨科目通用的讲义撰写规范与六个纯标准库脚本 | 「写一份期末复习讲义」「验收这份讲义」「出套模拟卷」 |

`exam-passing` 是本仓库唯一不面向「文档本身」、而面向「课程内容」的技能。它同样不含任何
具体课程的教材与题库：教材 OCR、作业、真题、课件都由当前项目提供。

## 目录

```text
agent-skills/
├── latex-book-retypeset/            重排主控
├── mathtranslation/                 翻译主控
├── latex-eq-numbering-audit/        公式编号
├── latex-display-layout-audit/      行间公式版面
├── latex-footnote-fidelity-audit/   脚注保真
├── latex-ocr-math-defect-audit/     OCR 数学缺陷
├── latex-array-diagram-audit/       交换图与图表
├── latex-bookmark-anchor-audit/     书签与目录锚点
├── latex-translation-fidelity-audit/ 翻译保真度
├── pdf/                             通用 PDF 处理
├── pdf-image-text-extractor/        图片 / PDF 文字提取
├── pdf-scanned-ocr-bookmark/        扫描件 OCR + 书签
├── math-pdf-bookmark/               数学 PDF 批量精确书签
└── exam-passing/                    课程备考
```

## 快速开始

```bash
# 取全部
git clone https://github.com/VesperaZephyr/agent-skills.git
cp -r agent-skills/latex-book-retypeset ~/.workbuddy/skills/

# 只取一个（不下载整仓历史）
git clone --filter=blob:none --sparse https://github.com/VesperaZephyr/agent-skills.git
cd agent-skills && git sparse-checkout set exam-passing
```

| Agent | 技能目录 |
|---|---|
| WorkBuddy | `~/.workbuddy/skills/<skill-name>/` |
| Claude Code / Codex | 各自的 skills 路径 |
| 其它 | 任意目录，让模型先读该技能的 `SKILL.md` |

加载后，Agent 依据 `SKILL.md` frontmatter 里的 `description` 判断何时调用；也可以在对话里
直接说「使用 `<skill-name>`」。

## 一个技能里有什么

```text
<skill-name>/
├── SKILL.md          入口。frontmatter 的 name / description 决定何时被触发
├── README.md         给人读的说明：定位、能力、结构、边界（不参与触发）
├── references/       方法论文档：规范、流程、坑位表、术语与对照策略
├── scripts/          可复现的脚本，多数只用 Python 标准库
└── assets/           模板与骨架（部分技能有）
```

`SKILL.md` 正文写的是**工作流与红线**：先做什么、按什么顺序、哪些绝对不许做、如何验收。
细节展开到 `references/`，可机器判定的部分交给 `scripts/`。这样拆分的好处是：Agent 只在
需要时读对应的参考文档，不必把几万字规范一次性塞进上下文。

## 这个仓库的偏好

- **先看渲染结果，再下结论**。`pdftotext` 干净、编译零警告，都不代表 PDF 是对的。
- **验收门槛写死成数字**：0 错误、0 缺字符、0 未定义引用、无新增 overfull、0 `??`。不写
  「尽量」「尽可能」。
- **坑位表来自实际失败**。每条坑都记了症状、根因、修复方式和「在哪一层能发现它」。
- **脚本优先纯标准库**。能离线跑、能在受限环境跑，比少写几行代码重要。
- **重复的内容合并，相似的内容对照**。这条既是讲义规范，也是这些技能自身的组织方式。

## 许可

除下表列出的例外，本仓库内容采用
[Creative Commons Attribution 4.0 International（CC BY 4.0）](https://creativecommons.org/licenses/by/4.0/)
许可：可复制、改编、商用，须保留署名与出处说明。完整条款见根目录 [`LICENSE`](LICENSE)。

| 目录 | 许可 | 说明 |
|---|---|---|
| `mathtranslation/` | MIT | 其模板与 logo 由 MathTranslations 创始人授权以 MIT 分发，见该目录 `NOTICE.md` |
| `pdf/` | Proprietary | 第三方分发的技能包，`SKILL.md` frontmatter 声明为专有许可；本仓库不作为著作权人重新许可 |

引用、改编上述两个目录的内容时，请遵循其自身条款。

## 反馈

各技能的 `README.md` 末尾写了边界与已知限制。发现某个技能在特定场景失效，最有用的反馈是
带上最小复现：输入文件类型、Agent 运行环境、失败时的日志或渲染页。方法论层面的问题（某条
规范在别的学科不成立）同样欢迎，但请附上反例。
