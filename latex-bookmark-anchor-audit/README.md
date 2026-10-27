# PDF 书签 / 目录锚点审计 / latex-bookmark-anchor-audit

审计并修复 LaTeX 生成 PDF 的**书签与目录超链接锚点**，让点击条目真正落到对应标题。
根因通常是星号标题（`\section*{}` / `\subsection*{}` / `\chapter*{}`）**不生成 hyperref
锚点**；而最关键的坑是 `\phantomsection` 的**顺序陷阱**——它会让目标整体偏移一页。
技能覆盖：症状→根因、`.toc` 中"借用锚点"的识别、PyMuPDF 验证循环，以及混合历史
写法的幂等规范化。

> 平台无关 Agent Skill：本技能只有 `SKILL.md`（方法与命令片段内嵌其中），没有随包脚本。

## 能力总览

| 能力 | 说明 | 入口 |
|---|---|---|
| 症状→根因 | 书签/目录"跳错位置"的成因归类 | `SKILL.md`「Symptom → root cause」 |
| 修复 | 为星号标题补锚点、纠正 `\addcontentsline` 顺序 | `SKILL.md`「Fix」 |
| 顺序陷阱 | `\phantomsection` 位置错误导致整体偏移一页 | `SKILL.md`「The ordering trap」 |
| 坏状态检测 | 从 `.toc` 识别"借用锚点" | `SKILL.md`「Detecting the bad state」 |
| 幂等规范化 | 统一混合历史写法 | `SKILL.md`「Normalising mixed legacy spellings」 |
| 验证 | PyMuPDF 逐条点击落点校验 | `SKILL.md`「Verification loop」 |

## 核心纪律

- 星号标题**不会**产生 hyperref 锚点，必须在正确位置补 `\phantomsection`。
- 顺序：`\phantomsection` 要写在 `\addcontentsline` **之前**，否则目标整体偏移。
- 判断"条目跳错"要用 `.toc` 里的锚点名对比，而不是只看渲染效果。
- 规范化必须**幂等**：重复运行不改变结果。
- 验证要点击落点（PyMuPDF 取目标 y 坐标），不是只看书签条目数。

## 目录结构

```text
latex-bookmark-anchor-audit/
└── SKILL.md        方法、命令片段、验证循环（无随包脚本）
```

## 安装与调用

仓库内 `latex-bookmark-anchor-audit/` 即本技能目录。注册为 Agent 的 skill，或让 Agent
先读 `latex-bookmark-anchor-audit/SKILL.md`；支持 `$skill` 语法时用
`$latex-bookmark-anchor-audit`。

```text
使用 $latex-bookmark-anchor-audit 修复这个 PDF 目录"点一下跳错页"的问题，
逐条验证落点，并说明哪些原本就是星号标题。
```

## 边界

本技能不含自动化脚本：`SKILL.md` 给出方法、命令与检测思路，实际修复需按项目现场执行。
链接数变多或书签数正确，都不等于落点正确——必须逐条校验目标页。
