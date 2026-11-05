"""Compare explicit physical page pairs, never certify mathematical fidelity.

Compatible with the original --pairs syntax; adds equal-length ranges, JSON
maps, all-page comparison and changed-only image export. No text-based pairing.
"""
import argparse
import hashlib
import json
from pathlib import Path
import pymupdf


def sha(path):
    h = hashlib.sha256()
    with Path(path).open('rb') as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b''):
            h.update(block)
    return h.hexdigest()


def page_range(value):
    parts = value.strip().split('-')
    if len(parts) == 1:
        return [int(parts[0])]
    if len(parts) != 2:
        raise ValueError('Expected page or ascending page range')
    start, stop = map(int, parts)
    if start > stop:
        raise ValueError('Descending page range')
    return list(range(start, stop + 1))


def parse_pairs(value):
    pairs = []
    for token in value.split(','):
        left, right = token.split(':')
        old, new = page_range(left), page_range(right)
        if len(old) != len(new):
            raise ValueError('Mapped ranges must have equal lengths')
        pairs.extend(zip(old, new))
    return pairs


def validate_pairs(pairs, old_count, new_count):
    if not pairs:
        raise ValueError('Empty page mapping')
    for pair in pairs:
        if len(pair) != 2 or any(type(n) is not int for n in pair):
            raise ValueError('Page pairs must contain two integers')
        if not (1 <= pair[0] <= old_count and 1 <= pair[1] <= new_count):
            raise ValueError('Physical page out of bounds: ' + repr(pair))
    for side in (0, 1):
        values = [pair[side] for pair in pairs]
        if len(values) != len(set(values)):
            raise ValueError('Duplicate mapped page; split separate comparison tasks instead')
    return ([n for n in range(1, old_count + 1) if n not in {p[0] for p in pairs}],
            [n for n in range(1, new_count + 1) if n not in {p[1] for p in pairs}])


def compare(before, after, pairs, out, dpi=120, save='all', expected=None, require_complete=False):
    if not 36 <= dpi <= 600:
        raise ValueError('DPI must be 36..600')
    if save not in ('all', 'changed', 'none'):
        raise ValueError('Unknown image save mode')
    before, after, out = Path(before).resolve(strict=True), Path(after).resolve(strict=True), Path(out)
    hashes = [sha(before), sha(after)]
    if expected and hashes != list(expected):
        raise ValueError('Mapping PDF hashes do not match these inputs')
    with pymupdf.open(before) as old, pymupdf.open(after) as new:
        if pairs is None:
            if len(old) != len(new):
                raise ValueError('--all requires equal page counts; supply explicit pairs after reflow')
            pairs = [(n, n) for n in range(1, len(old) + 1)]
        unmapped_old, unmapped_new = validate_pairs(pairs, len(old), len(new))
        if require_complete and (unmapped_old or unmapped_new):
            raise ValueError('Incomplete page mapping')
        out.mkdir(parents=True, exist_ok=False)
        try:
            rows = []
            for i, (left, right) in enumerate(pairs, 1):
                pixmaps = [doc[n - 1].get_pixmap(dpi=dpi, colorspace=pymupdf.csRGB, alpha=False, annots=True)
                           for doc, n in ((old, left), (new, right))]
                renders = [dict(page=n, width=pix.width, height=pix.height,
                                pixel_sha256=hashlib.sha256(pix.samples).hexdigest(), image=None)
                           for n, pix in zip((left, right), pixmaps)]
                same = all(renders[0][key] == renders[1][key] for key in ('width', 'height', 'pixel_sha256'))
                if save == 'all' or (save == 'changed' and not same):
                    for label, pix, record in zip(('before', 'after'), pixmaps, renders):
                        record['image'] = f'{i:04d}-{label}-p{record["page"]}.png'
                        pix.save(str(out / record['image']))
                rows.append(dict(before=renders[0], after=renders[1], identical_pixels=same,
                                 visual_review='not_performed'))
            if hashes != [sha(before), sha(after)]:
                raise ValueError('PDF changed during rendering; comparison is invalid')
            report = dict(schema_version=2, before_pdf=str(before), after_pdf=str(after),
                          before_sha256=hashes[0], after_sha256=hashes[1], dpi=dpi,
                          renderer=pymupdf.VersionBind, annotations=True, save_images=save,
                          pages=rows, unmapped_before=unmapped_old, unmapped_after=unmapped_new,
                          identical=sum(row['identical_pixels'] for row in rows),
                          limitation='Pixel equality at this DPI is not mathematical or visual certification.')
            (out / 'comparison.json').write_text(json.dumps(report, indent=2), encoding='utf-8')
            return report
        except Exception as exc:
            (out / 'INVALID.json').write_text(json.dumps(dict(error=str(exc))), encoding='utf-8')
            raise


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('before', type=Path)
    parser.add_argument('after', type=Path)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument('--pairs', help='Physical pairs/ranges: 1:1,3-6:4-7')
    group.add_argument('--pairs-file', type=Path, help='Hash-bound JSON page map')
    group.add_argument('--all', action='store_true', help='Same-number pairs; equal page counts only')
    parser.add_argument('--out', required=True, type=Path)
    parser.add_argument('--dpi', type=int, default=120)
    parser.add_argument('--save', choices=('all', 'changed', 'none'), default='all')
    parser.add_argument('--require-complete', action='store_true')
    args = parser.parse_args()
    expected = None
    if args.pairs_file:
        mapping = json.loads(args.pairs_file.read_text(encoding='utf-8-sig'))
        expected = (mapping['before_sha256'], mapping['after_sha256'])
        pairs = [(row['before'], row['after']) for row in mapping['pairs']]
    else:
        pairs = parse_pairs(args.pairs) if args.pairs else None
    report = compare(args.before, args.after, pairs, args.out, args.dpi, args.save, expected, args.require_complete)
    print(json.dumps(dict(report=str((args.out / 'comparison.json').resolve()),
                          pairs=len(report['pages']), identical=report['identical'],
                          unmapped_before_count=len(report['unmapped_before']),
                          unmapped_after_count=len(report['unmapped_after']),
                          visual_review='not_performed')))


if __name__ == '__main__':
    main()
