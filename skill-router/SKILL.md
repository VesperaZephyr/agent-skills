---
name: skill-router
description: >
  Local skill library router / table of contents for this WorkBuddy workspace.
  Use it as the single entry point when a task could match any bundled skill and you
  need to pick the right one, or when the user asks "which skill should I use" /
  wants an overview of available capabilities. Covers math-book LaTeX re-typeset &
  translation & fidelity audit, PDF read/extract/OCR/bookmark, Office docx/xlsx/pptx
  generation & editing, Windows shell-extension / orphan-entry cleanup, AstrBot plugin
  deploy, exam-prep assistance, and web access. Each listed skill remains
  independently invocable by name; this router only routes and does not duplicate
  their logic.
metadata:
  agent_created: true
---

# 本地 Skill 路由总览（skill-router）

本 workspace 的 skill 按领域归为四类。遇到具体任务时，先在本表定位**最匹配的子 skill**，
直接调用它；子 skill 各自独立、可单独触发，本路由只做"指路"，不重复实现逻辑。

> 设计原则：轻量索引、不删目录、不改现有 skill。若某任务明显落在某子 skill 范围内，
> 优先直接加载该子 skill，而非经由本路由二次跳转。

## 一、数学书 LaTeX（重排 / 翻译 / 审计）

| Skill | 一句话用途 | 何时调用（触发词） |
|---|---|---|
| `latex-book-retypeset` | 数学书**高保真重排**（不翻译）主控：Springer GTM / 中文书 / 分章页码 / 单卷裸编号四类版式的纪律、坑位、交叉引用、验收与终检脚本 | "重排某书""排成 LaTeX""补交叉引用""修 overfull""公式编号错位""OCR 乱码" |
| `mathtranslation` | 数学书 **LaTeX 翻译（中文化）** 主控：翻译纪律、术语、构建（xelatex/biber）与视觉验证 | "翻译某书""中文化排版""mathtranslation 项目" |
| `latex-eq-numbering-audit` | 对照原书**逐条核对公式编号**（多源投票法：构建/几何 OCR/MinerU/原书文本层） | "公式编号对不上原书""标签与渲染号矛盾""章节开头计数器未重置" |
| `latex-display-layout-audit` | 行间公式**版式审计**：over-wrap、假对齐、连字符/间距异常 | "行间公式排版怪""对齐看起来不对" |
| `latex-footnote-fidelity-audit` | **脚注保真审计**：脚注是否全部落地、文本是否完整 | "脚注丢了""脚注内容不全" |
| `latex-ocr-math-defect-audit` | **OCR 静默毁坏的数学**审计：公式/脚注 OCR 缺陷扫描 | "OCR 把公式搞坏了""数学符号被识别错" |
| `latex-array-diagram-audit` | **交换图 / 箭头图审计**：旧式图候选盘点、逐边方向/钩/双头核验、无视觉证据流程 | "交换图方向对不对""箭头钩/双头缺失""tikzcd 之外还有 array 拼的图" |
| `latex-bookmark-anchor-audit` | **PDF 书签锚点审计**：锚点定位与校验 | "书签跳转不准""锚点对不上原书页" |
| `latex-translation-fidelity-audit` | **中文数学翻译保真审计**：结构 / 交叉引用 / 词汇 / 数学多维度比对 | "翻译有几处错""终稿前全面审查""读者挑出错误" |

> `latex-book-retypeset` 与 `mathtranslation` 是两条主线的"主控"，其余 7 个是它们的**配套审计子技能**；
> 重排线不适用纯翻译项目，反之亦然。

## 二、PDF 处理

| Skill | 一句话用途 | 何时调用（触发词） |
|---|---|---|
| `pdf` | PDF **读取 / 创建 / 检查 / 渲染** 通用技能 | "读这个 PDF""生成 PDF""检查 PDF 结构""渲染某页" |
| `pdf-image-text-extractor` | 从**图片或 PDF** 中识别并提取文字（多图格式） | "从图片提取文字""OCR 这个扫描页" |
| `pdf-scanned-ocr-bookmark` | 给**扫描 PDF 加可搜索隐形文字层 + 书签** | "扫描件加文字层""扫描 PDF 可检索" |
| `math-pdf-bookmark` | 给**数学 PDF 添加精确可点击书签**（真实 TOC + 逐锚点 y 坐标校验 + 无损增量写入） | "给 PDF 加书签""忠实提取原书目录" |

## 三、Office 文档（docx / xlsx / pptx）

| Skill | 一句话用途 | 何时调用（触发词） |
|---|---|---|
| `minimax-docx` | **Word(.docx) 专业创作与美化**（OpenXML 深度控制） | "写 Word""生成 docx""排版美化文档" |
| `minimax-xlsx` | **Excel(.xlsx) 打开 / 创建 / 读取 / 分析 / 编辑** | "处理表格""生成 xlsx""分析 Excel" |
| `pptx` | **PowerPoint(.pptx) 创建 / 理解 / 编辑** | "做 PPT""生成幻灯片""改这页 PPT" |
| `fast-docx` | **极速 Word 生成通道**（快速出 .docx） | "快速生成一份 Word 文档" |
| `fast-pptx` | **极速 PPT 生成通道** | "快速生成一份 PPT" |
| `fast-xlsx` | **极速 Excel 生成通道** | "快速生成一份 Excel" |
| `markitdown-skill` | **文档转 Markdown**（提取文本 / 表格 / 元数据） | "转成 Markdown""提取文档内容" |

> docx / xlsx / pptx 各有 `minimax-*`（深度能力）与 `fast-*`（快速生成）两条路线，按需选用。

## 四、系统 / 工具 / 其他

| Skill | 一句话用途 | 何时调用（触发词） |
|---|---|---|
| `astrbot-plugin-deploy-verify` | **AstrBot 插件部署与端到端验证** | "部署 AstrBot 插件""验证插件可用" |
| `exam-passing` | 高校**数学课程综合学业助教**（数学建模等，含 LaTeX 输出） | "数学建模作业""课程习题解答" |
| `web-access` | **联网操作总入口**：搜索 / 网页抓取 / API | "联网搜""抓网页""调接口" |
| `windows-orphan-app-entry-cleanup` | 清理注册表中**孤立的应用程序条目**（右键菜单 / 卸载项等） | "右键菜单卡""清理无效程序项" |
| `windows-shell-extension-hang-diagnosis` | 诊断并修复 **Windows 资源管理器 shell 扩展导致的卡顿** | "资源管理器卡顿""右键转圈" |

## 使用约定

- 用户给出具体任务 → 直接加载最匹配的子 skill（见上表触发词）。
- 用户问"该用哪个 skill"或"有哪些能力" → 加载本 `skill-router` 给出导航。
- 本路由**不移动、不合并、不删除**任何子 skill；子 skill 目录保持独立、可独立升级/同步。
