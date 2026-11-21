"""Offline tests for the two-meter Ember Dual composition.
These check that the generated preset is built only from the proven theme's formulas and is
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

build, dual, preview = load('build'), load('dual'), load('dual_preview')

def formulas(item):
    return item.get('internal_formulas', {})

class DualTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.donor = json.loads((dual.DONOR/'preset.json').read_text(encoding='utf-8'))
        cls.donor_items = {i['internal_title']: i for i in cls.donor['preset_root']['viewgroup_items']}
        cls.plain = dual.compose('CLAUDE', 'phosphor')  # donor colours: formulas comparable as text
        cls.ember = dual.compose('CLAUDE', 'ember')
        cls.items = {i['internal_title']: i for i in cls.plain['preset_root']['viewgroup_items']}

    def test_weekly_row_reuses_theme_formulas_unchanged(self):
        pairs = [(f'7D / PERCENT / {n}', f'LIVE PERCENT / {n}') for n in range(1, 5)]
        pairs += [(f'7D / CELL {n:02d} of 20', f'07.{n:02d} / QUOTA CELL {n:02d} of 20') for n in range(1, 21)]
        pairs += [(f'7D / RESET / {n:02d}', f'RESET DATE / {n:02d}') for n in range(1, 24)]
        pairs += [(f'7D / STATE / {n:02d}', f'QUOTA / DATA STATE / {n:02d}') for n in range(1, 14)]
        for mine, theirs in pairs:
            with self.subTest(module=mine):
                for key in ('shape_path', 'paint_color'):
                    self.assertEqual(formulas(self.items[mine]).get(key), formulas(self.donor_items[theirs]).get(key))

    def test_five_hour_row_differs_only_by_feed_object_snapshot_slot_and_reset_format(self):
        for n in range(1, 13):
            with self.subTest(cell=n):
                mine = formulas(self.items[f'5H / RESET / {n:02d}'])['shape_path']
                theirs = formulas(self.donor_items[f'RESET DATE / {n:02d}'])['shape_path']
                restored = (mine.replace('".fiveHour.', '".weekly.')
                            .replace('gv(latch),"~",5))', 'gv(latch),"~",1))')
                            .replace('gv(latch),"~",6))', 'gv(latch),"~",2))')
                            .replace('gv(latch),"~",7))', 'gv(latch),"~",3))')
                            .replace(f'df("{dual.FIVE_HOUR_RESET_FORMAT}"', f'df("{dual.WEEKLY_RESET_FORMAT}"'))
                self.assertEqual(restored, theirs)
                self.assertNotIn('.weekly.', mine)
                # The request marker and the source time stay shared by both rows.
                self.assertIn('lv(tap,tc(split,gv(latch),"~",0)+0)', mine)
                self.assertIn('lv(ht,tc(split,gv(latch),"~",4))', mine)
        for title, item in self.items.items():
            if title.startswith('5H / ') and formulas(item):
                text = json.dumps(formulas(item))
                self.assertNotIn('.weekly.', text, title)
                self.assertNotRegex(text, r'gv\(latch\),\\"~\\",[123]\)\)', title)

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
        allowed = set().union(*(set(i) for i in self.donor['preset_root']['viewgroup_items']))
        for item in items:
            with self.subTest(module=item['internal_title']):
                self.assertLessEqual(set(item), allowed)
                for key in formulas(item):
                    self.assertEqual(item['internal_toggles'].get(key), 10)
                    self.assertTrue(formulas(item)[key].startswith('$') and formulas(item)[key].endswith('$'))
                    self.assertEqual(formulas(item)[key].count('('), formulas(item)[key].count(')'))
        text = json.dumps(packed)
        for variable in re.findall(r'gv\((p\d+)\)', text):
            self.assertIn(variable, packed['preset_root']['globals_list'])
        self.assertEqual(len({i['internal_title'] for i in items}), len(items))
        self.assertNotEqual(packed['preset_info']['id'], self.donor['preset_info']['id'])

    def test_layout_stays_inside_the_card_and_text_runs_do_not_collide(self):
        boxes = [(i['internal_title'], i['layout']) for i in self.ember['preset_root']['viewgroup_items']
                 if 'layout' in i and not i['internal_title'].startswith('TOUCH')]
        for title, (x, y, width, height) in boxes:
            with self.subTest(module=title):
                self.assertGreaterEqual(x, 60); self.assertLessEqual(x + width, 1380)
                self.assertGreaterEqual(y, 56); self.assertLessEqual(y + height, 544)
        for index, (title, (x, y, width, height)) in enumerate(boxes):
            for other, (ox, oy, ow, oh) in boxes[index + 1:]:
                overlap = x < ox + ow and ox < x + width and y < oy + oh and oy < y + height
                self.assertFalse(overlap, f'{title} overlaps {other}')

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

    def test_unsupported_label_or_palette_fails(self):
        for label in ('x'*21, '中文'):
            with self.subTest(label=label), self.assertRaises(ValueError):
                dual.compose(label)
        with self.assertRaises(ValueError): dual.compose('USAGE', 'neon')

    def test_preview_draws_every_visible_module(self):
        for name, sample in preview.SAMPLES.items():
            with self.subTest(sample=name):
                svg = preview.draw('CLAUDE', 'ember', sample)
                self.assertTrue(svg.startswith('<svg ')); self.assertGreater(svg.count('<rect '), 400)

if __name__ == '__main__':
    unittest.main()
