# 审图工具：按职责使用

本技能维护候选盘点、冻结、精确修复、页对回归和规则网格生成；`mathtranslation`维护PDF整页/局部导出。不要在三个技能中复制同一实现。PDF操作依赖PyMuPDF；候选盘点、精确替换和网格生成只需标准库。

|任务|工具|输出能证明什么|
|---|---|---|
|定位候选|`inventory_diagrams.py`|编译链环境/宏/箭头命中；不证明分类、图数或方向|
|冻结已结束构建|`freeze_review_pdf.py`|副本字节身份、页数、复制期间稳定；不判断构建成功|
|整页/局部导出|`../mathtranslation/scripts/capture_pdf_region.py`|PDF/PNG/来源JSON；不代表实际看过|
|应用已审提案|`apply_exact_repairs.py`|目标哈希、匹配次数、无重叠及备份；不证明数学正确|
|重编译回归|`compare_pdf_pages.py`|指定页对与DPI下RGB像素一致性、未映射页；不自动配页或授予目视通过|
|矩形截取的规则网格|`generate_clipped_lattice.py`|选定格模型的可编辑TikZ；模型与原图对应仍须审阅|

下例`<audit>`为本技能绝对目录，`<translation>`为已安装的mathtranslation目录；先确认本机路径，不照抄占位符。

## 盘点、冻结和裁图

```powershell
python '<audit>/scripts/inventory_diagrams.py' main.tex chapters/ch1.tex myarrows.sty --output review/inventory.json
python '<audit>/scripts/freeze_review_pdf.py' main.pdf --out review/frozen-01
python '<translation>/scripts/capture_pdf_region.py' review/frozen-01/review.pdf --page 17 --out review/page17 --dpi 120
python '<translation>/scripts/capture_pdf_region.py' review/frozen-01/review.pdf --page 17 --bbox 72 110 490 360 --out review/detail17 --dpi 600
```

构建退出并确认成功后才冻结。冻结目录必须不存在，生成`review.pdf`与`snapshot.json`（SHA256、页数、来源）；可加`--expected-sha256 HASH`绑定已知文件。复制时若输入变化，拒绝成功清单并写`INVALID.json`。它不能侦测将来恢复写入的暂停进程，不是文件锁或构建等待器。给代理的是冻结路径和哈希，不是活跃main.pdf。

裁图先实际打开整页，再量取PDF点坐标bbox、重渲染局部并打开。页码从1开始，表示物理页。保留侧车记录；旧裁框失配或截断时重取，不覆盖成“已看”状态。未安装裁图技能时可用现有PDF渲染工具实现同样的来源记录，不杜撰脚本路径。

## 精确替换：兼容原有格式

```json
{
  "source_sha256": "当前目标文件完整字节的SHA256",
  "replacements": [
    {"old": "旧文本\n", "new": "新文本\n", "expected_count": 1}
  ]
}
```

```powershell
python '<audit>/scripts/apply_exact_repairs.py' chapter.tex review/plan.json
python '<audit>/scripts/apply_exact_repairs.py' chapter.tex review/plan.json --apply --backup-dir review/backups
```

默认只预检，一个计划处理一个真实源文件。所有替换相对同一原始版本定位，拒绝哈希/次数不符、重叠及混合行尾；计划字符串UTF-8/LF，写回保留原BOM和LF/CRLF。先保存字节备份，再同目录临时文件替换；同文件编辑与构建串行。过期提案必须重新核对上下文，不能仅改哈希。工具不负责多文件事务；生成器项目改生成器。

## 页对回归：明确映射，不猜分页

原有`--pairs 12:12,13:14`命令继续可用，默认仍保存两版所有页图。新功能：

```powershell
# 仅在已确认同页对应且页数相同时使用；相同页数本身不证明对应
python '<audit>/scripts/compare_pdf_pages.py' before.pdf after.pdf --all --save changed --out review/regression-01 --dpi 120

# 范围两端长度须相同；新旧物理页可不同
python '<audit>/scripts/compare_pdf_pages.py' before.pdf after.pdf --pairs '1-633:1-633,641-660:643-662' --save none --out review/regression-02

# 用绑定PDF身份的文件保存人工确认的映射
python '<audit>/scripts/compare_pdf_pages.py' before.pdf after.pdf --pairs-file review/page-map.json --save changed --out review/regression-03
```

页对JSON：

```json
{
  "before_sha256": "...",
  "after_sha256": "...",
  "pairs": [{"before": 1, "after": 1}, {"before": 3, "after": 4}]
}
```

三种映射参数互斥。`--all`拒绝页数不同的文件；显式映射拒绝越界、重复旧页、重复新页和过期哈希，防止贪心配页重复使用同一新页。`comparison.json`总是列出`unmapped_before/unmapped_after`，`--require-complete`可拒绝未覆盖页。分拆/合并无法一对一对应时，保留这些未映射页另做直接审阅，不伪造页对。

`--save all|changed|none`只控制PNG落盘量，三者均渲染并保存每个页对的尺寸、RGB像素SHA256及`identical_pixels`；包括批注外观。`changed`只保存不一致页的两版PNG，`none`仅留JSON，便于全书比较。DPI允许36..600。新建输出目录，拒绝覆盖；渲染前后重验PDF哈希，竞态时写`INVALID.json`而不是成功报告。

像素相同只说明该页对在指定DPI下相同，不能证明原书内容正确，低dpi也可能漏细微差异。只有此前已实际看过且范围完整的图、页对已确认时，才能记录“图面一致沿用旧结论”。所有输出仍标`visual_review: not_performed`。不同也不等于数学错误，页眉/索引页码可能变化。变化图须重新定位、取完整局部并实际打开。

## 有限矩形中的规则格图

```powershell
python '<audit>/scripts/generate_clipped_lattice.py' --rows 6 --cols 7 --dx 3 --dy 2 --out review/lattice.tex --standalone
```

生成整数格点的映射`(i,j) -> (i+dx,j-dy)`，在外层格点围成的矩形内裁切连线，再画完整节点。保留进入有限节点的箭头头，向框外的边头在框外不显示；包含非节点边界短段。`--x-cm/--y-cm`调整实际格距，默认.55/.5 cm只是可调整初值，不能当原书比例。

仅适用于经源图验证符合该模型的示意图；不生成对象/标签、不推断任意双复形、不解决三维遮挡。输出拒绝覆盖，默认片段，`--standalone`可编译小样。图不能仅因生成器工作正常而标记源译一致；必须打开小样和最终书页，核对行列、步长、边界和可读性。

## 验证与兼容

`python -m unittest discover -s '<audit>/tests' -v`测试冻结竞态、显式映射、重复/越界/过期页对、未映射页、变化页保存及非节点交点。新增/修改生成图还应实际编译并目视，单元测试不能验证原书保真。现有inventory与exact-repair命令/计划格式保持不变；comparison旧字段保留，新增schema_version和未映射页字段。
