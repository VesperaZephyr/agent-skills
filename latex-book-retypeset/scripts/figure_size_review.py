#!/usr/bin/env python3
"""Produce a review-only illustration size report from explicit measurements.

CSV columns: id, asset, width_mm, pdf_page (optional, 1-based), asset_page (optional,
1-based; defaults to 1). Asset paths are relative to the manifest. width_mm is
declared or expected printed width of the *whole asset page*. When pdf_page is
provided and the vector form can be matched, the report measures actual rendered
size from the final PDF and scales extracted text-size estimates to that width.
If placement cannot be matched, text-size estimates use the declared width.
Requires PyMuPDF; Python 3.9+. See --help.
"""
from __future__ import annotations
import argparse
import csv
import hashlib
import html
import json
import math
import re
import statistics
import sys
from collections import Counter, defaultdict
from pathlib import Path

try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError as exc:
        raise SystemExit('Install PyMuPDF: python -m pip install pymupdf') from exc

FIELDS = ['id', 'asset', 'width_mm', 'height_mm', 'pdf_page', 'asset_page',
          'asset_width_pt', 'asset_height_pt', 'span_count', 'median_est_pt',
          'min_est_pt', 'text_size_basis', 'rendered_width_mm', 'rendered_height_mm',
          'placement_matches', 'rendered_alternatives_mm', 'effective_ppi', 'signals', 'notes']

def number(v, name, integer=False):
    try:
        x = float(v)
        if not math.isfinite(x) or x <= 0 or (integer and x != int(x)):
            raise ValueError()
        return int(x) if integer else x
    except (ValueError, TypeError):
        raise ValueError(f'{name} must be a positive {"integer" if integer else "number"}')

def safe_file(name):
    return re.sub(r'[^A-Za-z0-9_-]+', '_', name)[:40] or 'figure'


def multiply(new, old):
    a,b,c,d,e,f=new; g,h,i,j,k,l=old
    return (a*g+c*h,b*g+d*h,a*i+c*j,b*i+d*j,a*k+c*l+e,b*k+d*l+f)

TOKEN=re.compile(rb'%[^\r\n]*|<[^>]*>|\([^()]*\)|/[^\s<>\[\]()]+|[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[Ee][-+]?\d+)?|[A-Za-z*]+|[\[\]]')
FLOAT=re.compile(rb'[-+]?(?:\d+\.\d*|\.\d+|\d+)(?:[Ee][-+]?\d+)?')
IDENTITY=(1,0,0,1,0,0)

def rendered_forms(page):
    """Read nested PDF form placements and report transformed dimensions."""
    objects=page.get_xobjects()
    if not objects: return {}
    by_parent_name={(invoker,name):xref for xref,name,invoker,_ in objects}
    object_boxes={xref:bbox for xref,_,_,bbox in objects}
    parent=page.parent; hits={}

    def array_values(xref,key,fallback):
        kind,value=parent.xref_get_key(xref,key)
        vals=[float(x) for x in FLOAT.findall(value.encode('ascii','ignore'))] if kind=='array' else []
        return vals if vals else fallback

    def form_box(xref):
        fallback=object_boxes.get(xref,(0,0,0,0))
        vals=array_values(xref,'BBox',fallback)
        return tuple(vals[:4]) if len(vals)>=4 else fallback

    def form_matrix(xref):
        vals=array_values(xref,'Matrix',IDENTITY)
        return tuple(vals[:6]) if len(vals)>=6 else IDENTITY

    def record(xref,ctm):
        x0,y0,x1,y1=form_box(xref); a,b,c,d,_,_=ctm
        width=abs(a)*(x1-x0)+abs(c)*(y1-y0)
        height=abs(b)*(x1-x0)+abs(d)*(y1-y0)
        hits.setdefault((round(x1-x0,2),round(y1-y0,2)),[]).append((width,height))

    def scan(stream_xrefs,parent_xref,initial,depth,active):
        state=initial; stack=[]; operands=[]
        for stream_xref in stream_xrefs:
            for match in TOKEN.finditer(parent.xref_stream(stream_xref)):
                token=match.group()
                if token.startswith((b'%',b'<',b'(')) or token in (b'[',b']'): continue
                if FLOAT.fullmatch(token) or token.startswith(b'/'):
                    operands.append(token); continue
                if token==b'q': stack.append(state)
                elif token==b'Q': state=stack.pop() if stack else initial
                elif token==b'cm' and len(operands)>=6:
                    state=multiply(state,tuple(float(x) for x in operands[-6:]))
                elif token==b'Do' and operands and operands[-1].startswith(b'/') and depth<20:
                    name=operands[-1][1:].decode('latin1')
                    xref=by_parent_name.get((parent_xref,name))
                    if xref and xref not in active:
                        total=multiply(state,form_matrix(xref)); record(xref,total)
                        scan([xref],xref,total,depth+1,active|{xref})
                operands=[]

    scan(page.get_contents(),0,IDENTITY,0,set())
    return hits

