# 书签工具使用指南

工具位于本技能的 `references/`，新候选生成器位于 `scripts/`。先看各脚本开头的用法和默认路径；不要直接对原件运行不熟悉的脚本。

## 常用工具

| 目的 | 工具 | 注意 |
| --- | --- | --- |
| 筛查现有树 | `references/bm_quality.py` | 仅作风险线索；`needs-review` 不是通过结论，所有文件都须对照印刷目录和标题图像。稀疏、重复纵坐标及层级标志可能误报；无页码标签不代表出错。检查默认目录和参数。 |
| 文字层书籍定位 | `references/heading_scan.py` | 先按脚本用法试运行；`--write` 会写回 PDF。 |
| 旧树重定位 | `references/reanchor.py` | 先确认旧树完整；`--write` 会写回 PDF。 |
| 候选落点审计 | `references/ink_audit.py` | 使用 `--every 1` 并人工检查每张拼版；标题过高时可用 `--tileheight` 调整条带高度（pt）。 |
| **落点真值审计** | `references/landing_audit.py` | **必跑**。绕过 `get_toc` 的回声，直接读原始 `/XYZ` 反算 `view_top = crop.y1 − top`；分两块回答「口径」(写入=计划) 与「目标」(落点下方是否该标题，有文字层才可验)，末尾强制打印覆盖范围与 `PARTIAL`。`--sheet` 生成红线由原始目标反算的拼版，`--nonmono-review` 导出非单调裁决工作表。有硬问题退出码 1。 |
| **内容完整性比对** | `references/pdf_integrity.py` | **写回后用**。逐页比几何/内容流(原始+解码)/文字层/逐词坐标/图像/字体/矢量/链接/注释/控件，分 `CONTENT_DIFF`(硬失败) 与 `RECOMPRESSED`(重压缩)。只比图像流不足以证明正文无损。 |
| **一键写回验收** | `references/verify_writeback.py` | 依次跑内容完整性 + 落点审计，把「自动化检查」与「人工验收」分两栏汇总；结论 `PASS / AUTO-PASS / INCOMPLETE / FAIL`，退出码 0/2/3/1。`PASS` 必须附 `--manual-review` 全量记录。 |
| 页码与标签检查 | `references/folio_runs.py`、`references/label_folio_check.py`、`references/page_labels_candidate.py` | 印刷页码和页码标签都需要按书核对；候选写入只落副本，不写回原件。 |
| 制作候选 PDF | `scripts/bookmark_candidate.py` | 仅写新的候选副本和报告；不定位标题、不做人工视觉验收。 |
| **正文交叉引用跳转** | `scripts/xref_links.py` | 三子命令：`scan`（清点章/节/习题/定理类目标与编号作用域）、`build --dry-run/--apply`（发现引用并写副本）、`audit`（回读核验，`--marks` 出带红框验证副本）。只写副本。中文扫描件加 `--lang zh`，见下文。 |
| **写回前定位 / 旧树分型 / 拼版比对** | `scripts/bm_locate.py` | 三个子命令：`locate`（目录条目→标题落点）、`diagnose`（旧树错误分型）、`chunks`（拼版逐块比对）。扫描件加 `--rows`。详见下节。 |

`cn_build.py`、`routeP_cn_lihong.py`、`routeP_schiff.py` 等包含特定书的路径或目录数据，是**案例模板**；复制后按实际书籍改写，不能直接当通用命令运行。其他脚本使用前同样检查顶部配置和帮助说明。

当用户明确要求跳过 LaTeX 自动生成的书签时，可使用 `--skip-latex-native`。脚本只对制作信息含 hyperref 且所有书签均保留常见 hyperref 命名目标的文件标记 `latex-native-skip`；未匹配不代表一定不是 LaTeX 书签，元数据也不能单独证明书签未经后续修改。不要将此选项当作普遍质量保证。

