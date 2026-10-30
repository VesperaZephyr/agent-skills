# 书签工具使用指南

工具位于本技能的 `references/`，新候选生成器位于 `scripts/`。先看各脚本开头的用法和默认路径；不要直接对原件运行不熟悉的脚本。

## 常用工具

| 目的 | 工具 | 注意 |
| --- | --- | --- |
| 筛查现有树 | `references/bm_quality.py` | 仅作风险线索；`needs-review` 不是通过结论，所有文件都须对照印刷目录和标题图像。稀疏、重复纵坐标及层级标志可能误报；无页码标签不代表出错。检查默认目录和参数。 |
| 文字层书籍定位 | `references/heading_scan.py` | 先按脚本用法试运行；`--write` 会写回 PDF。 |
| 旧树重定位 | `references/reanchor.py` | 先确认旧树完整；`--write` 会写回 PDF。 |
| 候选落点审计 | `references/ink_audit.py` | 使用 `--every 1` 并人工检查每张拼版；标题过高时可用 `--tileheight` 调整条带高度（pt）。 |
| 页码与标签检查 | `references/folio_runs.py`、`references/label_folio_check.py` | 印刷页码和页码标签都需要按书核对。 |
| 制作候选 PDF | `scripts/bookmark_candidate.py` | 仅写新的候选副本和报告；不定位标题、不做人工视觉验收。 |

`cn_build.py`、`routeP_cn_lihong.py`、`routeP_schiff.py` 等包含特定书的路径或目录数据，是**案例模板**；复制后按实际书籍改写，不能直接当通用命令运行。其他脚本使用前同样检查顶部配置和帮助说明。

当用户明确要求跳过 LaTeX 自动生成的书签时，可使用 `--skip-latex-native`。脚本只对制作信息含 hyperref 且所有书签均保留常见 hyperref 命名目标的文件标记 `latex-native-skip`；未匹配不代表一定不是 LaTeX 书签，元数据也不能单独证明书签未经后续修改。不要将此选项当作普遍质量保证。

## 制作候选书签

需要 Python 和 PyMuPDF（提供 `pymupdf` 模块）。先根据印刷目录和正文整理 UTF-8 JSON 数组，每条包含层级、标题、1-based 物理页码、距页面顶部的目标 y（pt）：

```json
[
  {"level": 1, "title": "第一章 示例", "page": 5, "y": 105.2},
  {"level": 2, "title": "1.1 示例", "page": 6, "y": 120.0}
]
```

运行（将路径换为实际文件，输出目录必须存在，候选和报告都不能已存在）：

```powershell
python scripts/bookmark_candidate.py "原书.pdf" "条目.json" "候选.pdf" --report "候选报告.txt"
```

工具对每条目标做两点坐标标定，在副本写入并重新打开，核对标题、层级、页码和落点，以及页面几何、文本、内容流、图片引用、元数据和 PageLabels。它不会判断输入条目是否忠实于原书，也不会检查点击后视觉位置是否为标题；继续进行完整墨迹审计和人工看图。报告是候选回读记录，不是原件写回证明。

本工具不覆盖已有输出、不提供原件写回功能；真正写回仍须依技能入口进行备份和写后验证。

## 出版原生书签的保护：Grafakos 实测

Grafakos《Classical Fourier Analysis》第三版的原生书签共 260 条：3 条书前直接目标、257 条命名目标，名称包括 `chapter.*`、`section.*`、`section*.*`、`subsection.*`、`appendix.*`；印刷目录 257 个链接与这些条目对应，原书习题与各节同为二级。对照目录与不同类型的跳转，结构、页码、落点均可信时应保留并跳过。不要只因部分标题中上下标以纯文本呈现，或根据偏好改变习题层级就重建原树。

该原版和旧工具损坏后的版本拥有同样的 InDesign/Adobe PDF Library 元数据、页数、页码标签和目录链接，但后者只有 176 条全部直接目标，错层、遗漏且跳错页；元数据和目录链接本身不能证明现存书签正确。反过来，命名目标也可能不完整或已失效。先核对书签标题、顺序、层级和目录的对应，抽查书前、章节、习题、附录及各段页码的跳转；发现异常则进入完整核查。用 PyMuPDF 处理命名目标时不能把 `kind=4` 的 `to` 直接当作普通 `kind=1` 的页面坐标，需解析实际目标并核验阅读器显示。现有 `--skip-latex-native` 的检测不覆盖本书（混合直接与命名目标、creator 为 InDesign）；不要把它的未命中当作改写依据。
