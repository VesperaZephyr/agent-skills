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
| 正文内部引用 | 该链接的引用已链接，显示号和落点与原书相符 | 见下方三项终检 |
| 中文数学用书标点 | 工程体例一致，未经批准的残留为 0 | 见下方三项终检 |
| 行间公式 | 关系符和续行位置符合式组结构，编号与标签保真 | 见下方三项终检 |
| 习题内容和编号 | 与原书题干、子问、原印编号和共用条件逐项对应 | 见 §4 |
| CRLF / BOM | 全合规 | 见 §5 |

GTM 96 历史构建样例为 436 页，4 遍 exit=0，Overfull 65（持平未新增），标签 1828 个且无重复。这些是当时的结构指标。按原书逐句审阅和检查 PDF 实际链接语义时，另用[内容审阅流程](content-audit.md)。

---

<a id="body-review"></a>

## 正文引用、标点与行间公式终检

开工时确定标签规则、译文标点和多行公式示例，先用实际构建入口编成一小段，
查看正文引用点击落点和公式版面。分章时边写边加标签和引用。目标还没落盘时，
把引用位置、原显示号及预期目标记入未决清单，合稿后回填。

1. **正文引用。** 对实际进入构建的正文及前后置部分跑
   `python <skill>/scripts/audit_text_refs.py <源文件或目录 ...>`，
   裸号书另用 `audit_bare_xrefs.py`。将原书正文引用与译稿对照，补查脚本不覆盖的
   无关键词引用、无号条目、并列续号（如「定理 6.14 和 2.27」）、子项和项目私有宏。
   逐条裁决候选为已补链接或有理由保留，并对最终 aux 核查引用目标。
   在最终 PDF 核对正文每处引用的显示号、链接矩形及目标对象，尤其同页目标、重号、
   跨章及附录。可批量枚举 GoTo 与命名目标，再人工核实语义和机器无法解析的对象。
   「不存在未定义引用」只说明已写入引用命令的目标能解析。目录、书签或全书链数
   也不能验证正文覆盖。外部书内编号等有意保留项单列理由。
2. **中文标点。** 对实际排印的范围运行
   `python <skill>/scripts/unify_punct_halfwidth.py <实际源文件 ...> --report`。
   确认映射和保护范围后再按项目规则修订，生成器工程改生成源。保留逐字引用、
   原样复用图件及有特殊用途的字符所需体例，并登记例外；URL、代码、标签、
   数学分隔符和运算符按其语法处理。工具只换字符，不负责英文标点的空格、
   引号语法或换行。复查替换差异，重建后扫描 PDF 文本层的标点残留，
   打开各章的代表页和例外页检查句间空格、行末标点及公式衔接。
   PDF 文本层不可用时按最终页做目视复核。
3. **行间公式。** 逐章过一遍原书及最终 PDF 的多行显示式，尤其查找连续独立
   显示块、各行单独居中但属于同一推导、关系符用空格凑列、断行后符号位置混乱
   及公式编号脱离式组。等式链可用 `align*`；整组只有一个原编号时可用
   `equation` 加 `split` 或 `aligned`；逐行有号时须保留各行编号与锚点。
   续行确认 `&=` 等对齐点的语义。独立列举可用 `gather`，单式续行可用
   `multline`，分段定义用 `cases`。以实际成品检查对齐、式间距、
   页宽和编号落点，源码环境或 overfull 计数只供定位。
   专项修复见[行间公式版式审计](../../latex-display-layout-audit/SKILL.md)。

沿用工程审阅记录，至少按章登记实际覆盖范围、三项状态以及例外和未决位置。
发布前绑定最终 PDF 的版本或哈希，重新构建后更新受影响的页面和链接证据。
未执行、无法核实或仍有缺陷的项目按未完成交接，编译通过不能自动勾销。

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