## 写回前：定位 / 旧树分型 / 拼版比对（`scripts/bm_locate.py`）

2026-11-23 连做三本（严加安《测度论讲义》纯扫描、程其襄《实变函数与泛函分析基础》
扫描 + OCR 文字层、Bogachev《Measure Theory》两卷合订 born-digital），每本都临时手写了
同样的 locate / 旧树诊断脚本，坑重复踩。这个工具把三段固定下来，规则出处见精度规则 27、28。

三个子命令互相独立，可以只用其中一个。整条链是：

```
bm_locate.py locate  →  items.json  →  bookmark_candidate.py  →  landing_audit.py --sheet
                     →  逐格目视       →  备份写回  →  verify_writeback.py
```

### 1. `locate`：由印刷目录条目表定位标题行

先按第 1 步转录音印刷目录，落成 JSON 数组（UTF-8）：

```json
[
  {"level": 1, "kind": "text",    "title": "Preface", "page": 5, "key": "Preface"},
  {"level": 2, "kind": "chapter", "title": "Chapter 1. Constructions ...", "num": 1, "folio": 1},
  {"level": 3, "kind": "section", "title": "1.2. Algebras and σ-algebras", "num": "1.2", "folio": 3},
  {"level": 1, "title": "目录", "page": 1, "y": 145.0}
]
```

- 定位依据三选一：`page`（物理页，最高优先）> `folio`（印刷页，配合 `--offset`）> `expect`。
- `kind` 可省：有 `num` 且含点 → `section`，`num` 为整数 → `chapter`，否则 `text`。
- `key` 覆盖搜索文本；`y` 直接指定落点（书前内容、无标题行的目录页用）；`dy` 覆盖默认 6pt。
- **合订本**：各卷 folio 各自从 1 开始，全局 `--offset` 表达不了，就在条目里写 `"offset": 526`；
  单卷但有分段时用 `--offset 16 --offset 456=15`（folio ≥ 456 用 15）。

```bash
python scripts/bm_locate.py locate --pdf book.pdf --entries entries.json \
    --offset 16 --offset 456=15 -o out/
```

扫描件把文字层换成 OCR 行摘要（`winocr.ps1 -Words` → `ocr_rows.py --summary`）：

```bash
python scripts/bm_locate.py locate --pdf book.pdf --rows all_rows.txt \
    --entries entries.json -o out/
```

工具内置的几道闸门，都是踩出来的：

| 闸门 | 理由 |
|---|---|
| 按 y 容差聚类（默认 3pt）后按 x 排序拼接 | born-digital 把「2.7.」与题名排成同一行高、y 差 1–2pt 的两条 line（规则 28） |
| 节号锚 `^num\.\s+(?!\d)`，排除 Theorem/Definition 等词 | 否则「1.8.1. Theorem」会被当成 1.8 节，实测 9 条误判 |
| 非粗体行长度 ≤ 题名 +6 | 否则正文里以题名开头的句子会命中：「7.3 正则条件概率」被定到「…正则条件概率的第一个应用…」 |
| `bold` 或字号门槛；`y < 62` 与目录页剔除 | 页眉常印着同名章节（严加安 p232 页眉在 y=50.4） |
| 文本匹配四级回退：精确 → 折行/丢尾 → 子序列 → 相似度 0.85 | OCR 把 `Hausdorff` 读成 `HausdorfF`、`Choquet` 读成 `Choque`、`L^p` 整段丢掉 |

最后一级回退不要放宽到 0.7 以下：宁可报 MISS 让你目视，也不要静默落到错行。
实测严加安 69 条正文条目：64 条命中且落点与人工验收值**完全相同（0.0pt）**，
5 条 MISS 正是含 `L^p`、`L^∞`、`C_0(X)`、`R^m`、`Minlos` 的那几条（原本也是手工定的）。
Bogachev 105 条目录条目：105 命中，与已交付落点逐条比对最大偏差 **0.05pt**、页差 0。

