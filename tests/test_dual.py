"""Offline tests for the two-meter Ember Dual composition.
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

build, dual, preview = load('build'), load('dual'), load('preview')

def formulas(item):
    return item.get('internal_formulas', {})

def to_weekly(formula):
    """Undo the three documented differences of a five-hour module."""
    return (formula.replace('".fiveHour.', '".weekly.')
            .replace('gv(latch),"~",5))', 'gv(latch),"~",1))')
            .replace('gv(latch),"~",6))', 'gv(latch),"~",2))')
            .replace('gv(latch),"~",7))', 'gv(latch),"~",3))')
            .replace(f'df("{dual.FIVE_HOUR_RESET_FORMAT}"', f'df("{dual.WEEKLY_RESET_FORMAT}"'))

class DualTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.donor = json.loads((dual.DONOR/'preset.json').read_text(encoding='utf-8'))
        cls.donor_items = {i['internal_title']: i for i in cls.donor['preset_root']['viewgroup_items']}
        cls.plain = dual.compose('CLAUDE', 'phosphor')  # donor colours: formulas comparable as text
        cls.ember = dual.compose('CLAUDE', 'ember')
        cls.items = {i['internal_title']: i for i in cls.plain['preset_root']['viewgroup_items']}

    def pairs(self, tag):
        result = [(f'{tag} / PERCENT / {n}', f'LIVE PERCENT / {n}') for n in range(1, 5)]
        result += [(f'{tag} / CELL {n:02d} of 20', f'07.{n:02d} / QUOTA CELL {n:02d} of 20') for n in range(1, 21)]
        result += [(f'{tag} / STATE / {n:02d}', f'QUOTA / DATA STATE / {n:02d}') for n in range(1, 14)]
        cells = 23 if tag == '7D' else 12
        return result + [(f'{tag} / RESET / {n:02d}', f'RESET DATE / {n:02d}') for n in range(1, cells + 1)]

    def test_weekly_row_reuses_theme_formulas_unchanged(self):
        for mine, theirs in self.pairs('7D'):
            with self.subTest(module=mine):
                for key in ('shape_path', 'paint_color'):
                    self.assertEqual(formulas(self.items[mine]).get(key), formulas(self.donor_items[theirs]).get(key))

    def test_five_hour_row_differs_only_by_feed_object_snapshot_slot_and_reset_format(self):
        for mine, theirs in self.pairs('5H'):
            with self.subTest(module=mine):
                for key in ('shape_path', 'paint_color'):
                    ours, donor = formulas(self.items[mine]).get(key), formulas(self.donor_items[theirs]).get(key)
                    self.assertEqual(None if ours is None else to_weekly(ours), donor)
                    if ours is not None:
                        self.assertNotIn('.weekly.', ours)
                        # The request marker and the source time stay shared by both rows.
                        self.assertIn('lv(tap,tc(split,gv(latch),"~",0)+0)', ours)
        for title, item in self.items.items():
            if title.startswith('5H / ') and formulas(item):
                text = json.dumps(formulas(item))
                self.assertNotIn('.weekly.', text, title)
                self.assertNotRegex(text, r'gv\(latch\),\\"~\\",[123]\)\)', title)

    def test_meter_segments_are_the_theme_cells_drawn_leaning(self):
        for tag in ('5H', '7D'):
            lefts = []
            for n in range(1, 21):
                item = self.items[f'{tag} / CELL {n:02d} of 20']
                self.assertEqual(item['shape_type'], 'PATH')
                self.assertNotIn('shape_corners', item)
                self.assertRegex(item['shape_path'], r'^M0 0L0 0M100 100L100 100M[\d.]+ 0L100 0L[\d.]+ 100L0 100Z$')
                self.assertNotIn('shape_path', formulas(item))
                lefts.append(item['layout'][0])
            self.assertEqual(lefts, [dual.METER_X + dual.CELL_PITCH * n for n in range(20)])

    def test_time_left_line_adds_one_step_to_the_theme_reset_formula(self):
        donor_reset = formulas(self.donor_items['RESET DATE / 01'])['shape_path']
        donor_statements = donor_reset[1:-1].split('$$')
        shared = donor_statements[:1 + next(i for i, s in enumerate(donor_statements) if s.startswith('lv(rgood,'))]
        donor_text = json.dumps(self.donor)
        for row in dual.ROWS:
            line = self.items[f'{row["tag"]} / TIME LEFT']
            self.assertEqual(line['shape_type'], 'RECT')
            for key in ('shape_width', 'paint_color'):
                with self.subTest(row=row['tag'], formula=key):
                    formula = formulas(line)[key]
                    self.assertEqual(line['internal_toggles'][key], 10)
                    statements = to_weekly(formula)[1:-1].split('$$')
                    self.assertEqual(statements[:len(shared)], shared)  # the theme's validated reset time, untouched
                    self.assertEqual(len(statements), len(shared) + 2)
                    self.assertEqual(
                        statements[len(shared)],
                        f'lv(left,if(lv(rgood)=1,mu(max,0,mu(min,1,(df(S,dp(lv(riso),auto))-df(S))/{row["seconds"]})),0))')
                    added = '$$'.join(statements[len(shared):])
                    for function in re.findall(r'\b([a-z]{2})\(', added):
                        self.assertIn(function + '(', donor_text)  # only functions the themes already use
                    defined = set(re.findall(r'lv\((\w+),', formula))
                    self.assertLessEqual(set(re.findall(r'lv\((\w+)\)', formula)), defined)
                    self.assertEqual(formula.count('('), formula.count(')'))
                    if row['field'] != 'weekly':
                        self.assertNotIn('.weekly.', formula)
            self.assertTrue(formulas(line)['shape_width'].endswith(f'$$lv(left)*{dual.METER_WIDTH}*{dual.SCALE}$'))
            self.assertTrue(formulas(line)['paint_color'].endswith(
                f'$$if(lv(rgood)!=1,"{dual.DIM}",(lv(q)+0)<lv(left)*100,"{dual.ALERT}","{dual.LABEL}")$'))
            self.assertEqual(line['layout'][2], dual.METER_WIDTH)
        self.assertEqual([row['seconds'] for row in dual.ROWS], [18000, 604800])

    def test_one_tap_action_captures_both_rows(self):
        root = self.plain['preset_root']
        touch = self.items['TOUCH / body requests fresh web data']
        self.assertEqual(root['internal_events'], touch['internal_events'])
        self.assertEqual(len(touch['internal_events']), 1)
        event = touch['internal_events'][0]
        donor_event = self.donor['preset_root']['internal_events'][0]
        self.assertEqual({k: v for k, v in event.items() if k != 'switch_text'},
                         {k: v for k, v in donor_event.items() if k != 'switch_text'})
        text, donor_text = event['switch_text'], donor_event['switch_text']
        donor_body = donor_text[1:-1].split('$$')[:-1]
        statements = text[1:-1].split('$$')
        self.assertEqual(statements[:len(donor_body)], donor_body)  # the theme's own logic runs first, untouched
        added = statements[len(donor_body):-1]
        self.assertEqual([re.match(r'lv\((\w+),', s).group(1) for s in added],
                         ['hqx', 'hax', 'hrx', 'fallbackx', 'rawx', 'readurlx', 'qx', 'ax', 'rx', 'nx', 'okx'])
        self.assertTrue(all('.weekly.' not in s for s in added))
        defined = set(re.findall(r'lv\((\w+),', text))
        used = set(re.findall(r'lv\((\w+)\)', text))
        self.assertLessEqual(used, defined)  # no dangling local in the hand-assembled result
        # Eight fields either way: marker, then weekly quota/available/reset/source time (new or
        # held), then five-hour quota/available/reset (new or held).
        self.assertEqual(
            statements[-1],
            'df(S)+"~"+if(lv(ok)=1,lv(q)+"~"+lv(a)+"~"+tc(reg,lv(r),"[~]","")+"~"+tc(reg,lv(t),"[~]",""),'
            'lv(hq)+"~"+lv(ha)+"~"+lv(hr)+"~"+lv(ht))'
            '+"~"+if(lv(okx)=1,lv(qx)+"~"+lv(ax)+"~"+tc(reg,lv(rx),"[~]",""),lv(hqx)+"~"+lv(hax)+"~"+lv(hrx))')
        self.assertEqual(self.plain['preset_root']['globals_list']['latch']['value'].count('~'), 7)

    def test_public_defaults_and_no_private_hostnames(self):
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
        self.assertEqual(set(re.findall(r'[A-Za-z]', ''.join(i.get('shape_path', '') for i in items))) - set('MLhvHVZ'),
                         set())  # only path commands the themes already draw with
        self.assertEqual(len({i['internal_title'] for i in items}), len(items))
        self.assertNotEqual(packed['preset_info']['id'], self.donor['preset_info']['id'])

    def test_layout_stays_inside_the_card_and_text_does_not_collide(self):
        placed = [(i['internal_title'], i['layout']) for i in self.ember['preset_root']['viewgroup_items']
                  if 'layout' in i and not i['internal_title'].startswith('TOUCH')]
        for title, (x, y, width, height) in placed:
            with self.subTest(module=title):
                self.assertGreaterEqual(x, 60); self.assertLessEqual(x + width, 1380)
                self.assertGreaterEqual(y, 56); self.assertLessEqual(y + height, 544)
        text = [(t, box) for t, box in placed
                if re.search(r'PERCENT|STATE|RESET /|AGE|FETCH|resets tag|plate text|HEADER / [A-Z]+$|legend', t)]
        self.assertGreater(len(text), 100)
        for index, (title, (x, y, width, height)) in enumerate(text):
            for other, (ox, oy, ow, oh) in text[index + 1:]:
                overlap = x < ox + ow and ox < x + width and y < oy + oh and oy < y + height
                self.assertFalse(overlap, f'{title} overlaps {other}')
        # Each row's meter, time line and reset text stay clear of its digits and of the other row.
        for row, other in zip(dual.ROWS, reversed(dual.ROWS)):
            mine = [box for t, box in placed if t.startswith(row['tag'] + ' / ')]
            theirs = [box for t, box in placed if t.startswith(other['tag'] + ' / ')]
            for x, y, width, height in mine:
                for ox, oy, ow, oh in theirs:
                    self.assertFalse(x < ox + ow and ox < x + width and y < oy + oh and oy < y + height)

    def test_ember_palette_replaces_every_theme_colour(self):
        text = json.dumps(self.ember).upper()
        for donor_colour in dual.EMBER:
            self.assertNotIn(donor_colour, text)
        self.assertIn('#FFD97757', text)
        self.assertEqual(len(set(dual.EMBER.values())), len(dual.EMBER))  # roles stay distinguishable

    def test_archive_is_reproducible_and_carries_no_preview_hints(self):
        with tempfile.TemporaryDirectory() as td:
            one = dual.build_dual(Path(td)/'one', 'CLAUDE')
            two = dual.build_dual(Path(td)/'two', 'CLAUDE')
            self.assertEqual(one.read_bytes(), two.read_bytes())
            with zipfile.ZipFile(one) as archive:
                self.assertEqual(set(archive.namelist()), {'preset.json', 'preset_thumb_landscape.jpg',
                                                          'preset_thumb_portrait.jpg'})
                data = json.loads(archive.read('preset.json'))
            for item in data['preset_root']['viewgroup_items']:
                self.assertNotIn('layout', item); self.assertNotIn('text', item)
            self.assertEqual(data['preset_info']['title'], 'CD4.2 / Ember Dual / CLAUDE')

    def test_published_downloads_match_the_builder(self):
        sums = (ROOT/'dual'/'SHA256SUMS.txt').read_text().split()
        with tempfile.TemporaryDirectory() as td:
            for label in ('CLAUDE', 'CODEX'):
                with self.subTest(label=label):
                    built = dual.build_dual(Path(td)/label, label)
                    published = ROOT/'dual'/built.name
                    self.assertEqual(published.read_bytes(), built.read_bytes())
                    self.assertIn(built.name, sums)
                    with zipfile.ZipFile(published) as archive:
                        data = json.loads(archive.read('preset.json'))
                    self.assertEqual(data['preset_root']['globals_list']['source']['value'], build.PLACEHOLDER)
                    self.assertNotRegex(json.dumps(data), r'[\w.-]+\.ts\.net')

    def test_unsupported_label_or_palette_fails(self):
        for label in ('x'*21, '中文'):
            with self.subTest(label=label), self.assertRaises(ValueError):
                dual.compose(label)
        with self.assertRaises(ValueError): dual.compose('USAGE', 'neon')

    def test_preview_draws_both_sample_states(self):
        for name, sample in preview.SAMPLES.items():
            with self.subTest(sample=name):
                svg = preview.draw('dual', 'CLAUDE', 'ember', sample)
                self.assertTrue(svg.startswith('<svg ')); self.assertGreater(svg.count('<polygon '), 400)

if __name__ == '__main__':
    unittest.main()
