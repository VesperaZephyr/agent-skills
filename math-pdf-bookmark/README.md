# 数学 PDF 批量精确书签 / math-pdf-bookmark

给大文件夹的数学 PDF 加**精确、可点击**的书签——跳转到标题的 y 坐标，而不是页面顶端。
处理两类藏书：有文字层的 PDF（目录需从 span 几何解析），以及纯扫描件（需先 OCR：批量
做不可见文字层；单本精修则把 OCR dump 放在 PDF **外面**，即 ROUTE P-IMG）。还能设置
PDF 页标签，让阅读器页码等于印刷 folio；并可审计/重做"只跳页顶、扁平、缺条、标题脏"
的旧书签。已在数论 / 拓扑 / 代数学 / 分析学等 **1000+ PDF** 上验证。

> 平台无关 Agent Skill：以 `SKILL.md` 为准，`README.md` 仅供人读。

## 能力总览

| 能力 | 说明 |
|---|---|
| 分类诊断 | 先分文字层 / 扫描件 / 图像目录书，再选路线 |
| 批量 OCR | 给纯扫描件加不可见文字层（批量、可续跑） |
| 书签生成 | 从文字层 span 或印刷目录重建多层精确书签树 |
| 精确落点 | 跳到标题 y 坐标，而非页顶 |
| 页标签 | 让阅读器页码 == 原书印刷页码 |
| 质量复审 | 找"页顶式/扁平/缺条/脏标题"并重做 |

## 核心纪律（不可让步）

- 书签必须落到**标题 y 坐标**；只跳到页顶视为未完成。
- 印刷目录是**白名单**：不得把正文/习题/公式误当条目录入。
- 页码用原书 folio 校验，不靠"估计偏移"。
- 单本精修的 OCR dump 放在 PDF **外面**（ROUTE P-IMG），不污染原文件。
- 改完必须用 PyMuPDF 逐条点击验证落点，不能只看条数。

## 目录结构

脚本工具集历史地放在 `references/` 下（不设 `scripts/`）：

```text
math-pdf-bookmark/
├── SKILL.md
└── references/
    ├── bm_quality.py            书签质量复审
    ├── cn_build.py / cn_verify.py   中文书书签构建 / 校验
    ├── dirtytext_build.py       脏文字层构建
    ├── pureimage_build.py       纯图像扫描件构建
    ├── scan_build.py / scan_verify.py / scan_toc_data.py  扫描件构建/校验/目录数据
    ├── reanchor.py / crop_reanchor.py   重锚 / 裁切重锚
    ├── heading_scan.py / ink_audit.py / inkband.py   标题扫描 / 墨迹审计 / 墨带
    ├── label_folio_check.py     标签-页码核对（另有 .bak_20261011 备份）
    ├── folio_runs.py / shift_probe.py   页码段 / 偏移探测
    ├── size_census.py / toc_zoom.py     字号普查 / 目录放大
    ├── routeP_schiff.py / routeP_cn_lihong.py   ROUTE P 模板（Schiff / 李红）
    ├── missdiag.py / render_range.py / verify_r.py / sheet.py   缺漏诊断/范围渲染/校验/表格
    └── winocr.ps1               WinRT OCR 回退
```

> 注意：`SKILL.md` 正文提到的 `diag.py` / `build_t1.py` / `verify.py` / `recover_empties.py`
> 属于历史管线名，未随包提供；随包的是上表 `references/` 下的工具集。另有一个
> `label_folio_check.py.bak_20261011` 是遗留备份，可清理。

## 脚本参考（按功能分组）

| 分组 | 主要脚本 | 用途 |
|---|---|---|
| 诊断/分类 | `missdiag.py`、`size_census.py`、`inkband.py` | 判断藏书类型与可疑区域 |
| 文字层路线 | `heading_scan.py`、`dirtytext_build.py`、`toc_zoom.py` | 解析 span 几何、清理脏 OCR |
| 扫描件路线 | `scan_build.py`、`scan_toc_data.py`、`pureimage_build.py`、`scan_verify.py` | 扫描件 OCR + 书签 |
| 重锚/精修 | `reanchor.py`、`crop_reanchor.py`、`shift_probe.py` | 修正整本偏移、裁切重锚 |
| 质量与验收 | `bm_quality.py`、`verify_r.py`、`ink_audit.py`、`render_range.py` | 复审、校验、渲染对照 |
| ROUTE P 模板 | `routeP_schiff.py`、`routeP_cn_lihong.py`、`folio_runs.py` | 按已知模板批量落条 |
| 中文书 | `cn_build.py`、`cn_verify.py`、`label_folio_check.py` | 中文扫描教科书专项 |
| OCR 回退 | `winocr.ps1` | RapidOCR 不可用时用 WinRT |

## 安装与调用

仓库内 `math-pdf-bookmark/` 即本技能目录。注册为 Agent 的 skill，或让 Agent 先读
`math-pdf-bookmark/SKILL.md`；支持 `$skill` 语法时用 `$math-pdf-bookmark`。

```text
使用 $math-pdf-bookmark 给 F:/.../分析学 这个文件夹的 PDF 加精确书签，
逐本跳到标题位置，并核对印刷页码。
```

## 边界

书签忠实提取原书**正式目录**；误抓正文/习题/公式视为失败。纯扫描件无目录页时，
需按技能内的 ROUTE P-IMG 流程做定点 OCR，不能凭空编号。