### 2. `diagnose`：旧树错误分型

```bash
python scripts/bm_locate.py diagnose --pdf book.pdf            # 有文字层
python scripts/bm_locate.py diagnose --pdf book.pdf --rows all_rows.txt   # 纯扫描
```

它按「题名反查实际页码」把旧树分成几类，并给出结论（重建还是微调）：

| 类别 | 含义 | Bogachev 旧树实测 |
|---|---|---|
| `in_toc` | 目标指向目录页（把目录当正文） | 60 条（第二卷 Ch.6–10 全落在 p521–523） |
| `far` | 页码差一个量级 | 11 条 |
| `page_off` | 页码差 ≤ 检索窗 | 9 条 |
| `top` / `neg` / `oor` | 落点在页顶 / 负值 / 越界 | 12 / 0 / 0 |
| `title_digits` | 标题混入页码 | 0 |
| `order` | 页序倒退 | 0 |

**输出是待核查信号，不是判决**（规则 24）。`nofind` 一栏多为书前内容（Half-title /
Title page / Copyright page 本来就没有印出来的标题行），要看一眼再决定。

两个已知的假警报：书签本身叫「Contents」而指向目录页，是对的；`Preface to Volume 2`
的尾数是卷号不是页码。两者都已排除。索引页行尾也全是页码，会被 `toc_like` 当目录页跳过，
所以索引条目常落进 `nofind`。

纯扫描件不给 `--rows` 时页码核对无法进行，工具会明说并跳过那一栏，不会输出 76 条假 `nofind`。

### 3. `chunks`：拼版只重看变了的块

```bash
python scripts/bm_locate.py chunks --a sheets_v2 --b sheets_v3 --out chunks_v3 --tile 970
```

改一处重新出拼版后，不必整本重看：它把两次的切片逐块哈希比对，只打印差异块名
（程其襄实测 8 块中 1 块不同，正是改过的那格）。

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

工具对每条目标做两点坐标标定，在副本写入并重新打开，核对标题、层级、页码和落点，以及页面几何、文本、内容流、图片引用、字体、矢量、链接、元数据和 PageLabels。它不会判断输入条目是否忠实于原书，也不会检查点击后视觉位置是否为标题；继续进行完整墨迹审计和人工看图。报告是候选回读记录，不是原件写回证明。报告里 `readback_error_pt` 是循环验证（只证明树写进去了），`raw_xyz_checked` 是原始 `/XYZ` 反算的覆盖范围（`n/N`），`raw_xyz_unverified` 列出的条目**没有验证过**。目标页 `rotation≠0` 时工具直接拒绝写入，不会"写进去再标注未验证"。

本工具不覆盖已有输出、不提供原件写回功能；真正写回仍须依技能入口进行备份和写后验证。

## 落点真值审计（写回前后都必须做）

`bookmark_candidate.py` 的回读断言和 `bm_quality.py` 的 `to.y` 都走 `get_toc`，而 `get_toc` 的 `to.y` 通常只是写进去的值的另一种表示（crop/media 原点不一致时还带偏移）——**这类断言是循环验证，抓不出坐标口径错误**（把 y 按页高翻错的版本照样报 0.0001 pt）。真值只有一个：PDF 里存的 `/XYZ top`。

```powershell
# 落点是否与计划一致；有问题退出码 1
python references/landing_audit.py "候选.pdf" --items "条目.json"

# 红线由原始 /XYZ 反算的拼版（--every 3 可抽样）
python references/landing_audit.py "候选.pdf" --sheet "sheets" --every 1

# 写回原件后再跑一次
python references/landing_audit.py "原书.pdf" --items "条目.json"
```

它同时检查：落点是否越出页面、树序 `(页, 落点)` 是否非单调、编号标题是否被按字符串排成 `12.10 < 12.9`、`crop 高 ≠ rect 高` 的 shift、`rotation≠0` 的页面（此时公式不成立，剔出"可比对"并单列未验证）、以及 `left` 取值分布。

