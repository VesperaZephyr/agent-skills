#!/usr/bin/env python3
"""Bulk-register source inventory units in a review_ledger.py ledger.

The input CSV is an inventory, not a review verdict. All imported units start
unreviewed. Preview is the default; --apply writes after whole-file validation.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import shutil
import sys
import uuid
from collections import Counter
from pathlib import Path

import review_ledger as ledger

REQUIRED = {'unit_id', 'source_physical_page', 'kind'}
OPTIONAL = {'source_region', 'source_identifier', 'translation_tex_file'}


def digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def run(args: argparse.Namespace) -> None:
    root, manifest_path, pages_path = ledger.ledger_paths(args.ledger_dir)
    units_path = root / 'units.csv'
    manifest = ledger.read_manifest(manifest_path)
    pages = ledger.read_csv_rows(pages_path, ledger.PAGE_FIELDS)
    units = ledger.read_csv_rows(units_path, ledger.UNIT_FIELDS)
    problems = ledger.validate_rows(manifest, pages, units)
    if problems:
        raise ValueError('invalid existing ledger: ' + '; '.join(problems[:5]))
    existing_counts = Counter(int(u['source_physical_page']) for u in units)
    for page in pages:
        number = int(page['source_physical_page'])
        if int(page['unit_count'] or '0') != existing_counts[number]:
            raise ValueError(f'page {number}: existing unit_count disagrees with units.csv')
    originals = {p: digest(p) for p in (manifest_path, pages_path, units_path)}
    by_page = {int(p['source_physical_page']): p for p in pages}
    existing = {u['unit_id'] for u in units}
    seen: set[str] = set()
    added = []
    counts: Counter[int] = Counter()
    inventory = Path(args.csv).expanduser().resolve()
    with inventory.open(encoding='utf-8-sig', newline='') as stream:
        reader = csv.DictReader(stream)
        headers = reader.fieldnames or []
        if len(headers) != len(set(headers)) or not REQUIRED <= set(headers) or set(headers) - REQUIRED - OPTIONAL:
            raise ValueError('CSV header must contain unit_id, source_physical_page, kind; optional: source_region, source_identifier, translation_tex_file')
        for line, item in enumerate(reader, 2):
            if None in item or any(value is None for value in item.values()):
                raise ValueError(f'line {line}: malformed CSV row')
            item = {k: v.strip() for k, v in item.items()}
            uid, kind = item['unit_id'], item['kind']
            if not uid or not kind or uid in existing or uid in seen:
                raise ValueError(f'line {line}: empty kind/ID or duplicate unit_id: {uid!r}')
            try:
                page_no = int(item['source_physical_page'])
            except ValueError as exc:
                raise ValueError(f'line {line}: invalid source physical page') from exc
            if page_no not in by_page or by_page[page_no]['in_scope'] != 'yes':
                raise ValueError(f'line {line}: page {page_no} outside ledger scope')
            row = dict.fromkeys(ledger.UNIT_FIELDS, '')
            tex = item.get('translation_tex_file', '')
            if tex:
                tex_path = Path(tex).expanduser()
                tex = str((tex_path if tex_path.is_absolute() else inventory.parent / tex_path).resolve())
            row.update(unit_id=uid, source_physical_page=str(page_no),
                       source_printed_page=by_page[page_no]['source_printed_page'],
                       kind=kind, source_region=item.get('source_region', ''),
                       source_identifier=item.get('source_identifier', ''),
                       translation_tex_file=tex, semantic_status='not_started',
                       repair_status='not_applicable', pdf_status='not_checked')
            added.append(row)
            seen.add(uid)
            counts[page_no] += 1
    if not added:
        raise ValueError('inventory CSV contains no units')
    for page_no, count in counts.items():
        by_page[page_no]['unit_count'] = str(int(by_page[page_no]['unit_count'] or '0') + count)
    units.extend(added)
    print(f'{"APPLY" if args.apply else "PREVIEW"}: {len(added)} new units; ' +
          ', '.join(f'p{page}={counts[page]}' for page in sorted(counts)))
    print('All imported units remain not_started / not_checked; page review statuses are unchanged.')
    if not args.apply:
        return
    if any(digest(path) != old for path, old in originals.items()):
        raise ValueError('ledger changed during import; retry after other writers finish')
    backup = root / ('bulk-import-backup-' + uuid.uuid4().hex)
    backup.mkdir()
    for path in (pages_path, units_path):
        shutil.copy2(path, backup / path.name)
    try:
        ledger.write_csv_atomic(units_path, ledger.UNIT_FIELDS, units)
        ledger.write_csv_atomic(pages_path, ledger.PAGE_FIELDS, pages)
    except Exception:
        for path in (pages_path, units_path):
            shutil.copy2(backup / path.name, path)
        raise
    print(f'Backups: {backup}')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--ledger-dir', required=True, help='directory created by review_ledger.py init')
    parser.add_argument('--csv', required=True, help='source inventory CSV; relative TeX paths resolve from this file')
    parser.add_argument('--apply', action='store_true', help='write validated new units; default is preview only')
    args = parser.parse_args()
    try:
        run(args)
    except (OSError, ValueError, csv.Error, KeyError) as exc:
        print(f'import_review_units: {exc}', file=sys.stderr)
        return 2
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
