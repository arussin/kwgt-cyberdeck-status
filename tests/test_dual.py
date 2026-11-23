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

def check_layout(test, data, rows):
    """Everything stays inside the card, text does not collide, and the two rows keep clear of each other."""
    placed = [(i['internal_title'], i['layout']) for i in data['preset_root']['viewgroup_items']
              if 'layout' in i and not i['internal_title'].startswith('TOUCH')]
    for title, (x, y, width, height) in placed:
        with test.subTest(module=title):
            test.assertGreaterEqual(x, 60); test.assertLessEqual(x + width, 1380)
            test.assertGreaterEqual(y, 56); test.assertLessEqual(y + height, 544)
    text = [(t, box) for t, box in placed
            if re.search(r'PERCENT|STATE|RESET /|AGE|FETCH|READOUT|resets tag|plate text|HEADER / [A-Z]+$|legend', t)]
    test.assertGreater(len(text), 100)
    for index, (title, (x, y, width, height)) in enumerate(text):
        for other, (ox, oy, ow, oh) in text[index + 1:]:
            overlap = x < ox + ow and ox < x + width and y < oy + oh and oy < y + height
            test.assertFalse(overlap, f'{title} overlaps {other}')
    for row, other in zip(rows, reversed(rows)):
        mine = [box for t, box in placed if t.startswith(row['tag'] + ' / ')]
        theirs = [box for t, box in placed if t.startswith(other['tag'] + ' / ')]
        test.assertGreater(len(mine), 50)
        for x, y, width, height in mine:
            for ox, oy, ow, oh in theirs:
                test.assertFalse(x < ox + ow and ox < x + width and y < oy + oh and oy < y + height)

