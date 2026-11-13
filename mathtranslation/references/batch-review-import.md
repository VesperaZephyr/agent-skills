# 批量登记原书清单

`scripts/import_review_units.py` 将已由审阅者建立的源单位清单批量登记到
`scripts/review_ledger.py init` 创建的台账。它只登记清单，不能审阅原书、判断
译文、推断闭包横线、完成页面挑战或认证最终PDF。既有项目使用不同CSV结构时，
先按含义转换并人工校对，不要仅凭相似列名套用。

准备 UTF-8 CSV，必填 `unit_id,source_physical_page,kind`，可选
`source_region,source_identifier,translation_tex_file`；不接受状态字段。
物理页必须在台账范围内，ID在台账及本CSV中均须唯一。示例：

```csv
unit_id,source_physical_page,kind,source_region,source_identifier
P12-001,12,heading,top,Section heading
P12-002,12,formula,body,Equation 1
```

```text
python scripts/review_ledger.py init --source SOURCE.pdf --translation FROZEN.pdf --ledger-dir REVIEW_DIR --edition EDITION --build-entrypoint BUILD_COMMAND
python scripts/import_review_units.py --ledger-dir REVIEW_DIR --csv inventory.csv
python scripts/import_review_units.py --ledger-dir REVIEW_DIR --csv inventory.csv --apply
python scripts/review_ledger.py report --ledger-dir REVIEW_DIR
```

第二行仅预览；第三行经全文件校验后写入。写入前两个CSV的原件保存为台账目录下
`bulk-import-backup-<id>/`，发生普通写入异常时尝试回滚；意外中断时可使用备份
恢复并检查两个CSV。禁止多个进程同时写同一台账；相对 `translation_tex_file`
路径相对于输入CSV所在目录解析。所有导入条目初始为 `not_started` /
`not_checked`，页面审阅状态保持不变；后续按照真实证据使用 `mark-unit` 和
`mark-page`，不得把“登记成功”写成“审阅通过”。
