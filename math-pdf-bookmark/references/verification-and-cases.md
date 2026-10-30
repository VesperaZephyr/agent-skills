### 验收（ROUTE R / P / P-CN / P-TXT / P-IMG / C / H 共用）
**ROUTE P-CN（三源交叉的中文扫描本）的八道闸门**，缺一道就可能有真错放行：
① 印刷目录白名单（条目集合/层级/folio 的唯一权威）· ② MISS=0 ·
③ `页码偏差直方图 = {0: N}` · ④ G0 标题卫生（控制字符/度量垃圾/点线/首尾空格）·
⑤ G1(a) 目录编号 vs 正文实证 + G1(b) 章节编号连续 · ⑥ **G1(c) 题名有序逐字差分**（查漏字，集合式查不出）·
⑦ **G1(d) 空隙逐字实测**（查空格印没印，只有跨 span 可信）· ⑧ G2 `(page, 墨顶)` 单调 +
G3 `ink_audit --every 1` 全量看图 + **回读活树 vs 报告** + **负对照**。
详见下面"ROUTE P-CN 变体（吉田中译本）"一节。

`python verify_r.py <pdf> --tag xx` → A 结构（levels/page-top/oor/nonmono/dirty）+ B ink（逐条
`[y+3, y+16]` 必须有墨、`[y-14, y-2]` 必须基本无墨）+ C **contact sheet 12 条一张，逐张用眼睛看**。
**优先用 `references/ink_audit.py <pdf> [--x0 48] [--x1 505] [--out prefix]`（硬规则 10）**：它按"落点上方是否有短标题带"逐条判分，
171/171 这种全量结论比"标题上下有无墨"强得多，且自带 contact sheet。
**它的六条判据都是被假阳性逼出来的**（文件头 docstring 逐条写了证据，改动前必读）：
① 落点＝读回的 `to.y`，**不要再加一次 shift**；② 取带窗口要**比带宽**（`landing-40..+70`，窗口窄了
灰度分位阈值跟着变，整个窗口并成一条巨带 → 假 NO-BAND）；③ **`--x0/--x1` 是文字块的边界不是页宽**
（stein 中译本块右沿 457、folio 在 461..484，不砍掉版心外就把每条都判 BAD，`--x1 455`）；
④ **尘埃带不算带**（左簇 <15 pt 或高 <3 pt 直接跳过——2.2×0.4 pt 的一个斑点曾在 引言 上方 0.3 pt 处
把完美锚点判成 BAD）；⑤ **线宽取带顶 11 pt**（标题与下一行正文并成 29 pt 巨带时整带宽，
但顶部那一截是标题自己），层级 ≥2 用 `gap≤8 且 顶宽≤265 pt` 把关；⑥ **lvl1 允许落在带内**
（章标题字大、上方空气里仍有 1–4% 暗像素，带顶会比锚点高 15 pt）；
⑦ **`--maxhead` 是语言相关的**：265 pt 只对中文书成立（中文标题短），英文 ALL-CAPS 节标题合法宽度
270–320 pt，不传 `--maxhead 340` 会把 16 条完美锚点判成 BAD（Lang 实测）；
⑧ **`--tilex1` 决定 contact sheet 的右边界**（默认 330 pt）——宽标题的书必须给到 400，
否则图上根本看不到标题右半，"看图验收"变成假验收。**中文书也可能撞线**：
《101泛函分析》24 字长标题 `3.2 开映射定理、逆算子定理、闭图像定理和共鸣定理` 合法宽 **342 pt**，
`--maxhead 360 --tilex1 420` 才 57/57（抬上限必须**同时**抬图宽）。
⚠️ 别用"按峰值密度砍掉淡行"来治 ⑤/⑥——短标题比并进下面的正文行**淡得多**，砍完把标题本身吃掉
（p67 `2.1 例子` 就是这样从 BAD 变成 NO-BAND 的，已回滚并写进 docstring）。
⑨ **`--every N`（本轮新增）＝每条第几张出图**，默认 6；**逐条看图用 `--every 1`**。
⚠️ 参数必须 `int(float(...))` 解析，否则 `range(0, n, 4.0)` 直接 TypeError。
⚠️ **但 ink 审计全 PASS ≠ 锚点正确**：它**分不清标题和页眉 running head**（页眉也是版心内的一条短墨带）。
《101泛函分析》旧树 12 条页眉锚（y≈42–44）**全部通过审计**，是 `页码偏差直方图` ＋逐条看图才抓住的。
⇒ **页眉/页脚过滤要写在定位器里**（`y1 ≤ 0.10*H or y0 ≥ 0.90*H` 整条扔），审计只做兜底（硬规则 11）。
工具可信度用**三方对照**证明：stein 中译本 119/119 通过、Ahlfors 中译本 171/171（改动后**无回归**）、
Lang 英文原版 125/125（`--maxhead 340 --tilex1 400`，加参数后中文两本仍 119/171 不变）、
《101泛函分析》57/57（`--every` 新参数加完后本书仍 57/57，**非回归**）、
张恭庆《复分析》上册 page-top 控制组仍抓到 2/36（**不会把真错也放过去**）。
`python sheet.py <pdf> <tag> <idxfile>` 只拼**子集**（补看某几条时不必重出 12 张）。
`python missdiag.py <pdf> <report>` 逐条打印候选行，并把该页字高最大的前 6 行标 `*BIG*`——
定位失败先看它，比猜阈值快得多。
- **`label_folio_check.py` 只查"标题里带 `[n]`"的条目**，所以对大多数书它等于只查了标题卫生 + 编号空洞。
  **阅读页码必须逐条证**：把印刷目录转录表（`lvl num exp folio title`）与**从文件读回的树**逐条比对，
  模板 = `_工作产物/Terse/_ts_folio.py`（手解 `/PageLabels`；两级匹配键：先节号、后"只留字母"）。
  没有这张表就退化成抽查，`bm_quality` 的 `labels` 列只数段数、**不证明段数对**。
