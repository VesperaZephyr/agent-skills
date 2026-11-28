# 全书索引审阅总账

## 先锁定审阅范围

1. 按原书版次和主索引、符号索引各建一份总账。从扫描页逐栏抄录完整词头路径、印刷页与物理页、每个引页的字重，以及 `see` 和 `see also` 的目标。跨栏和跨页的续项要接回原词头，无页码父项也要登记。用旧表和 OCR 帮助定位，遇到字重、缩进或字符疑点时看原书页图。比较已知旧分母并解释差异，按实际扫描确定范围。
2. 冻结原书 PDF 和本批用于比较的现有 PDF。登记后固定原书行号与编号。已有结论要按相同原书路径和引页找到记录，核对证据和版本后才写成已审。聚合数和相似词只作定位线索。
3. 主审按页、栏和实际工作量把互斥编号分给各审阅者。审阅者先读原书，再打开冻结稿，在自己的分表填写结论和依据。新增疑点回到既有编号，涉及其他分表时交主审统一判定。主审串行合并，并让复核人对高风险项和边界抽查，如同页不同义、粗体、续栏、转引和前言罗马页码。

## 集中修改与两道验收

- **内容审阅**逐项核对原书引页的正文语境和当前对应位置，标为 `match`、`repair` 或 `exception`。原书疑误、体例调整等例外须给出依据和处置。准备好相关父子词头的修订，再预检并集中修改。只有需要回答排版、分页、构建失败等具体问题时才提前重编。留一次最终完整构建及索引收敛检查。
- **成品验收**独立登记最后一份 PDF 的可见索引，从原书到成品检查漏项，从成品回查来源或补充理由。每个引页应核对目标页语义、显示页码、字重和实际链接，转引核对可见词头与目标，页面记录版面检查依据。构建结果、内容覆盖和最终验收分别报告。最后一份 PDF 发生变化时重新对照页码、链接和涉及的版面，保留仍有效的语义审阅记录。只有原书与成品两边的记录都关闭，才报告全书终审完成。

## 工具

`scripts/index_review_ledger.py` 使用 Python 3.9+ 标准库。它登记人工从索引页转录的数据，分派互斥编号，合并审阅分表，检查待核清单和最终 PDF 证据。每份转录文件代表一个索引页，格式如下。

```text
left|ideal|vii 1
left|ideal > primary|*21
right|domain|see: integral domain
right|fibre|branch:
```

空行及以 `#` 开头的注释可用。罗马页码用小写，粗体页码前加 `*`，范围拆为各个实际引页，转引可用 `see-also:`。编号由索引页物理页、转录行号和该行引页次序组成。冻结后沿用 CSV 中的编号。

```text
python index_review_ledger.py inventory audit.csv source original.pdf --page 317 332 source-317.txt
python index_review_ledger.py assign audit.csv reviewer-a.csv reviewer-a source 317 --column left
python index_review_ledger.py merge audit.csv reviewer-a.csv
python index_review_ledger.py status audit.csv --pending
python index_review_ledger.py status audit.csv --gate source
python index_review_ledger.py inventory audit.csv final final.pdf --page 303 317 final-303.txt
python index_review_ledger.py assign audit.csv final-a.csv final-reviewer-a final 303
python index_review_ledger.py status audit.csv --gate final --pdf final.pdf
```

每个 `--page` 参数依次填写印刷页标签、从 1 起算的物理页、转录文件。登记某一侧时，通过重复 `--page` 一次传入该侧的所有索引页。分表只编辑审阅栏。分派和合并由主审串行操作，审阅者只写自己的分表。对已有结论重新裁决或补填最终证据时，主审可在最新分表基础上明确使用 `merge --replace-review`。如需重发分表，可按指定编号从当前总账复制相同列和行。给成品换版用 `inventory … final … --replace-final`，重新分派成品行并补填证据。

- `evidence` 填基线版本、原书和稿件的正文位置及判断依据。成品侧的 `decision` 可填 `match`、`addition` 或 `exception`，新增检索入口应说明正文依据。
- `counterpart` 填空格分隔的另一侧编号，双向互填。原书 `match` 和 `repair` 必须有成品对应行。确有例外或新增时可以留空并解释。
- `final_evidence` 记录最终可见词头、字重、页码和语义落点，或例外在成品中的处理。 `visual_evidence` 记录已看过的索引页或版面检查记录。 `link_check` 填 `match` 或 `not-applicable`，页码链接不适用时在证据栏说明理由。 `verified_pdf_sha256` 填所核验 PDF 的实际哈希。主审合并原书侧和成品侧的最新记录后再运行最终检查。

工具只检查已登记记录的唯一性、分派冲突、必填证据、双向对应及最终 PDF 版本。页数范围、转录完整性、证据真假和数学语义由审阅者根据扫描页及成品核验。

<a id="final-evidence"></a>

## 最终版如何取证

1. 从最终 PDF 登记每个可见引页、字重、转引及父项。由原书正文语境和已核实的基线映射建立双向对应。相似词、页码接近或同页共现只生成候选。逐项确认重命名、层级调整和多对一合并，特别留意同页不同义。新增入口须记录正文段落或节导览依据。区分原书误引后省略与已有证据支持的改引。
2. 逐项比较定义字重与正文用途。原书粗体若落在导言或节标题，先查正文。改正定义引页后，同词头的其他常规引页仍需复核。Matsumura 终审中，0-étale 的定义页补回粗体，同一词头的另一处讨论仍为常规体。
3. 从 PDF 链接注释矩形读取可见页码，解析实际目标（包括命名目标），比较目标页标签。转录与注释按索引物理页比较页码及出现次数，发现漏链、额外链接或计数差异时回看位置。重复标签还须核对目标分部与物理页。文本转引检查目标词头能否找到。页标签吻合只证明跳页，正文语义仍须另查。
4. 打开最后一版索引的页图检查缩进、粗体、长词换行、续栏续页及裁切。重建后重新绑定 PDF 哈希并刷新位置证据。报告分别列出生成器输入、成品可见记录、实际链接和未决项。门禁通过表示字段和对应关系齐备，模糊配对和自动摘录须经复核才可作为结论。

### 索引链接批查工具

安装 PyMuPDF 后运行：

```text
python <mathtranslation>/scripts/audit_index_pdf_links.py final.pdf audit.csv --output index-links.csv
```

输入为带最终 PDF 哈希的独立成品总账。CSV 记录注释编号、目标物理页、页标签和检查状态。工具按索引物理页比较页码出现次数，发现漏链、多链、错链或无法分类的注释时返回非零。同页有可点击的非页码转引、单个注释覆盖若干页码、PDF 缺少合适的页标签或目标页标签重复时，应按明细复核版式和实际目标。工具不判断正文语义或转录覆盖范围。
