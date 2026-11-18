# 验收与构建：LaTeX 数学书重排

---

## 1. 构建命令

按工程实际构建入口操作。以下以 D: 盘的 TeX Live 和需要三遍 XeLaTeX 的 GTM 工程为例。

```bash
export PATH="/d/texlive/2026/bin/windows:$PATH"
cd /path/to/project

# 常规 3 遍（解析交叉引用与目录）
xelatex -interaction=batchmode main.tex
xelatex -interaction=batchmode main.tex
xelatex -interaction=batchmode main.tex
```

**改动 label 命名 / 大批量替换后**，必须清空辅助文件再编 4 遍（坑 D）：

```bash
rm -f main.aux main.out main.toc main.log
xelatex -interaction=batchmode main.tex   # ×4
```

> 注：项目在 F: 盘；E: 盘 `rm` 有配额/极慢问题，但项目自身生成的 `aux/out/toc/log`
> 属可重建产物，直接 `rm -f` 安全。若系统拒绝，用 `os.replace()` 归拢到 `_scratch/`。

**类里用 `fontspec` 时不能用 pdflatex**（报 `fontspec requires XeTeX or LuaTeX`）。
这类项目直接 `lualatex -interaction=nonstopmode main.tex` × 2–3；`latexmk` 若残留旧 fdb
仍可能拉 pdflatex，必要时绕过 latexmk 直接调用。Samuel 项目实测 2 遍即稳定。

---

## 2. 终局验收清单

| 指标 | 合格线 | 核查方式 |
|---|---|---|
| 构建命令退出码 | 工程构建各轮全 0 | `echo $?` 每遍 |
| errors | 0 | `grep -c "!" main.log` |
| multiply defined | 0 | `grep -c "multiply defined" main.log` |
| undefined references | 0 | `grep -c "undefined references" main.log` |
| Rerun / 需重跑 | 0 | `rg -c "Rerun to get|Please rerun|Warning:.*[Rr]erun" main.log` |
| hyperref 死链 | 0 | `grep -c "does not exist" main.log` |
| 习题内容和编号 | 与原书题干、子问、原印编号和共用条件逐项对应 | 见 §4 |
| CRLF / BOM | 全合规 | 见 §5 |

GTM 96 历史构建样例为 436 页，4 遍 exit=0，Overfull 65（持平未新增），标签 1828 个且无重复。这些是当时的结构指标。按原书逐句审阅和检查 PDF 实际链接语义时，另用[内容审阅流程](content-audit.md)。

---

## 3. 死链 / 冲突快速定位

```bash
grep -n "does not exist" main.log          # hyperref 死链锚点
grep -n "multiply defined" main.log         # 重复 label
grep -n "undefined references" main.log     # 未定义引用
```

---

## 4. 习题内容和编号核对

先按原图逐节列出实有题号、题目身份、共用说明和子问。再核对 TeX 和成品的显示编号、题干与链接。序列扫描可提示漏题、错号或解析错误；原书连续编号的节才适用连续性断言。原书跳号照录并登记。题数和编号序列均相同时，仍须核跨页、末题和同号题的题干。

---

## 5. 行尾 / BOM 检查

按工程要求检查源文件的行尾和编码。以下示例用于独立构建目录中要求 **CRLF + UTF-8 无 BOM** 的 `.tex` 文件。

```python
import pathlib
for p in pathlib.Path('.').rglob('*.tex'):
    b = p.read_bytes()
    if b[:3] == b'\xef\xbb\xbf':
        p.write_bytes(b[3:])                 # 去 BOM
    p.write_bytes(p.read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n'))
```

对本轮实际构建的源文件按同一约定检查。

---

## 6. 纯文本保留项审计

按原书与编辑约定建立纯文本引用清单，注明每项保留原因。审计脚本对照清单逐项核验；当数量变化时回查具体条目及目标。


日志检查须排除正常包信息（例如 Package: rerunfilecheck ... Rerun checks ...）；只匹配真实重跑告警。PDF 死链还须遍历 Link 注释的 GoTo/D 与最终 named destinations，不能只靠日志或 get_links 的页号检查。详见 [Ahlfors 并行与页级核验经验](parallel-retypeset.md)。

---

## 7. 内部链接与颜色（单卷裸编号书）

```bash
python scripts/audit_internal_links.py --aux main.aux --root .   # 0 missing
python scripts/audit_bare_xrefs.py chapters/*.tex back/*.tex     # 逐条判定残留
python scripts/check_link_color.py main.pdf --expect 0,0,178     # 像素采样
```

- `audit_internal_links.py` 覆盖 `\ref/\eqref/\pageref/\hyperref[...]`；只查 `\ref` 会漏掉
  大量 `\hyperref`（Samuel 项目 229 个 `\ref` vs 846 个总链接）。
- `audit_bare_xrefs.py` 先整段屏蔽 `\hyperref[...]{...}`（花括号配平）与数学，
  否则已链接文本会全部误报；`\[...\]` 的屏蔽必须 `re.S`。
- 颜色不能以源码 `colorlinks` 为准：多处 `\hypersetup` 后者覆盖前者，
  实测曾出现源码写 colorlinks、PDF 却是纯红。`check_link_color.py` 渲染链接矩形、
  统计非白像素直方图，`blue!70!black` = `(0,0,178)`。
