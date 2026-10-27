# 显示公式版面审计 / latex-display-layout-audit

对照**原书 PDF** 审计重排书的行间公式版面，并修复异常——过度折行、"假对齐"（把
`align` 误用作悬挂缩进）、显示环境套显示环境、`\text{}` 内的空格连字符——**且不改动
任何公式编号**。适用于读者指着某页公式说"和原书对比一下""奇奇怪怪的排版"的场景。

> 平台无关 Agent Skill：以 `SKILL.md` 为准，`README.md` 仅供人读。

## 能力总览

| 能力 | 说明 | 入口 |
|---|---|---|
| 定位原书页 | 先用公式里的独特片段搜源码，再取原书对应页/bbox | `SKILL.md`「第一原则：先拿到原书页」 |
| 判异常类型 | 跑扫描器区分折行 / 假对齐 / 嵌套环境 / 空格连字符 | `scripts/scan_layout_oddities.py` |
| 改写保编号 | 重排版面但**编号不变** | `SKILL.md`「步骤 3：改写」 |
| 批量小修 | 统一关闭 `\text{}` 内空格连字符 | `scripts/fix_hyphen_spacing.py` |
| 编译 + 视觉验证 | 编译后出对比图，几何量测为准 | `SKILL.md`「步骤 5 / 6」 |

## 核心纪律

- **保住公式编号是红线**：版面可以重排，编号与标签不得改变。
- 排版真值来自**几何量测**（原书像素坐标），不是"看起来差不多"。
- 裁剪原书页要先取 bbox 再 clip，不能整页缩放后目测。
- `align` 不是用来做悬挂缩进的；显示环境不得嵌套。
- 改完必须编译 + 出对比图，缺一不可。

## 目录结构

```text
latex-display-layout-audit/
├── SKILL.md
└── scripts/
    ├── scan_layout_oddities.py    扫嵌套显示环境 / 全 notag 编号环境
    └── fix_hyphen_spacing.py      关闭 \text{} 内空格连字符（自动备份、保留 CRLF）
```

## 脚本参考

| 脚本 | 用途 | 说明 |
|---|---|---|
| `scan_layout_oddities.py` | 扫 (A) 嵌套显示环境 / (B) 全 `notag` 编号环境 | 只读 |
| `fix_hyphen_spacing.py` | 关掉 `\text{}` 内空格连字符 | 自动备份、保留 CRLF |

## 安装与调用

仓库内 `latex-display-layout-audit/` 即本技能目录。注册为 Agent 的 skill，或让 Agent
先读 `latex-display-layout-audit/SKILL.md`；支持 `$skill` 语法时用
`$latex-display-layout-audit`。

```text
使用 $latex-display-layout-audit 对照原书检查这一页的公式版面，
只修排版、不要改任何编号，并给出原书与重排的对比图。
```

## 边界

只处理**版面**问题，不判断数学内容对错；编号映射与内容保真由其他审计技能负责。
