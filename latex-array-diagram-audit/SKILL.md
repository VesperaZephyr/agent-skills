---
name: latex-array-diagram-audit
description: Audit and repair mathematical arrow-and-node diagrams against the published source, including diagrams hidden in array/aligned/matrix or macros and existing tikzcd diagrams. Check missing injection hooks, reversed arrows, endpoints, labels, zero rows, and rendering. Use for drawing or reviewing commutative diagrams and when image inspection is unavailable; distinguish verified facts from unresolved visual details.
metadata:
  agent_created: true
---

# 交换图绘制与保真审校

目标是原书与译稿的节点、边、方向及特殊箭头一致。`tikzcd` 能编译、图看起来像矩形、正文数学通顺，都不能证明交换图正确。

## 绘制与审校的入口

- 新画、修复或迁移交换图、态射图、正合列网格，使用 `tikzcd`，保留原书节点位置、空格位、零行/列、标签和边的类型。不要默认用 `array` 拼图。
- 审校已有稿时，先列出**全部实际编译源码**的图候选，包括脚注/附录和被调用的图宏；不能只搜 `tikzcd`，也不能把 `array` 全部归入“公式”而跳过。
- 运行 `scripts/inventory_diagrams.py <compiled-files...> --output inventory.json`。该脚本列出环境及宏候选，只做定位，不自动认证方向或将所有 `array` 改成图。逐项分类：真正的图、公式/表格、宏待展开、未决；记录原书对应物理页与译稿位置。
- 扫描范围包括 `array`、`aligned/alignedat`、`matrix/smallmatrix`、`CD`、`xymatrix`、旧 XY/TikZ 图以及 `tikzcd`；另查箭头字形、`\Big\downarrow`、`\overset`、手工连线和自定义图宏。源码内有节点和映射关系即进入审校，不以环境名作为排除条件。

## 先写边清单，再写箭头

分别从原书和译稿建立节点网格及有向边表，避免用译稿推测原图后“比对自己”。每条边至少记录：原节点、目标节点、单/双箭头头、单射钩所在端、实/虚线、等号/无头线、标签及其侧别、曲线/平行偏移、证据与结论。行/列交换、遗漏前导/尾随零、漏整行及错误的空节点，都按结构差异处理。

写 `\arrow[r]` 前确认“当前单元格是什么节点、右边是什么节点”。`u/d/l/r`、`ur/dl`、多步 `rr/dd` 是几何目标，不是从数学直觉猜出的方向。检查 `from`/`to`、命名节点、`leftarrow`/反向端点样式；实际箭头头可能与位置方向相反。复杂图优先显式 `from=1-1,to=2-2`。`hook'` 改钩的侧别，不负责反转映射。

## 箭头样式必须真实出现

| 原图关系 | 常见写法 | 要检查的细节 |
|---|---|---|
| 单射 | `\arrow[r, hook]` | 源端有钩，目标端有箭头头；必要时按原图换 `hook'` |
| 满射 | `\arrow[r, two heads]` | 目标端确有双头，不能只是普通头 |
| 等同/双线 | `\arrow[r, equal]` | 双线及无头符合原图，不随意改成双向箭头 |
| 无头连线 | `\arrow[r, dash]` | 两端均无头；不能因为是包含关系就擅自加箭头 |
| 有向虚线 | `\arrow[r, dashed]` | 虚线与方向都保留；`dash` 与 `dashed` 不同 |

原书出现 `\hookrightarrow`，不意味着译稿的普通 `\arrow[r]` 会自动带钩。把 `\hookrightarrow` 写进节点或箭头标签也不能改变边样式。检查局部选项与 `\tikzcdset`、`every arrow/.style`、`arrows={...}`、自定义样式的叠加次序；例如 `hook, rightarrow` 中后者可重置尾端使钩消失。孤立小样与最终书页都要核验，不能只数源码的 `hook` 关键词。

## 证据、页码与视觉能力

- 原书 PDF 是可见内容的权威；原始 TeX、文字层和 OCR 是辅助证据。语义能排除不合理的映射，不能单独证明原书箭头的方向或样式。
- AUX 可给出译本陈述的印刷页，**不自动给出原书页，更不保证证明里的图就在该页**。分别标定原书/译稿页码，用图前后文字、节点和陈述定位；不要沿用另一本书的固定偏移。
- 视觉可用：原图与译图并排查看，整图确认结构，再对钩/双头等微细部位作高分辨率裁剪检查。保存物理页、裁剪框和逐边结论。
- 视觉不可用或显示调用失败：阅读 [references/no-vision-verification.md](references/no-vision-verification.md)，继续源码网格/边清单、文本跨度和 PDF 几何核验；细节不能确认时保留未决。工具失败或返回过滤信息本身不证明模型没有视觉能力。

## 验收

1. 全量候选已分类，残留 `array` 等真正的图已迁移或有明确、授权的保留理由；普通公式矩阵不乱改。
2. 每条边均有原书证据；节点、方向、标签与样式逐项对应，宏/全局样式没有绕过检查。
3. 按项目现有构建流程重编译，确认无图相关错误及新溢出，最终页无碰撞、截断、漏钩/双头；检查图引用和编号保持正确。
4. 报告分别说明结构核验、PDF 几何核验、直接目视核验的范围。未决方向/钩不能写成“交换图全部通过”；不能识图时尤其不能把编译成功当视觉通过。

保留源码编码、行尾、现有类和宏约定；同文件编辑串行并校验替换次数。验证图可先孤立编译，但最终必须在原项目样式中验证。保留验收证据，不在交付前无差别删除裁剪图和清单。