- **落盘前的旧树字节体检**（判据 ⑤）：
  `sum(1 for _,t,_,_ in doc.get_toc() if re.search(r'[\x00-\x08]', t))` —— 非 0 即不交付。
  Terse 89/89 条拖 `\x00` 而条目集与页码全对，**差集查不出来**。
  ⚠️ 写这类"控制字符类"正则时别把 `\x00` 直接嵌进源码字符串里（heredoc 改行容易写出真 NUL，
  文件立刻 `SyntaxError: source code cannot contain null bytes`）——用
  `''.join(chr(c) for c in range(0x00,9)+...)` 拼，或整文件重写。
- ⚠️ **每道新写的闸门都要跑一次负对照**（拿已知的脏文件喂给它，必须报错）：
  `_ts_folio.py` 跑 `_pre1` 旧树 → `DIRTY-TITLE 89/89`、`problem=90`，跑成品 → `problem=0`。
  只看"成品 0 problem"不能证明闸门在干活。
- ⚠️ 打分链 `if/elif` 之前必须 `s = 0.0`，否则候选行 0 分时 `UnboundLocalError: local variable 's'`。
- ⚠️ `get_toc(simple=False)` 的 dest 里 `'to'` 是 **`Point` 对象**：取 `.y`，`['y']` / `.get()` 都会抛。
实测本轮：Ahlfors 英文 172 条、Alpay 136 条（ROUTE R），Schiff 140 条（ROUTE P），
Ahlfors 中译本 171 条（ROUTE P-TXT，`ink_audit` 171/171 全量通过），
stein《复分析》中译本 119 条（ROUTE P-IMG，`ink_audit --x1 455` **119/119**，35 张 contact sheet 逐条看过）。
**《101泛函分析》57 条**（泛函分析子目录第一本，ROUTE H REJECT → ROUTE P-TXT 变体：目标页锁定＋旧树交叉核对，
`ink_audit --maxhead 360 --tilex1 420` **57/57** ＋ `--every 1` 57 张**逐条**看过，`{0:55, 1:2}` 两条 +1＝**目录印错**）。
**Lax 英文 218 条**（P-TXT-EN 变体，`ink_audit` 218/218、14 张拼版逐条看过）·
**Bogachev《TVS》109 条**（变体 2，109/109、7 张拼版）·
**De Gruyter《Terse》89 条**（变体 3 born-digital，`ink_audit --maxhead 340 --tilex1 400 --every 1`
即 **89/89**、6 张拼版逐条看完、`_ts_folio.py` 逐条 folio 全等、回读 `max|落点-目标| = 0.000 pt`；
默认 265 会把 3 条长英文标题（宽 297/311/325 pt）误判 BAD，**是已知语言标定假阳性、不是回归**）。
**孙永生《泛函分析讲义》54 条**（泛函分析 lane B 第一本，ROUTE P-CN；`ink_audit --every 1` **54/54**、
4 张拼版逐条看过、`gap` 全在 `−0.3..+0.4 pt`、`_sy_folio.py` 230 页 +1 游程 + 逐条 label 全等；
本书把 `ink_audit` 逼出 **rule 8 灰度封顶**，见硬规则 10①）。
**吉田耕作《泛函分析》中译本第6版 160 条**（lane B 第二本，ROUTE P-CN 变体：三源交叉＋八道闸门，
`ink_audit --every 1` **160/160 bad=0**、10 张拼版逐条看过、`{0:160}`、回读 160/160 一致、
`_jz_folio.py` 508 页 K=15 mismatch=0、负对照 7 处注入缺陷被三道闸分别抓到；
新增长句 **硬规则 15「OCR 字符框只有跨 span 可信」** 与闸门 **G1(c) 有序差分 / G1(d) 空隙实测**）。
**吉田《Functional Analysis》英文第6版 157 条**（泛函分析 lane B 第三本，ROUTE P-TXT-EN 变体 4；
`ink_audit --maxhead 315 --every 1` **157/157**、10 张拼版逐条看完、`{0:157}`、回读 157/157、
坐实 **索引区双偏移**（缺扫空白折页 → `+17`/`+16` 两段）与"页注入只有回读能抓"；见变体 4 一节）。
**Stein–Shakarchi《Functional Analysis》Princeton 2011 152 条**（泛函分析 lane B 第四本，P-TXT-EN 变体 5 born-digital；
`ink_audit --x0 30 --x1 358 --maxhead 345 --every 1` **150/152 ok + 2 条章扉页碎带假 BAD 看图裁决**、
10 张拼版 152 tile 逐张看完、`{0:152}`、独立回读 `max|落点−ink| = 0.0001 pt`、
负对照 y 注入被 ink_audit **放行**/页注入被抓——与 Yosida 互补 ⇒ **回读仍是唯一全闸**、
出版商 `/PageLabels` 14 点核对未重写、`bm_quality` OK；见变体 5 一节）。
**Helemskii《Lectures and exercises on functional analysis》AMS TMM 233 58 条**（泛函分析 lane B 第五本，P-TXT-EN 变体 6；
OCR 字号全废 ⇒ 无字号门槛判别器、RH 提前印节名 ⇒ y 带过滤、扫描器重扫 folio 218/219 跨页 ⇒ K=15/17 双偏移＋五段页码标签、
`ink_audit --dpi 150 --every 1` **58/58 ok**、4 张拼版逐张看完、`{0:58}`、回读 58/58、
负对照 ink_audit **双放行**仅回读抓住、`bm_quality` OK；见变体 6 一节）。
**张恭庆/郭懋正《泛函分析讲义》下册 59 条**（泛函分析 lane B 第六本，ROUTE P-CN 变体；
垃圾 OCR 字号全废 ⇒ y 带＋中文数字章号＋整 token 编号（`(?![\d.])` 治习题号 `5.1.1`）＋CJK 覆盖率≥0.7、
folio 证据＝文字层 341 条 `·N·` 行全部 `p=fol+14`、页码标签 4 段（符号表/目录两段罗马各自重启）、
`ink_audit --every 1` **59/59 ok**、4 张拼版逐张看完、`{0:59}`、回读 `0.0000 pt`、
负对照恰 2 处被回读抓到（ink_audit 也双抓）、`bm_quality` OK；见 ROUTE P-CN 变体节）。
以上各本均 0 MISS / 0 page-top / 0 dirty / 单调，Schiff 0 ink 失败；Ahlfors 报了 29 条 ink 失败，
**全是假阳性**（该书行距极紧，标题上方 2–14 pt 带里本来就有上一行正文的墨）→ ink 只是初筛，
**结论以看图为准**。
⚠️ Schiff 的 `/PageLabels` 出版商已经写对（p1–16 罗马、p17 起阿拉伯 1），补标签前先
`get_page_labels()` 核对，别盲目重写。


