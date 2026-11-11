# LaTeX 数学书重排工程 / latex-book-retypeset

为**高保真重排（re-typeset，非翻译）**沉淀的工程方法论与坑位库。它不绑定具体书目，
而是按原书类型给出可复用的做法：① Springer GTM 类西文书（共享 `gtmitem` 计数器、
原生 TikZ、CRLF 无 BOM、xelatex 构建）；② 中文数学书（xeCJK + Fandol + 自建 `cls`）；
③ 分章页码专著（`\chapcode` 版式，如 Serre《Abelian l-Adic Representations》）；
④ 单卷连续页码、按节裸编号专著（Samuel 类）。内容涵盖硬性纪律、坑位表、交叉引用
七轮补全、页码映射、验收门槛与终检脚本。

> 平台无关 Agent Skill：以 `SKILL.md` 为准，`README.md` 仅供人读。

## 能力总览

| 能力 | 说明 | 入口 |
|---|---|---|
| 西文书（GTM 类） | OCR 乱码、编号公式共享计数器错位、Claim 按章编号、overfull 修复 | `references/pitfalls.md` |
| 中文书（xeCJK） | TikZ 曲线 `plot[domain]` 失败转 `plot[smooth] coordinates`、Fandol 缺字回退、CJKglue 松排、biber 中文书目 | `references/cjk-retypeset.md` |
| 分章页码专著 | `\chapcode` 页码机制、`\pagestyle{empty}` 泄漏、`biblatex` sortkey、目录页码超链接 | `references/chapcode-retypeset.md` |
| 裸编号专著 | 按关键词/按节重启、`\folio` 只锁分部起点、`bib:n`/`exer:` 锚点、`.aux` 配平解析 | `references/samuel-style-retypeset.md` |
| 交叉引用补全 | 七轮递进策略 + 习题 label 安全重建 | `references/crossref.md` |
| 验收与终检 | 构建命令、验收清单、CRLF/BOM 检查、全书终检器 | `references/verification.md` |

## 核心纪律（红线）

- **0 LaTeX 错误 / 0 缺字符（`Missing character`）/ 0 未定义引用 / 无新增 overfull**。
- 源文件一律 **CRLF 行尾、无 BOM**；图形一律**原生 TikZ**，禁用位图替代。
- 物理页 = 书页 + 偏移，页码映射必须显式记录，不得凭感觉换算。
- 只编辑生成器/片段，不手改汇编产物；不删正文/公式/引用去"绕"编译错误。
- 编号正确性必须从**渲染 PDF 文本实抽**验证，不能只看退出码。

## 目录结构

```text
latex-book-retypeset/
├── SKILL.md
├── references/
│   ├── discipline.md            文档类/计数器速查、页码映射、文献区参数
│   ├── pitfalls.md              西文书坑位总表
│   ├── cjk-retypeset.md         中文书专项
│   ├── chapcode-retypeset.md    分章页码专著专项
│   ├── samuel-style-retypeset.md 单卷裸编号专著专项
│   ├── crossref.md              交叉引用七轮 + 习题重建 + 保留纯文本清单
│   ├── verification.md          构建命令、验收清单、CRLF/BOM 检查
│   ├── parallel-retypeset.md    有界并行与页级 OCR 来源
│   ├── narrow-ams-retypeset.md  窄栏 ams 环境排版
│   └── recalled-exams.md        中文回忆版试卷合集
└── scripts/
    ├── audit_text_refs.py        硬编码引用扫描器（只读清单）
    ├── audit_bare_xrefs.py       屏蔽已链接文本后的裸引用枚举
    ├── audit_internal_links.py   内部链接目标对 aux 全量核验
    ├── audit_log_4pass.py        4-pass 编译日志审计
    ├── rebuild_exercise_labels.py 习题 label 安全重建（默认 dry-run）
    ├── gen_tikz_curve.py         参数/笛卡尔/极坐标曲线 → plot[smooth] coordinates
    ├── verify_cjk_book.py        全书终检（?? / 书签 / 回填落点 / 文献 / 缺字符）
    ├── dump_page_heads.py        分章页码书页眉/页码 + 目录页码超链接终检
    └── check_link_color.py       PDF Link 矩形像素采样，断言链接颜色
```

## 脚本参考

| 脚本 | 用途 | 写盘 |
|---|---|---|
| `audit_text_refs.py` | 扫描 `.tex` 中尚未 `\ref` 化的硬编码引用 | 只读 |
| `audit_bare_xrefs.py` | 枚举 STMT/PAREN/FORM/BIB/EXERC 各类裸引用 | 只读 |
| `audit_internal_links.py` | 校验 `\ref/\eqref/\pageref/\hyperref` 目标是否存在于 aux | 只读 |
| `audit_log_4pass.py` | 四轮编译日志逐轮判定 | 只读 |
| `rebuild_exercise_labels.py` | 安全重建 `exercise:c.s.i` | 默认 dry-run |
| `gen_tikz_curve.py` | 生成 `plot[smooth] coordinates` 曲线片段 | 输出片段 |
| `verify_cjk_book.py` | 全书终检 | 只读 |
| `dump_page_heads.py` | 逐页导出顶/底文本带，核对页眉页码 | 只读 |
| `check_link_color.py` | 渲染 PDF 后对 Link 矩形采样，防 `\hypersetup` 后写覆盖 | 只读 |

## 安装与调用

仓库内 `latex-book-retypeset/` 即本技能目录。注册为 Agent 的 skill，或让 Agent 先读
`latex-book-retypeset/SKILL.md`；支持 `$skill` 语法时用 `$latex-book-retypeset`。

```text
使用 $latex-book-retypeset 按 GTM 类西文书流程重排这本书，
守住 0 错误/0 缺字符/0 未定义引用，并用终检脚本给出证据。
```

## 边界

不适用于 `mathtranslation` 类纯翻译项目（那类走翻译模板体系）。重排要求"忠于原书、
不改内容"；任何疑似原书错误的修正都必须单独记录并经确认。
