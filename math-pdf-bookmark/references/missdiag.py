# -*- coding: utf-8 -*-
"""Diagnose MISS entries of a reanchor report: dump the real lines near p.

Usage: python _missdiag.py <pdf> <report.txt> [max_cases]
"""
import fitz, os, re, sys
sys.path.insert(0, r"C:/Users/asus")
sys.stdout.reconfigure(encoding='utf-8', errors='replace')
from _reanchor import page_lines, probes, clean, nz, body_size

src, rep = sys.argv[1], sys.argv[2]
maxn = int(sys.argv[3]) if len(sys.argv) > 3 else 99
rows = []
for l in open(rep, encoding='utf-8'):
    m = re.match(r"^MISS L(\d) p(\d+)\s+y=\S+\s+(.*)$", l.rstrip())
    if m:
        t = m.group(3).strip()
        if len(t) > 2 and t[0] == t[-1] and t[0] in "\"'":
            t = t[1:-1]
        rows.append((int(m.group(1)), int(m.group(2)), t))
d = fitz.open(src)
bs = body_size(d)
out = ["body size = %.2f  pages = %d  misses = %d" % (bs, d.page_count, len(rows))]
for lvl, p, t in rows[:maxn]:
    out.append("=" * 74)
    out.append("L%d p%d  %r" % (lvl, p, t[:80]))
    out.append("   probes: %r" % [nz(x)[:44] for x in probes(t)])
    for q in (p, p + 1, p - 1):
        if q < 1 or q > d.page_count:
            continue
        ls = sorted(page_lines(d[q - 1]))
        out.append("   -- p%d lines (y/x0/size/bold):" % q)
        for (y, x, s, b, txt) in ls[:9]:
            out.append("      y=%-6.1f x=%-6.1f sz=%-4.1f b=%d %r" % (y, x, s, b, clean(txt)[:66]))
        key = nz(t.split(' ')[-1])
        hits = [ln for ln in ls if len(key) > 3 and key in nz(ln[4])]
        for ln in hits[:3]:
            out.append("      *KEY* y=%-6.1f x=%-6.1f sz=%-4.1f b=%d %r"
                       % (ln[0], ln[1], ln[2], ln[3], clean(ln[4])[:66]))
        heads = [ln for ln in ls if ln[2] >= (bs or 0) + 0.9 or ln[3]]
        for ln in heads[:6]:
            out.append("      *BIG* y=%-6.1f x=%-6.1f sz=%-4.1f b=%d %r"
                       % (ln[0], ln[1], ln[2], ln[3], clean(ln[4])[:66]))
op = os.path.join(r"C:/Users/asus", "_missdiag_" + os.path.basename(rep))
with open(op, "w", encoding="utf-8") as fh:
    fh.write("\n".join(out) + "\n")
print("wrote", len(out), "lines ->", op)
