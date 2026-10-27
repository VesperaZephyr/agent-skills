# OCR 数学缺陷审计 / latex-ocr-math-defect-audit

找出并修复 **OCR 层在进入重排 LaTeX 之前就已悄悄损坏**的数学，并证明没有残留。适用
场景：读者说"公式看着怪怪的"，尤其是**脚注里的公式**被弄坏——积分被盗进指数、区域积分
的下标丢失、集合构造记法的花括号错位、微分落在数学环境之外、或整个词被排进了数学。
核心判断：**原书页面图像**才是权威，OCR dump 不是。

> 平台无关 Agent Skill：以 `SKILL.md` 为准，`README.md` 仅供人读。

## 能力总览

| 能力 | 说明 | 入口 |
|---|---|---|
| 四类缺陷 | 积分入指数 / 积分下标丢失 / 花括号错位 / 微分与整词入数学 | `SKILL.md`「The four defect classes」 |
| 全文扫描 | 不止四类，跑全文 pass 才能发现更多 | `SKILL.md`「Beyond the four」 |
| 散文层拼写扫描 | 没有词典时用自举法找疑似错字 | `SKILL.md`「bootstrap spell scan」 |
| 数学审计 | LaTeX 结构缺陷伪装成 OCR 缺陷 | `scripts/mathaudit.py` |
| 脚注数学 | 脚注里的公式单独审 | `scripts/fnaudit.py`、`scripts/fndump.py`、`scripts/fnshow.py` |

## 核心纪律

- 判定"是不是 OCR 错"时，以**原书页图**为准；OCR dump 只是候选。
- 不要"看着像就改"：先区分真缺陷与误报（见误报目录）。
- 数学结构缺陷可能不是 OCR 造成，而是 LaTeX 转写引入，需分别归因。
- 自己的扫描器也有 bug，任何告警都要人工复核后再动。
- 修复后必须重跑扫描，证明缺陷为零，而不是"改完了"。

## 目录结构

```text
latex-ocr-math-defect-audit/
├── SKILL.md
└── scripts/
    ├── mathaudit.py     全文数学缺陷扫描
    ├── fnaudit.py       脚注数学缺陷审计
    ├── fndump.py        导出脚注数学供核对
    └── fnshow.py        展示单条脚注上下文
```

## 脚本参考

| 脚本 | 用途 |
|---|---|
| `mathaudit.py` | 全文扫描数学缺陷候选 |
| `fnaudit.py` | 脚注内数学缺陷专项审计 |
| `fndump.py` | 导出脚注数学文本供对照原书 |
| `fnshow.py` | 展示指定脚注的上下文 |

## 安装与调用

仓库内 `latex-ocr-math-defect-audit/` 即本技能目录。注册为 Agent 的 skill，或让 Agent
先读 `latex-ocr-math-defect-audit/SKILL.md`；支持 `$skill` 语法时用
`$latex-ocr-math-defect-audit`。

```text
使用 $latex-ocr-math-defect-audit 检查这本书 OCR 引入的公式错误，
重点看脚注里的积分，逐条对照原书页图。
```

## 边界

需要原书页图作为判据；纯文本环境下只能给出"疑似"，不能宣称已修复。数学语义正确性
仍需领域知识判断。