**非单调只是警告，不是判决**：索引、并列条目、分栏阅读顺序都可能合法地回退。用
`--nonmono-review 工作表.md` 导出裁决表，逐处填「前置条目 / 当前条目 / 各自页与落点 /
目录里的先后 / 裁决 / 依据」。裁决只有 `keep`（合理非单调，保留）、`fix-landing`（压错行）、
`fix-order`（树序与目录不符）、`unresolved`（证据不足，不得算通过）四种；汇报要给出四个计数。

**它回答两个不同的问题，输出也分两块，不要混读：**

- **Q1 口径**：`--items` 给出的计划 `y` 与实际写入的落点是否一致。这一项只证明"写入没走样"。
  反证：把计划 `y` 全换成 `页高 − y`（错误的镜像计划）再交给生成器，它照样把书签放到被要求的位置，
  于是 Q1 依旧报 `0.000015 pt`。**计划本身错时，比写入与回读永远通过。**
- **Q2 目标**：落点下方是否真的是该编号的标题。有文字层时工具会取落点下方文字，
  校验行首编号（`7.15` → 书中 `15.`）或标题正文；没有文字层就只报 `0/n 可验`，
  要求逐格看拼版。它**不会**用 `OK` 掩盖这种情形。

工具末尾固定打印覆盖范围（`口径可反算 x/n`、`口径未验证`、`目标自动可验 y/n`、`目标需目视 n/n`），
存在未验证条目时结尾是 `PARTIAL` 而不是 `OK`。汇报时必须原样带上这些分母。

`--tol` 默认 0.5 pt（≈0.18 mm，肉眼不可辨），判错位用的是"扣除中位数后的偏差"：
常数偏移（标定残差）会被单列成警告，不会淹没成几十条"错位"。

**不要自己手写 apply 脚本。** `bookmark_candidate.py` 对每条目标打了两发探针、解出该页真实的 `k, b` 再反算写入值，因此它**不会自己再翻一次**（这类口径错误它免疫）；2026-11-19《实分析中的反例》的 530 条全错，正是绕过它、手写 `to = Point(x, H - y)` 的结果。但"免疫"仅限于此：探针的测量方式、目标页是否选错、计划 `y` 本身错，它一概不免疫。若确实需要自写写入逻辑，必须照搬两探针标定，并在写后用 `landing_audit.py` 复核。

**探针必须用原始 `/XYZ` 反算，不能用 `get_toc()['to'].y`。** 2026-11-23 一本书的 `cropbox.y0=0` 但 `mediabox.y0≈−60`，`get_toc` 回读值本身带 −60pt 偏移；旧标定据此算出 `b≈+60` 并二次补偿，80 条整体偏 60pt（详见 `detailed-rules.md` 规则 27）。现版本已改为读原始 `/XYZ top` 解 `k, b`，并用同一口径核对写入值；`get_toc` 只用来核树结构。

**边界**：它对"自己再翻一次"免疫，但探针测量方式错、目标页选错、计划 `y` 错，它都照做不误——你给错 y，它就精准地放到错处。落点是否压对标题，只能靠 Q2 证据（文字层 + 拼版）。

## 内容完整性比对（"正文无损"取证）

```powershell
# 逐页比全部 facet；真实内容差异 exit 1，有读取失败项 exit 2
python references/pdf_integrity.py --base "原件.pdf" --new "写回后.pdf"

# 只比指定页，或输出 JSON
python references/pdf_integrity.py --base A.pdf --new B.pdf --pages 1-40,300
python references/pdf_integrity.py --base A.pdf --new B.pdf --json diff.json
```

