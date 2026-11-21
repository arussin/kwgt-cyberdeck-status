#!/usr/bin/env python3
"""Compose "Ember Dual": one card with two meters, five-hour above weekly.

Almost nothing here is hand-written Kustom logic. Percentages, state words, reset times,
meter colours and the tap action are taken from the Phosphor Classic source, the theme
checked on a phone, and only three things change: where a module sits, which colours it
uses, and which object of the feed the upper row reads. The one addition is the thin line
under each meter that shows how much of the window's time is left; see `time_left`.
The feed needs both a `fiveHour` and a `weekly` object; see docs/DUAL.md.

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
ANCHORS = 'M0 0L0 0M100 100L100 100'  # keeps a path's 0..100 box, as every theme path does
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
# Phosphor roles used for parts this file adds; they are recoloured with everything else.
LABEL, DIM, RULE, TRACK, ALERT, FILLED = '#FFBACDBF', '#FF81998A', '#FF536A5C', '#FF27382F', '#FFFF845F', '#FFAAE3BB'
INK = '#FF15100E'  # text on a filled plate; the Ember screen colour, and no Phosphor colour

# Layout in the 1440 x 600 design space every theme uses. Row y is the top of its digits.
ROWS = (
    {'tag': '5H', 'field': 'fiveHour', 'y': 150, 'reset_cells': 12, 'reset_format': FIVE_HOUR_RESET_FORMAT,
     'seconds': 5 * 3600},
    {'tag': '7D', 'field': 'weekly', 'y': 312, 'reset_cells': 23, 'reset_format': WEEKLY_RESET_FORMAT,
     'seconds': 7 * 24 * 3600},
)
LEGEND = 'BAR=QUOTA LINE=TIME'
STATE_CELLS = 13
AGE_CELLS = 23
FETCH_CELLS = 12
METER_X, METER_WIDTH, CELL_PITCH, CELL_WIDTH, CELL_HEIGHT = 548, 800, 40, 48, 56
SLANT = 29.0  # how far a meter segment leans, as a share of its box width


def number(value: float) -> str:
    return f'{value:.4f}'.rstrip('0').rstrip('.') or '0'


def polygon(points: list[tuple[float, float]]) -> str:
    """A closed outline in the 0..100 box of its module (M/L/Z only)."""
    first, *rest = points
    return (f'M{number(first[0])} {number(first[1])}'
            + ''.join(f'L{number(x)} {number(y)}' for x, y in rest) + 'Z')


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
    for key, formula in item.get('internal_formulas', {}).items():
        for old, new in held.items():
            formula = formula.replace(f'tc(split,gv(latch),"~",{old}))', f'tc(split,gv(latch),"~",{new}))')
        item['internal_formulas'][key] = formula.replace('".weekly.', f'".{field}.')
    return item


def shape(title: str, colour: str, path: str | None = None, corners: float = 0) -> dict:
    """A fixed rectangle, or a fixed native path when one is given."""
    item = {'internal_type': 'ShapeModule', 'internal_title': title, 'position_anchor': 'TOPLEFT',
            'shape_type': 'PATH' if path else 'RECT', 'paint_color': colour}
    if path:
        item['shape_path'] = path
    else:
        item['shape_corners'] = corners
    return item


def box(title: str, colour: str, x: float, y: float, width: float, height: float, corners: float = 0) -> dict:
    item = geometry(shape(title, colour, corners=corners / 2), x, y, width, height)
    if corners:
        item['internal_formulas']['shape_corners'] = f'${corners:g}*{SCALE}$'
        item['internal_toggles']['shape_corners'] = 10
    return item


def static_text(data: dict, text: str, title: str, colour: str) -> dict:
    """A fixed pixel label composed from the alphabet already in the preset."""
    item = shape(title, colour, path=build.header_path(data, text))
    item['text'] = text
    return item


def time_left(reset_formula: str, seconds: int) -> tuple[str, str]:
    """Width and colour formulas for the line showing how much of a window's time is left.

    This is the one piece of logic the themes do not already have. It starts from the theme's
    own reset-time formula, keeps everything up to its validated reset timestamp, and adds one
    step: the share of the window still to run, from 0 to 1. The line is as long as that share
    of the meter, and turns to the alert colour when the reserve left is smaller than the time
    left, which means the reserve is being used faster than the clock.
    """
    statements = reset_formula[1:-1].split('$$')
    end = next(index for index, statement in enumerate(statements) if statement.startswith('lv(rgood,'))
    head = statements[:end + 1] + [
        f'lv(left,if(lv(rgood)=1,mu(max,0,mu(min,1,(df(S,dp(lv(riso),auto))-df(S))/{seconds})),0))']
    width = '$' + '$$'.join(head + [f'lv(left)*{METER_WIDTH}*{SCALE}']) + '$'
    colour = '$' + '$$'.join(
        head + [f'if(lv(rgood)!=1,"{DIM}",(lv(q)+0)<lv(left)*100,"{ALERT}","{LABEL}")']) + '$'
    return width, colour


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

    def text(words: str, title: str, colour: str, x: float, y: float, cell: float, height: float) -> dict:
        return geometry(static_text(donor, words, title, colour), x, y, cell * len(words), height)

    items = [part('01a / NATIVE CASE OUTER'), part('01b / NATIVE CASE INNER EDGE'), part('01c / NATIVE PHOSPHOR SCREEN')]
    for item, title in zip(items, ('CASE / outer', 'CASE / inner edge', 'CASE / screen')):
        item['internal_title'] = title

    # Header: the title on a filled plate, the age of the PC's reading on the right.
    items += [
        box('HEADER / plate', FILLED, 76, 62, 36 * len(label) + 32, 54),
        text(label, 'HEADER / ' + label.upper(), INK, 92, 68, 36, 42),
        box('RULE / header', RULE, 76, 130, 1288, 3),
        box('RULE / footer', RULE, 76, 474, 1288, 3),
        text(LEGEND, 'FOOTER / legend', DIM, 76, 500, 21, 28),
    ]
    for index in range(AGE_CELLS):
        items.append(geometry(part(f'PC SOURCE DATA AGE / {index + 1:02d}'), 835 + 23 * index, 78, 23, 32))
    for index in range(FETCH_CELLS):
        items.append(geometry(part(f'FETCH CONTROL / {index + 1:02d}'), 1076 + 21 * index, 500, 21, 28))
    lamp = geometry(part('03 / STATUS MARK'), 1344, 504, 20, 20)
    lamp['internal_title'] = 'STATUS MARK'
    items.append(lamp)

    lean = polygon([(SLANT, 0), (100, 0), (100 - SLANT, 100), (0, 100)])
    for row in ROWS:
        tag, field, top = row['tag'], row['field'], row['y']

        def live(title: str, new_title: str, x: float, y: float, width: float, height: float) -> dict:
            cell = read_field(part(title), field)
            cell['internal_title'] = f'{tag} / {new_title}'
            items.append(geometry(cell, x, y, width, height))
            return cell

        items.append(box(f'{tag} / plate', FILLED, 76, top, 88, 94))
        items.append(text(tag, f'{tag} / plate text', INK, 90, top + 26, 30, 44))
        for index in range(4):
            live(f'LIVE PERCENT / {index + 1}', f'PERCENT / {index + 1}', 184 + 78 * index, top, 78, 94)
        for index in range(STATE_CELLS):
            live(f'QUOTA / DATA STATE / {index + 1:02d}', f'STATE / {index + 1:02d}',
                 184 + 22 * index, top + 106, 22, 32)

        # The meter: the theme's twenty cells, each drawn as a leaning segment instead of a box.
        for index in range(20):
            segment = live(f'07.{index + 1:02d} / QUOTA CELL {index + 1:02d} of 20', f'CELL {index + 1:02d} of 20',
                           METER_X + CELL_PITCH * index, top, CELL_WIDTH, CELL_HEIGHT)
            segment.pop('shape_corners', None)
            segment['shape_type'], segment['shape_path'] = 'PATH', ANCHORS + lean

        # Under it: a track the length of the meter, quarter marks, and the time-left line.
        items.append(box(f'{tag} / time track', TRACK, METER_X, top + 70, METER_WIDTH, 4))
        for quarter in range(5):
            items.append(box(f'{tag} / time mark {quarter}', RULE, METER_X + quarter * (METER_WIDTH - 3) / 4,
                             top + 80, 3, 10))
        line = box(f'{tag} / TIME LEFT', LABEL, METER_X, top + 66, METER_WIDTH, 12)
        width, colour = time_left(by_title['RESET DATE / 01']['internal_formulas']['shape_path'], row['seconds'])
        line['internal_formulas'].update({'shape_width': width, 'paint_color': colour})
        line['internal_toggles']['paint_color'] = 10
        items.append(read_field(line, field))

        items.append(text('RESETS', f'{tag} / resets tag', DIM, METER_X, top + 108, 21, 28))
        for index in range(row['reset_cells']):
            cell = live(f'RESET DATE / {index + 1:02d}', f'RESET / {index + 1:02d}', 690 + 23 * index, top + 106, 23, 32)
            cell['internal_formulas']['shape_path'] = cell['internal_formulas']['shape_path'].replace(
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
    args = parser.parse_args()
    try:
        path = build_dual(args.output, args.label, args.palette)
    except (ValueError, OSError, KeyError) as error:
        parser.exit(1, f'Build failed: {error}\n')
    print(f'Built {path}')
    print('This layout has not been proven on every device. Verify it on your phone.')
