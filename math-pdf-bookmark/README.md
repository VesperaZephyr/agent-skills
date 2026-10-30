# math-pdf-bookmark · 数学 PDF 精确书签

给数学专著的 PDF 加**精确、可点击**的书签——跳到标题所在行的 y 坐标，而不是页面顶端。
已在数论、拓扑、代数学、分析学等 **1000+ 本** PDF 上验证。

覆盖三类藏书：有文字层的 PDF（从 span 几何解析目录）、脏文字层的扫描本（OCR 证据只放 PDF 外）、
纯图像扫描本（定点渲染 + PDF 外 OCR）。也能审计和重做"只跳页顶、扁平无层次、缺条、标题脏"的旧书签，
并可设置 PDF 页标签，让阅读器页码等于原书印刷页码。

> **平台无关的 Agent Skill**：`SKILL.md` 是唯一执行依据；本 `README.md` 只给人看，
> 两者若有出入，以 `SKILL.md` 为准。

## 为什么"精确"是难点

书签落到页面顶端很容易，落到**标题行**很难：PDF 写入的 y 值与阅读器最终落点之间存在
与页面几何相关的线性变换，不同书、不同页高都不一样。**不能套用固定偏移量。**

本技能的做法是用两个探针现场标定：写入 `y` 和 `y+37` 两个值，读回归算出
`landing = k·input + b`，再反解出真正该写入的值。标定后要求回读误差 **< 0.05 pt**，
且写入前后页面内容、图像流、元数据、页标签的哈希全部不变。

## 目录结构

```text
math-pdf-bookmark/
├── SKILL.md              路由主文件（48 行）：先判断怎么做 → 执行与验收 → 按需查阅
├── README.md             本文件，仅供人读
├── scripts/              随包可执行脚本（本次重构新增）
│   ├── bookmark_candidate.py   标定 + 生成候选书签 + 无损自校验
│   └── ocr_rows.py            OCR 碎片按基线重组成视觉行
└── references/           按需加载的专题文档与工具集
    ├── *.md              10 个专题文档（见下方导航）
    ├── *.py              24 个工具脚本（见下方分组表）
    └── winocr.ps1        WinRT OCR 回退（RapidOCR 不可用时）
```

## 按需查阅导航

`SKILL.md` 只给路由，细节按场景拆到这 10 个文档，**用到才读**，不要把全部塞进上下文：

| 场景 | 读哪个 |
|---|---|
| 要用工具、要生成候选书签、遇到出版方原生书签 | [`bookmark-tools-guide.md`](references/bookmark-tools-guide.md) |
| 坐标变换、页眉误判、OCR、页标签、审计盲区 | [`detailed-rules.md`](references/detailed-rules.md) |
| 分阶段流程、扫描本实例 | [`detailed-pipeline.md`](references/detailed-pipeline.md) |
| 中文书、脏文字层、扫描件路线（ROUTE H/R/P/P-CN/P-TXT/P-IMG/C） | [`routes-chinese-and-scan.md`](references/routes-chinese-and-scan.md) |
| 英文书与快速路线（ROUTE P-TXT-EN 各变体、born-digital） | [`routes-english-and-fast.md`](references/routes-english-and-fast.md) |
| 纯扫描本：先扫全书页眉定偏移分段、再谈定位 | [`scanned-bookmark-guide.md`](references/scanned-bookmark-guide.md) |
| 批量给扫描件加文字层（并行、可续跑） | [`scanned-ocr-pipeline.md`](references/scanned-ocr-pipeline.md) |
| 读回校验、无损写入、视觉验收、环境差异 | [`verification-and-cases.md`](references/verification-and-cases.md) |
| 书前内容、无页码目录、同名页眉的处理边界 | [`ode-lessons.md`](references/ode-lessons.md) |
| 目录版本不一致、旋转页面、页码对齐要求 | [`pde-lessons.md`](references/pde-lessons.md) |

## 随包脚本

### `scripts/bookmark_candidate.py` — 生成候选书签

**只读原件**，输出到新的候选文件，并顺带完成标定、无损校验和落点回读。

```bash
python scripts/bookmark_candidate.py 原书.pdf items.json 候选.pdf --report 报告.txt
```

`items.json` 是条目数组（level 从 1 起，**不允许跳级**）：

```json
[
  {"level": 1, "page": 12, "title": "Chapter 1",  "y": 96.5},
  {"level": 2, "page": 12, "title": "1.1 Definitions", "y": 210.0}
]
```

它会强制检查，任一条不过就直接失败而不是产出可疑结果：

- `level` 必须是正整数，且 `level ≤ 上一条 level + 1`
- `page` 为 1-based 且不超出页数；`y` 落在页高范围内
- 两探针标定出的 `|k|` 偏离 1 超过 0.02 → 报"坐标变换异常"
- 回读落点误差最大值 > 0.05 pt → 失败
- 页数、元数据、页标签、每页 rect / 文字 / 内容流 / 图像流的哈希与原件不一致 → 失败

报告里给出 `entries`、`max_error_pt` 和逐条的 `标题 / 页码 / y / 误差`。

