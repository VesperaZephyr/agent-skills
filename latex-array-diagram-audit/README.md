# 交换图保真审计 / latex-array-diagram-audit

对照出版源审查并修复数学"箭头—节点"图：既包括直接写成 `tikzcd` 的图，也包括藏在
`array` / `aligned` / `matrix` 或自定义宏里、容易被漏掉的图。核对缺失的单射钩、反向
箭头、端点、标签、空节点/零行与最终渲染；在无法查看图片时也能给出可复现的结构化结论。

> 平台无关 Agent Skill：以 `SKILL.md` 为准，`README.md` 仅供人读。

## 能力总览

| 能力 | 说明 | 入口 |
|---|---|---|
| 绘制交换图 | 先列边清单，再落箭头；优先 `tikzcd` 原生重绘 | `SKILL.md`「先写边清单，再写箭头」 |
| 逐边保真审计 | 方向、端点、单射钩侧、双头/等号/无头、标签侧、空节点与零行 | `SKILL.md`「箭头样式必须真实出现」 |
| 隐藏图盘点 | `array`/`aligned`/`matrix`/宏里的图一并纳入候选 | `scripts/inventory_diagrams.py` |
| 无视觉校验 | 看图失败时改用源栅格 + 边表 + PDF 文本/矢量证据 | `references/no-vision-verification.md` |

## 核心纪律

- `r/l/u/d` 只描述**位置**，不是数学方向；`hook'` 改的是钩的**侧**，不是边方向。
- 标签里的 `\hookrightarrow` 字形，或被后置 `rightarrow` 覆盖的 `hook` 选项，**都不会**渲染出单射钩。
- 环境名或"候选计数"本身不能证明审过；必须给出结构 / 几何 / 直观三重结论。
- 看图工具报错不等于模型没有视觉能力；先排查图片路径与查看器。
- 视觉保真**不能**只凭编译通过或 OCR 文本认定。

## 目录结构

```text
latex-array-diagram-audit/
├── SKILL.md
├── references/
│   └── no-vision-verification.md     无视觉能力时的核查流程
└── scripts/
    └── inventory_diagrams.py         盘点真实构建链中的所有图候选
```

## 安装与调用

仓库内 `latex-array-diagram-audit/` 即本技能目录。把该目录注册为 Agent 的 skill，
或让 Agent 先读 `latex-array-diagram-audit/SKILL.md`；支持 `$skill` 语法时用
`$latex-array-diagram-audit`。

```text
使用 $latex-array-diagram-audit 对照原书核对这一章的交换图，
逐边检查箭头方向、端点与单射钩，并说明哪些细节无法确认。
```

## 边界

编译成功、候选数相等都不等于图正确；几何量测与源图比对才算证据。无法看图时，
必须把"结构性核查 / 几何核查 / 直接视觉核查"分开报告，未核实项明确标注未验证。