## Page labels — 让阅读器页码 == 原书印刷页码
`doc.set_page_labels([{'startpage':P(0-based！), 'prefix':'', 'style':S, 'firstpagenum':N}, ...])`，
`S`：`'r'/'R'` 罗马、`'D'` 阿拉伯、`'a'/'A'` 字母。
⚠️ **`startpage` 是 0-based 的 `doc` 下标**（本轮实测坐实：Alpay 印刷页 1 在物理第 13 页 →
必须写 12；写 13 会让 `doc[12].get_label()` 直接抛 IndexError，阅读器整本偏一页。
Schiff 出版商 `{0,'R',1},{16,'D',1}`、Alpay `{0,'C'…},{2,'r',1},{12,'D',1}`、
Conway `{1,'r',2},{16,'D',1},{410,'a',1}` 三份现存标签都按此读）。
下面各例的 `p…` 也都是 `doc[p]` 下标。分段规则（Conway 实测）：
- 前置：`{'startpage':1,'style':'r','firstpagenum':2}` ⇒ 封面记为 `ii`，这样**每一张印了 folio 的页**
  阅读器数字都和书面一致（p6→vii、p15→xvi）。
- 正文：`{'startpage':16,'style':'D','firstpagenum':1}` ⇒ p16→1、p42→27、p409→394。
- 尾部**无页码**的插页（丛书目录、封底）：`{'startpage':410,'style':'a','firstpagenum':1}` ⇒ a/b/c，
  永远不会被误认为书面页码。
  ⚠️ **但"没有 folio"要分两种**（Lang 实测）：出版社**附加页**（丛书目录/郑重声明/封底）用字母段；
  而**编号内容的续页**（索引最后几页、编号文献表——书面只是不印页码，页码序列本身还在）必须
  **续十进制**（`{'startpage':499,'style':'D','firstpagenum':486}`），否则阅读器给读者 a/b/c/d，
  与书面 486..489 的位置感不符。判据：看这几页的**内容**是不是前面编号页的延续，别看有没有 folio。
