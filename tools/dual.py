#!/usr/bin/env python3
"""Compose "Ember Dual": one card with two meters, five-hour above weekly.

Nothing here is hand-written Kustom logic. Every live formula is taken from the Phosphor
Classic source, the theme checked on a phone, and only three things change: where a module
sits, which colours it uses, and which object of the feed the upper row reads. The feed
needs both a `fiveHour` and a `weekly` object; see docs/DUAL.md.

Python 3.10+, standard library only. Does not call any service or change your phone.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build  # noqa: E402  (sibling module; tools/ is not a package)

ROOT = build.ROOT
DONOR = ROOT/'src'/'00_Phosphor_Classic'
ASSETS = ROOT/'dual'
SCALE = '(mu(min,si(rwidth)/1440,si(rheight)/600))'
EMPTY_LATCH = '0~~~~~~~'  # request marker, weekly q/a/reset, source time, five-hour q/a/reset
WEEKLY_RESET_FORMAT = 'EEE · MMM d · h:mm A'
FIVE_HOUR_RESET_FORMAT = 'EEE h:mm A'

# Phosphor Classic colour -> Ember colour. Roles, not shades, decide the pairing.
EMBER = {
    '#FF4C5B54': '#FF4B3B34',  # case
    '#FF1D2923': '#FF261D19',  # case inner edge
    '#FF0B1410': '#FF15100E',  # screen
    '#FF536A5C': '#FF6B5549',  # rules and brackets
    '#FFBACDBF': '#FFDCCBBD',  # labels
    '#FF81998A': '#FF9B8678',  # dim text, and readings that are not fresh
    '#FF7C9386': '#FF8C786B',  # dim detail
    '#FFD5F1D2': '#FFF7ECE1',  # percentage digits
    '#FFAAE3BB': '#FFD97757',  # filled meter cells
    '#FF27382F': '#FF32261F',  # empty meter cells
    '#FFC6FFCE': '#FFFFE9C4',  # full
    '#FFFFC36E': '#FFFFD23F',  # low reserve; yellow, so it cannot be mistaken for the coral cells
    '#FFFF845F': '#FFFF5E57',  # data-state alerts
}
PALETTES = {'ember': EMBER, 'phosphor': {}}

# Layout in the 1440 x 600 design space every theme uses. Row y is the top of its digits.
ROWS = (
    {'tag': '5H', 'field': 'fiveHour', 'y': 150, 'reset_cells': 12, 'reset_format': FIVE_HOUR_RESET_FORMAT},
    {'tag': '7D', 'field': 'weekly', 'y': 312, 'reset_cells': 23, 'reset_format': WEEKLY_RESET_FORMAT},
)
LEGEND = '5H SESSION · 7D WEEK'
STATE_CELLS = 13
AGE_CELLS = 23
FETCH_CELLS = 12


def geometry(item: dict, x: float, y: float, width: float, height: float) -> dict:
    """Position a module with the same centring and scaling formulas the themes use."""
    formulas = item.setdefault('internal_formulas', {})
    toggles = item.setdefault('internal_toggles', {})
    formulas['position_offset_x'] = f'$(si(rwidth)-1440*{SCALE})/2+({x:g})*{SCALE}$'
    formulas['position_offset_y'] = f'$({y:g})*{SCALE}$'
    formulas['shape_width'] = f'$({width:g})*{SCALE}$'
    formulas['shape_height'] = f'$({height:g})*{SCALE}$'
    for key, value in (('position_offset_x', x), ('position_offset_y', y),
                       ('shape_width', width), ('shape_height', height)):
        toggles[key] = 10
        item[key] = value / 2  # unscaled fallback, as stored by the other themes
    item['layout'] = [x, y, width, height]  # removed before packing; used by the preview
    return item


def read_field(item: dict, field: str) -> dict:
    """Point a weekly module at another feed object and at that object's held snapshot."""
    if field == 'weekly':
        return item
    held = {1: 5, 2: 6, 3: 7}  # weekly quota/available/reset -> the second set of latch fields
    for store in ('internal_formulas',):
        for key, formula in item.get(store, {}).items():
            for old, new in held.items():
                formula = formula.replace(f'tc(split,gv(latch),"~",{old}))', f'tc(split,gv(latch),"~",{new}))')
            item[store][key] = formula.replace('".weekly.', f'".{field}.')
    return item


def static_text(data: dict, text: str, title: str, colour: str) -> dict:
    """A fixed pixel label composed from the alphabet already in the preset."""
    return {
        'internal_type': 'ShapeModule', 'internal_title': title, 'position_anchor': 'TOPLEFT',
        'shape_type': 'PATH', 'shape_path': build.header_path(data, text), 'paint_color': colour,
        'text': text,
    }


