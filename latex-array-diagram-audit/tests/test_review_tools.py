"""Behavioral checks with disposable PDFs; no book source mutation."""
import importlib.util
import json
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch
import pymupdf

SCRIPTS = Path(__file__).resolve().parents[1] / 'scripts'


def load(name):
    spec = importlib.util.spec_from_file_location(name, SCRIPTS / (name + '.py'))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


freeze = load('freeze_review_pdf')
compare = load('compare_pdf_pages')
lattice = load('generate_clipped_lattice')


def pdf(path, texts):
    with pymupdf.open() as doc:
        for text in texts:
            page = doc.new_page(width=200, height=200)
            page.insert_text((25, 50), text)
        doc.save(path)


class ToolsTest(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.root = Path(self.temp.name)
        self.before, self.after = self.root / 'before.pdf', self.root / 'after.pdf'
        pdf(self.before, ['alpha', 'beta'])
        pdf(self.after, ['alpha', 'changed'])

    def tearDown(self):
        self.temp.cleanup()

    def test_frozen_bytes_and_no_overwrite(self):
        result = freeze.freeze(self.before, self.root / 'frozen')
        self.assertEqual(Path(result['frozen_pdf']).read_bytes(), self.before.read_bytes())
        self.assertEqual(result['pages'], 2)
        with self.assertRaises(FileExistsError):
            freeze.freeze(self.before, self.root / 'frozen')
        with self.assertRaises(ValueError):
            freeze.freeze(self.before, self.root / 'wrong', expected='0' * 64)
        self.assertFalse((self.root / 'wrong').exists())

    def test_mid_copy_mutation_invalidates_bundle(self):
        original_copy = freeze.shutil.copyfile

        def mutating_copy(source, target):
            original_copy(source, target)
            source.write_bytes(source.read_bytes() + b'\n% changed')

        with patch.object(freeze.shutil, 'copyfile', side_effect=mutating_copy):
            with self.assertRaises(ValueError):
                freeze.freeze(self.before, self.root / 'bad')
        self.assertTrue((self.root / 'bad' / 'INVALID.json').exists())
        self.assertFalse((self.root / 'bad' / 'snapshot.json').exists())

    def test_changed_only_and_explicit_mapping(self):
        report = compare.compare(self.before, self.after, None, self.root / 'cmp', save='changed')
        self.assertEqual(report['identical'], 1)
        self.assertEqual(len(list((self.root / 'cmp').glob('*.png'))), 2)
        self.assertEqual(report['pages'][0]['visual_review'], 'not_performed')
        self.assertIsNone(report['pages'][0]['before']['image'])
        inserted = self.root / 'inserted.pdf'
        pdf(inserted, ['new page', 'alpha', 'beta'])
        with self.assertRaises(ValueError):
            compare.compare(self.before, inserted, None, self.root / 'unequal')
        mapped = compare.compare(self.before, inserted, [(1, 2), (2, 3)], self.root / 'mapped', save='none')
        self.assertEqual(mapped['identical'], 2)
        self.assertEqual(mapped['unmapped_after'], [1])
        self.assertFalse(list((self.root / 'mapped').glob('*.png')))

    def test_rejects_duplicate_stale_and_incomplete_maps(self):
        for pairs in [[(1, 1), (1, 2)], [(1, 1), (2, 1)], [(0, 1)]]:
            with self.assertRaises(ValueError):
                compare.compare(self.before, self.after, pairs, self.root / 'reject')
        with self.assertRaises(ValueError):
            compare.compare(self.before, self.after, [(1, 1)], self.root / 'partial', require_complete=True)
        with self.assertRaises(ValueError):
            compare.compare(self.before, self.after, None, self.root / 'stale', expected=('0' * 64, '0' * 64))
        self.assertEqual(compare.parse_pairs('1:2,3-5:4-6'), [(1, 2), (3, 4), (4, 5), (5, 6)])
        with self.assertRaises(ValueError):
            compare.parse_pairs('1-3:2-3')

    def test_comparison_detects_mid_render_mutation(self):
        real_sha = compare.sha
        calls = 0

        def changing_sha(path):
            nonlocal calls
            calls += 1
            return real_sha(path) if calls <= 2 else 'f' * 64

        with patch.object(compare, 'sha', side_effect=changing_sha):
            with self.assertRaises(ValueError):
                compare.compare(self.before, self.after, None, self.root / 'race', save='none')
        self.assertTrue((self.root / 'race' / 'INVALID.json').exists())
        self.assertFalse((self.root / 'race' / 'comparison.json').exists())

    def test_cli_hash_bound_pairs_file(self):
        mapping = self.root / 'map.json'
        mapping.write_text(json.dumps(dict(before_sha256=compare.sha(self.before),
                                          after_sha256=compare.sha(self.after),
                                          pairs=[dict(before=1, after=1)])), encoding='utf-8')
        result = subprocess.run([sys.executable, str(SCRIPTS / 'compare_pdf_pages.py'),
                                 str(self.before), str(self.after), '--pairs-file', str(mapping),
                                 '--save', 'none', '--out', str(self.root / 'cli')], capture_output=True)
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(json.loads(result.stdout)['unmapped_before_count'], 1)
        saved = json.loads((self.root / 'cli' / 'comparison.json').read_text(encoding='utf-8'))
        self.assertEqual(saved['unmapped_before'], [2])
        self.assertEqual(json.loads(result.stdout)['visual_review'], 'not_performed')

    def test_non_node_boundary_intersection(self):
        self.assertEqual(lattice.clipped_segment(-1, 1, 3, 2, 6, -5), (.5, 1.0))
        self.assertIsNone(lattice.clipped_segment(-3, 0, 3, 2, 6, -5))
        for dx, dy in [(1, 0), (2, 1), (3, 2)]:
            output = lattice.generate(dx=dx, dy=dy)
            self.assertEqual(output.count('\\fill '), 42)
        with self.assertRaises(ValueError):
            lattice.generate(dx=0)


if __name__ == '__main__':
    unittest.main()