- 前置罗马段**可能要两段**：扫描里常缺页（Lang 印刷 `viii` 整页不在），于是要
  `{1:'r',1}` 管 i..vii + `{8:'r',9}` 管 ix..xiv，一段并到底会让后面的 folio 全体偏 1。
校验：自己写 `label_of(p)`（本 PyMuPDF 版本**没有** `get_label_value`，罗马/字母要手写转换），
逐点打印 `p→label` 对照印刷页码；书签 `page` 字段永远是物理页，页码标签只改**显示**。
⚠️ **别只从目录条目推段**：前置不编号的书（Alpay）目录里一条罗马页码都没有，
纯目录推导会把封面标成"1"、把书面 `vii…x` 那几页标成 8–12。正确做法见 ROUTE H 第 8 条
（`heading_scan.roman_front()`：页眉/页脚带里"逐页 +1 的罗马游程"反推 `startpage`）。
**批量补标签**（库里 ~75 本 `add-labels`，不走 ROUTE H 的书）用
`python references/folio_runs.py <pdf> [<pdf> …]`：全本做同一套"逐页 +1 游程"反推，
阿拉伯段＋罗马段一起给，并把出版商已有标签并排打出来供人工核对（只读，不落盘）。

## 无损写入路径（中文文件名必读）
`shutil.copy2(SRC, "C:/Users/asus/_x_tmp.pdf")`（ASCII 路径，避开 fitz 的路径编码坑和跨盘
WinError 17）→ `set_toc` / `set_page_labels` → `doc.saveIncr()` → `shutil.move(tmp, SRC)`。
写前先 `shutil.copy2` 到 `F:/大学/数字资源/数学/_bm_rerun_backup/<相对路径>/<name>_pre1.pdf`。
写完必须 `fitz.open(SRC).get_toc(simple=False)` 复验条数、dest、页数不变。

