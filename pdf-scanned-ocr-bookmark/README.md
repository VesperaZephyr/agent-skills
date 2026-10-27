# 扫描 PDF → OCR 文本层 → 书签 / pdf-scanned-ocr-bookmark

用命令行 OCR 管线（RapidOCR / PP-OCRv6，离线）给**纯扫描（纯图像）PDF** 加一层可搜索的
不可见文字层，再从识别出的文本重建**忠实的目录书签树**。适用场景：PDF 没有文字层
（`get_text()` 为空）却需要 OCR + 书签；或有人要求**批量 OCR** 扫描 PDF（"福昕/Adobe
OCR 只能一本本做，能否批量 OCR 再加书签"）。**不要**依赖福昕/Adobe 内置 OCR——它
只能图形界面操作，无法脚本化。

> 平台无关 Agent Skill：本技能只有 `SKILL.md`（方法与脚本说明内嵌其中），随包不含脚本。

## 能力总览

| 能力 | 说明 | 入口 |
|---|---|---|
| 批量 OCR | 并行 + 可续跑的 OCR 脚本（`ocr_batch.py`，需自备） | `SKILL.md`「Batch OCR script」 |
| 目录重建 | 从文字层重建多层书签树 | `SKILL.md`「Rebuild bookmarks」 |
| 校验落点 | 验证书签条与目标页 | `SKILL.md`「Verify & place」 |
| WinRT 回退 | RapidOCR 不可用时改用 Windows 内置 OCR | `SKILL.md`「FALLBACK」 |
| DPI 匹配 | 渲染 DPI 必须匹配扫描原生分辨率 | `SKILL.md`「match the render DPI」 |
| 精确落点 | 跳到标题，而非页顶 | `SKILL.md`「PRECISE bookmark destinations」 |
| 文字层捷径 | 已有文字层的 PDF 不走 OCR，直接解析 | `SKILL.md`「TEXT-LAYER PDFs」 |

## 核心纪律

- **不用**福昕/Adobe 内置 OCR：GUI-only、不可脚本化、难批量。
- 渲染 DPI 必须匹配扫描原生分辨率，否则 OCR 质量骤降。
- 有文字层的 PDF **优先**走文字层解析，不要浪费时间去 OCR。
- 分类"扫描 vs 文字层"不能只看平均文字密度，容易误判。
- 精确书签要定位标题行，不能整页顶。
- 无目录页页码时，按技能内流程用定点 OCR 找标题，不凭空编号。

## 目录结构

```text
pdf-scanned-ocr-bookmark/
└── SKILL.md        方法、管线、坑位（ocr_batch.py / precise.py 等需按正文自备）
```

> 说明：`SKILL.md` 正文描述的 `ocr_batch.py`、`precise.py` 等脚本**未随包提供**，
> 需按文中说明现场实现或放置。

## 安装与调用

仓库内 `pdf-scanned-ocr-bookmark/` 即本技能目录。注册为 Agent 的 skill，或让 Agent 先读
`pdf-scanned-ocr-bookmark/SKILL.md`；支持 `$skill` 语法时用 `$pdf-scanned-ocr-bookmark`。

```text
使用 $pdf-scanned-ocr-bookmark 给这个纯扫描 PDF 批量 OCR 加文字层，
再从目录重建精确书签，跳到标题而不是页顶。
```

## 边界

本技能不含随包脚本，属"方法论 + 管线说明"型技能，落地需要按项目现场实现脚本。OCR
识别质量受扫描分辨率与字体影响；识别错误的标题需人工复核后再入书签树。
