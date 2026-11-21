#!/usr/bin/env python3
"""Compose "Data Cassette": a tape in the deck, with one reel per reserve.

The left reel holds the five-hour reserve and the right reel the weekly one. Tape winds off
a reel as its reserve is used, in twenty steps. The cassette label lists both reset times
like a track listing, and the panel beside it shows the percentages and data state.

Like tools/dual.py, this writes almost no Kustom logic of its own. Percentages, state words,
reset times, colours and the tap action are Phosphor Classic's formulas, moved and recoloured.
A reel is the theme's twenty meter cells drawn as stacked discs instead of a row of boxes.
The one new formula turns the reel hubs a third of a turn each minute. See docs/CASSETTE.md.

Python 3.10+, standard library only. Does not call any service or change your phone.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
import math
from pathlib import Path
import re
import sys
import uuid

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build  # noqa: E402  (sibling modules; tools/ is not a package)
import dual  # noqa: E402

ROOT = build.ROOT
ASSETS = ROOT/'cassette'
ANCHORS = 'M0 0L0 0M100 100L100 100'  # keeps a path's 0..100 box, as every theme path does
PIXEL = 4.0  # one drawn pixel, in the 1440 x 600 design space

# Fixed colours of the cassette itself. None of them is a Phosphor colour, so the palette
# table in tools/dual.py leaves them alone.
SHELL_EDGE, SHELL, PAPER, BAND = '#FF5A463B', '#FF2A211C', '#FFEFE3D2', '#FFD97757'
INK, INK_SOFT, FRAME, GLASS = '#FF241813', '#FF8A7564', '#FF5E493D', '#FF0D0908'
PANEL_EDGE, PANEL, TAPE, FOOT = '#FF3A2D26', '#FF120D0B', '#FF8F4E38', '#FF382B25'
HUB, RIDGE, GLARE = '#FFCDBFAE', '#FF3A2E27', '#0EFFFFFF'  # the hub stays visible beside a full, cream reel
LABEL, DIM, RULE = '#FFBACDBF', '#FF81998A', '#FF536A5C'  # Phosphor roles; recoloured with the rest

REELS = (
    {'tag': '5H', 'field': 'fiveHour', 'x': 318, 'y': 342, 'track_y': 166, 'reset_cells': 12,
     'reset_format': dual.FIVE_HOUR_RESET_FORMAT, 'row_y': 122},
    {'tag': '7D', 'field': 'weekly', 'x': 618, 'y': 342, 'track_y': 198, 'reset_cells': 23,
     'reset_format': dual.WEEKLY_RESET_FORMAT, 'row_y': 288},
)
HUB_RADIUS, REEL_RADIUS, STEPS = 28.0, 84.0, 20
HUB_FRAMES = ('hub0', 'hub1', 'hub2')
# Minutes since 1970, modulo three, written with only the functions the themes already use.
HUB_FORMULA = ('$lv(f,mu(floor,df(S)/60)-3*mu(floor,mu(floor,df(S)/60)/3))$'
               '$if(lv(f)=0,gv(hub0),lv(f)=1,gv(hub1),gv(hub2))$')


def number(value: float) -> str:
    return f'{value:.4f}'.rstrip('0').rstrip('.') or '0'


def disc(radius: float) -> str:
    """A pixel-art disc filling its square box, drawn as horizontal slabs (M/h/v/Z only)."""
    rows = max(2, round(2 * radius / PIXEL))
    step = 100 / rows
    parts = [ANCHORS]
    for row in range(rows):
        middle = (row + 0.5) * step - 50
        half = min(50.0, max(step / 2, round(math.sqrt(max(0.0, 2500 - middle * middle)) / step) * step))
        parts.append(f'M{number(50 - half)} {number(row * step)}h{number(2 * half)}v{number(step)}h-{number(2 * half)}Z')
    return ''.join(parts)


def polygon(points: list[tuple[float, float]]) -> str:
    """A closed outline in the 0..100 box of its module (M/L/Z only)."""
    first, *rest = points
    return (f'M{number(first[0])} {number(first[1])}'
            + ''.join(f'L{number(x)} {number(y)}' for x, y in rest) + 'Z')


def hub_teeth(turn: float) -> str:
    """Three drive teeth around the hub hole, rotated by `turn` degrees."""
    parts = [ANCHORS]
    for tooth in range(3):
        angle = math.radians(turn + 120 * tooth)
        along, across = (math.cos(angle), math.sin(angle)), (-math.sin(angle), math.cos(angle))
        corners = [(18, -7), (40, -7), (40, 7), (18, 7)]
        parts.append(polygon([(50 + r * along[0] + w * across[0], 50 + r * along[1] + w * across[1])
                              for r, w in corners]))
    return ''.join(parts)


def shape(title: str, colour: str, path: str | None = None, corners: float = 0) -> dict:
    item = {'internal_type': 'ShapeModule', 'internal_title': title, 'position_anchor': 'TOPLEFT',
            'shape_type': 'PATH' if path else 'RECT', 'paint_color': colour}
    if path:
        item['shape_path'] = path
    else:
        item['shape_corners'] = corners
    return item


def box(title: str, colour: str, x: float, y: float, width: float, height: float, corners: float = 0) -> dict:
    item = dual.geometry(shape(title, colour, corners=corners / 2), x, y, width, height)
    if corners:
        item['internal_formulas']['shape_corners'] = f'${corners:g}*{dual.SCALE}$'
        item['internal_toggles']['shape_corners'] = 10
    return item


def disc_at(title: str, colour: str, x: float, y: float, radius: float) -> dict:
    return dual.geometry(shape(title, colour, path=disc(radius)), x - radius, y - radius, 2 * radius, 2 * radius)


def compose(label: str = 'USAGE', palette: str = 'ember') -> dict:
    """Build the cassette preset as a Python object, with preview hints still attached."""
    if palette not in dual.PALETTES:
        raise ValueError('Palette must be one of: ' + ', '.join(sorted(dual.PALETTES)))
    donor = json.loads((dual.DONOR/'preset.json').read_text(encoding='utf-8'))
    root = donor['preset_root']
    by_title = {item['internal_title']: item for item in root['viewgroup_items']}

    def part(title: str) -> dict:
        return copy.deepcopy(by_title[title])

    def text(words: str, title: str, colour: str, x: float, y: float, cell: float, height: float) -> dict:
        return dual.geometry(dual.static_text(donor, words, title, colour), x, y, cell * len(words), height)

    items = [part('01a / NATIVE CASE OUTER'), part('01b / NATIVE CASE INNER EDGE'), part('01c / NATIVE PHOSPHOR SCREEN')]
    for item, title in zip(items, ('CASE / outer', 'CASE / inner edge', 'CASE / screen')):
        item['internal_title'] = title

    # The cassette: shell, paper label, window, feet.
    items += [
        box('SHELL / edge', SHELL_EDGE, 56, 52, 824, 496, 26),
        box('SHELL / body', SHELL, 60, 56, 816, 488, 23),
        box('LABEL / paper', PAPER, 92, 76, 752, 156),
        box('LABEL / band', BAND, 92, 76, 752, 30),
        text('SIDE A', 'LABEL / side', INK, 104, 80, 18, 22),
        text('C-300 · C-10080', 'LABEL / lengths', INK, 566, 80, 18, 22),
        text(label, 'HEADER / ' + label.upper(), INK, 104, 114, 34, 42),
        text('PLAN RESERVE TAPE', 'LABEL / kind', INK_SOFT, 530, 126, 18, 24),
        box('WINDOW / frame', FRAME, 164, 244, 608, 196, 12),
        box('WINDOW / glass', GLASS, 168, 248, 600, 188, 10),
        dual.geometry(shape('FOOT / plate', FOOT, path=ANCHORS + polygon([(7, 0), (93, 0), (100, 100), (0, 100)])),
                      286, 452, 364, 92),
        disc_at('FOOT / hole left', GLASS, 396, 500, 12),
        disc_at('FOOT / hole right', GLASS, 540, 500, 12),
        box('FOOT / slot', GLASS, 452, 492, 32, 16),
        disc_at('SCREW / left', FRAME, 96, 516, 8),
        disc_at('SCREW / right', FRAME, 840, 516, 8),
        text('TYPE IV', 'SHELL / type', INK_SOFT, 120, 505, 17, 22),
        text('NR · ON', 'SHELL / noise', INK_SOFT, 690, 505, 17, 22),
        box('TAPE / run', TAPE, 234, 428, 468, 3),
        disc_at('TAPE / guide left', FRAME, 234, 429, 8),
        disc_at('TAPE / guide right', FRAME, 702, 429, 8),
    ]
    for tick in range(5):
        items.append(box(f'WINDOW / tick {tick + 1}', FRAME, 444 + 12 * tick, 330, 3, 24))
    for side, left in (('left', 96), ('right', 788)):
        for ridge in range(9):
            items.append(box(f'SHELL / grip {side} {ridge + 1}', RIDGE, left, 264 + 18 * ridge, 52, 5))

    globals_ = copy.deepcopy(root['globals_list'])
    next_index = 1 + max(value['index'] for value in globals_.values())
    for offset, name in enumerate(HUB_FRAMES):
        globals_[name] = {'index': next_index + offset, 'type': 'TEXT', 'title': f'{name.upper()} / reel hub teeth',
                          'value': hub_teeth(40 * offset)}

    for reel in REELS:
        tag, field, centre_x, centre_y = reel['tag'], reel['field'], reel['x'], reel['y']

        def live(title: str, new_title: str, x: float, y: float, width: float, height: float) -> dict:
            cell = dual.read_field(part(title), field)
            cell['internal_title'] = f'{tag} / {new_title}'
            items.append(dual.geometry(cell, x, y, width, height))
            return cell

        # The reel: the theme's twenty meter cells as discs, largest first so smaller ones cover them.
        for step in range(STEPS, 0, -1):
            radius = HUB_RADIUS + (REEL_RADIUS - HUB_RADIUS) * step / STEPS
            ring = live(f'07.{step:02d} / QUOTA CELL {step:02d} of 20', f'REEL {step:02d} of 20',
                        centre_x - radius, centre_y - radius, 2 * radius, 2 * radius)
            ring.pop('shape_corners', None)
            ring['shape_type'], ring['shape_path'] = 'PATH', disc(radius)
        items.append(disc_at(f'{tag} / hub', HUB, centre_x, centre_y, HUB_RADIUS - 2))
        teeth = dual.geometry(shape(f'{tag} / hub teeth', GLASS, path=hub_teeth(0)),
                              centre_x - 26, centre_y - 26, 52, 52)
        teeth['internal_formulas']['shape_path'] = HUB_FORMULA
        teeth['internal_toggles']['shape_path'] = 10
        items.append(teeth)
        items.append(disc_at(f'{tag} / spindle', GLASS, centre_x, centre_y, 8))
        items.append(text(tag, f'{tag} / reel tag', LABEL, 180 if centre_x < 468 else 716, 258, 21, 28))

        # The track listing on the paper label, in ink.
        track = reel['track_y']
        items.append(text(f'{tag} RESETS', f'{tag} / track', INK, 104, track, 20, 26))
        for index in range(reel['reset_cells']):
            cell = live(f'RESET DATE / {index + 1:02d}', f'RESET / {index + 1:02d}', 304 + 20 * index, track, 20, 26)
            cell['internal_formulas']['shape_path'] = cell['internal_formulas']['shape_path'].replace(
                f'df("{dual.WEEKLY_RESET_FORMAT}"', f'df("{reel["reset_format"]}"')
            cell['paint_color'] = INK

    # Two faint streaks of light across the window, over the reels.
    glare = polygon([(60, 0), (72, 0), (58, 100), (46, 100)]) + polygon([(77, 0), (80, 0), (66, 100), (63, 100)])
    items.append(dual.geometry(shape('WINDOW / glare', GLARE, path=ANCHORS + glare), 168, 248, 600, 188))

    # The readout panel beside the cassette.
    items += [box('PANEL / edge', PANEL_EDGE, 908, 52, 476, 496, 16), box('PANEL / face', PANEL, 912, 56, 468, 488, 13)]
    for index in range(dual.AGE_CELLS):
        items.append(dual.geometry(part(f'PC SOURCE DATA AGE / {index + 1:02d}'), 932 + 19 * index, 74, 19, 27))
    items += [box('RULE / panel top', RULE, 932, 108, 428, 3), box('RULE / panel bottom', RULE, 932, 452, 428, 3)]
    for index in range(dual.FETCH_CELLS):
        items.append(dual.geometry(part(f'FETCH CONTROL / {index + 1:02d}'), 932 + 21 * index, 470, 21, 28))
    items.append(text('POLL 5M', 'PANEL / poll', DIM, 1196, 474, 18, 22))
    lamp = dual.geometry(part('03 / STATUS MARK'), 1340, 475, 20, 20)
    lamp['internal_title'] = 'STATUS MARK'
    items.append(lamp)
    for reel in REELS:
        tag, field, top = reel['tag'], reel['field'], reel['row_y']
        items.append(box(f'{tag} / plate', BAND, 932, top, 72, 110))
        items.append(text(tag, f'{tag} / plate text', INK, 942, top + 34, 26, 42))
        for index in range(4):
            cell = dual.read_field(part(f'LIVE PERCENT / {index + 1}'), field)
            cell['internal_title'] = f'{tag} / PERCENT / {index + 1}'
            items.append(dual.geometry(cell, 1016 + 88 * index, top, 88, 110))
        for index in range(dual.STATE_CELLS):
            cell = dual.read_field(part(f'QUOTA / DATA STATE / {index + 1:02d}'), field)
            cell['internal_title'] = f'{tag} / STATE / {index + 1:02d}'
            items.append(dual.geometry(cell, 932 + 22 * index, top + 118, 22, 28))

    items.append(part('13 / NATIVE SCANLINES'))
    items[-1]['internal_title'] = 'SCANLINES'
    body = dual.geometry(part('TOUCH / body requests fresh web data'), 20, 112, 1400, 466)
    body['internal_events'] = [dual.dual_latch(body['internal_events'][0])]
    items += [body, dual.geometry(part('TOUCH / title opens KWGT editor'), 36, 26, 1368, 82)]

    globals_['source']['value'] = build.PLACEHOLDER
    globals_['latch']['value'] = dual.EMPTY_LATCH
    info = copy.deepcopy(donor['preset_info'])
    info['title'] = 'CD4.2 / Data Cassette / ' + label.upper()
    info['description'] = ('Native cyberdeck status widget drawn as a data cassette: one reel per reserve, '
                           'five-hour and weekly. Set source to your own endpoint. See docs/CASSETTE.md.')
    info['id'] = uuid.uuid5(uuid.NAMESPACE_URL, info['id'] + ':cassette:' + palette + ':' + label.upper()).hex
    data = {'preset_info': info,
            'preset_root': {'internal_type': root['internal_type'],
                            'background_color': root['background_color'],
                            'internal_events': [dual.dual_latch(root['internal_events'][0])],
                            'viewgroup_items': items, 'globals_list': globals_}}
    return dual.recolour(data, dual.PALETTES[palette])


def build_cassette(output: Path, label: str = 'USAGE', palette: str = 'ember') -> Path:
    data = dual.strip_hints(compose(label, palette))
    destination = output/f'Data_Cassette_{re.sub(r"[^A-Z0-9]+", "_", label.upper()).strip("_")}.kwgt'
    thumbnails = ASSETS if (ASSETS/'preset_thumb_landscape.jpg').exists() else dual.DONOR
    build.pack(data, thumbnails, destination)
    (output/'SHA256SUMS.txt').write_text(
        hashlib.sha256(destination.read_bytes()).hexdigest() + '  ' + destination.name + '\n')
    return destination


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--output', type=Path, default=ROOT/'local'/'cassette')
    parser.add_argument('--label', default='USAGE', help='Pixel title on the tape label, e.g. CLAUDE. Max 20 characters.')
    parser.add_argument('--palette', default='ember', choices=sorted(dual.PALETTES))
    args = parser.parse_args()
    try:
        path = build_cassette(args.output, args.label, args.palette)
    except (ValueError, OSError, KeyError) as error:
        parser.exit(1, f'Build failed: {error}\n')
    print(f'Built {path}')
    print('This layout has not been proven on every device. Verify it on your phone.')