⚠️ **三件写回时的硬坑（Lang 实测，每一条都会静默写坏）**：
1. **dest 必须是 python `float`**。`set_toc` 的第 4 字段若塞进 numpy 标量（`np.float64`，
   墨迹带测量 `top = cy0 + rows[0]/SC` 算出来的就是它），PyMuPDF **不报错**，但写出的 dest 变成
   垃圾（读回 `to.y = 630.14 = 页高 − 36.0`）。Lang 125 条里 4 条被这样写坏，只有读回才发现。
   → 凡是经过 numpy 运算的 y，写入前一律 `float(y)`；写完断言 `max|landing − asked| < 0.05`。
2. **`set_toc` 不允许层级跳级**（`ValueError: bad hierarchy level in row N`）。印刷目录里
   `Appendix` 是 1 级、它下面的 `§1…§7` 是 3 级时，必须 `lv = min(intended, prev_lv + 1)` 夹一下，
   并把夹后的层级写进 toc（Lang 附录 7 条）。
3. **封面/封底段不要给 `style` 键**。`{"style": "No Style"}` 会让 `set_page_labels` 抛
   `FzErrorSyntax: invalid key in dict`；出版商原文件里这两段本来就**没有** style，照抄即可。
4. **备份只存最初的原件**：`if not os.path.exists(BAK): shutil.copy2(PDF, BAK)`。
   无条件 copy2 会在第二次重跑时把"已经写过一轮书签"的文件当成原件存进备份，回滚点就没了。


## 视觉验收（不许只读数字）
`references/scan_verify.py` 两件事：
1. **ink check**：对**每一条**书签，渲染 `[y, y+60]` 带必须有暗像素（>0.004），
   `[y-55, y-5]` 带必须基本空白（<0.02）——证明落点确实在标题行而不是页顶。
2. **contact sheet**：每条裁 `[y-18, y+78]` 长条，21 条一张拼版，条目标红字
   `L<level> p<page> (printed <label>) y=<y>  <title>`，然后用 Read 工具**逐张用眼睛看**。
   数字只证明脚本自洽，看图才证明书签真的落在标题上。

## Critical gotchas (tlbmk.py / 通用)
- `_split_page_number`：对**单 span 行**访问 `row[-2]` 会越界崩溃 → `if len(row) < 2: return row, None`。
  宽松路径才会触发；崩溃时该书保持 0 书签而非写坏。
- 目录页可能含后续分册内容 → 连续 10 条定位不到即截断，避免把"下册目录"挂到本册。
- worklist 顺序会漂移：重跑时**不要**用旧日志的索引指认某本书，永远按路径核对。
- 若某本在旧日志显示很多书签、实测 0 → 多半是 worklist 顺序漂移指到别书，或该书 40+ 页是公式非目录（搜不到"目录"字样即图像目录，需另做"仅前台 OCR"）。
- **GBK 控制台**：打印 `§` / `é` / `–` 会 `UnicodeEncodeError` 中断整份报告 →
  脚本开头 `sys.stdout.reconfigure(encoding='utf-8', errors='replace')`，长报告落文件再看。
- **Write 工具会二次转义**：想写 Cesàro / H^p 的上标时，常落成字面的反斜杠转义序列
  （如 `\\u02b0`）而不是真字符；涉及非 ASCII 的目录数据一律手写真实字符，
  写完 `grep -n '\\\\u'` 一遍确认没漏，再靠 Python 侧断言（K 一致、条数对）兜底。
- 比较 dest 时 `Point > int` 会 `TypeError` → 先 `dest['to'].y` 取值再比。
- **page-top 的判据是 `to.y <= 0.5`**：`y=1.0 / 3.5 / 5.8` 可能是印刷就顶到版心的章号，不是缺陷，
  别为了凑"0 page-top"把它们改掉。
- 备份不在 PDF 旁边：`next_bak()` 写到 `_bm_rerun_backup/<相对路径>/<name>_preN.pdf`。
  重跑几次就会攒出 `_pre2/_pre3`（内容可能完全相同），找不到备份先怀疑自己来错目录，
  **绝不要**因此删掉现存备份。
