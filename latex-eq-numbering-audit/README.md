# 公式编号审计 / latex-eq-numbering-audit

对照**原书印刷本**审计重排书的公式编号，报告**并修复**具体章节与缺失编号。适用场景：
标签与渲染编号不一致、编号行间公式被压成行内文字、章首节未重启计数器、原书用罗马
数字 `(i)(ii)(iii)` 却排成了阿拉伯数字。方法核心是**四个独立来源交叉投票**，而不是
只信单一信号。

> 平台无关 Agent Skill：以 `SKILL.md` 为准，`README.md` 仅供人读。

## 能力总览

| 能力 | 说明 | 入口 |
|---|---|---|
| 内部一致性（免费且精确） | 自己重算计数器，比对 `\label` 与渲染值 | `scripts/audit_eq_numbering.py` |
| 原书真值（像素） | 渲染原书对应页/条带做几何核对 | `scripts/render_orig_strip.py`、`scripts/find_orig_page.py` |
| 采集原书标签带 | 从原书页右缘采收 `(n)` 编号带（常一锤定音） | `scripts/textlayer_eqseq.py` |
| 四源投票 | 内部 / 像素 / 标签带 / 结构 交叉定案 | `scripts/triangulate_eqnums.py` |
| 编号带量测 | 量测右缘标签带的几何与间隙特征 | `scripts/probe_eq_tags.py` |
| 节级核对 | 校验节结构与编号重启点 | `scripts/verify_sections.py` |

## 核心纪律

- 编号结论必须来自**渲染 PDF 文本**或原书像素，不能只看源码 `\label`。
- 原书罗马数字标签要保留其形式，不得统一改成阿拉伯数字。
- 四源不一致时**不得强行收敛**；标注为未决，给出各源证据。
- 修复编号时不得改动公式内容与数学语义。
- 工具的残余 `layer-diff` 差异要逐条判"良性/真缺陷"，不能一概当噪声。

## 目录结构

```text
latex-eq-numbering-audit/
├── SKILL.md
└── scripts/
    ├── audit_eq_numbering.py     Step 1：精确的内部一致性检查
    ├── textlayer_eqseq.py        Step 3：采收原书右缘标签带
    ├── triangulate_eqnums.py     四源投票（消费 _orig_struct.json）
    ├── probe_eq_tags.py          量测 PDF 右缘标签带（几何 + 间隙特征）
    ├── render_orig_strip.py      渲染原书标签带/整页供目检
    ├── find_orig_page.py         定位原书对应页
    └── verify_sections.py        节结构与编号重启核对
```

## 脚本参考

| 脚本 | 用途 |
|---|---|
| `audit_eq_numbering.py` | Step 1：精确内部一致性检查 |
| `textlayer_eqseq.py` | Step 3：从原书采收右缘 `(n)` 标签带 |
| `triangulate_eqnums.py` | 四源投票定案 |
| `probe_eq_tags.py` | 量测右缘标签带几何 |
| `render_orig_strip.py` | 渲染原书标签带 / 整页 |
| `find_orig_page.py` | 定位原书对应页 |
| `verify_sections.py` | 节结构与重启点核对 |

## 安装与调用

仓库内 `latex-eq-numbering-audit/` 即本技能目录。注册为 Agent 的 skill，或让 Agent
先读 `latex-eq-numbering-audit/SKILL.md`；支持 `$skill` 语法时用
`$latex-eq-numbering-audit`。

```text
使用 $latex-eq-numbering-audit 对照原书核对第 3 章的公式编号，
逐条给出四源证据，只修编号、不改公式内容。
```

## 边界

不判断数学正确性，只保证"编号与原书一一对应"。若原书本身印错编号，按原样保留并记录，
不擅自"修正"。
