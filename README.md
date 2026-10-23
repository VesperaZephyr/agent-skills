# agent-skills

本人（VesperaZephyr）在 WorkBuddy 中使用的自定义 Agent 技能集合。

> **本仓库当前仅发布「数学书 LaTeX」与「PDF 处理」两类。** Office 文档、系统/工具/其他类仅本地保留，暂不入库（见 `.gitignore`）。
>
> 这些 skill 配合 WorkBuddy（`~/.workbuddy/skills/`）使用；每个子目录是一个独立 skill，含 `SKILL.md`（入口与触发词）、`references/`（参考素材）与 `scripts/`（可执行脚本）。

## 目录（已发布）

### 数学书 LaTeX（重排 / 翻译 / 审计）

| Skill | 用途 |
|---|---|
| `latex-book-retypeset` | 主控：高保真 LaTeX 数学书重排（re-typeset）工作流 |
| `mathtranslation` | 主控：数学书中文翻译与排版 |
| `latex-eq-numbering-audit` | 审计：公式编号一致性与锚点 |
| `latex-display-layout-audit` | 审计：行间公式排版与断行 |
| `latex-footnote-fidelity-audit` | 审计：脚注保真度 |
| `latex-ocr-math-defect-audit` | 审计：OCR 数学缺陷（fnaudit / mathaudit） |
| `latex-array-diagram-audit` | 审计：矩阵 / 图表保真度 |
| `latex-bookmark-anchor-audit` | 审计：PDF 书签锚点 |
| `latex-translation-fidelity-audit` | 审计：翻译保真度（配合 mathtranslation） |

### PDF 处理

| Skill | 用途 |
|---|---|
| `pdf` | 读取 / 摘要 / 检索 / 理解 PDF（本地 CLI） |
| `pdf-image-text-extractor` | 从图片或 PDF 中识别并提取文字 |
| `pdf-scanned-ocr-bookmark` | 为扫描版 PDF 添加可搜索隐藏文本 + 书签 |
| `math-pdf-bookmark` | 为数学书 PDF 添加精确可点击书签 |

## 仅本地保留、未发布到本仓库的类别

以下类别当前**仅保存在本地** `~/.workbuddy/skills/`，**未推送**到本仓库（已在 `.gitignore` 中忽略；后续如需发布，取消对应忽略项并 `git add` 即可）：

- **Office 文档**：`pptx` / `minimax-docx` / `minimax-xlsx` / `fast-docx` / `fast-pptx` / `fast-xlsx` / `markitdown-skill`
- **系统 / 工具 / 其他**：`astrbot-plugin-deploy-verify` / `exam-passing` / `web-access` / `windows-orphan-app-entry-cleanup` / `windows-shell-extension-hang-diagnosis` / `skill-router`

## 说明

- 本仓库是 `~/.workbuddy/skills` 中**已发布部分**的镜像，不含 WorkBuddy 内部迁移标记与编译缓存（见 `.gitignore`）。
- 各 skill 的 `SKILL.md` 顶部 `name` / `description` 决定其被自动触发的场景。
