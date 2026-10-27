# 脚注保真审计 / latex-footnote-fidelity-audit

审计重排书，确保 OCR 记录的**每一条脚注**都真正进入了打印 PDF，并修复没能进入的那些。
适用场景：脚注引用被扫描器写成了奇怪形式（`$^3$`、`{~}^2`、`.^4`、`^{\textrm{5}}`、
`{}^{2}`、`\ldots^{7}`、Unicode 上标）、注文整段丢失、脚注带高于常规页阈值、或某个
`\index{}` 标记随丢失的注文一起消失。

> 平台无关 Agent Skill：以 `SKILL.md` 为准，`README.md` 仅供人读。

## 能力总览

| 能力 | 说明 | 入口 |
|---|---|---|
| 三类独立丢失模式 | 引用丢失 / 注文丢失 / 索引条目丢失，分开审计 | `SKILL.md`「Three independent loss modes」 |
| 引用形式归一 | 识别各种畸形上标写法并统一 | `scripts/footnote_survey.py` |
| 注文核对 | 逐条比对 OCR 原文与 PDF 实际注文 | `scripts/check_footnote_text.py` |
| 恢复后的两个新坑 | 只在脚注被补回后才暴露的排版/索引问题 | `SKILL.md`「Two traps」 |

## 核心纪律

- **每一条** OCR 记录到的脚注都必须能在打印 PDF 中找到，不能抽样。
- 引用与注文要配对核对；只补引用不补注文等于没修。
- `\index{}` 若挂在丢失的脚注里，索引条目也会一起丢，必须连带核查。
- 恢复脚注后要重编译并复查页码/版面，别引入新 overfull。
- 畸形上标不可"看着像"就改，必须先确认它对应的原书注号。

## 目录结构

```text
latex-footnote-fidelity-audit/
├── SKILL.md
└── scripts/
    ├── footnote_survey.py        脚注普查（引用/注文/形式）
    └── check_footnote_text.py    逐条比对 OCR 原文与 PDF 注文
```

## 脚本参考

| 脚本 | 用途 |
|---|---|
| `footnote_survey.py` | 普查脚注引用形式与分布，列出可疑项 |
| `check_footnote_text.py` | 逐条核对注文是否真正落到 PDF |

## 安装与调用

仓库内 `latex-footnote-fidelity-audit/` 即本技能目录。注册为 Agent 的 skill，或让
Agent 先读 `latex-footnote-fidelity-audit/SKILL.md`；支持 `$skill` 语法时用
`$latex-footnote-fidelity-audit`。

```text
使用 $latex-footnote-fidelity-audit 证明这本书 OCR 到的脚注一条没丢，
列出缺失项并修复。
```

## 边界

只保证"OCR 记录到 → PDF 打印出"这条链路不丢；若原书 OCR 本身就漏扫了脚注，本技能
无法凭空恢复，需回到扫描/OCR 环节。