def rule(title: str, colour: str) -> dict:
    return {'internal_type': 'ShapeModule', 'internal_title': title, 'position_anchor': 'TOPLEFT',
            'shape_type': 'RECT', 'paint_color': colour, 'shape_corners': 0}


def dual_latch(event: dict) -> dict:
    """Extend the tap action so one tap captures both rows' readings in one global.

    The action is the theme's own formula followed by a renamed copy of its per-metric
    statements for the five-hour object. One action, so nothing depends on how Kustom
    orders several touch actions on one module.
    """
    text = event['switch_text']
    statements = text[1:-1].split('$$')
    body, result = statements[:-1], statements[-1]
    expected = ('df(S)+"~"+if(lv(ok)=1,lv(q)+"~"+lv(a)+"~"+tc(reg,lv(r),"[~]","")+"~"+tc(reg,lv(t),"[~]",""),'
                'tc(reg,gv(latch),"^[^~]*[~]",""))')
    if not (text.startswith('$') and text.endswith('$')) or result != expected:
        raise ValueError('The Phosphor Classic tap action changed; review tools/dual.py before building.')
    per_metric = ('hq', 'ha', 'hr', 'fallback', 'raw', 'readurl', 'q', 'a', 'r', 'n', 'ok')
    held = {'hq': 5, 'ha': 6, 'hr': 7}
    second = []
    for statement in body:
        name = re.match(r'lv\((\w+),', statement).group(1)
        if name not in per_metric:
            continue
        for local in per_metric:
            statement = statement.replace(f'lv({local})', f'lv({local}x)').replace(f'lv({local},', f'lv({local}x,')
        if name in held:
            statement = re.sub(r'"~",\d\)\)$', f'"~",{held[name]}))', statement)
        second.append(statement.replace('".weekly.', '".fiveHour.'))
    if len(second) != len(per_metric):
        raise ValueError('The Phosphor Classic tap action changed; review tools/dual.py before building.')
    keep = lambda *names: '+"~"+'.join(f'lv({name})' for name in names)  # noqa: E731
    result = ('df(S)+"~"+if(lv(ok)=1,lv(q)+"~"+lv(a)+"~"+tc(reg,lv(r),"[~]","")+"~"+tc(reg,lv(t),"[~]",""),'
              + keep('hq', 'ha', 'hr', 'ht') + ')+"~"+if(lv(okx)=1,lv(qx)+"~"+lv(ax)+"~"+tc(reg,lv(rx),"[~]",""),'
              + keep('hqx', 'hax', 'hrx') + ')')
    return {**event, 'switch_text': '$' + '$$'.join(body + second + [result]) + '$'}


