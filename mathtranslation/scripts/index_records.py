"""Inspect standard indexentry records; candidates are not semantic verdicts."""
import argparse,collections,hashlib,json,re
from pathlib import Path

def group(s,p):
    if p>=len(s) or s[p]!='{': raise ValueError('Expected braced argument')
    start=p+1; depth=1;p+=1
    while p<len(s):
        if s[p]=='\\' and p+1<len(s) and s[p+1] in '{}%':p+=2;continue
        if s[p]=='{':depth+=1
        elif s[p]=='}':
            depth-=1
            if not depth:return s[start:p],p+1
        p+=1
    raise ValueError('Unclosed argument')

def split(s,delimiter):
    parts=[];start=0;depth=0;p=0
    while p<len(s):
        if s[p]=='"':p+=2;continue
        if s[p]=='\\' and p+1<len(s) and s[p+1] in '{}%':p+=2;continue
        if s[p]=='{':depth+=1
        elif s[p]=='}':depth-=1
        elif s[p]==delimiter and depth==0:parts.append(s[start:p]);start=p+1
        p+=1
    parts.append(s[start:]);return parts

def parse(text):
    rows=[];errors=[];spans=[]
    for m in re.finditer(r'\\indexentry(?:\[([^\]]+)\])?\s*',text):
        prefix=text[text.rfind('\n',0,m.start())+1:m.start()]
        if re.search(r'(?<!\\)%',prefix):continue
        try:
            entry,end=group(text,m.end()); pos=end
            while pos<len(text) and text[pos].isspace():pos+=1
            page,end=group(text,pos);spans.append((m.start(),end));body=split(entry,'|');levels=[]
            if len(body)>2:raise ValueError('Multiple unquoted encapsulators')
            for level in split(body[0],'!'):
                pair=split(level,'@')
                if len(pair)>2:raise ValueError('Multiple unquoted display separators')
                levels.append(dict(sort=pair[0],display=pair[-1]))
            rows.append(dict(index=m.group(1) or 'main',entry=entry,page=page,levels=levels,encap=body[1] if len(body)==2 else '',line=text.count('\n',0,m.start())+1))
        except ValueError as exc:errors.append(dict(line=text.count('\n',0,m.start())+1,error=str(exc)))
    residue=text
    for start,end in reversed(spans):residue=residue[:start]+' '*(end-start)+residue[end:]
    residue=re.sub(r'(?m)%.*$','',residue)
    if residue.strip():errors.append(dict(error='Unsupported content outside standard indexentry records',sample=residue.strip()[:120]))
    return rows,errors

def snapshot(path):
    data=Path(path).read_bytes();rows,errors=parse(data.decode('utf-8-sig'))
    records=collections.Counter((r['index'],r['entry'],r['page']) for r in rows)
    return data,rows,errors,records

def main():
    p=argparse.ArgumentParser(description=__doc__);p.add_argument('input');p.add_argument('--compare');p.add_argument('--out',required=True);a=p.parse_args()
    data,rows,errors,records=snapshot(a.input);report=dict(sha256=hashlib.sha256(data).hexdigest(),records=rows,errors=errors,semantic_review='not_performed',limitation='Standard indexentry only; no macro expansion. Quote syntax assumes makeindex default double quote.')
    if a.compare:
        other,rr,ee,new=snapshot(a.compare);report.update(after_sha256=hashlib.sha256(other).hexdigest(),after_errors=ee,converged=not errors and not ee and records==new,removed=[dict(index=k[0],entry=k[1],page=k[2],count=v) for k,v in (records-new).items()],added=[dict(index=k[0],entry=k[1],page=k[2],count=v) for k,v in (new-records).items()])
    else:
        candidates=[]
        for axis,opposite in [('display','sort'),('sort','display')]:
            groups=collections.defaultdict(set)
            for r in rows:
                for depth in range(1,len(r['levels'])+1):
                    levels=r['levels'][:depth];key=(r['index'],tuple(x[axis] for x in levels));groups[key].add(tuple(x[opposite] for x in levels))
            candidates.extend(dict(kind=axis+'_path_conflict',index=k[0],path=k[1],variants=sorted(v)) for k,v in groups.items() if len(v)>1)
        report['candidates']=candidates
    out=Path(a.out)
    with out.open('x',encoding='utf-8') as f:json.dump(report,f,ensure_ascii=False,indent=2)
    print(json.dumps(dict(records=len(rows),errors=len(errors),converged=report.get('converged'),semantic_review='not_performed')))
    return 1 if errors or (a.compare and not report['converged']) else 0
if __name__=='__main__':raise SystemExit(main())
