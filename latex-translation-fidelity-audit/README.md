# 译文保真审计 / latex-translation-fidelity-audit

审计重排的**中文 LaTeX 译稿**对原书的保真度。先查**结构保真**（相对原书目录整节缺失、
未超链接的跨章裸引用如 `§VI.7.2` / `习题~VI.6.5` / `[VI.6.16]`、`.aux` 里"打印编号 vs
hyperref 锚点"错配陷阱、每节习题标题缺失或畸形、未翻译的节标题、静默丢字、索引过期、
FandolFang 缺粗体回退），再查**词汇/数学保真**（算符宏 `Frob`/`Nm`、fraktur 字母、
残留未译英文、数字/度数误译、按节数学簇等价）。适用于读者已报错、交付前终审、或
"全面审查"一个数学翻译项目。

> 平台无关 Agent Skill：以 `SKILL.md` 为准，`README.md` 仅供人读。

## 能力总览

| 能力 | 说明 | 入口 |
|---|---|---|
| 结构保真 F1–F9 | 节数对齐 / 裸跨章引用 / 编号映射 / 习题标题 / 未译标题 / 丢字 / 索引 / 重复 label / 中文强调 | `SKILL.md`「First: structural & cross-reference fidelity」 |
| 编号映射 | 从**打印编号**而非 hyperref 锚点建映射 | `scripts/aux_number_map.py` |
| 裸引用扫描 | 找从未超链接的跨章引用 | `scripts/xref_bare_scan.py` |
| 节级对齐 | 与原书目录逐节比对 | `scripts/section_parity.py` |
| 算符宏审计 | `Frob`/`Nm` 等宏是否正确渲染 | `scripts/operator_macro_scan.py` |
| fraktur 审计 | 𝔭 𝔪 𝔞 … 等花体字母保真 | `scripts/fraktur_audit.py` |
| 残留英文 | 找未翻译的英文散文 | `scripts/residual_english_scan.py` |
| 数学簇等价 | 按节比对公式簇（尽力而为） | `scripts/math_cluster_audit.py` |
| 上下文查看 | 定位问题所在上下文 | `scripts/show_context.py`、`scripts/extract_pdf_text.py` |

## 核心纪律

- **结构保真优先**：整节缺失比个别错字严重得多，先跑结构检查。
- 编号映射必须来自 `.aux` 的**打印编号**，不能拿 hyperref 锚点当编号。
- `$` 配平是脆弱的：`\erratum{}` 之类内嵌 `$` 会造成误判，需特殊处理。
- `Missing character` 必须为 **0**；静默丢字不可接受。
- 索引可能"构建成功但已过期"，要看实际生成结果，不看退出码。
- 新增 label 前先 grep 查重，改完再查 `undefined`。

## 目录结构

```text
latex-translation-fidelity-audit/
├── SKILL.md
└── scripts/
    ├── section_parity.py          与原书目录逐节对齐
    ├── xref_bare_scan.py          裸跨章引用扫描
    ├── aux_number_map.py          从 .aux 建"打印编号→锚点"映射
    ├── operator_macro_scan.py     算符宏（Frob/Nm…）审计
    ├── fraktur_audit.py           fraktur 花体字母保真
    ├── residual_english_scan.py   残留未译英文
    ├── math_cluster_audit.py      按节数学簇等价（尽力而为）
    ├── show_context.py            展示问题上下文
    └── extract_pdf_text.py        抽取 PDF 文本供比对
```

## 脚本参考

| 脚本 | 用途 |
|---|---|
| `section_parity.py` | 节数与标题对齐原书目录 |
| `xref_bare_scan.py` | 扫描从未超链接的跨章引用 |
| `aux_number_map.py` | 从 `.aux` 构建编号映射（取打印编号） |
| `operator_macro_scan.py` | 检查算符宏渲染是否正确 |
| `fraktur_audit.py` | 检查 fraktur 字母是否保真 |
| `residual_english_scan.py` | 找残留英文散文 |
| `math_cluster_audit.py` | 按节比对数学簇 |
| `show_context.py` | 打印问题附近上下文 |
| `extract_pdf_text.py` | 抽取 PDF 文本 |

## 安装与调用

仓库内 `latex-translation-fidelity-audit/` 即本技能目录。注册为 Agent 的 skill，或让
Agent 先读 `latex-translation-fidelity-audit/SKILL.md`；支持 `$skill` 语法时用
`$latex-translation-fidelity-audit`。

```text
使用 $latex-translation-fidelity-audit 全面审查这个中文译本，
先查整节缺失与裸跨章引用，再查算符宏与残留英文，给出证据。
```

## 边界

不替代译者判断：数学内容是否"译对"仍需领域知识。本技能提供的是**可核查的偏差清单**
与证据，不等于"已证明译文正确"。
