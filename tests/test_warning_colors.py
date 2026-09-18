"""Regression checks for the actual final color expressions in all six presets.

The small interpreter below supports only their color-expression subset. It does
not emulate KWGT networking, snapshot selection, Android, or on-device rendering.
"""
from __future__ import annotations
import ast
import hashlib
import json
from pathlib import Path
import re
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
LOW = 'lv(ok)=1 & lv(q)+0<10'


def color(formula, **state):
    expression = formula.rsplit('$$', 1)[-1].strip('$')
    expression = re.sub(r'\bif\(', 'choose(', expression)
    expression = re.sub(r'(?<![<>=!])=(?!=)', '==', expression)
    expression = expression.replace('&', ' and ').replace('|', ' or ')
    tree = ast.parse(expression, mode='eval').body

    def visit(node):
        if isinstance(node, ast.Constant):
            return node.value
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Name):
            if node.func.id == 'lv':
                return state[node.args[0].id]
            if node.func.id == 'choose':
                for index in range(0, len(node.args) - 1, 2):
                    if visit(node.args[index]):
                        return visit(node.args[index + 1])
                return visit(node.args[-1])
        if isinstance(node, ast.BoolOp):
            values = (visit(value) for value in node.values)
            return all(values) if isinstance(node.op, ast.And) else any(values)
        if isinstance(node, ast.BinOp) and isinstance(node.op, ast.Add):
            return visit(node.left) + visit(node.right)
        if isinstance(node, ast.Compare) and len(node.ops) == 1:
            left, right = visit(node.left), visit(node.comparators[0])
            op = node.ops[0]
            if isinstance(op, ast.Eq): return left == right
            if isinstance(op, ast.NotEq): return left != right
            if isinstance(op, ast.Lt): return left < right
            if isinstance(op, ast.Gt): return left > right
        raise AssertionError('Unsupported color syntax: ' + ast.dump(node))

    return visit(tree)


class WarningColorTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = [(p, json.loads(p.read_text(encoding='utf-8')))
                       for p in sorted((ROOT / 'src').glob('*/preset.json'))]
        cls.formulas = []
        for path, data in cls.sources:
            for item in data['preset_root']['viewgroup_items']:
                formula = item.get('internal_formulas', {}).get('paint_color', '')
                # Include the old form too, so reverting a formula fails tests.
                tail = formula.rsplit('$$', 1)[-1]
                if 'lv(q)+0<10' in tail or 'lv(code)=8' in tail:
                    cls.formulas.append((path.parent.name, item['internal_title'], formula))

    def value(self, formula, q=6, ok=1, fresh=1, code=8, cells=20):
        return color(formula, q=q, ok=ok, fresh=fresh, code=code, cells=cells)

    def test_warning_rule_covers_every_theme_and_accent(self):
        expected = [25, 25, 25, 30, 26, 26]
        self.assertEqual(len(self.sources), 6)
        for (path, _), count in zip(self.sources, expected):
            entries = [f for theme, _, f in self.formulas if theme == path.parent.name]
            self.assertEqual(len(entries), count)
            for formula in entries:
                tail = formula.rsplit('$$', 1)[-1]
                self.assertIn(LOW, tail)
                self.assertNotIn('lv(code)=8', tail)

    def test_warning_survives_stale_cached_unknown_age_and_clock_skew(self):
        for theme, title, formula in self.formulas:
            expected = self.value(formula)
            for fresh, code in ((0, 6), (1, 11), (0, 11), (0, 4), (0, 5)):
                with self.subTest(theme=theme, item=title, fresh=fresh, code=code):
                    self.assertEqual(self.value(formula, fresh=fresh, code=code), expected)

    def test_zero_and_fractional_low_values_keep_warning(self):
        # Exercise the filled-color branch; empty cells are checked separately.
        for theme, title, formula in self.formulas:
            expected = self.value(formula)
            for quota in (0, 0.01, 6, 9, 9.99):
                with self.subTest(theme=theme, item=title, quota=quota):
                    self.assertEqual(self.value(formula, q=quota, fresh=0, code=6), expected)

    def test_ten_percent_and_above_clear_the_warning(self):
        for theme, title, formula in self.formulas:
            warning = self.value(formula)
            for quota, code in ((10, 10), (50, 10), (100, 9)):
                with self.subTest(theme=theme, item=title, quota=quota):
                    self.assertNotEqual(self.value(formula, q=quota, code=code), warning)

    def test_missing_invalid_and_unavailable_are_not_low(self):
        for theme, title, formula in self.formulas:
            warning = self.value(formula)
            for quota in (None, '', 'bad', -1, 101, 6):
                for code in (1, 2, 3):
                    with self.subTest(theme=theme, item=title, quota=quota, code=code):
                        self.assertNotEqual(self.value(formula, q=quota, ok=0,
                                                       fresh=0, code=code), warning)

    def test_unfilled_cells_keep_their_off_color(self):
        for theme, title, formula in self.formulas:
            match = re.search(r'lv\(cells\)>(\d+)', formula.rsplit('$$', 1)[-1])
            if not match:
                continue
            index = int(match[1])
            for quota, cells in ((0, 0), (6, 2)):
                if index >= cells:
                    with self.subTest(theme=theme, item=title, quota=quota):
                        off = self.value(formula, ok=0, fresh=0, code=3, cells=0)
                        self.assertEqual(self.value(formula, q=quota, fresh=0,
                                                    code=6, cells=cells), off)

    def test_freshness_status_and_full_guards_are_preserved(self):
        status = 'lv(tgood)!=1,4,lv(age)<-2,5,lv(age)>15,6'
        full = 'lv(cached)=1,11,lv(q)+0=100,9,10'
        for path, data in self.sources:
            with self.subTest(theme=path.parent.name):
                items = data['preset_root']['viewgroup_items']
                state = next(i for i in items if i['internal_title'] == 'QUOTA / DATA STATE / 01')
                formula = state['internal_formulas']['shape_path']
                self.assertIn(status, formula)
                self.assertIn(full, formula)
                for label in ('STALE DATA', 'CACHED DATA', 'UNAVAILABLE', 'INVALID DATA'):
                    self.assertIn(label, formula)

    def test_shipped_archives_match_sources_and_checksums(self):
        checksums = dict(line.split()[::-1] for line in
                         (ROOT / 'presets/SHA256SUMS.txt').read_text().splitlines())
        for path, data in self.sources:
            archive_path = ROOT / 'presets' / (path.parent.name + '.kwgt')
            with self.subTest(theme=path.parent.name):
                self.assertEqual(hashlib.sha256(archive_path.read_bytes()).hexdigest(),
                                 checksums[archive_path.name])
                with zipfile.ZipFile(archive_path) as archive:
                    self.assertIsNone(archive.testzip())
                    self.assertEqual(json.loads(archive.read('preset.json')), data)


if __name__ == '__main__':
    unittest.main()