比较范围：页面几何（Rect/MediaBox/CropBox/旋转）、内容流（原始字节 + 解码字节）、
文字层、逐词坐标、图像（尺寸/位深/色彩空间/字节）、字体资源、矢量几何、
链接（kind/目标页/`to` 点/网址/文件/命名目标/点击区）、注释、
表单控件（名称/类型/**字段值**/标志/可选项/位置）；文档级比页数、页码标签、加密状态、
嵌入文件、元数据。书签**不在**范围内（那是本次要改的东西）。

结果分四类：

| 类别 | 含义 | 处理 |
|---|---|---|
| `CONTENT_DIFF` | 真实内容变化 | 必须回退（exit 1） |
| `RECOMPRESSED` | 流字节变、解码后一致（重压缩） | 列出但不判失败 |
| `META` | 元数据变化（ModDate 等） | 列出，按任务要求决定 |
| `UNVERIFIED` | 某 facet 在任一侧读取失败 | 单列 `?` 行，exit 2，**不许当成"两侧都空=相等"** |

**覆盖边界要照实说**：它只能比对"能读到的 facet"。控件外观流与 JavaScript 动作没比，
launch/remote 等动作没枚举，两侧都读不出的 URI 也看不见。所以通过只能说
"逐页 facet 比对未见差异（范围见工具头）"，不能说"所有内容及交互均无损"。

**只比图像流 md5 不足以证明无损**：文字层、矢量绘图、字体资源都可能被重写破坏而图像全等。
同样**不要拿 xref 编号当比较键**——重存后必变，会报"每页都有差异"。

## 一键写回验收（推荐入口）

```powershell
python references/verify_writeback.py --new "写回后.pdf" --orig "备份.pdf" `
    --items "条目.json" --sheet "sheets" --manual-review "review.json"
```

依次跑内容完整性 + 落点审计，把**自动化检查**与**人工验收**分成两栏，且**拒绝把两层合成一个 PASS**：

```
【自动化检查】
  内容完整性 : PASS     0 硬差异, 0 未验证 facet
  Q1 口径    : PASS     可反算 553/553
  Q2 目标    : 0/553 有文字层证据 (…, 无文字层 553)
               文字层证据只说明'落点下方文字与标题相符', 不等于排版上压准标题上沿
  —— 自动层结论: 覆盖完整
【人工验收】
  记录       : 553/553 条  (18 张拼版, 逐格拼版目视, 2026-11-19)
结论: PASS —— 自动检查完整通过, 人工验收记录覆盖全部条目
```

结论四态与退出码：

| 结论 | 条件 | exit |
|---|---|---|
| `FAIL` | 内容硬差异 / 落点越界 / 落点可证错位 | 1 |
| `INCOMPLETE` | 缺 `--orig` 或 `--items`，或有 `UNVERIFIED`，或 `--manual-review` 记录无效 | 3 |
| `AUTO-PASS` | 自动层完整通过，人工验收未记录或未覆盖全部 | 2 |
| `PASS` | 自动层通过 **且** 人工记录覆盖全部条目 | 0 |

`--manual-review` 的 JSON：`{"reviewed": 553, "total": 553, "sheets": 18,
"method": "逐格拼版目视", "by": "...", "date": "2026-11-19", "notes": ""}`；
`reviewed` 可写整数或 1-based 序号列表，`method` 不能空。记录不足只会降级，永远不会升级结论。
`--strict-text` 要求 Q2 全部有文字层证据（纯扫描件必然失败，只适合文字层书）。
`--strict-text` 可把"Q2 无证据"直接判失败，用于自动化闸门。

## 出版原生书签的保护：Grafakos 实测

Grafakos《Classical Fourier Analysis》第三版的原生书签共 260 条：3 条书前直接目标、257 条命名目标，名称包括 `chapter.*`、`section.*`、`section*.*`、`subsection.*`、`appendix.*`；印刷目录 257 个链接与这些条目对应，原书习题与各节同为二级。对照目录与不同类型的跳转，结构、页码、落点均可信时应保留并跳过。不要只因部分标题中上下标以纯文本呈现，或根据偏好改变习题层级就重建原树。

该原版和旧工具损坏后的版本拥有同样的 InDesign/Adobe PDF Library 元数据、页数、页码标签和目录链接，但后者只有 176 条全部直接目标，错层、遗漏且跳错页；元数据和目录链接本身不能证明现存书签正确。反过来，命名目标也可能不完整或已失效。先核对书签标题、顺序、层级和目录的对应，抽查书前、章节、习题、附录及各段页码的跳转；发现异常则进入完整核查。用 PyMuPDF 处理命名目标时不能把 `kind=4` 的 `to` 直接当作普通 `kind=1` 的页面坐标，需解析实际目标并核验阅读器显示。现有 `--skip-latex-native` 的检测不覆盖本书（混合直接与命名目标、creator 为 InDesign）；不要把它的未命中当作改写依据。

### 中文劣质 OCR 扫描件（--lang zh）

```
python xref_links.py scan  --pdf book.pdf --lang zh --skip-pages 0-12,246-253 \
                           --ymin 55 --sec-x0-max 100 --json heads.json
