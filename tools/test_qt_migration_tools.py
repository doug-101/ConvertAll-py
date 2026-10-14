"""Standard-library tests for the isolated research tools (no Qt required).

Run: python3 -m unittest discover -s tools -p 'test_*.py' -v
"""

import ast
from contextlib import redirect_stderr, redirect_stdout
import io
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import benchmark_qt
import qt6_probe


ROOT = Path(__file__).resolve().parents[1]


class PrototypeTests(unittest.TestCase):
    def invoke(self, source, output):
        argv = ['qt6_probe.py', '--source', str(source), '--output', str(output)]
        with patch('sys.argv', argv), redirect_stdout(io.StringIO()), redirect_stderr(io.StringIO()):
            qt6_probe.main()

    def test_fresh_copy_preserves_engine_and_resources(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory) / 'probe'
            self.invoke(ROOT, output)
            for filename in qt6_probe.ENGINE:
                self.assertEqual((ROOT / 'source' / filename).read_bytes(),
                                 (output / 'source' / filename).read_bytes())
            for folder in ('data', 'doc', 'icons', 'translations', 'win'):
                for original in (ROOT / folder).rglob('*'):
                    if original.is_file():
                        self.assertEqual(original.read_bytes(),
                                         (output / original.relative_to(ROOT)).read_bytes())
            self.assertEqual((ROOT / 'install.py').read_bytes(), (output / 'install.py').read_bytes())
            for path in (output / 'source').glob('*.py'):
                ast.parse(path.read_text(encoding='utf-8'), filename=str(path))
            self.assertIn('PyQt6', (output / 'source' / 'convertall.py').read_text(encoding='utf-8'))
            self.assertNotIn('qApp', (output / 'source' / 'colorset.py').read_text(encoding='utf-8'))

    def test_existing_directory_is_not_overwritten(self):
        with tempfile.TemporaryDirectory() as directory:
            output = Path(directory)
            marker = output / 'keep.txt'
            marker.write_text('keep')
            with self.assertRaises(SystemExit):
                self.invoke(ROOT, output)
            self.assertEqual(marker.read_text(), 'keep')

    def test_application_directories_are_protected(self):
        target = ROOT / 'source' / '_forbidden_migration_output'
        self.assertFalse(target.exists())
        with self.assertRaises(SystemExit):
            self.invoke(ROOT, target)
        self.assertFalse(target.exists())

    def test_repository_and_its_parent_are_protected(self):
        for target in (ROOT, ROOT.parent):
            with self.assertRaises(SystemExit):
                self.invoke(ROOT, target)

    def test_unknown_checkout_is_rejected(self):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            with self.assertRaises(SystemExit):
                self.invoke(root, root / 'output')
            self.assertFalse((root / 'output').exists())

    def test_short_enums_and_exec_are_rewritten(self):
        source = 'from PyQt5.QtCore import Qt\nf(Qt.Key_Down)\nd.exec_()\n'
        result, changes = qt6_probe.transform(source, 'example.py')
        self.assertIn('PyQt6.QtCore', result)
        self.assertIn('Qt.Key.Key_Down', result)
        self.assertIn('d.exec()', result)
        self.assertEqual(changes['imports'], 1)

    def test_mismatching_audited_code_fails_loudly(self):
        with self.assertRaises(ValueError):
            qt6_probe.transform('pass\n', 'helpview.py')


class StatisticsTests(unittest.TestCase):
    def test_summary_includes_raw_samples_and_nearest_rank_p95(self):
        values = list(range(1, 21))
        result = benchmark_qt.summary(values)
        self.assertEqual(result['median'], 10.5)
        self.assertEqual(result['p95'], 19)
        self.assertEqual(result['n'], 20)
        self.assertEqual(result['samples'], values)


if __name__ == '__main__':
    unittest.main()