def attach_rendered_size(result, asset_rect, page):
    width,height=asset_rect
    hits=rendered_forms(page)
    candidates=[]
    for (w,h),sizes in hits.items():
        if abs(w-width)<0.15 and abs(h-height)<0.15:
            candidates.extend(sizes)
    if not candidates:
        result['_placement_note']='could not match the asset page dimensions to a top-level PDF form'
        return
    sizes=sorted(set((round(w*25.4/72,2),round(h*25.4/72,2)) for w,h in candidates))
    if len(sizes)==1:
        result['rendered_width_mm'],result['rendered_height_mm']=sizes[0]
    else:
        result['rendered_alternatives_mm']='; '.join(f'{w}x{h}' for w,h in sizes)
        result['_placement_note']='same asset has multiple distinct rendered sizes on this page'
    result['placement_matches']=len(sizes)

def measure(row, root, book, out, idx, threshold, height_limit):
    result = {k: '' for k in FIELDS}
    result.update({k: (row.get(k) or '').strip() for k in ('id', 'asset', 'width_mm', 'pdf_page', 'asset_page')})
    signals, notes = [], []
    try:
        if not result['id'] or not result['asset']:
            raise ValueError('id and asset are required')
        width = number(result['width_mm'], 'width_mm')
        ap = number(result['asset_page'] or '1', 'asset_page', True)
        result['asset_page'] = ap
        path = Path(result['asset']); path = path if path.is_absolute() else root / path
        if not path.is_file(): raise ValueError('asset not found')
        spans = []
        doc = fitz.open(str(path))
        try:
            if ap > len(doc): raise ValueError('asset_page exceeds page count')
            page = doc[ap-1]
            rect = page.rect
            if rect.width <= 0 or rect.height <= 0: raise ValueError('asset page has zero size')
            height = width * rect.height / rect.width
            result.update(width_mm=round(width, 3), height_mm=round(height, 3),
                          asset_width_pt=round(rect.width, 3), asset_height_pt=round(rect.height, 3))
            spans = [s['size'] for b in page.get_text('dict')['blocks'] for line in b.get('lines', [])
                     for s in line.get('spans', []) if s.get('text', '').strip() and s.get('size', 0) > 0]
            result['span_count'] = len(spans)
            if spans:
                notes.append('text estimates include fragments, subscripts and possibly hidden text')
            else:
                signals.append('no_extractable_text'); notes.append('outlined or raster labels still need visual review')
            if path.suffix.lower() in {'.png', '.jpg', '.jpeg', '.tif', '.tiff', '.bmp'}:
                pix = fitz.Pixmap(str(path)); result['effective_ppi'] = round(pix.width / (width / 25.4), 1)
                notes.append('ppi is for the whole raster file at declared width')
            if height_limit is not None and height > height_limit: signals.append('height_candidate')
            name = f'{idx:04d}-{safe_file(result["id"])}-asset.png'
            page.get_pixmap(matrix=fitz.Matrix(1.4, 1.4), alpha=False).save(str(out / name))
            result['asset_preview'] = name
        finally: doc.close()
        if result['pdf_page']:
            page_no = number(result['pdf_page'], 'pdf_page', True); result['pdf_page'] = page_no
            if book is None: raise ValueError('pdf_page supplied but --book not supplied')
            if page_no > len(book): raise ValueError('pdf_page exceeds book page count')
            attach_rendered_size(result, (round(rect.width,2),round(rect.height,2)), book[page_no-1])
            if result.get('_placement_note'): signals.append('placement_review'); notes.append(result.pop('_placement_note'))
            name = f'page-{page_no:04d}.png'
            if not (out/name).exists(): book[page_no-1].get_pixmap(matrix=fitz.Matrix(1.2,1.2),alpha=False).save(str(out/name))
            result['page_preview'] = name
        else: signals.append('page_not_provided')
        estimate_width = float(result.get('rendered_width_mm') or width)
        result['text_size_basis'] = ('measured_pdf_placement'
                                     if result.get('rendered_width_mm') else 'declared_width')
        if spans:
            scale = estimate_width * 72 / 25.4 / rect.width
            result['median_est_pt'] = round(statistics.median(spans) * scale, 2)
            result['min_est_pt'] = round(min(spans) * scale, 2)
            if result['median_est_pt'] < threshold: signals.append('small_text_candidate')
        notes.append('confirm actual width, crop, labels, caption and page placement manually')
    except Exception as exc:
        signals.append('input_error'); notes.append(f'{type(exc).__name__}: {exc}')
    result['signals'] = '; '.join(signals) if signals else 'manual_review_required'
    result['notes'] = '; '.join(notes)
    return result


