---
name: fast-docx
display_name_zh: 极速 Word 文档生成
display_name_en: Fast DOCX Generator
description: >
  极速 Word (.docx) 生成专属通道。当用户需要生成、编写、排版或导出 Word 报告、实验报告、论文、合同、总结或文档时优先使用本 Skill。
  绕过官方多层子代理（Orchestrator/doc-writer/doc-formatter/doc-converter）及繁复微调 RPC，
  通过单轮生成结构化排版 HTML 并直调本地内核转换脚本，2~3 秒内高质量生成 .docx，并自动打开预览。
triggers:
  - 生成Word
  - 做个Word
  - 实验报告
  - 导出word
  - docx
  - 打印文档
  - 写报告
  - 排版文档
---

# Fast DOCX 极速文档生成指南

## 核心设计思想
传统的 Office 插件通过 4 层子代理串行交互、或通过数十次微细粒度 RPC 操作文档，导致耗时高达数分钟。
**本 Skill 采用单阶段直达范式（One-Shot Fastpath）**：
1. **主 Agent 单轮输出** 完整、专业的语义化 HTML（含内联 CSS 排版、标准三线表、图片与图题、页眉页脚、分页控制）；
2. **直连极速本地内核**：调用配套转换脚本，在 **2~3 秒内** 直接转成 `.docx`；
3. **完成呈现**：调用 `present_files` 立即为用户打开呈现。

## 一键生成命令

```bash
"C:\Users\asus\.workbuddy\binaries\python\versions\3.13.12\python.exe" "C:\Users\asus\.workbuddy\skills\fast-docx\scripts\fast_convert.py" --html "<临时或交付HTML绝对路径>" --output "<目标.docx绝对路径>"
```

## HTML 排版标准规范（即插即用模版）

生成的 HTML 必须包含以下精美规范：
- **页面设置**：
  ```css
  @page {
      size: A4 portrait;
      margin: 2.0cm 2.0cm 2.0cm 2.0cm;
      @bottom-center { content: counter(page); font-family: 'Times New Roman', SimSun; font-size: 9pt; }
  }
  ```
- **字体族体系**：中文正文使用 `宋体`，标题使用 `黑体`，数字与英文使用 `Times New Roman`。
- **学术标准三线表**：
  ```css
  table.three-line { width: 100%; border-collapse: collapse; margin: 8px 0; font-size: 9.5pt; text-align: center; }
  table.three-line thead tr:first-child th { border-top: 1.5pt solid #000; }
  table.three-line thead tr:last-child th { border-bottom: 0.75pt solid #000; }
  table.three-line tbody tr:last-child td { border-bottom: 1.5pt solid #000; }
  table.three-line th, table.three-line td { padding: 4px 6px; border-left: none; border-right: none; }
  ```
- **图片排版**：单张大图居中配图题；多张子图采用无边框表格 `table.img-grid` 两两并排。
- **分页控制**：在章节之间使用 `<div style="page-break-before: always;"></div>`。

转换成功后，立即调用 `present_files` 呈递产物给用户。