- `fitz` 导入会打 `deprecated, use pymupdf` 警告，无害；报告落文件时记得 `2>/dev/null`。
- 章起始页常**没有**页眉页码 → 页码审计要把"无 folio"单列，不能算 mismatch。
- **DPI 与坐标缩放要逐本确认**：只有当 `page.rect` 恰好等于扫描原生像素尺寸时（Conway 2242×3857）
  才能用 dpi=72 让 1 px == 1 pt。普通中文教材 `page.rect`≈524×734，必须 200 dpi 渲染并
  `SC = 72/200 = 0.36` 缩放 OCR 框，否则所有 y 都偏大 2.8 倍、"看起来对"但整本落点全错。
- **contact sheet 拼版时每条的 crop 文件名必须唯一**：PyMuPDF 按文件名缓存图片，
  复用同一个 `crop.png` 会让 21 张拼版全是同一张图（我第一次就这样白看了一遍）。
- 中文标题里的**全角/半角**、以及旧列表遗留的控制字符，都会让"字符串比较"静默失效；
  凡是用标题做匹配/过滤，先归一化再比（见 Phase 6 第 2、7 条）。
- **`bm_quality.py <路径>` 的参数是目录不是 PDF**：传单个 PDF 会得到 `PDFs: 0 / REWORK: 0`，
  看着像"没问题"其实是**一本都没扫**（本轮实测踩过）。"0 异常"只有在确认它扫到了 N 本之后才算数。
- **`get_toc()` 默认 `simple=True` 只给 3 元组**（没有 dest），所以"看起来这本书没有 y"；
  验 y 一律 `get_toc(simple=False)`，行是 `[lv, title, page, dest]`（page 在 `r[2]`，`dest['to']` 是 Point，
  ⚠️ `to` 是 Point 不是 dict，别写 `to['page']`）。
- **共享工具的默认输出落在用户主目录**：`ink_audit.py` → `C:/Users/asus/_ink_audit.txt` + `_ink_audit_sheet_*.png`，
  `shift_probe.py` → `_shiftprobe.txt`。**每轮收尾 `ls C:/Users/asus | grep '^_'` 必须为空**：
  报告 `.txt` 移进 `_工作产物/<书>/` 并改成自说明的文件名（例：`_旧树ink_audit-12条页眉锚全PASS.txt`
  ——它就是硬规则 11"ink 审计分不清页眉与标题"的证据），截图与 contact sheet 直接删。
- **⚠️ 大字号标题的 bbox 顶 ≠ 墨顶（`ink_audit` rule 7）**：42–47 pt 章号 / 23.5 pt 粗体大写标题，
  文字层 bbox 顶比自己的墨顶高 **6–21 pt**（Lax 章 22/26 实测 39.6 vs 59.8）。旧版把这类全判 `NO-BAND`
  （46 条假失败）。现在 `ink_audit` 在 `pick is None` 时才启用 rule 7（`--leadabove`，默认 24 pt，
  且要求 `b[1]>=12` 字号 + `b[4]>=15` 宽度），**已通过的旧书不受影响**。
- **`env VAR=… python …` 在 Git Bash 里会吞掉 stdout**（看着像脚本没输出）→ 用 `VAR=… python …` 前置赋值。
- **`page.get_pixmap(dpi=…)` 的 dpi 必须是 int**：传 `300.0` 直接 `TypeError`；条带裁片同理。
- **"PDF 有 /PageLabels" ≠ "页码标签是对的"**：Lax 英文本自带的标签就是错的。
  凡设标签，一律逐页读书面 folio 重新推分段，写回后 `get_page_labels()` + 抽查 `page.get_label()` 读回。
- **干净文字层也可能单字符乱码**（`8 function` = `δ function`、`Muntz` = `Müntz`、`B.l` = `B.1`）：
  字符串比对、`bm_quality`、`ink_audit` **三道都拦不住**，只有逐条看图能发现 →
  这就是"写完必须看图"要**全量 `--every 1`**、不能抽样的理由（Lax 218 条 14 张拼版全看完，改出 12 处）。
- **⚠️ 书签落在"章编号行"还是"章名行"，只有 ink 审计能替你发现**（Bogachev《TVS》5 个章全 BAD）：
  `CHAPTER 1`(10.9 pt) + 章名(14.35 pt) 两行式开场白，去空格比对时 `chapter1introduction…`
  会以 `a.startswith(b)` 命中 `CHAPTER1` 那行、章名行反而 0 分。落点给编号行不仅读者体验差，
  而且 10.9 pt 字的墨带只有 7.9 pt，过不了 `ink_audit` 的 L1 判据 `h >= 8.0` →
  **章条目要先剥掉 `^Chapter\s+\d+\.` 再比，并把候选字号下限抬到 `bs + 1.0`**。