### `scripts/ocr_rows.py` — OCR 碎片重组

把 `winocr.ps1` 的词级输出按基线重组成视觉行，保留几何信息和来源。

```bash
python scripts/ocr_rows.py dump.txt --summary          # 人读：p0012 y=96.5|x=72  文本
python scripts/ocr_rows.py dump.txt --page 11          # JSON，单页
```

关键设计：**渲染 dpi 必须写进 dump 头**，绝不让像素到点的换算静默出错。

```powershell
.\winocr.ps1 -PngDir D:\ocr\png -OutFile D:\ocr\dump.txt -LangCode en-US -Dpi 400 -Words
```

- `-Dpi` 会写入 dump 首行 `#dpi=400;scale=1.0;lang=en-US`，`ocr_rows.py` 取 `dpi × scale` 作有效 dpi
- 若命令行 `--dpi` 与头部冲突（偏差 > 0.5%）→ 直接报错退出
- 若 dump 无头部且未给 `--dpi` → 直接退出，不做任何猜测
- `-Words` 逐词输出是必需的：按行输出只保留首尾词的包围盒，会丢失页眉页码、目录页码列的 x 坐标

行分组用**固定质心**（中位数）而非相邻比较，避免相邻基线被链式粘连成一行。

## 工具参考（`references/` 下 24 个脚本）

| 分组 | 脚本 | 用途 |
|---|---|---|
| 诊断/分类 | `missdiag.py`、`size_census.py`、`inkband.py` | 判断藏书类型与可疑区域 |
| 文字层路线 | `heading_scan.py`、`dirtytext_build.py`、`toc_zoom.py` | 解析 span 几何、清理脏 OCR |
| 扫描件路线 | `scan_build.py`、`scan_toc_data.py`、`pureimage_build.py`、`scan_verify.py` | 扫描件 OCR + 书签 |
| 重锚/精修 | `reanchor.py`、`crop_reanchor.py`、`shift_probe.py` | 修正整本偏移、裁切重锚 |
| 质量与验收 | `bm_quality.py`、`verify_r.py`、`ink_audit.py`、`render_range.py` | 复审、校验、渲染对照 |
| ROUTE P 模板 | `routeP_schiff.py`、`routeP_cn_lihong.py`、`folio_runs.py` | 按已知模板批量落条 |
| 中文书 | `cn_build.py`、`cn_verify.py`、`label_folio_check.py` | 中文扫描教科书专项 |
| OCR 回退 | `winocr.ps1` | RapidOCR 不可用时用 WinRT |

> `SKILL.md` 正文里提到的 `diag.py` / `build_t1.py` / `verify.py` / `recover_empties.py`
> 属历史管线名，未随包提供。另有一个 `label_folio_check.py.bak_20261011` 是遗留备份，可清理。
> 用 `ink_audit.py` 前务必按目标页的页面尺寸和版心设置 `--x0` / `--x1` / `--tilex1`，
> 工具会拒绝越出页面的窗口。

## 安装与调用

把 `math-pdf-bookmark/` 整个目录放进你的 Agent 技能目录即可；支持 `$skill` 语法时用
`$math-pdf-bookmark`。

```text
使用 $math-pdf-bookmark 给 F:/.../分析学 这个文件夹的 PDF 加精确书签，
逐本跳到标题位置，并核对印刷页码。
```

依赖：Python 3 + [PyMuPDF](https://pymupdf.readthedocs.io/)；OCR 走 RapidOCR（离线）或
Windows 自带的 WinRT（用 `winocr.ps1`，纯 ASCII + BOM + CRLF，需 PowerShell 5.1+）。

## 核心纪律（不可让步）

- 书签必须落到**标题行的 y 坐标**；只跳到页顶视为未完成
- 印刷目录是**白名单**：误抓正文、习题、公式当作条目 = 失败
- 页码用原书 folio 逐条校验，不靠"估计偏移"；扫描缺页会让偏移分段变化
- 单本精修的 OCR dump 放在 PDF **外面**（ROUTE P-IMG），不污染原文件
- 改完必须逐条点击验证落点，**不能只看条数**
- 墨迹审计通过 ≠ 命中的是标题；未通过也可能是正确落点与检测间距不符，要结合图像判断

## 边界与已知限制

- 忠实提取原书**正式目录**：目录只到章时就按章处理，不自行补小节；缺级可以，跳级不行
- 纯扫描件没有目录页时，按 ROUTE P-IMG 做定点 OCR，不能凭空编号
- 缺页导致标题页不存在时，落点写该节现存首页并**在汇报中注明**，不伪装成精确命中
- 自动检测结果只能说"自动检测"，不能表述成"人工已确认"
- 与同仓库 [`pdf-scanned-ocr-bookmark`](../pdf-scanned-ocr-bookmark) 的分工：
  那个只做「批量给扫描件加可搜索文字层 + 据识别文本重建目录」；
  本技能覆盖更广（文字层书、脏文字层、单本精修、页标签、旧书签审计），
  且强调落点标定与无损写入。若要批量给一摞扫描件加层，用那个更直接。
