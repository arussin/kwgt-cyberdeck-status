#!/usr/bin/env python3
"""Draw a generated two-reserve design as an SVG with sample readings, without a phone.

This checks placement, spacing and colour roles only. It does not run Kustom formulas:
the sample text and colours below are written out by hand for two example states.
Python 3.10+, standard library only.
"""
from __future__ import annotations
import argparse
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parent))
import cassette  # noqa: E402  (sibling modules; tools/ is not a package)
import dual  # noqa: E402

DESIGNS = {'dual': dual.compose, 'cassette': cassette.compose}
# Phosphor colours by role; the palette table is applied when drawing.
BRIGHT, LABEL, DIM, FILLED, EMPTY = '#FFD5F1D2', '#FFBACDBF', '#FF81998A', '#FFAAE3BB', '#FF27382F'
LOW, ALERT, FULL = '#FFFFC36E', '#FFFF845F', '#FFC6FFCE'
ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789:·-/[].+><%|!='
DIGITS = '0123456789%-<'

# 'upper' and 'lower' are the two rows of Ember Dual (the left and right reel of the cassette).
SAMPLES = {
    'normal': {
        'age': 'PC DATA · 3M OLD', 'fetch': 'TAP / FETCH',
        'upper': {'percent': 58, 'state': 'REMAINING', 'reset': 'SAT 8:30 PM', 'time': 0.46},
        'lower': {'percent': 59, 'state': 'REMAINING', 'reset': 'MON · NOV 23 · 10:00 AM', 'time': 0.12},
        'scoped': {'label': 'FABLE', 'percent': 19},
    },
    'low': {
        'age': 'PC DATA · 12M OLD', 'fetch': 'TAP / FETCH',
        'upper': {'percent': 8, 'state': 'LOW RESERVE', 'reset': 'SAT 11:45 PM', 'time': 0.35},
        'lower': {'percent': 100, 'state': 'FULL', 'reset': 'WED · NOV 25 · 10:39 PM', 'time': 0.98},
        'scoped': {'label': 'FABLE', 'percent': 6},
    },
}
# For Ember Dual with one model's weekly limit in the upper row: both rows are seven-day windows.
MODEL_SAMPLES = {
    'normal': {
        'age': 'PC DATA · 3M OLD', 'fetch': 'TAP / FETCH',
        'upper': {'percent': 41, 'state': 'REMAINING', 'reset': 'MON · NOV 30 · 10:00 AM', 'time': 0.62},
        'lower': {'percent': 78, 'state': 'REMAINING', 'reset': 'MON · NOV 30 · 10:00 AM', 'time': 0.62},
    },
    'low': {
        'age': 'PC DATA · 12M OLD', 'fetch': 'TAP / FETCH',
        'upper': {'percent': 7, 'state': 'LOW RESERVE', 'reset': 'MON · NOV 30 · 10:00 AM', 'time': 0.31},
        'lower': {'percent': 52, 'state': 'REMAINING', 'reset': 'MON · NOV 30 · 10:00 AM', 'time': 0.31},
    },
}


def outlines(path: str) -> list[list[tuple[float, float]]]:
    """Closed outlines of a theme path. Themes use M, L, h, v, H, V and Z in a 0..100 box."""
    result: list[list[tuple[float, float]]] = []
    points: list[tuple[float, float]] = []
    x = y = 0.0
    for command, arguments in re.findall(r'([MLhvHVZ])([^MLhvHVZ]*)', path):
        values = [float(value) for value in re.findall(r'-?\d+(?:\.\d+)?', arguments)]
        if command == 'M':
            if len(points) > 2:
                result.append(points)
            x, y = values
            points = [(x, y)]
            continue
        if command == 'Z':
            if len(points) > 2:
                result.append(points)
            points = []
            continue
        if command == 'L':
            x, y = values
        elif command == 'h':
            x += values[0]
        elif command == 'v':
            y += values[0]
        elif command == 'H':
            x = values[0]
        else:
            y = values[0]
        points.append((x, y))
    return result


def cells(percent: int) -> int:
    return 20 if percent == 100 else min(19, max(1, round(percent / 5))) if percent > 0 else 0


def metric_colour(percent: int, normal: str) -> str:
    return LOW if percent < 10 else FULL if percent == 100 else normal