- **⚠️ 凡是"编号由脚本自己排"的书（目录摘要段展开成 `N.M(i)`），必须跑 G1(a)**：
  词元相似度对 `(i)` vs `(ii)` 完全不敏感（0.98 相似照样命中），唯一防线是把目录标题的编号前缀
  和正文所匹配行的编号前缀**逐条比对**。Bogachev 实测 98 条带编号、0 错，才敢写盘。
- **`y < 50` 不能当"这是页眉"的判据**：Bogachev 的 `Author index`(y=37.6) / `Subject index`(y=40.0)
  是 14.35 pt 大标题、那两页根本没有页眉 → 一刀切会 MISS=2。判页眉要用**字号**
  （`sz < bs - 0.4`，或 `y < 50 and sz < bs + 1.0`）。
- **后记区（Comments/Bibliography/Index）的 folio 常在另一个 span**（`x >= 360`），
  不在标题行尾部 → 正则组是 `None`，`int(f)+K` 直接 `TypeError`；写 `f = m.group(2) or str(folio)`。
- **⚠️ 罗马前 folio 会跳号**（Bogachev p8=vii → p9=**ix**，viii 不存在，缺空白折页）：
  页码标签必须**四段**、第三段专管跳号（`{'startpage': 8, 'style': 'r', 'firstpagenum': 9}`），
  否则跳号之后阅读器页码全体比书面 folio 小 1。
- **`label_folio_check.py` 的编号空洞检查会误报**：`N.M(i)` 子标题曾被并进父组 →
  假 `HOLE dup=True`（Bogachev 5 章全中）。已改为罗马号单独成组（`groups=5(+5 罗马组)`）。
  见到 `dup=True, missing=[]` 先怀疑检查器，别怀疑书签。

## 环境差异（Qoder 侧与旧 WorkBuddy 文档不一致，实测为准）
- Bash **可以**启动 PowerShell：`powershell -NoProfile -ExecutionPolicy Bypass -File winocr.ps1 ...` 正常。
- F: 盘删除并不慢（实测 0.058 s），但**仍需**先备份、仍**不许**碰 `_bm_rerun_backup`；
  工程产物归到 `F:/大学/数字资源/数学/_工作产物/`（`ocr/` 存 OCR dump，报告 CSV 同级）。
- **精品单本的归档单位是"一本书一个目录"**：`_工作产物/<书名>/` 放 ①专用脚本 ②那份**人眼转录的
  条目表**（`_cw_toc.py` / `_lh_build.py` 里的 `E` 表——丢了就要重新盯目录页，比丢 OCR 更贵）
  ③最终 locate/verify 报告 ④旧书签清单（`_old_*.txt`，证明"重做前是什么样"）。
  **contact sheet、页面截图、行级 dump 一律不归档**——它们从 PDF 几秒就能重生成，留着只是占地方。
- **通用工具（`reanchor / verify_r / sheet / missdiag / bm_quality / inkband / cn_* / routeP_* / scan_*`）
  只在 skill 的 `references/` 存一份**；`C:/Users/asus/` 里的工作副本做完就删，
  换书时从 references 复制成 `_<书>_xxx.py` 再改顶部常量。
- 删任何"看起来是中间产物"的 PDF 副本前，先用 fitz 比 **TOC＋page labels＋页数**和库内原件是否一致
  （例：`_narasimhan_tmp.pdf` 26 MB 就是这样核对后才确认是上一轮写回忘了删的副本）。
- 删除任何 OCR 产物前，必须先确认该层**已回拷进库内原文件**（逐本 `get_text()` 非空核对），
  本次删 14.76 GB 前核了 68 本。

## Deliverable / report
收尾给用户：总 PDF 数、总书签数、本管线产出书数量、剩余 0 书签清单（标明哪些是可 OCR 救回的
正规书、哪些确实无目录）。**批量任务**额外给 `bm_quality.py` 的 verdict 直方图（page-top / flat / dirty-title / add-labels / OK / EMPTY），
并把 CSV 落到 `_工作产物/`。
**单本任务**给：条数与层级构成、K、页码标签分段、验收结论（ink 0 失败 + 看图确认）、字节增量、
**以及所有被丢弃/被改写的旧条目**（出版社后置项、错页、错字、LaTeX 残迹）——这些是用户会逐条查的地方。
绝不谎称 100% 覆盖。