def compose(label: str = 'USAGE', palette: str = 'ember') -> dict:
    """Build the two-meter preset as a Python object, with preview hints still attached."""
    if palette not in PALETTES:
        raise ValueError('Palette must be one of: ' + ', '.join(sorted(PALETTES)))
    donor = json.loads((DONOR/'preset.json').read_text(encoding='utf-8'))
    root = donor['preset_root']
    by_title = {item['internal_title']: item for item in root['viewgroup_items']}

    def part(title: str) -> dict:
        return copy.deepcopy(by_title[title])

    label_colour, dim_colour, rule_colour = '#FFBACDBF', '#FF81998A', '#FF536A5C'
    items = [
        part('01a / NATIVE CASE OUTER'),
        part('01b / NATIVE CASE INNER EDGE'),
        part('01c / NATIVE PHOSPHOR SCREEN'),
        geometry(part('03 / STATUS MARK'), 76, 72, 38, 38),
        geometry(static_text(donor, label, 'HEADER / ' + label.upper(), label_colour),
                 136, 70, 36 * len(label), 43),
        geometry(rule('RULE / header', rule_colour), 76, 130, 1288, 3),
        geometry(rule('RULE / footer', rule_colour), 76, 474, 1288, 3),
        geometry(static_text(donor, LEGEND, 'FOOTER / legend', dim_colour), 76, 500, 21 * len(LEGEND), 28),
    ]
    items[0]['internal_title'] = 'CASE / outer'
    items[1]['internal_title'] = 'CASE / inner edge'
    items[2]['internal_title'] = 'CASE / screen'
    items[3]['internal_title'] = 'STATUS MARK'

    for index in range(AGE_CELLS):
        cell = part(f'PC SOURCE DATA AGE / {index + 1:02d}')
        items.append(geometry(cell, 835 + 23 * index, 78, 23, 32))
    for index in range(FETCH_CELLS):
        cell = part(f'FETCH CONTROL / {index + 1:02d}')
        items.append(geometry(cell, 1112 + 21 * index, 500, 21, 28))

    for row in ROWS:
        tag, field, top = row['tag'], row['field'], row['y']

        def live(title: str, new_title: str, x: float, y: float, width: float, height: float) -> None:
            cell = read_field(part(title), field)
            cell['internal_title'] = f'{tag} / {new_title}'
            items.append(geometry(cell, x, y, width, height))

        items.append(geometry(static_text(donor, tag, f'{tag} / tag', label_colour), 76, top + 10, 104, 62))
        for index in range(4):
            live(f'LIVE PERCENT / {index + 1}', f'PERCENT / {index + 1}', 206 + 78 * index, top, 78, 94)
        for index in range(STATE_CELLS):
            live(f'QUOTA / DATA STATE / {index + 1:02d}', f'STATE / {index + 1:02d}',
                 208 + 22 * index, top + 106, 22, 32)
        for index in range(20):
            live(f'07.{index + 1:02d} / QUOTA CELL {index + 1:02d} of 20', f'CELL {index + 1:02d} of 20',
                 564 + 40 * index, top + 12, 33, 64)
        items.append(geometry(static_text(donor, 'RESETS', f'{tag} / resets tag', dim_colour),
                              564, top + 108, 126, 28))
        for index in range(row['reset_cells']):
            live(f'RESET DATE / {index + 1:02d}', f'RESET / {index + 1:02d}', 706 + 23 * index, top + 106, 23, 32)
            items[-1]['internal_formulas']['shape_path'] = items[-1]['internal_formulas']['shape_path'].replace(
                f'df("{WEEKLY_RESET_FORMAT}"', f'df("{row["reset_format"]}"')

    items.append(part('13 / NATIVE SCANLINES'))
    items[-1]['internal_title'] = 'SCANLINES'
    body = geometry(part('TOUCH / body requests fresh web data'), 20, 134, 1400, 444)
    body['internal_events'] = [dual_latch(body['internal_events'][0])]
    items.append(body)
    items.append(geometry(part('TOUCH / title opens KWGT editor'), 36, 26, 1368, 104))

    globals_ = copy.deepcopy(root['globals_list'])
    globals_['source']['value'] = build.PLACEHOLDER
    globals_['latch']['value'] = EMPTY_LATCH
    info = copy.deepcopy(donor['preset_info'])
    info['title'] = 'CD4.2 / Ember Dual / ' + label.upper()
    info['description'] = ('Native two-meter cyberdeck status widget: five-hour and weekly reserve. '
                           'Set source to your own endpoint. See repository README and docs/DUAL.md.')
    info['id'] = uuid.uuid5(uuid.NAMESPACE_URL, info['id'] + ':dual:' + palette + ':' + label.upper()).hex
    data = {'preset_info': info,
            'preset_root': {'internal_type': root['internal_type'],
                            'background_color': root['background_color'],
                            'internal_events': [dual_latch(root['internal_events'][0])],
                            'viewgroup_items': items, 'globals_list': globals_}}
    return recolour(data, PALETTES[palette])


def recolour(data: dict, mapping: dict) -> dict:
    if not mapping:
        return data
    pattern = re.compile('|'.join(re.escape(colour) for colour in mapping), re.IGNORECASE)
    text = pattern.sub(lambda match: mapping[match.group(0).upper()], json.dumps(data, ensure_ascii=False))
    return json.loads(text)


def strip_hints(data: dict) -> dict:
    """Drop the preview-only keys so the archive holds nothing Kustom does not expect."""
    data = copy.deepcopy(data)
    for item in data['preset_root']['viewgroup_items']:
        item.pop('layout', None)
        item.pop('text', None)
    return data


def build_dual(output: Path, label: str = 'USAGE', palette: str = 'ember') -> Path:
    data = strip_hints(compose(label, palette))
    destination = output/f'Ember_Dual_{re.sub(r"[^A-Z0-9]+", "_", label.upper()).strip("_")}.kwgt'
    thumbnails = ASSETS if (ASSETS/'preset_thumb_landscape.jpg').exists() else DONOR
    build.pack(data, thumbnails, destination)
    (output/'SHA256SUMS.txt').write_text(
        hashlib.sha256(destination.read_bytes()).hexdigest() + '  ' + destination.name + '\n')
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--output', type=Path, default=ROOT/'local'/'dual')
    parser.add_argument('--label', default='USAGE', help='Pixel header, e.g. CLAUDE. Max 20 characters.')
    parser.add_argument('--palette', default='ember', choices=sorted(PALETTES))
    parser.add_argument('--layout', type=Path, help='Also write the layout as JSON for the offline preview.')
    args = parser.parse_args()
    try:
        path = build_dual(args.output, args.label, args.palette)
        if args.layout:
            args.layout.parent.mkdir(parents=True, exist_ok=True)
            args.layout.write_text(json.dumps(compose(args.label, args.palette), ensure_ascii=False))
    except (ValueError, OSError, KeyError) as error:
        parser.exit(1, f'Build failed: {error}\n')
    print(f'Built {path}')
    print('This layout has not been proven on every device. Verify it on your phone.')
