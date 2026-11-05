#!/usr/bin/env python3
"""Locate index entries related to terms; emit candidates, not semantic verdicts."""
import argparse, json, re
from pathlib import Path

def entries(text):
    pattern = re.compile(r'\\index(?:\[([^\]]*)\])?\s*\{')
    for m in pattern.finditer(text):
        line_start = text.rfind('\n', 0, m.start()) + 1
        prefix = text[line_start:m.start()]
        # Unescaped % starts a TeX comment; skip commented-out entries.
        if re.search(r'(?<!\\)%', prefix):
            continue
        pos, depth = m.end(), 1
        while pos < len(text) and depth:
            if text[pos] == '\\' and pos + 1 < len(text) and text[pos+1] in '{}%':
                pos += 2
                continue
            if text[pos] == '{': depth += 1
            elif text[pos] == '}': depth -= 1
            pos += 1
        if depth:
            yield m.start(), m.group(1), None, pos
        else:
            yield m.start(), m.group(1), text[m.end():pos-1], pos

def main():
    p=argparse.ArgumentParser(description=__doc__)
    p.add_argument('files', nargs='+', help='actual compiled source files')
    p.add_argument('--term', action='append', required=True, help='old/new Chinese or English variant; repeat')
    p.add_argument('--output', help='optional JSON output')
    a=p.parse_args(); rows=[]; errors=[]
    for name in a.files:
        path=Path(name); text=path.read_text(encoding='utf-8-sig')
        for start, kind, entry, end in entries(text):
            if entry is None:
                errors.append({'file':str(path),'line':text.count('\n',0,start)+1,'error':'unclosed index argument'}); continue
            matched=[term for term in a.term if term.casefold() in entry.casefold()]
            if not matched: continue
            left=max(0,start-180); right=min(len(text),end+180)
            context=re.sub(r'\s+',' ',text[left:right])
            rows.append({'file':str(path),'line':text.count('\n',0,start)+1,'index':kind or 'main','entry':entry,'matched':matched,'context':context,'status':'needs_review'})
    result={'terms':a.term,'candidates':rows,'errors':errors,'note':'Candidates only: check entry hierarchy, meaning, actual placement and final PDF links manually.'}
    out=json.dumps(result,ensure_ascii=False,indent=2)
    if a.output: Path(a.output).write_text(out+'\n',encoding='utf-8')
    else: print(out)
    return bool(errors)
if __name__=='__main__': raise SystemExit(main())