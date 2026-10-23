"""Inventory diagram candidates in explicit compiled TeX files; no visual certification.

Lists all array-like environments, not just blocks already using tikzcd.
Treat output as a review queue, not proof that a block is a diagram or is correct.
"""
from pathlib import Path
import argparse, json, re

ENVIRONMENTS = {'tikzcd','array','aligned','alignedat','matrix','smallmatrix','pmatrix',
                'bmatrix','Bmatrix','vmatrix','Vmatrix','CD','tikzpicture','split','gathered'}
ARROW = re.compile(r'\\(?:arrow|ar|xrightarrow|xleftarrow|hookrightarrow|hookleftarrow|'
                   r'twoheadrightarrow|twoheadleftarrow|longrightarrow|longleftarrow|'
                   r'rightarrow|leftarrow|uparrow|downarrow|nearrow|searrow|swarrow|nwarrow|'
                   r'mapsto|mapsfrom|leftrightarrow|Rightarrow|Leftarrow)(?![A-Za-z])')

def balanced_end(text, start, opening='{', closing='}'):
    depth=0;brace_depth=0;quoted=False
    for i in range(start,len(text)):
        n=0;j=i-1
        while j>=0 and text[j]=='\\':n+=1;j-=1
        if n%2:continue
        c=text[i]
        if opening=='[':
            if c=='{':brace_depth+=1
            elif c=='}':brace_depth-=1
            elif c=='"' and brace_depth==0:quoted=not quoted
            if brace_depth or quoted:continue
        if c==opening:depth+=1
        elif c==closing:
            depth-=1
            if depth==0:return i+1
    return None

def mask_noncode(text):
    chars=list(text)
    def hide(a,b):
        for i in range(a,b):
            if chars[i] not in '\r\n':chars[i]=' '
    for m in re.finditer(r'\\begin\{(verbatim\*?|lstlisting|minted)\}.*?\\end\{\1\}',text,re.S):hide(*m.span())
    for m in re.finditer(r'\\verb\*?([^A-Za-z\s]).*?\1',text):hide(*m.span())
    for m in re.finditer(r'%[^\r\n]*',''.join(chars)):
        n=0;j=m.start()-1
        while j>=0 and text[j]=='\\':n+=1;j-=1
        if n%2==0:hide(*m.span())
    return ''.join(chars)

def arrows_in(block):
    rows=[]
    for m in ARROW.finditer(block):
        pos=m.end()
        while pos<len(block) and block[pos].isspace():pos+=1
        options=None
        if pos<len(block) and block[pos]=='[':
            end=balanced_end(block,pos,'[',']')
            options=block[pos+1:end-1] if end else None
        flags=[]
        if options and re.search(r'\bhook\b.*\b(?:rightarrow|leftarrow|no tail|dash)\b',options,re.S):flags.append('possible-hook-reset-review-order')
        if options and re.search(r'\b(?:leftarrow|hookleftarrow|reversed)\b',options):flags.append('review-effective-head-endpoint')
        rows.append({'command':m.group(),'offset_in_block':m.start(),'options':options,'review_flags':flags})
    return rows

def inventory(path):
    raw=path.read_bytes().decode('utf-8-sig');text=mask_noncode(raw);stack=[];blocks=[];issues=[]
    for m in re.finditer(r'\\(begin|end)\{([^{}]+)\}',text):
        kind,env=m.groups()
        if kind=='begin':stack.append((env,m.start()))
        elif not stack or stack[-1][0]!=env:
            issues.append({'line':raw.count('\n',0,m.start())+1,'issue':'unmatched-environment','token':m.group()})
        else:
            name,start=stack.pop()
            if name in ENVIRONMENTS:blocks.append((name,start,m.end()))
    for env,start in stack:
        issues.append({'line':raw.count('\n',0,start)+1,'issue':'unclosed-environment','environment':env})
    for m in re.finditer(r'\\(?:xymatrix|tikzcdset|tikz)(?![A-Za-z])',text):
        pos=text.find('{',m.end())
        if pos<0:continue
        end=balanced_end(text,pos)
        if end:blocks.append((m.group()[1:],m.start(),end))
        else:issues.append({'line':raw.count('\n',0,m.start())+1,'issue':'unclosed-macro-group','token':m.group()})
    rows=[]
    for env,a,b in sorted(blocks,key=lambda x:(x[1],-x[2])):
        block=text[a:b]
        rows.append({'file':str(path),'environment_or_macro':env,'line':raw.count('\n',0,a)+1,
                     'end_line':raw.count('\n',0,b)+1,'start':a,'end':b,'source':raw[a:b],
                     'arrows':arrows_in(block),'classification':'needs-review',
                     'original_pdf_page':None,'visual_verification':False,
                     'style_resolution':'not-performed'})
    # Glyphs outside candidate blocks can indicate custom macros or hand-made diagrams.
    for m in ARROW.finditer(text):
        if any(a<=m.start()<b for _,a,b in blocks):continue
        a=max(0,m.start()-80);b=min(len(raw),m.end()+120)
        rows.append({'file':str(path),'environment_or_macro':'arrow-outside-listed-environment',
                     'line':raw.count('\n',0,m.start())+1,'start':m.start(),'end':m.end(),
                     'source':raw[a:b],'classification':'needs-review','visual_verification':False})
    return {'file':str(path),'candidates':rows,'parse_issues':issues}

def main():
    ap=argparse.ArgumentParser(description=__doc__)
    ap.add_argument('files',nargs='+',type=Path,help='Compiled sources and relevant macro/style files; exclude backups')
    ap.add_argument('--output',required=True,type=Path)
    args=ap.parse_args();results=[inventory(p) for p in args.files]
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps({'schema_version':1,'inventory_only':True,'files':results},ensure_ascii=False,indent=2),encoding='utf-8')
    print('Candidates:',sum(len(r['candidates']) for r in results),'Parse issues:',sum(len(r['parse_issues']) for r in results))

if __name__=='__main__':main()
