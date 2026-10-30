#!/usr/bin/env python3
"""Group WinRT OCR fragments into visual rows, preserving geometry and provenance.
Usage: python ocr_rows.py OCR.txt [--dpi 250] [--tolerance-px 12] [--page 11]
Outputs JSON to stdout; never changes the PDF or decides bookmark destinations.

DPI: if the dump starts with `#dpi=300;scale=1.0;lang=en-US` (written by
winocr.ps1 -Dpi), the effective dpi (dpi*scale) is taken from the header and
--dpi is only cross-checked; a mismatch is an error, because a wrong dpi
scales every y silently.  --dpi is still required for older dumps without a
header line.
"""
import argparse,json,re,statistics,math,sys
from pathlib import Path

def group(lines,tolerance):
    rows=[]
    for item in sorted(lines,key=lambda a:(a['y'],a['x0'])):
        # Fixed centroid prevents transitive chaining across nearby baselines.
        choices=[r for r in rows if abs(item['y']-statistics.median(x['y'] for x in r)) <= tolerance]
        if choices:
            min(choices,key=lambda r:abs(item['y']-statistics.median(x['y'] for x in r))).append(item)
        else: rows.append([item])
    return sorted(rows,key=lambda r:min(x['y'] for x in r))

def parse_header(first):
    """Return dict(dpi=,scale=,lang=) or None when the line is not a header."""
    if not first.startswith('#dpi='): return None
    out={}
    for part in first.lstrip('#').strip().split(';'):
        k,_,v=part.partition('=')
        out[k.strip()]=v.strip()
    try:
        out['dpi']=float(out.get('dpi',0) or 0); out['scale']=float(out.get('scale',1) or 1)
    except ValueError:
        raise ValueError('Malformed OCR header: '+first)
    return out

def parse(path,dpi,tolerance):
    text=Path(path).read_text(encoding='utf-8-sig')
    raw=text.splitlines()
    header=parse_header(raw[0].strip()) if raw else None
    if header:
        eff=header['dpi']*header['scale']
        if eff<=0: raise ValueError('Header has no positive dpi*scale: '+raw[0])
        if dpi is not None and abs(dpi-eff)>0.005*eff:
            raise ValueError('--dpi %.3f conflicts with dump header (dpi=%.3f scale=%.3f -> %.3f). '
                             'Rendering dpi and pixel->point scale must match.'%(dpi,header['dpi'],header['scale'],eff))
        dpi=eff
        raw=raw[1:]
    elif dpi is None:
        sys.exit('No #dpi= header in dump; pass --dpi with the dpi used for rendering.')
    pages={}; current=None
    for line in raw:
        if line.startswith('#####'):
            m=re.search(r'page_(\d+)\.png',line,re.I)
            if not m:raise ValueError('Unrecognised page marker: '+line)
            current=int(m.group(1));pages.setdefault(current,[]);continue
        fields=line.split('\t',4)
        if current is None or len(fields)!=5:raise ValueError('Malformed OCR line: '+line)
        y,x0,x1,h=map(int,fields[:4])
        pages[current].append(dict(y=y,x0=x0,x1=x1,h=h,text=fields[4]))
    result=[]
    for page,lines in sorted(pages.items()):
        for row in group(lines,tolerance):
            parts=sorted(row,key=lambda a:a['x0'])
            result.append(dict(page=page,y_px=round(statistics.median(x['y'] for x in row),1),
                y_pt=round(statistics.median(x['y'] for x in row)*72/dpi,2),
                text=' | '.join(x['text'] for x in parts),fragments=parts))
    return result,dpi

def main():
    p=argparse.ArgumentParser(description=__doc__,formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument('ocr');p.add_argument('--dpi',type=float,default=None)
    p.add_argument('--tolerance-px',type=float,default=12);p.add_argument('--page',type=int)
    p.add_argument('--summary',action='store_true',help='pipe-separated text only, one row per line with page/y_pt')
    a=p.parse_args()
    if a.dpi is not None and a.dpi<=0:p.error('dpi must be positive')
    if a.tolerance_px<0:p.error('tolerance must be nonnegative')
    try:
        rows,eff=parse(a.ocr,a.dpi,a.tolerance_px)
    except ValueError as exc:
        sys.exit('ocr_rows: '+str(exc))
    print('#effective_dpi=%g'%eff,file=sys.stderr)
    rows=[r for r in rows if a.page is None or r['page']==a.page]
    if a.summary:
        for r in rows: print('p%04d y=%.1f|x=%.1f\t%s'%(r['page'],r['y_pt'],min(f['x0'] for f in r['fragments']),r['text']))
    else:
        print(json.dumps(rows,ensure_ascii=False,indent=2))
if __name__=='__main__':main()