def check_structure(test, donor, data):
    """The packed preset uses only what the native themes use, and carries no private endpoint."""
    packed = dual.strip_hints(data)
    items = packed['preset_root']['viewgroup_items']
    test.assertTrue(all(i['internal_type'] == 'ShapeModule' for i in items))
    test.assertEqual({i['shape_type'] for i in items}, {'RECT', 'PATH'})
    allowed = set().union(*(set(i) for i in donor['preset_root']['viewgroup_items']))
    for item in items:
        with test.subTest(module=item['internal_title']):
            test.assertLessEqual(set(item), allowed)
            test.assertEqual('shape_path' in item, item['shape_type'] == 'PATH')
            for key in formulas(item):
                test.assertEqual(item['internal_toggles'].get(key), 10)
                test.assertTrue(formulas(item)[key].startswith('$') and formulas(item)[key].endswith('$'))
                test.assertEqual(formulas(item)[key].count('('), formulas(item)[key].count(')'))
    text = json.dumps(packed)
    for variable in re.findall(r'gv\((p\d+)\)', text):
        test.assertIn(variable, packed['preset_root']['globals_list'])
    test.assertEqual(set(re.findall(r'[A-Za-z]', ''.join(i.get('shape_path', '') for i in items))) - set('MLhvHVZ'),
                     set())  # only path commands the themes already draw with
    test.assertEqual(len({i['internal_title'] for i in items}), len(items))
    test.assertNotEqual(packed['preset_info']['id'], donor['preset_info']['id'])
    globals_ = packed['preset_root']['globals_list']
    test.assertEqual(globals_['source']['value'], build.PLACEHOLDER)
    test.assertEqual(globals_['latch']['value'], dual.EMPTY_LATCH)
    test.assertNotRegex(text, r'[\w.-]+\.ts\.net')
    test.assertNotRegex(text, r'100\.\d+\.\d+\.\d+')
    test.assertNotIn('desktop-', text)

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

    def scoped_to_weekly(self, formula):
        """Undo the documented differences of a per-model limit module."""
        return (formula.replace('".weeklyScoped.', '".weekly.')
                .replace('gv(latch),"~",8))', 'gv(latch),"~",1))')
                .replace('gv(latch),"~",9))', 'gv(latch),"~",2))')
                .replace('gv(latch),"~",10))', 'gv(latch),"~",3))'))

    def check_added_steps(self, formula, added):
        donor_text = json.dumps(self.donor)
        for function in re.findall(r'\b([a-z]{2})\(', '$$'.join(added)):
            self.assertIn(function + '(', donor_text)  # only functions the themes already use
        defined = set(re.findall(r'lv\((\w+),', formula))
        self.assertLessEqual(set(re.findall(r'lv\((\w+)\)', formula)), defined)
        self.assertEqual(formula.count('('), formula.count(')'))
        self.assertNotIn('.weekly.', formula)
        # Its held values point past the end of the snapshot, so it never shows another limit's old reading.
        self.assertNotRegex(formula, r'gv\(latch\),"~",[123567]\)\)')
        self.assertIn('lv(tap,tc(split,gv(latch),"~",0)+0)', formula)

    def test_model_limit_needle_extends_the_theme_percentage_formulas(self):
        percent = formulas(self.donor_items['LIVE PERCENT / 1'])
        checked = dual.through(percent['paint_color'], 'ok')
        fresh = dual.through(percent['paint_color'], 'fresh')
        weekly_top = dual.ROWS[1]['y']
        for title in ('7D / SCOPED shadow', '7D / SCOPED needle', '7D / SCOPED cap'):
            with self.subTest(module=title):
                item = self.items[title]
                x, y, width, height = item['layout']
                position = dual.statements(self.scoped_to_weekly(formulas(item)['position_offset_x']))
                self.assertEqual(position[:len(checked)], checked)  # the theme's validated reading, untouched
                self.assertEqual(position[len(checked):], [
                    'lv(level,if(lv(ok)=1,lv(q)+0,0))',
                    f'(si(rwidth)-1440*{dual.SCALE})/2+(({x:g})+lv(level)*8)*{dual.SCALE}'])
                colour = dual.statements(self.scoped_to_weekly(formulas(item)['paint_color']))
                if title.endswith('shadow'):
                    self.assertEqual(colour, checked + [f'if(lv(ok)!=1,"#00000000","{dual.INK}")'])
                else:
                    self.assertEqual(colour, fresh + [
                        f'if(lv(ok)!=1,"#00000000",lv(q)+0<10,"{dual.LOW}",lv(fresh)!=1,"{dual.DIM}","{dual.BRIGHT}")'])
                for key in ('position_offset_x', 'paint_color'):
                    self.assertEqual(item['internal_toggles'][key], 10)
                    self.check_added_steps(formulas(item)[key], dual.statements(formulas(item)[key])[len(checked):])
                # From empty to full it stays over the weekly meter and inside the card.
                self.assertGreaterEqual(x, dual.METER_X - 12); self.assertLessEqual(x + dual.METER_WIDTH + width, 1380)
                self.assertGreater(y, weekly_top - 24); self.assertLess(y + height, weekly_top + dual.CELL_HEIGHT + 10)
        self.assertEqual(dual.METER_WIDTH / 100, 8)
        order = [i['internal_title'] for i in self.plain['preset_root']['viewgroup_items']]
        self.assertLess(order.index('7D / SCOPED shadow'), order.index('7D / SCOPED needle'))
        self.assertGreater(order.index('7D / SCOPED shadow'), order.index('7D / CELL 20 of 20'))  # drawn over the meter

    def test_model_limit_footer_text_spells_the_feed_label_and_value(self):
        percent = formulas(self.donor_items['LIVE PERCENT / 1'])
        shown = dual.through(percent['shape_path'], 'show')
        checked = dual.through(percent['paint_color'], 'ok')
        glyphs = dual.statements(formulas(self.donor_items['QUOTA / DATA STATE / 01'])['shape_path'])[-1]
        cells = [self.items[f'SCOPED / READOUT / {n:02d}'] for n in range(1, dual.SCOPED_CELLS + 1)]
        self.assertGreaterEqual(dual.SCOPED_CELLS, len('MARK=SONNET 100%'))
        for index, cell in enumerate(cells):
            with self.subTest(cell=index + 1):
                steps = dual.statements(self.scoped_to_weekly(formulas(cell)['shape_path']))
                self.assertEqual(steps[:len(shown)], shown)
                self.assertEqual(steps[len(shown):], [
                    'lv(name,tc(up,wg(lv(readurl),json,".weekly.label")))',
                    'lv(words,if(lv(ok)=1,"MARK="+lv(name)+" "+lv(show),""))',
                    f'lv(c,tc(cut,lv(words),{index},1))',
                    glyphs])
                self.assertIn('".weeklyScoped.label"', formulas(cell)['shape_path'])
                self.check_added_steps(formulas(cell)['shape_path'],
                                       dual.statements(formulas(cell)['shape_path'])[len(shown):-1])
                colour = dual.statements(self.scoped_to_weekly(formulas(cell)['paint_color']))
                self.assertEqual(colour, checked + [f'if(lv(ok)=1 & lv(q)+0<10,"{dual.LOW}","{dual.LABEL}")'])
        lefts = [cell['layout'][0] for cell in cells]
        self.assertEqual(lefts, sorted(lefts))
        self.assertEqual(len({cell['layout'][1] for cell in cells}), 1)

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
        check_structure(self, self.donor, self.ember)

    def test_layout_stays_inside_the_card_and_text_does_not_collide(self):
        check_layout(self, self.ember, dual.ROWS)

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
                    self.assertIn(built.name, sums)
                    # Compare what is inside, not the archive bytes: compressed output can
                    # differ between zlib builds while the preset itself is identical.
                    with zipfile.ZipFile(published) as archive, zipfile.ZipFile(built) as fresh:
                        self.assertEqual(archive.namelist(), fresh.namelist())
                        for member in fresh.namelist():
                            self.assertEqual(archive.read(member), fresh.read(member), member)
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

