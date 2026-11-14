#!/usr/bin/env python3
"""Build a source-to-translation full-page illustration review atlas.

The default caption patterns cover books using captions like ``Fig. 2.3`` in
the source and ``图2.3:`` in Chinese. Patterns must match from the beginning of
a PyMuPDF text block and expose the figure ID as the first capture group or a
named ``label`` group. Pages in reports are physical PDF pages, one-based.

Requires PyMuPDF. This tool inventories caption IDs and prepares visual review
pages; it does not certify that a figure is correct or that two drawings match.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import html
import json
import re
from collections import Counter, defaultdict
from pathlib import Path

try:
    import pymupdf as fitz
except ImportError:
    try:
        import fitz
    except ImportError as exc:
        raise SystemExit('Install PyMuPDF: python -m pip install pymupdf') from exc


SOURCE_CAPTION = r'^\s*Fig\.[ \t]*((?:\d+|[A-Z])\.\d+[a-z]?)\b'
TRANSLATION_CAPTION = r'^\s*图\s*((?:\d+|[A-Z])\.\d+[a-z]?)\s*[:：]'


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            digest.update(block)
    return digest.hexdigest()


def natural_label_key(label: str):
    match = re.fullmatch(r'(\d+|[A-Z])\.(\d+)([a-z]?)', label, re.I)
    if not match:
        return (2, label.casefold())
    chapter = match.group(1)
    chapter_key = (0, int(chapter)) if chapter.isdigit() else (1, chapter.upper())
    return (*chapter_key, int(match.group(2)), match.group(3).casefold())


def normalize_manifest_id(value: str):
    """Return (caption ID, original placement ID) for common asset IDs."""
    original = value.strip()
    if re.fullmatch(r'(?:\d+|[A-Z])\.\d+[a-z]?', original, re.I):
        return original, original
    match = re.fullmatch(r'(?:fig-)?(\d+|[A-Z])(?:\.|-)(\d+)(?:-(?:upper|lower|\d+))?', original, re.I)
    if match:
        return f'{match.group(1)}.{match.group(2)}', original
    return None, original


def scan_placement_manifest(path: Path):
    placements = defaultdict(list)
    with path.open('r', encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        fields = {field.strip().casefold(): field for field in (reader.fieldnames or [])}
        if 'id' not in fields or 'pdf_page' not in fields:
            raise ValueError('placement manifest needs id and pdf_page columns')
        for row_num, row in enumerate(reader, start=2):
            raw_id = (row.get(fields['id']) or '').strip()
            raw_page = (row.get(fields['pdf_page']) or '').strip()
            figure_id, placement_id = normalize_manifest_id(raw_id)
            if figure_id is None:
                continue
            try:
                page = int(raw_page)
            except ValueError as exc:
                raise ValueError(f'placement manifest row {row_num}: invalid pdf_page {raw_page!r}') from exc
            if page < 1:
                raise ValueError(f'placement manifest row {row_num}: pdf_page must be one-based and positive')
            item = {'id': placement_id, 'page': page}
            if item not in placements[figure_id]:
                placements[figure_id].append(item)
    return placements


def scan_captions(doc, pattern: str, label: str):
    try:
        rx = re.compile(pattern, re.I)
    except re.error as exc:
        raise ValueError(f'invalid {label} caption regex: {exc}') from exc
    if 'label' not in rx.groupindex and rx.groups < 1:
        raise ValueError(f'{label} caption regex needs a capture group for the figure ID')
    found = defaultdict(list)
    for page_index, page in enumerate(doc):
        for block in page.get_text('blocks'):
            block_text = block[4].strip()
            match = rx.match(block_text)
            if not match:
                continue
            figure_id = match.group('label') if 'label' in rx.groupindex else match.group(1)
            item = {
                'page': page_index + 1,
                'caption': block_text,
                'bbox': [round(float(x), 2) for x in block[:4]],
            }
            if item not in found[figure_id]:
                found[figure_id].append(item)
    return found


def build_mapping(source_caps, translation_caps, placement_manifest=None):
    rows = []
    for figure_id in sorted(set(source_caps) | set(translation_caps), key=natural_label_key):
        source = source_caps.get(figure_id, [])
        translated = translation_caps.get(figure_id, [])
        source_pages = sorted({item['page'] for item in source})
        translated_pages = sorted({item['page'] for item in translated})
        placement_items = (placement_manifest or {}).get(figure_id, [])
        placement_pages = sorted({item['page'] for item in placement_items})
        if not source:
            status = 'source_caption_missing'
        elif not translated:
            status = 'translation_caption_missing'
        elif placement_manifest is not None and not placement_items:
            status = 'placement_missing'
        elif len(source_pages) > 1 or len(translated_pages) > 1:
            status = 'multiple_caption_pages'
        else:
            status = 'matched'
        used_translation_pages = placement_pages if placement_manifest is not None else translated_pages
        rows.append({
            'figure_id': figure_id,
            'source_pages': source_pages,
            'translation_pages': translated_pages,
            'placement_pages': placement_pages,
            'placement_ids': [item['id'] for item in placement_items],
            'used_translation_pages': used_translation_pages,
            'status': status,
            'source_captions': source,
            'translation_captions': translated,
        })
    return rows


def draw_pair_sheets(rows, source_doc, translation_doc, out: Path, columns: int, rows_per_sheet: int):
    pair_labels = defaultdict(set)
    for item in rows:
        for source_page in item['source_pages']:
            for translation_page in item['used_translation_pages']:
                pair_labels[(source_page, translation_page)].add(item['figure_id'])
    pairs = sorted(pair_labels, key=lambda pair: (natural_label_key(sorted(pair_labels[pair], key=natural_label_key)[0]), pair))
    per_sheet = columns * rows_per_sheet
    cell_w, cell_h = 620, 455
    sheet_names = []

    for start in range(0, len(pairs), per_sheet):
        batch = pairs[start:start + per_sheet]
        atlas = fitz.open()
        sheet = atlas.new_page(width=columns * cell_w, height=rows_per_sheet * cell_h)
        for slot, (source_page, translation_page) in enumerate(batch):
            col, row = slot % columns, slot // columns
            x, y = col * cell_w, row * cell_h
            outer = fitz.Rect(x + 3, y + 3, x + cell_w - 3, y + cell_h - 3)
            sheet.draw_rect(outer, color=(0.72, 0.72, 0.72), width=0.5)
            labels = sorted(pair_labels[(source_page, translation_page)], key=natural_label_key)
            shown = ', '.join(labels[:5])
            if len(labels) > 5:
                shown += f', +{len(labels) - 5}'
            sheet.insert_text((x + 8, y + 14), f'Fig. {shown}', fontsize=8, color=(0.08, 0.08, 0.08))

            half_w = (cell_w - 22) / 2
            source_box = fitz.Rect(x + 6, y + 32, x + 6 + half_w, y + cell_h - 8)
            translation_box = fitz.Rect(x + 16 + half_w, y + 32, x + cell_w - 6, y + cell_h - 8)
            sheet.insert_text((source_box.x0 + 2, y + 27), f'EN p.{source_page}', fontsize=7, color=(0.22, 0.22, 0.22))
            sheet.insert_text((translation_box.x0 + 2, y + 27), f'ZH p.{translation_page}', fontsize=7, color=(0.22, 0.22, 0.22))
            sheet.show_pdf_page(source_box, source_doc, source_page - 1, keep_proportion=True)
            sheet.show_pdf_page(translation_box, translation_doc, translation_page - 1, keep_proportion=True)

        name = f'page-pairs-{start // per_sheet + 1:03d}.png'
        # A page is shown at about half its native width inside a left/right pair;
        # 3x sheet rendering keeps the embedded full pages near the 110 dpi first-pass target.
        sheet.get_pixmap(matrix=fitz.Matrix(3.0, 3.0), alpha=False).save(str(out / name))
        atlas.close()
        sheet_names.append(name)
    return pairs, pair_labels, sheet_names


def main():
    parser = argparse.ArgumentParser(description='Prepare full-page source/translation illustration comparison sheets; visual review remains manual.')
    parser.add_argument('source_pdf', type=Path, help='published/source PDF')
    parser.add_argument('translation_pdf', type=Path, help='compiled translated PDF')
    parser.add_argument('--out', type=Path, required=True, help='new or empty output directory')
    parser.add_argument('--source-caption-regex', default=SOURCE_CAPTION,
                        help='regex anchored at a text block start; first or named label group gives the figure ID')
    parser.add_argument('--translation-caption-regex', default=TRANSLATION_CAPTION,
                        help='regex anchored at a text block start; first or named label group gives the figure ID')
    parser.add_argument('--translation-placement-manifest', type=Path,
                        help='optional CSV with id,pdf_page columns for actual translated figure placement pages; missing IDs are reported, never silently replaced by caption pages')
    parser.add_argument('--columns', type=int, default=2, help='page-pair columns per sheet (default: 2)')
    parser.add_argument('--rows', type=int, default=2, help='page-pair rows per sheet (default: 2)')
    args = parser.parse_args()
    if args.columns < 1 or args.rows < 1:
        parser.error('--columns and --rows must be positive integers')
    if args.out.exists() and (not args.out.is_dir() or any(args.out.iterdir())):
        parser.error('output directory must be new or empty')
    if not args.source_pdf.is_file() or not args.translation_pdf.is_file():
        parser.error('source and translation PDFs must exist')
    if args.translation_placement_manifest and not args.translation_placement_manifest.is_file():
        parser.error('translation placement manifest must exist')

    out = args.out.resolve()
    out.mkdir(parents=True, exist_ok=True)
    source_doc = fitz.open(str(args.source_pdf))
    translation_doc = fitz.open(str(args.translation_pdf))
    source_page_count = len(source_doc)
    translation_page_count = len(translation_doc)
    try:
        source_caps = scan_captions(source_doc, args.source_caption_regex, 'source')
        translation_caps = scan_captions(translation_doc, args.translation_caption_regex, 'translation')
        if not source_caps and not translation_caps:
            raise ValueError('caption patterns found no figures in either PDF; supply patterns for the book')
        placement_manifest = (scan_placement_manifest(args.translation_placement_manifest)
                              if args.translation_placement_manifest else None)
        if placement_manifest:
            invalid_pages = sorted({item['page'] for items in placement_manifest.values()
                                    for item in items if item['page'] > translation_page_count})
            if invalid_pages:
                raise ValueError(f'placement manifest pages exceed translation PDF page count ({translation_page_count}): {invalid_pages}')
        mapping = build_mapping(source_caps, translation_caps, placement_manifest)
        pairs, pair_labels, sheet_names = draw_pair_sheets(
            mapping, source_doc, translation_doc, out, args.columns, args.rows)
    finally:
        source_doc.close()
        translation_doc.close()

    pair_to_sheet = {}
    per_sheet = args.columns * args.rows
    for index, pair in enumerate(pairs):
        pair_to_sheet[pair] = f'page-pairs-{index // per_sheet + 1:03d}.png'
    for item in mapping:
        item['page_pair_sheets'] = sorted({
            pair_to_sheet[(sp, tp)]
            for sp in item['source_pages'] for tp in item['used_translation_pages']
            if (sp, tp) in pair_to_sheet
        })

    status_counts = Counter(item['status'] for item in mapping)
    summary = {
        'source_pdf': args.source_pdf.name,
        'source_sha256': sha256_file(args.source_pdf),
        'source_pages': source_page_count,
        'translation_pdf': args.translation_pdf.name,
        'translation_sha256': sha256_file(args.translation_pdf),
        'translation_pages': translation_page_count,
        'translation_placement_manifest': args.translation_placement_manifest.name if args.translation_placement_manifest else None,
        'translation_placement_manifest_sha256': sha256_file(args.translation_placement_manifest) if args.translation_placement_manifest else None,
        'source_caption_ids': len(source_caps),
        'translation_caption_ids': len(translation_caps),
        'shared_caption_ids': len(set(source_caps) & set(translation_caps)),
        'source_only_ids': sorted(set(source_caps) - set(translation_caps), key=natural_label_key),
        'translation_only_ids': sorted(set(translation_caps) - set(source_caps), key=natural_label_key),
        'placement_missing_ids': [item['figure_id'] for item in mapping if item['status'] == 'placement_missing'],
        'unmatched_placement_ids': sorted(
            set(placement_manifest or {}) - set(source_caps) - set(translation_caps), key=natural_label_key),
        'mapping_status_counts': dict(status_counts),
        'unique_page_pairs': len(pairs),
        'pair_sheets': sheet_names,
        'contact_sheet_grid': f'{args.columns}x{args.rows}',
        'warning': 'Caption/page matches do not prove figure identity, completeness, crop fidelity, readability, or correct placement. Review every sheet; enlarge uncertain figures and inspect the original and translated assets.',
    }
    (out / 'summary.json').write_text(json.dumps(summary, ensure_ascii=False, indent=2), encoding='utf-8')
    csv_rows = []
    for item in mapping:
        csv_rows.append({
            'figure_id': item['figure_id'],
            'source_pages': ';'.join(map(str, item['source_pages'])),
            'translation_caption_pages': ';'.join(map(str, item['translation_pages'])),
            'translation_placement_pages': ';'.join(map(str, item['placement_pages'])),
            'translation_placement_ids': ';'.join(item['placement_ids']),
            'used_translation_pages': ';'.join(map(str, item['used_translation_pages'])),
            'status': item['status'],
            'source_caption': ' || '.join(c['caption'] for c in item['source_captions']),
            'translation_caption': ' || '.join(c['caption'] for c in item['translation_captions']),
            'page_pair_sheets': ';'.join(item['page_pair_sheets']),
        })
    with (out / 'caption-page-map.csv').open('w', encoding='utf-8-sig', newline='') as stream:
        writer = csv.DictWriter(stream, fieldnames=list(csv_rows[0]) if csv_rows else [
            'figure_id','source_pages','translation_caption_pages','translation_placement_pages','translation_placement_ids','used_translation_pages','status','source_caption','translation_caption','page_pair_sheets'])
        writer.writeheader()
        writer.writerows(csv_rows)

    esc = lambda value: html.escape(str(value), quote=True)
    gallery = ''.join(
        f'<a href="{esc(name)}"><img src="{esc(name)}" alt="页面对照表 {i+1}"></a>'
        for i, name in enumerate(sheet_names)
    )
    statuses = ''.join(f'<li>{esc(key)}: {esc(value)}</li>' for key, value in status_counts.items())
    doc = ('<!doctype html><html lang="zh"><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">'
           '<title>原书与译稿插图页面对照</title><style>body{font-family:sans-serif;max-width:1400px;margin:auto;padding:1em}img{max-width:min(100%,1100px);border:1px solid #ddd;margin:1em 0}.gallery{display:grid;grid-template-columns:repeat(auto-fit,minmax(460px,1fr));gap:1em}.gallery img{width:100%;margin:0}li{margin:.3em 0}p{line-height:1.5}</style>'
           '<h1>原书与译稿插图页面对照</h1><p>按题注图号配对的整页首轮核对材料。若提供放置页清单，右侧优先使用图片实际出现页；否则使用译稿题注页。页面为 PDF 物理页码；每个格子左侧是原书，右侧是译稿。</p>'
           '<h2>覆盖与映射</h2><ul>' + ''.join(f'<li>{esc(k)}: {esc(v)}</li>' for k,v in summary.items() if k not in {'source_sha256','translation_sha256','source_only_ids','translation_only_ids','mapping_status_counts','pair_sheets','warning'}) +
           f'{statuses}</ul><p>{esc(summary["warning"])}</p><p>文件哈希：原书 {esc(summary["source_sha256"])}；译稿 {esc(summary["translation_sha256"])}</p>'
           '<h2>整页对照总览</h2><div class="gallery">' + gallery + '</div><p>逐图页码与原/译题注见 <a href="caption-page-map.csv">caption-page-map.csv</a>。</p></html>')
    (out / 'index.html').write_text(doc, encoding='utf-8')

    print(f'{len(mapping)} caption IDs; {len(pairs)} unique page pairs; {len(sheet_names)} sheets; statuses: {dict(status_counts)}; report: {out / "index.html"}')
    return 1 if summary['source_only_ids'] or summary['translation_only_ids'] or summary['placement_missing_ids'] or any(
        key != 'matched' for key in status_counts
    ) else 0


if __name__ == '__main__':
    raise SystemExit(main())
