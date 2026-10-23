# 验收与构建：LaTeX 数学书重排

---

## 1. 构建命令

TeX Live 在 D: 盘（本机保留），PATH 需显式前置：

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
| XeLaTeX 退出码 | 4 遍全 0 | `echo $?` 每遍 |
| errors | 0 | `grep -c "!" main.log` |
| multiply defined | 0 | `grep -c "multiply defined" main.log` |
| undefined references | 0 | `grep -c "undefined references" main.log` |
| Rerun / 需重跑 | 0 | `rg -c "Rerun to get|Please rerun|Warning:.*[Rr]erun" main.log` |
| hyperref 死链 | 0 | `grep -c "does not exist" main.log` |
| 习题编号连续 | 逐节 1..N 无缺口 | 见 §4 |
| CRLF / BOM | 全合规 | 见 §5 |

GTM96 实测终局：436 页，4 遍 exit=0，0/0/0/0，Overfull 65（持平未新增），
label 1828 / 0 重复，\ref+\eqref 1492，PDF 链接 cite 163 + idx 741 + 内部 1606。

---

## 3. 死链 / 冲突快速定位

```bash
grep -n "does not exist" main.log          # hyperref 死链锚点
grep -n "multiply defined" main.log         # 重复 label
grep -n "undefined references" main.log     # 未定义引用
```

---

## 4. 习题编号连续性核对

思路：逐节扫描 `exercise:c.s.i` 的 `i` 序列，断言 `1,2,...,N` 连续无缺口、无跳号。
发现缺口即回头查坑 A / 坑 B（习题块识别漏题）。

---

## 5. 行尾 / BOM 检查

所有 `.tex/.cls/.py` 必须 **CRLF + UTF-8 无 BOM**：

```python
import pathlib
for p in pathlib.Path('.').rglob('*.tex'):
    b = p.read_bytes()
    if b[:3] == b'\xef\xbb\xbf':
        p.write_bytes(b[3:])                 # 去 BOM
    p.write_bytes(p.read_bytes().replace(b'\r\n', b'\n').replace(b'\n', b'\r\n'))
```

每轮改完后统一跑一次。

---

## 6. 纯文本保留项审计

原书自身编号不一致处保留纯文本，不擅自改写。写审计脚本定期扫：统计仍存在的硬编码引用数量，
确认稳定在某常数（GTM96 = 7 处）。数量突变即说明某轮误改了应保留项或漏改了应链接项。


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