class ModelRowTests(unittest.TestCase):
    """Ember Dual for an account with no five-hour limit: one model's weekly limit in the upper row."""
    @classmethod
    def setUpClass(cls):
        cls.donor = json.loads((dual.DONOR/'preset.json').read_text(encoding='utf-8'))
        cls.donor_items = {i['internal_title']: i for i in cls.donor['preset_root']['viewgroup_items']}
        cls.default = dual.compose('CLAUDE', 'phosphor')
        cls.plain = dual.compose('CLAUDE', 'phosphor', 'weeklyScoped', 'FBL')
        cls.ember = dual.compose('CLAUDE', 'ember', 'weeklyScoped', 'FBL')
        cls.items = {i['internal_title']: i for i in cls.plain['preset_root']['viewgroup_items']}
        cls.rows = dual.rows('weeklyScoped', 'FBL')

    @staticmethod
    def pairs(tag):
        result = [(f'{tag} / PERCENT / {n}', f'LIVE PERCENT / {n}') for n in range(1, 5)]
        result += [(f'{tag} / CELL {n:02d} of 20', f'07.{n:02d} / QUOTA CELL {n:02d} of 20') for n in range(1, 21)]
        result += [(f'{tag} / STATE / {n:02d}', f'QUOTA / DATA STATE / {n:02d}') for n in range(1, 14)]
        return result + [(f'{tag} / RESET / {n:02d}', f'RESET DATE / {n:02d}') for n in range(1, 24)]

    @staticmethod
    def to_weekly(formula):
        """Undo the two documented differences of the upper row: its feed object and its snapshot slots."""
        return (formula.replace('".weeklyScoped.', '".weekly.')
                .replace('gv(latch),"~",5))', 'gv(latch),"~",1))')
                .replace('gv(latch),"~",6))', 'gv(latch),"~",2))')
                .replace('gv(latch),"~",7))', 'gv(latch),"~",3))'))

    def test_both_rows_are_seven_day_windows(self):
        upper, lower = self.rows
        self.assertEqual((upper['tag'], upper['field']), ('FBL', 'weeklyScoped'))
        self.assertEqual((lower['tag'], lower['field']), ('ALL', 'weekly'))
        for key in ('seconds', 'reset_cells', 'reset_format'):
            self.assertEqual(upper[key], dual.ROWS[1][key]); self.assertEqual(lower[key], dual.ROWS[1][key])
        self.assertEqual((upper['y'], lower['y']), (dual.ROWS[0]['y'], dual.ROWS[1]['y']))
        self.assertEqual(dual.rows('weeklyScoped')[0]['tag'], dual.MODEL_TAG)
        self.assertIs(dual.rows(), dual.ROWS)  # the default layout is untouched

    def test_lower_row_reuses_theme_formulas_unchanged(self):
        for mine, theirs in self.pairs('ALL'):
            with self.subTest(module=mine):
                for key in ('shape_path', 'paint_color'):
                    self.assertEqual(formulas(self.items[mine]).get(key), formulas(self.donor_items[theirs]).get(key))

    def test_upper_row_differs_only_by_feed_object_and_snapshot_slot(self):
        for mine, theirs in self.pairs('FBL'):
            with self.subTest(module=mine):
                for key in ('shape_path', 'paint_color'):
                    ours, donor = formulas(self.items[mine]).get(key), formulas(self.donor_items[theirs]).get(key)
                    self.assertEqual(None if ours is None else self.to_weekly(ours), donor)
                    if ours is not None:
                        self.assertNotIn('.weekly.', ours)
                        self.assertIn('lv(tap,tc(split,gv(latch),"~",0)+0)', ours)
        for row in self.rows:  # each time line measures a seven-day window from its own row's reset time
            line = formulas(self.items[f'{row["tag"]} / TIME LEFT'])
            for key in ('shape_width', 'paint_color'):
                self.assertIn('/604800', line[key])
                self.assertIn(f'".{row["field"]}.', line[key])
        self.assertNotIn('.weekly.', json.dumps(formulas(self.items['FBL / TIME LEFT'])))

    def test_needle_footer_text_and_five_hour_reading_are_gone(self):
        self.assertEqual([title for title in self.items if 'SCOPED' in title], [])
        self.assertTrue(any('SCOPED' in i['internal_title'] for i in self.default['preset_root']['viewgroup_items']))
        text = json.dumps(dual.strip_hints(self.plain))
        self.assertNotIn('fiveHour', text)
        self.assertNotIn('MARK=', text)
        self.assertLess(len(self.plain['preset_root']['viewgroup_items']),
                        len(self.default['preset_root']['viewgroup_items']))

    def test_one_tap_action_holds_the_upper_row_reading(self):
        touch = self.items['TOUCH / body requests fresh web data']
        self.assertEqual(self.plain['preset_root']['internal_events'], touch['internal_events'])
        usual = {i['internal_title']: i for i in self.default['preset_root']['viewgroup_items']}[
            'TOUCH / body requests fresh web data']['internal_events'][0]
        event = touch['internal_events'][0]
        self.assertIn('".fiveHour.', usual['switch_text'])
        # The same action as the five-hour layout, reading the per-model object for the upper row.
        self.assertEqual(event, {**usual, 'switch_text': usual['switch_text'].replace('".fiveHour.', '".weeklyScoped.')})
        self.assertEqual(self.plain['preset_root']['globals_list']['latch']['value'].count('~'), 7)

    def test_structure_matches_the_native_themes(self):
        check_structure(self, self.donor, self.ember)

    def test_layout_stays_inside_the_card_and_text_does_not_collide(self):
        check_layout(self, self.ember, self.rows)
        for tag in ('FBL', 'ALL'):  # a three-character tag stays on its plate
            px, py, pw, ph = self.items[f'{tag} / plate']['layout']
            x, y, width, height = self.items[f'{tag} / plate text']['layout']
            self.assertGreater(x, px); self.assertLess(x + width, px + pw)
            self.assertGreater(y, py); self.assertLess(y + height, py + ph)

    def test_it_is_a_separate_preset_with_its_own_file_name(self):
        usual = dual.compose('CLAUDE', 'ember')
        self.assertEqual(self.ember['preset_info']['title'], 'CD4.2 / Ember Dual / CLAUDE / FBL')
        self.assertIn("one model's weekly reserve", self.ember['preset_info']['description'])
        self.assertNotEqual(self.ember['preset_info']['id'], usual['preset_info']['id'])
        self.assertNotEqual(self.ember['preset_info']['id'],
                            dual.compose('CLAUDE', 'ember', 'weeklyScoped')['preset_info']['id'])
        with tempfile.TemporaryDirectory() as td:
            one = dual.build_dual(Path(td)/'one', 'CLAUDE', 'ember', 'weeklyScoped', 'FBL')
            two = dual.build_dual(Path(td)/'two', 'CLAUDE', 'ember', 'weeklyScoped', 'FBL')
            self.assertEqual(one.name, 'Ember_Dual_CLAUDE_FBL.kwgt')
            self.assertEqual(one.read_bytes(), two.read_bytes())
            self.assertEqual(dual.build_dual(Path(td)/'three', 'CLAUDE', 'ember', 'weeklyScoped').name,
                             f'Ember_Dual_CLAUDE_{dual.MODEL_TAG}.kwgt')
            with zipfile.ZipFile(one) as archive:
                data = json.loads(archive.read('preset.json'))
            for item in data['preset_root']['viewgroup_items']:
                self.assertNotIn('layout', item); self.assertNotIn('text', item)

    def test_unsupported_upper_row_or_tag_fails(self):
        for upper, tag in (('monthly', None), ('weekly', None), ('weeklyScoped', 'F'), ('weeklyScoped', 'FBLE'),
                           ('weeklyScoped', 'ALL'), ('weeklyScoped', 'F-L'), ('fiveHour', 'FBL')):
            with self.subTest(upper=upper, tag=tag), self.assertRaises(ValueError):
                dual.compose('CLAUDE', 'ember', upper, tag)

    def test_preview_draws_both_sample_states(self):
        for name, sample in preview.MODEL_SAMPLES.items():
            with self.subTest(sample=name):
                svg = preview.draw('dual', 'CLAUDE', 'ember', sample, 'weeklyScoped', 'FBL')
                self.assertTrue(svg.startswith('<svg ')); self.assertGreater(svg.count('<polygon '), 400)
        with self.assertRaises(ValueError):
            preview.draw('cassette', 'CLAUDE', 'ember', preview.SAMPLES['normal'], 'weeklyScoped')

if __name__ == '__main__':
    unittest.main()