python xref_links.py build --pdf book.pdf --lang zh --skip-pages 0-12,246-253 \
                           --ymin 55 --sec-x0-max 100 --report links.json --dry-run
python xref_links.py build --pdf book.pdf --lang zh --skip-pages 0-12,246-253 \
                           --ymin 55 --sec-x0-max 100 --report links.json --out linked.pdf --apply
python xref_links.py audit --pdf linked.pdf --report links.json --marks marked.pdf
```

中文专属参数：`--x0-min-zh/--x0-max-zh`（结果标题左边距，默认 **74–150**；
"注" 类标题可到 x≈131，旧的 112 会漏）、`--sec-x0-max`（节标题左边距，
默认 **100**）、`--eq-xmin`（右边缘公式号最小 x，默认 180）。`--lang` 只影响
scan/build；audit 从报告里自动读 lang。**必须从无交叉引用链接的备份/原件构建**：
如果原 PDF 已写过一轮链接，`--apply` 会叠加出重复链接；先确认 `get_links()` 计数，
再决定是否从 `.bak-xref-*` 重建。

**词级定位**：中文 OCR 的 rawdict 字符顺序与聚行文本不一致、`search_for` 对 NBSP
几乎搜不到，所以框坐标必须由 `get_text('words')` 的词 bbox 直接拼，
不能用"行内字符比例"或 `search_for` 反推——后者会框到错误的词上。

中文模式还有六个不可回退的实现约束：

1. **标题扫描走原始 OCR 行**（`zh_raw_lines`），不要走 `zh_vlines()` 聚合行；
   聚合会把标题与同物理行的后续正文倒序拼接，令 `^定理` 判据漏掉标题。
2. **触发只看词尾是否为类型词**，并支持类型词与编号黏在同一词；
   编号片段最多三段，尾随乱码取头部即可，但 `，0`/`，7` 不能吃成第四段。
3. **`zh_num()` 必须先纠形再清洗**：把所有非数字非分隔符（含 `)`、乱码）
   换成空格。保留未知字符会让 `1.1.6)` 整号失效。
4. **同号候选先按"像不像标题"打分**：编号后接 `说明/表明/中/的证明` 的是正文句，
   接 `（副题）` 或很短的才是真标题；再按页距选，避免跳到正文提及句。
5. **公式号 `(N.M)` 与节号 `N.N 节` 都要认拆词**：`（`+`4`+`．`+`17`+`）`、
   `1`+`．`+`4`+`节`。整词 `(4.17)` / `1.4节` 只是少数。定义点 OCR 成 `L4`
   时由 `zh_eq_num()` 特判为 `1.4`。
6. **OCR 映射要逐字验证**：`彐` 在 `例 1.4 彐 4` 中是 `14` 的前半，
   直接映射成 `1` 会拼出错误的 `1.4.1`；这种字不要进数字映射表。
