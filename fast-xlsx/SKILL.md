---
name: fast-xlsx
display_name_zh: 极速 Excel/XLSX 生成与处理
display_name_en: Fast XLSX Generator
description: >
  极速 Excel (.xlsx) 表格生成专属通道。当用户需要创建新 Excel 工作簿、从文本/数据/Markdown 中提取整理表格并导出为 .xlsx 时优先使用本 Skill。
  绕过官方繁复的多轮意图探测和逐单元格低效 MCP 通信，基于极速原生构建引擎在 0.1 秒内直接输出规范美观的专业 Excel 工作簿。
triggers:
  - 生成Excel
  - 导出excel
  - 做个表
  - 整理成表格
  - 导出xlsx
  - 新建表格
  - 做个excel
---

# Fast XLSX 极速表格生成指南

## 核心设计思想
传统 `workbuddy-sheetagent` 或 `workbuddy-sheet-generation` 会触发多轮子代理委派、公式试算以及逐格 RPC，生成一个表格往往需要数轮等待。

**本 Skill 采用原生直写快车道（Zero-Delay Fastpath）**：
1. **主 Agent 直接提取/整理数据**，组织为简单的 JSON 数据结构或 CSV 文件；
2. **本地脚本 0.05 秒落盘**：调用 `fast_xlsx_builder.py` 直接生成包含专业主题样式、自适应列宽、细边框、浅蓝表头的高清 `.xlsx` 工作簿；
3. **完成呈现**：调用 `present_files` 立即打开预览。

## 一键生成命令

### 方式 1：通过 JSON 数据直接生成（支持多工作表）

```bash
"C:\Users\asus\.workbuddy\binaries\python\versions\3.13.12\python.exe" "C:\Users\asus\.workbuddy\skills\fast-xlsx\scripts\fast_xlsx_builder.py" \
  --json-data "<JSON文件路径或JSON字符串>" \
  --output "<目标.xlsx绝对路径>"
```

JSON 格式示例：
```json
[
  {
    "name": "实验数据记录",
    "headers": ["波长 (nm)", "频率 (10^14 Hz)", "截止电压 (V)"],
    "rows": [
      [412, 7.282, -1.022],
      [433, 6.928, -0.869]
    ]
  }
]
```

### 方式 2：从 CSV 文件一键转换为美化 Excel

```bash
"C:\Users\asus\.workbuddy\binaries\python\versions\3.13.12\python.exe" "C:\Users\asus\.workbuddy\skills\fast-xlsx\scripts\fast_xlsx_builder.py" \
  --csv "<输入.csv绝对路径>" \
  --sheet-name "数据汇总" \
  --output "<目标.xlsx绝对路径>"
```

生成完毕后，调用 `present_files` 为用户呈递查看。
