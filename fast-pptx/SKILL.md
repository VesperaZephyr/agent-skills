---
name: fast-pptx
display_name_zh: 极速 PPTX 演示文稿生成
display_name_en: Fast PPTX Generator
description: >
  极速 PPT (.pptx) 生成专属通道。当用户需要快速制作、生成、导出汇报幻灯片、学术报告 PPT、演示文稿或大纲 PPT 时优先使用本 Skill。
  跳过官方冗长的逐页 VLM 视觉检测轮询及多轮需求追问，采用大纲/页面 DSL 一次性批量组装模式，
  调用本地配套脚本在数秒内合成完整 .pptx，大幅提升演示文稿产出效率。
triggers:
  - 做PPT
  - 生成PPT
  - 制作PPT
  - 幻灯片
  - pptx
  - 演示文稿
---

# Fast PPTX 极速演示文稿生成指南

## 核心设计思想
传统 `workbuddy-pptx` 流程为：多轮需求提问 -> 写 STORY.md -> 写 DESIGN.md -> 单页写 DSL -> 调用 `slidep upsert-dsl` -> 调用 `slidep lint --visual`（VLM截屏送检）-> 逐页修复，每页耗时 1~2 分钟，整套 PPT 往往需要 10~15 分钟。

**本 Skill 采用批量装配快车道（Batch Fastpath）**：
1. **主 Agent 一次性规划结构**：依据用户主题直接生成页面 DSL（放入临时 `slides/01.slide`, `slides/02.slide` 等）；
2. **本地脚本一键装配**：调用 `fast_build_pptx.py` 脚本，在 2~3 秒内将全部页面依次注入 `.pptx`；
3. **完成呈现**：调用 `present_files` 立即打开预览。

## 一键批量合成命令

```bash
"C:\Users\asus\.workbuddy\binaries\python\versions\3.13.12\python.exe" "C:\Users\asus\.workbuddy\skills\fast-pptx\scripts\fast_build_pptx.py" --slides-dir "<包含01.slide等文件的目录>" --output "<目标.pptx路径>"
```

## Slide DSL 核心结构范例（极简稳定语法）

每页保存为一个 `.slide` 文件（如 `01.slide`）：

```markdown
# 页面标题文字

## 副标题或分类标注

- 核心要点 1：详细论述与数据支撑
- 核心要点 2：量化指标与成果说明
- 核心要点 3：后续行动或结论总结
```

装配完成后，使用 `present_files` 为用户打开预览面板。