def render(data: dict, mapping: dict, sample: dict, tags: tuple[str, str] = ('5H', '7D')) -> str:
    """Draw a composed design (with its preview hints) for one sample state.

    `tags` are the title prefixes of the design's two readings, in the order upper, lower."""
    globals_ = data['preset_root']['globals_list']
    readings = dict(zip(tags, (sample['upper'], sample['lower'])))
    shapes: list[str] = []

    def colour(value: str) -> tuple[str, float]:
        value = mapping.get(value.upper(), value)
        return '#' + value[3:], int(value[1:3], 16) / 255

    def box(x: float, y: float, width: float, height: float, fill: str, radius: float = 0) -> None:
        rgb, alpha = colour(fill)
        shapes.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{width:.2f}" height="{height:.2f}" '
                      f'rx="{radius:.2f}" fill="{rgb}" fill-opacity="{alpha:.3f}"/>')

    def path(layout: list[float], shape_path: str, fill: str) -> None:
        x, y, width, height = layout
        rgb, alpha = colour(fill)
        for outline in outlines(shape_path):
            points = ' '.join(f'{x + px * width / 100:.2f},{y + py * height / 100:.2f}' for px, py in outline)
            shapes.append(f'<polygon points="{points}" fill="{rgb}" fill-opacity="{alpha:.3f}"/>')

    def glyph(char: str, big: bool) -> str:
        if big:
            return globals_[f'p{DIGITS.index(char):03d}' if char in DIGITS else 'p013']['value']
        return globals_[f'p{14 + ALPHABET.index(char):03d}' if char in ALPHABET else 'p013']['value']

    for item in data['preset_root']['viewgroup_items']:
        title = item['internal_title']
        if title.startswith('TOUCH'):
            continue
        layout = item.get('layout') or [item['position_offset_x'] * 2, item['position_offset_y'] * 2,
                                        item['shape_width'] * 2, item['shape_height'] * 2]
        if title.startswith('CASE') or title == 'SCANLINES':
            layout = layout if item['shape_type'] == 'RECT' else [0, 0, 1440, 600]
        formulas = item.get('internal_formulas', {})
        painted = 'paint_color' in formulas  # otherwise the stored colour is the colour
        reading = readings.get(title.partition(' / ')[0])
        family = re.search(r'/ (PERCENT|STATE|RESET|CELL|REEL)\b', title)
        index = int(match.group(1)) - 1 if (match := re.search(r'(\d+)(?: of 20)?$', title)) else 0
        fill, shape_path = item['paint_color'], item.get('shape_path')

        if title.startswith('PC SOURCE DATA AGE'):
            fill, shape_path = DIM, glyph(sample['age'][index:index + 1] or ' ', False)
        elif title.startswith('FETCH CONTROL'):
            shape_path = glyph(sample['fetch'][index:index + 1] or ' ', False)
        elif title == 'STATUS MARK':
            fill = LABEL
        elif family and family.group(1) == 'PERCENT':
            text = f'{reading["percent"]}%'
            fill, shape_path = metric_colour(reading['percent'], BRIGHT), glyph(text[index:index + 1] or ' ', True)
        elif family and family.group(1) == 'STATE':
            state = reading['state']
            fill = LABEL if state == 'REMAINING' else FULL if state == 'FULL' else ALERT
            shape_path = glyph(state[index:index + 1] or ' ', False)
        elif family and family.group(1) == 'RESET':
            shape_path = glyph(reading['reset'][index:index + 1] or ' ', False)
        elif family:  # a meter cell or a reel step
            fill = metric_colour(reading['percent'], FILLED) if index < cells(reading['percent']) else EMPTY
        elif '/ SCOPED ' in title:  # the per-model limit's place along the weekly meter
            scoped = sample['scoped']
            layout = [layout[0] + scoped['percent'] / 100 * dual.METER_WIDTH, layout[1], layout[2], layout[3]]
            fill = dual.INK if title.endswith('shadow') else LOW if scoped['percent'] < 10 else BRIGHT
        elif title.startswith('SCOPED / READOUT'):
            scoped = sample['scoped']
            words = 'MARK={label} {percent}%'.format(**scoped)
            fill = LOW if scoped['percent'] < 10 else LABEL
            shape_path = glyph(words[index:index + 1] or ' ', False)
        elif title.endswith('/ TIME LEFT'):  # as long as the share of the window still to run
            layout = [layout[0], layout[1], layout[2] * reading['time'], layout[3]]
            fill = ALERT if reading['percent'] < reading['time'] * 100 else LABEL
        elif painted and not title.startswith('CASE'):
            raise ValueError(f'Preview does not know how to colour {title!r}.')

        if item['shape_type'] == 'RECT':
            box(*layout, fill, item.get('shape_corners', 0) * 2)
        else:
            path(layout, shape_path, fill)
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1440 600" width="1440" height="600">\n'
            + '\n'.join(shapes) + '\n</svg>\n')


def draw(design: str, label: str, palette: str, sample: dict, upper: str = 'fiveHour',
         upper_tag: str | None = None) -> str:
    """Draw one design. `upper` and `upper_tag` choose Ember Dual's upper row, as in tools/dual.py."""
    if design != 'dual':
        if upper != 'fiveHour' or upper_tag:
            raise ValueError('Only Ember Dual has a choice of upper row.')
        return render(DESIGNS[design](label, palette), dual.PALETTES[palette], sample)
    tags = tuple(row['tag'] for row in dual.rows(upper, upper_tag))
    return render(dual.compose(label, palette, upper, upper_tag), dual.PALETTES[palette], sample, tags)


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--design', default='cassette', choices=sorted(DESIGNS))
    parser.add_argument('--output', type=Path, default=dual.ROOT/'local'/'preview')
    parser.add_argument('--label', default='USAGE')
    parser.add_argument('--palette', default='ember', choices=sorted(dual.PALETTES))
    parser.add_argument('--upper', default='fiveHour', choices=dual.UPPER_FIELDS,
                        help='Ember Dual only: the feed object for the upper row.')
    parser.add_argument('--upper-tag', help='Ember Dual with --upper weeklyScoped: the upper plate, e.g. FBL.')
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    model = args.upper != 'fiveHour'
    for name, sample in (MODEL_SAMPLES if model else SAMPLES).items():
        target = args.output/f'{args.design}{"-model" if model else ""}-{name}.svg'
        try:
            svg = draw(args.design, args.label, args.palette, sample, args.upper, args.upper_tag)
        except ValueError as error:
            parser.exit(1, f'Preview failed: {error}\n')
        target.write_text(svg, encoding='utf-8')
        print(f'Wrote {target}')
    print('Sample data only. This does not evaluate Kustom formulas or prove Android rendering.')