FLAG_LABELS = {
    'small_text_candidate': 'small text',
    'no_extractable_text': 'no text layer',
    'height_candidate': 'tall',
    'placement_review': 'placement review',
    'input_error': 'input error',
}


def page_review_flags(results, out):
    """Return figure-bearing pages and only pages with actionable review signals."""
    pages = set()
    flags = defaultdict(set)
    ignored = {'manual_review_required', 'page_not_provided'}
    for row in results:
        try:
            page_no = int(row.get('pdf_page') or 0)
        except (TypeError, ValueError):
            continue
        if page_no < 1 or not (out / f'page-{page_no:04d}.png').is_file():
            continue
        pages.add(page_no)
        for signal in (row.get('signals') or '').split(';'):
            signal = signal.strip()
            if signal and signal not in ignored:
                flags[page_no].add(signal)
    return sorted(pages), flags


def write_contact_sheets(page_numbers, flags, out, columns, rows, stem):
    """Make printable page montages from the exact rendered page previews."""
    per_sheet = columns * rows
    cell_w, cell_h = 190, 270
    sheet_names = []
    for start in range(0, len(page_numbers), per_sheet):
        batch = page_numbers[start:start + per_sheet]
        doc = fitz.open()
        sheet = doc.new_page(width=columns * cell_w, height=rows * cell_h)
        for slot, page_no in enumerate(batch):
            col, row = slot % columns, slot // columns
            x, y = col * cell_w, row * cell_h
            cell = fitz.Rect(x + 3, y + 3, x + cell_w - 3, y + cell_h - 3)
            sheet.draw_rect(cell, color=(0.76, 0.76, 0.76), width=0.4)
            labels = sorted(flags.get(page_no, set()))
            short = ', '.join(FLAG_LABELS.get(s, s.replace('_', ' ')) for s in labels)
            title = f'p.{page_no}' + (f'  {short}' if short else '')
            sheet.insert_text((x + 8, y + 14), title[:64], fontsize=7.5, color=(0.1, 0.1, 0.1))
            image_box = fitz.Rect(x + 8, y + 19, x + cell_w - 8, y + cell_h - 8)
            image_path = out / f'page-{page_no:04d}.png'
            sheet.insert_image(image_box, filename=str(image_path), keep_proportion=True)
        name = f'{stem}-{start // per_sheet + 1:02d}.png'
        pix = sheet.get_pixmap(matrix=fitz.Matrix(1.25, 1.25), alpha=False)
        pix.save(str(out / name))
        doc.close()
        sheet_names.append(name)
    return sheet_names


