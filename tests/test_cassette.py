"""Offline tests for the Data Cassette composition.
These check that the generated preset is built from the proven theme's formulas and is
structurally sound. They do not emulate KWGT's formula engine or Android rendering.
"""
from __future__ import annotations
import importlib.util
import json
from pathlib import Path
import re
import sys
import tempfile
import unittest
import zipfile

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT/'tools'))

def load(name):
    spec = importlib.util.spec_from_file_location(name, ROOT/'tools'/f'{name}.py')
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

build, dual, cassette, preview = load('build'), load('dual'), load('cassette'), load('preview')

def formulas(item):
    return item.get('internal_formulas', {})

def to_weekly(formula):
    """Undo the three documented differences of a five-hour module."""
    return (formula.replace('".fiveHour.', '".weekly.')
            .replace('gv(latch),"~",5))', 'gv(latch),"~",1))')
            .replace('gv(latch),"~",6))', 'gv(latch),"~",2))')
            .replace('gv(latch),"~",7))', 'gv(latch),"~",3))')
            .replace(f'df("{dual.FIVE_HOUR_RESET_FORMAT}"', f'df("{dual.WEEKLY_RESET_FORMAT}"'))

class CassetteTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.donor = json.loads((dual.DONOR/'preset.json').read_text(encoding='utf-8'))
        cls.donor_items = {i['internal_title']: i for i in cls.donor['preset_root']['viewgroup_items']}
        cls.plain = cassette.compose('CLAUDE', 'phosphor')  # donor colours: formulas comparable as text
        cls.ember = cassette.compose('CLAUDE', 'ember')
        cls.items = {i['internal_title']: i for i in cls.plain['preset_root']['viewgroup_items']}

    def pairs(self, tag):
        result = [(f'{tag} / PERCENT / {n}', f'LIVE PERCENT / {n}') for n in range(1, 5)]
        result += [(f'{tag} / REEL {n:02d} of 20', f'07.{n:02d} / QUOTA CELL {n:02d} of 20') for n in range(1, 21)]
        result += [(f'{tag} / STATE / {n:02d}', f'QUOTA / DATA STATE / {n:02d}') for n in range(1, 14)]
        cells = 23 if tag == '7D' else 12
        return result + [(f'{tag} / RESET / {n:02d}', f'RESET DATE / {n:02d}') for n in range(1, cells + 1)]

    def test_weekly_side_reuses_theme_formulas_unchanged(self):
        for mine, theirs in self.pairs('7D'):
            with self.subTest(module=mine):
                self.assertEqual(formulas(self.items[mine]).get('paint_color'),
                                 formulas(self.donor_items[theirs]).get('paint_color'))
                if 'REEL' not in mine:  # a reel step has a fixed disc path where the theme has a box
                    self.assertEqual(formulas(self.items[mine]).get('shape_path'),
                                     formulas(self.donor_items[theirs]).get('shape_path'))

    def test_five_hour_side_differs_only_by_feed_object_snapshot_slot_and_reset_format(self):
        for mine, theirs in self.pairs('5H'):
            with self.subTest(module=mine):
                for key in ('paint_color', 'shape_path'):
                    if key == 'shape_path' and 'REEL' in mine:
                        continue
                    ours, donor = formulas(self.items[mine]).get(key), formulas(self.donor_items[theirs]).get(key)
                    self.assertEqual(None if ours is None else to_weekly(ours), donor)
                    if ours is not None:
                        self.assertNotIn('.weekly.', ours)

    def test_reels_are_the_twenty_meter_cells_drawn_largest_first(self):
        order = [i['internal_title'] for i in self.plain['preset_root']['viewgroup_items']]
        for tag in ('5H', '7D'):
            steps = [t for t in order if t.startswith(f'{tag} / REEL')]
            self.assertEqual(steps, [f'{tag} / REEL {n:02d} of 20' for n in range(20, 0, -1)])
            sizes = [self.items[t]['layout'][2] for t in steps]
            self.assertEqual(sizes, sorted(sizes, reverse=True))
            self.assertAlmostEqual(sizes[0], 2 * cassette.REEL_RADIUS)
            centres = {(round(self.items[t]['layout'][0] + self.items[t]['layout'][2] / 2),
                        round(self.items[t]['layout'][1] + self.items[t]['layout'][3] / 2)) for t in steps}
            self.assertEqual(len(centres), 1)  # concentric
            # The hub, its teeth and the spindle are drawn after every step, so tape never covers them.
            self.assertGreater(order.index(f'{tag} / hub'), order.index(steps[-1]))
            self.assertGreater(order.index(f'{tag} / hub teeth'), order.index(f'{tag} / hub'))
            for title in steps:
                item = self.items[title]
                self.assertEqual(item['shape_type'], 'PATH')
                self.assertNotIn('shape_corners', item)
                self.assertRegex(item['shape_path'], r'^M0 0L0 0M100 100L100 100(M[\d.]+ [\d.]+h[\d.]+v[\d.]+h-[\d.]+Z)+$')

    def test_drawn_shapes_use_only_proven_path_commands(self):
        text = ''.join(i.get('shape_path', '') for i in self.plain['preset_root']['viewgroup_items'])
        text += ''.join(self.plain['preset_root']['globals_list'][name]['value'] for name in cassette.HUB_FRAMES)
        self.assertEqual(set(re.findall(r'[A-Za-z]', text)) - set('MLhvHVZ'), set())

    def test_hub_formula_uses_known_functions_and_defined_frames(self):
        globals_ = self.plain['preset_root']['globals_list']
        frames = [globals_[name]['value'] for name in cassette.HUB_FRAMES]
        self.assertEqual(len(set(frames)), 3)
        self.assertEqual(len({value['index'] for value in globals_.values()}), len(globals_))
        for tag in ('5H', '7D'):
            teeth = self.items[f'{tag} / hub teeth']
            self.assertEqual(formulas(teeth)['shape_path'], cassette.HUB_FORMULA)
            self.assertEqual(teeth['shape_path'], frames[0])  # shown as-is if the formula is switched off
        donor_text = json.dumps(self.donor)
        for function in re.findall(r'\b([a-z]{2})\(', cassette.HUB_FORMULA):
            self.assertIn(function + '(', donor_text)
        for name in re.findall(r'gv\((\w+)\)', cassette.HUB_FORMULA):
            self.assertIn(name, globals_)
        self.assertEqual(cassette.HUB_FORMULA.count('('), cassette.HUB_FORMULA.count(')'))

    def test_track_listing_is_ink_on_the_paper_label(self):
        paper = self.items['LABEL / paper']['layout']
        for title, item in self.items.items():
            if ' / RESET / ' in title or title.endswith('/ track') or title.startswith('HEADER'):
                x, y, width, height = item['layout']
                self.assertEqual(item['paint_color'], cassette.INK, title)
                self.assertNotIn('paint_color', formulas(item), title)
                self.assertTrue(paper[0] <= x and x + width <= paper[0] + paper[2], title)
                self.assertTrue(paper[1] <= y and y + height <= paper[1] + paper[3], title)

    def test_one_tap_action_and_public_defaults(self):
        root = self.plain['preset_root']
        touch = self.items['TOUCH / body requests fresh web data']
        donor_event = self.donor['preset_root']['internal_events'][0]
        self.assertEqual(root['internal_events'], [dual.dual_latch(donor_event)])
        self.assertEqual(touch['internal_events'], root['internal_events'])
        for data in (self.plain, self.ember):
            globals_ = data['preset_root']['globals_list']
            self.assertEqual(globals_['source']['value'], build.PLACEHOLDER)
            self.assertEqual(globals_['latch']['value'], dual.EMPTY_LATCH)
            text = json.dumps(data)
            self.assertNotRegex(text, r'[\w.-]+\.ts\.net')
            self.assertNotRegex(text, r'100\.\d+\.\d+\.\d+')
            self.assertNotIn('desktop-', text)

    def test_structure_matches_the_native_themes(self):
        packed = dual.strip_hints(self.ember)
        items = packed['preset_root']['viewgroup_items']
        self.assertTrue(all(i['internal_type'] == 'ShapeModule' for i in items))
        self.assertEqual({i['shape_type'] for i in items}, {'RECT', 'PATH'})
        allowed = set().union(*(set(i) for i in self.donor['preset_root']['viewgroup_items']))
        for item in items:
            with self.subTest(module=item['internal_title']):
                self.assertLessEqual(set(item), allowed)
                self.assertEqual('shape_path' in item, item['shape_type'] == 'PATH')
                for key in formulas(item):
                    self.assertEqual(item['internal_toggles'].get(key), 10)
                    self.assertTrue(formulas(item)[key].startswith('$') and formulas(item)[key].endswith('$'))
                    self.assertEqual(formulas(item)[key].count('('), formulas(item)[key].count(')'))
        text = json.dumps(packed)
        for variable in re.findall(r'gv\((p\d+)\)', text):
            self.assertIn(variable, packed['preset_root']['globals_list'])
        self.assertEqual(len({i['internal_title'] for i in items}), len(items))

    def test_layout_stays_inside_the_card_and_text_does_not_collide(self):
        placed = [(i['internal_title'], i['layout']) for i in self.ember['preset_root']['viewgroup_items']
                  if 'layout' in i and not i['internal_title'].startswith('TOUCH')]
        for title, (x, y, width, height) in placed:
            with self.subTest(module=title):
                self.assertGreaterEqual(x, 50); self.assertLessEqual(x + width, 1390)
                self.assertGreaterEqual(y, 46); self.assertLessEqual(y + height, 554)
        text = [(t, box) for t, box in placed
                if re.search(r'PERCENT|STATE|RESET /|AGE|FETCH|track|tag$|plate text|HEADER|LABEL / (side|lengths|kind)'
                             r'|SHELL / (type|noise)|PANEL / poll', t)]
        self.assertGreater(len(text), 100)
        for index, (title, (x, y, width, height)) in enumerate(text):
            for other, (ox, oy, ow, oh) in text[index + 1:]:
                overlap = x < ox + ow and ox < x + width and y < oy + oh and oy < y + height
                self.assertFalse(overlap, f'{title} overlaps {other}')

    def test_archive_is_reproducible_and_carries_no_preview_hints(self):
        with tempfile.TemporaryDirectory() as td:
            one = cassette.build_cassette(Path(td)/'one', 'CLAUDE')
            two = cassette.build_cassette(Path(td)/'two', 'CLAUDE')
            self.assertEqual(one.read_bytes(), two.read_bytes())
            with zipfile.ZipFile(one) as archive:
                self.assertEqual(set(archive.namelist()), {'preset.json', 'preset_thumb_landscape.jpg',
                                                          'preset_thumb_portrait.jpg'})
                data = json.loads(archive.read('preset.json'))
            for item in data['preset_root']['viewgroup_items']:
                self.assertNotIn('layout', item); self.assertNotIn('text', item)
            self.assertEqual(data['preset_info']['title'], 'CD4.2 / Data Cassette / CLAUDE')

    def test_preview_draws_both_sample_states(self):
        for name, sample in preview.SAMPLES.items():
            with self.subTest(sample=name):
                svg = preview.draw('cassette', 'CLAUDE', 'ember', sample)
                self.assertTrue(svg.startswith('<svg ')); self.assertGreater(svg.count('<polygon '), 1000)

if __name__ == '__main__':
    unittest.main()