## ROUTE P-TXT 变体：表示论文件夹的快速候选重建（2026-10-28）

适用于有可搜索文字层、印刷目录可读的数学书目录重做。表示论文件夹本轮得到一份已写回实证和三份已审核候选：冯克勤教材 53 条已写回；《群的表示和特征标》36 条、《模表示论讲义_cde三角》36 条、《表示论入门_Muke》25 条仅生成候选并逐条验收，按用户指示未写入原件。候选验收数据不可报告成原件已完成。

### 快速而可复核的流程

1. **先做印刷目录白名单。** 一行一条，记录原文标题、显式层级、目录页码和顺序。目录决定书签集合、标题和层级；旧树仅用于提供候选页/坐标、发现差异。目录只有一层就保留一层，不从章节编号推断未印出的层级。目录中的编号属于标题时，书签文字要带上编号。
2. **一次提取，按页缓存。** 对文字层逐页提取 text/span，建立物理页索引；每条目录项只在目录页码映射得到的候选正文页附近查询并复核。不要在逐条匹配循环中反复扫描整本 PDF。表示论文件夹中，重复全书扫描拖慢了流程；改用缓存索引后继续批量比对，候选书签分别 36、36、25 条全部定位成功。
3. **把目录页码当线索，不当真值。** 由印刷页码、已有 PageLabels 和实测 folio 顺序缩小候选范围，再以正文标题行确定物理页和 y。若目录与正文矛盾，逐条核对 folio 连续性和正文，保存可指名的差异；确认后书签跟正文标题走，并在交付中说明目录错页。模表示论讲义_cde三角有 5 条目录页码与正文页不一致。
4. **旧树与正文逐项比对。** 旧树看似齐全也可能页码偏一页、缺目录编号或混入非目录条目。《群的表示和特征标》旧树多出的“目录”不是印刷内容目录的正文项目，应排除；《表示论入门_Muke》旧树 4 条分别比正文标题早一物理页，应按正文重锚。保留已有页码标签并核对写前写后完全一致；Muke 原有 3 段标签不可顺手重写。
5. **校准必须实测。** 对目标落点 y 与 y+37 分别写入探针，拟合该条目的 landing=k*input+b，按逆变换写候选值，再从 get_toc(simple=False) 读回比较。不要把一个 PDF 或一页的单点 shift 外推给别的页面。上述 97 条候选的最大回读误差小于 0.00005 pt。
6. **检测逐条，拼版可读全标题。** 墨迹检测使用 --every 1；contact sheet 的裁剪范围必须包含标题完整左边缘和编号。Muke 拼版曾裁去一部分左侧编号，虽不影响 y，但会妨碍人工判断。逐张查看候选拼版，确认红线落在正文标题而非页眉、正文行或标题下方的着色定理框。检测 PASS 不能代替人工分类。
7. **候选与原件分开验收。** 写回前确认原件未变，创建字节级备份；写回后重新打开 PDF，断言 TOC 条数、层级、标题、页码和 y 均与白名单一致，并核查页数、PageLabels、元数据、页面几何和内容载荷没有意外变化。中途暂停时保留候选和报告，明确标记原件仍未写回，不要把候选状态写成完成。

### 本轮证据与留档

- 《群的表示和特征标》405 页：印刷目录 36 项，一级结构；候选审计 36/36。
- 《模表示论讲义_cde三角》13 页：36 项，L1 15 / L2 21；候选审计 36/36；5 处目录页码偏差逐条留档。
- 《表示论入门_Muke》49 页：25 项，L1 2 / L2 23；候选审计 25/25；修正旧树 4 条早一物理页，原 3 段 PageLabels 保持。
- 三份候选均以正文标题为落点，人工审完 8 张拼版。相关转录、定位、校准、ink 与差异文件在 F:/大学/数字资源/数学/_工作产物/ 对应书名目录；目前只有冯克勤教材的原件已写回。