def sha256_file(path):
    digest = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def build_summary(results, pages, page_flags, manifest, book, threshold, height_limit):
    signal_rows = Counter()
    for row in results:
        for signal in set(x.strip() for x in (row.get('signals') or '').split(';') if x.strip()):
            if signal != 'manual_review_required':
                signal_rows[signal] += 1
    return {
        'manifest': manifest.name,
        'manifest_sha256': sha256_file(manifest),
        'book': book.name if book else None,
        'book_sha256': sha256_file(book) if book else None,
        'label_threshold_pt': threshold,
        'height_limit_mm': height_limit,
        'placements': len(results),
        'pages_with_figures': len(pages),
        'pages_with_review_flags': sum(bool(v) for v in page_flags.values()),
        'rows_with_measured_placement': sum(bool(r.get('rendered_width_mm')) for r in results),
        'signal_rows': dict(sorted(signal_rows.items())),
        'warning': 'Signals are review candidates, not visual pass/fail judgments; flags can overlap.',
    }

def main():
    p = argparse.ArgumentParser(description='Review-only size triage from an explicit CSV manifest; never edits source or decides pass/fail.')
    p.add_argument('manifest', type=Path, help='UTF-8 CSV: id,asset,width_mm; optional pdf_page,asset_page')
    p.add_argument('--book', type=Path, help='compiled PDF for full-page previews; page numbers are physical, 1-based')
    p.add_argument('--out', type=Path, required=True, help='new or empty report directory')
    p.add_argument('--label-threshold-pt', type=float, default=8.0, help='median extracted-span estimate flag, not a pass criterion (default: 8)')
    p.add_argument('--height-limit-mm', type=float, help='optional image-height flag; caption height is not included')
    p.add_argument('--contact-columns', type=int, default=4, help='contact-sheet columns (default: 4)')
    p.add_argument('--contact-rows', type=int, default=4, help='contact-sheet rows (default: 4)')
    a=p.parse_args()
    if not math.isfinite(a.label_threshold_pt) or a.label_threshold_pt <= 0: p.error('label threshold must be positive')
    if a.height_limit_mm is not None and (not math.isfinite(a.height_limit_mm) or a.height_limit_mm <= 0): p.error('height limit must be positive')
    if a.contact_columns <= 0 or a.contact_rows <= 0: p.error('contact-sheet rows and columns must be positive integers')
    try:
        with a.manifest.open(encoding='utf-8-sig', newline='') as f:
            reader=csv.DictReader(f)
            if not reader.fieldnames or not {'id','asset','width_mm'}.issubset(reader.fieldnames): p.error('CSV requires id,asset,width_mm columns')
            rows=list(reader)
        if not rows: p.error('CSV has no data rows')
        if a.out.exists() and (not a.out.is_dir() or any(a.out.iterdir())): p.error('output directory must be new or empty')
        book=fitz.open(str(a.book)) if a.book else None
        a.out.mkdir(parents=True,exist_ok=True)
        try: results=[measure(row,a.manifest.resolve().parent,book,a.out,i+1,a.label_threshold_pt,a.height_limit_mm) for i,row in enumerate(rows)]
        finally:
            if book is not None: book.close()
        pages, page_flags = page_review_flags(results, a.out)
        all_sheets = []
        focus_sheets = []
        if a.book:
            all_sheets = write_contact_sheets(
                pages, page_flags, a.out, a.contact_columns, a.contact_rows, 'all-pages')
            flagged_pages = [page_no for page_no in pages if page_flags.get(page_no)]
            focus_sheets = write_contact_sheets(
                flagged_pages, page_flags, a.out, a.contact_columns, a.contact_rows, 'focus-pages')
        summary = build_summary(results, pages, page_flags, a.manifest.resolve(),
                                a.book.resolve() if a.book else None,
                                a.label_threshold_pt, a.height_limit_mm)
        summary.update({
            'figure_pages': pages,
            'flagged_pages': {str(page): sorted(page_flags[page])
                              for page in sorted(page_flags) if page_flags[page]},
            'all_page_sheets': all_sheets,
            'focus_page_sheets': focus_sheets,
            'contact_sheet_grid': f'{a.contact_columns}x{a.contact_rows}',
        })
        (a.out/'summary.json').write_text(json.dumps(summary,ensure_ascii=False,indent=2),encoding='utf8')
        with (a.out/'measurements.csv').open('w',encoding='utf-8-sig',newline='') as f:
            w=csv.DictWriter(f,fieldnames=FIELDS,extrasaction='ignore');w.writeheader();w.writerows(results)
        (a.out/'measurements.json').write_text(json.dumps(results,ensure_ascii=False,indent=2),encoding='utf8')
        esc=lambda v: html.escape(str(v),quote=True)
        cards=[]
        for r in results:
            imgs=''.join(f'<a href="{esc(r[k])}"><img src="{esc(r[k])}" alt="{esc(k)}"></a>' for k in ('asset_preview','page_preview') if k in r)
            info=' · '.join(f'{esc(k)}: {esc(r[k])}' for k in ('width_mm','height_mm','rendered_width_mm','rendered_height_mm','pdf_page','span_count','median_est_pt','min_est_pt','text_size_basis','placement_matches','rendered_alternatives_mm','effective_ppi','signals') if r[k] != '')
            cards.append(f'<section><h2>{esc(r["id"])}</h2><p>{info}</p><p>{esc(r["notes"])}</p><div>{imgs}</div></section>')
        summary_cards=''.join(f'<li>{esc(k)}: {esc(v)}</li>' for k,v in summary.items() if k not in {'signal_rows','warning','manifest_sha256','book_sha256'})
        signal_cards=''.join(f'<li>{esc(k)}: {esc(v)}</li>' for k,v in summary['signal_rows'].items()) or '<li>无自动提示</li>'
        overview=lambda files, title: (
            f'<h3>{esc(title)}</h3><div class="sheets">' +
            ''.join(f'<a href="{esc(name)}"><img src="{esc(name)}" alt="{esc(title)} {i+1}"></a>'
                    for i,name in enumerate(files)) + '</div>' if files else '')
        doc='''<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>插图尺寸人工核查</title><style>body{font-family:sans-serif;max-width:1320px;margin:auto;padding:1em}section{border-top:1px solid #aaa;padding:1em 0}section div{display:flex;align-items:start;gap:1em}img{max-width:48vw;max-height:900px;border:1px solid #ddd}.sheets{display:flex;flex-wrap:wrap;gap:1em}.sheets img{max-width:min(48vw,760px);max-height:none}p{line-height:1.5}li{margin:.25em 0}</style><h1>插图尺寸人工核查</h1><p>图幅实测与文字字号估计用于筛查，不自动判断是否合格。低字号、超高图幅或无可提取文字都只是提示；请对照页面预览，检查主体大小、标签、图题、裁边和局部空间。</p><h2>报告概览</h2><ul>'''+summary_cards+f'</ul><h3>候选提示（可能重叠）</h3><ul>{signal_cards}</ul><p>{esc(summary["warning"])}</p>'+overview(all_sheets,'全部含图页面（页码为物理页）')+overview(focus_sheets,'带有人工复核提示的页面')+'<h2>逐图测量和页面预览</h2>'+''.join(cards)+'</html>'
        (a.out/'index.html').write_text(doc,encoding='utf8')
        errors=sum('input_error' in r['signals'] for r in results)
        print(f'{len(results)} rows, {len(pages)} figure pages, {sum(bool(v) for v in page_flags.values())} flagged pages, {errors} input errors; report: {a.out / "index.html"}')
        return 1 if errors else 0
    except (OSError, ValueError, RuntimeError) as exc:
        print(f'error: {exc}',file=sys.stderr); return 2

if __name__ == '__main__': raise SystemExit(main())
