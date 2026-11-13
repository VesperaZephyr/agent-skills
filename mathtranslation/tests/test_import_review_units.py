import csv
import os
import subprocess
import sys
import tempfile
import unittest
import uuid
from pathlib import Path

SCRIPTS = Path(__file__).resolve().parent.parent / 'scripts'


class ImportTest(unittest.TestCase):
    def setUp(self):
        self.root = Path(os.environ.get('MATH_REVIEW_TEST_DIR', tempfile.gettempdir())) / ('math-review-test-' + uuid.uuid4().hex)
        self.root.mkdir(parents=True)
        source, target = self.root / 'source.pdf', self.root / 'target.pdf'
        source.write_bytes(b'fake-source-for-page-count-test')
        target.write_bytes(b'fake-target-for-page-count-test')
        self.ledger = self.root / 'ledger'
        r = subprocess.run([sys.executable, str(SCRIPTS / 'review_ledger.py'), 'init',
            '--source', str(source), '--translation', str(target), '--ledger-dir', str(self.ledger),
            '--source-page-count', '5', '--translation-page-count', '5', '--scope-start', '2',
            '--scope-end', '4'], capture_output=True, text=True, encoding='utf-8')
        self.assertEqual(r.returncode, 0, r.stderr)
        self.csv = self.root / 'inventory.csv'

    def call(self, apply=False):
        args = [sys.executable, str(SCRIPTS / 'import_review_units.py'), '--ledger-dir', str(self.ledger), '--csv', str(self.csv)]
        if apply:
            args.append('--apply')
        return subprocess.run(args, capture_output=True, text=True, encoding='utf-8')

    def rows(self, name):
        with (self.ledger / name).open(encoding='utf-8-sig', newline='') as f:
            return list(csv.DictReader(f))

    def test_preview_apply_and_duplicate_are_safe(self):
        self.csv.write_text('unit_id,source_physical_page,kind,source_identifier\nu1,2,formula,closure\nu2,4,paragraph,opening\n', encoding='utf-8')
        before = {n: (self.ledger / n).read_bytes() for n in ('pages.csv', 'units.csv')}
        preview = self.call()
        self.assertEqual(preview.returncode, 0, preview.stderr)
        self.assertEqual(before, {n: (self.ledger / n).read_bytes() for n in before})
        apply = self.call(True)
        self.assertEqual(apply.returncode, 0, apply.stderr)
        rows = self.rows('units.csv')
        self.assertEqual([r['unit_id'] for r in rows], ['u1', 'u2'])
        self.assertTrue(all(r['semantic_status'] == 'not_started' and r['pdf_status'] == 'not_checked' for r in rows))
        pages = {int(r['source_physical_page']): r for r in self.rows('pages.csv')}
        self.assertEqual((pages[2]['unit_count'], pages[4]['unit_count']), ('1', '1'))
        self.assertEqual(pages[2]['source_inventory_status'], 'not_started')
        after = {n: (self.ledger / n).read_bytes() for n in before}
        self.assertEqual(self.call(True).returncode, 2)
        self.assertEqual(after, {n: (self.ledger / n).read_bytes() for n in before})
        self.assertEqual(len(list(self.ledger.glob('bulk-import-backup-*'))), 1)

    def test_reject_invalid_and_unknown_verdict_fields_without_writes(self):
        before = {n: (self.ledger / n).read_bytes() for n in ('pages.csv', 'units.csv')}
        cases = ['unit_id,source_physical_page,kind\nx,5,formula\n',
                 'unit_id,source_physical_page,kind\nx,2,formula\nx,3,formula\n',
                 'unit_id,source_physical_page,kind,semantic_status\nx,2,formula,matched\n']
        for value in cases:
            self.csv.write_text(value, encoding='utf-8')
            self.assertEqual(self.call(True).returncode, 2)
            self.assertEqual(before, {n: (self.ledger / n).read_bytes() for n in before})

    def test_reject_existing_page_count_mismatch(self):
        pages = self.rows('pages.csv')
        pages[1]['unit_count'] = '1'
        with (self.ledger / 'pages.csv').open('w', encoding='utf-8-sig', newline='') as f:
            writer = csv.DictWriter(f, fieldnames=pages[0].keys())
            writer.writeheader()
            writer.writerows(pages)
        self.csv.write_text('unit_id,source_physical_page,kind\nx,2,formula\n', encoding='utf-8')
        before = {n: (self.ledger / n).read_bytes() for n in ('pages.csv', 'units.csv')}
        result = self.call(True)
        self.assertEqual(result.returncode, 2)
        self.assertIn('unit_count disagrees', result.stderr)
        self.assertEqual(before, {n: (self.ledger / n).read_bytes() for n in before})


if __name__ == '__main__':
    unittest.main()
