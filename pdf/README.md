# PDF 文档处理 / pdf

综合 PDF 处理工具包：抽取文本与表格、创建新 PDF、合并/拆分文档、处理表单（AcroForm
字段提取与填写）、以及批量分析。底层使用 `pypdf` / `pdfplumber` / `reportlab` 与
poppler（`pdftotext`）、`qpdf` 等命令行工具。

> 平台无关 Agent Skill：以 `SKILL.md` 为准，`README.md` 仅供人读。

## 能力总览

| 能力 | 说明 | 入口 |
|---|---|---|
| 文本/表格抽取 | `pypdf` 基础操作、`pdfplumber` 文本与表格 | `SKILL.md`「Python Libraries」 |
| 创建 PDF | `reportlab` 绘制文本/线条/多页 | `SKILL.md`「reportlab」 |
| 命令行工具 | `pdftotext` / `qpdf` / `pdftk` 的合并、拆分、旋转、解密 | `SKILL.md`「Command-Line Tools」 |
| 扫描件 OCR | 转图 + `pytesseract`（按需安装） | `SKILL.md`「Extract Text from Scanned PDFs」 |
| 表单处理 | 字段提取、可填写域检测、填写与校验 | `scripts/*`、`forms.md` |
| 参考手册 | 详细 API 与操作说明 | `reference.md`、`forms.md` |

## 目录结构

```text
pdf/
├── SKILL.md                    主指南（库 + 命令行 + 常见任务）
├── reference.md                详细参考手册
├── forms.md                    表单处理说明
├── requirements.txt
├── requirements-dev.txt
├── _skillhub_meta.json
└── scripts/
    ├── check_fillable_fields.py      检测可填写表单域
    ├── extract_form_field_info.py    提取表单字段信息
    ├── fill_fillable_fields.py       填写可填写字段
    ├── fill_pdf_form_with_annotations.py  用注释方式填表
    ├── choice_appearance.py          选择/下拉框外观
    ├── form_utils.py                 表单工具函数
    ├── convert_pdf_to_images.py      PDF 转图片
    ├── create_validation_image.py    生成校验图
    ├── check_bounding_boxes.py       检查 bbox
    ├── check_bounding_boxes_test.py  上述测试
    └── pdf_forms_test.py             表单流程测试
```

## 脚本参考

| 脚本 | 用途 |
|---|---|
| `check_fillable_fields.py` | 检测 PDF 是否存在可填写表单域 |
| `extract_form_field_info.py` | 抽取表单字段（名称/类型/位置） |
| `fill_fillable_fields.py` | 程序化填写可填写字段 |
| `fill_pdf_form_with_annotations.py` | 以注释方式填写（适用于非 AcroForm） |
| `choice_appearance.py` | 处理选择框/下拉框外观 |
| `form_utils.py` | 表单相关公共函数 |
| `convert_pdf_to_images.py` | 将 PDF 页面转成图片 |
| `create_validation_image.py` | 生成填表校验图 |
| `check_bounding_boxes.py` | 校验坐标框 |
| `check_bounding_boxes_test.py` / `pdf_forms_test.py` | 单元/流程测试 |

## 安装与调用

仓库内 `pdf/` 即本技能目录。注册为 Agent 的 skill，或让 Agent 先读 `pdf/SKILL.md`；
支持 `$skill` 语法时用 `$pdf`。

```text
使用 $pdf 读取这份 PDF 的文本和表格，并把这个表单的字段填好。
```

## 许可注意（需处理）

`SKILL.md` 的 frontmatter 声明 `license: Proprietary. LICENSE.txt has complete terms`，
但**当前技能目录内并不存在 `LICENSE.txt`**（仅有 `requirements*.txt`）。使用/再分发前
请向来源确认许可条款，或补回该文件——这是一个待修的实际缺陷。

## 边界

本技能偏"通用 PDF 工程"，不含针对数学书籍的版面/编号/书签审计（那些见 `latex-*` 与
`*bookmark` 系列技能）。扫描件 OCR 依赖外部 OCR 引擎，需按需安装。
