#!/usr/bin/env python3
"""Draw the Ember Dual layout as an SVG with sample readings, without a phone.

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
import dual  # noqa: E402  (sibling module; tools/ is not a package)

# Donor colours by role; the palette mapping is applied when drawing.
BRIGHT, LABEL, DIM, FILLED, EMPTY = '#FFD5F1D2', '#FFBACDBF', '#FF81998A', '#FFAAE3BB', '#FF27382F'
LOW, ALERT, FULL = '#FFFFC36E', '#FFFF845F', '#FFC6FFCE'
ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ0123456789:·-/[].+><%|!='
DIGITS = '0123456789%-<'

SAMPLES = {
    'normal': {
        'age': 'PC DATA · 3M OLD', 'fetch': 'TAP / FETCH',
        '5H': {'percent': 32, 'state': 'REMAINING', 'reset': 'SAT 6:20 PM'},
        '7D': {'percent': 94, 'state': 'REMAINING', 'reset': 'MON · NOV 23 · 10:00 AM'},
    },
    'low': {
        'age': 'PC DATA · 12M OLD', 'fetch': 'TAP / FETCH',
        '5H': {'percent': 8, 'state': 'LOW RESERVE', 'reset': 'SAT 11:45 PM'},
        '7D': {'percent': 100, 'state': 'FULL', 'reset': 'WED · NOV 25 · 10:39 PM'},
    },
}


def rectangles(path: str) -> list[tuple[float, float, float, float]]:
    """The pixel alphabet is made only of M x y h w v h h -w Z boxes in a 0..100 space."""
    found = re.findall(r'M(-?[\d.]+) (-?[\d.]+)h(-?[\d.]+)v(-?[\d.]+)h-?[\d.]+Z', path)
    return [(float(x), float(y), float(w), float(h)) for x, y, w, h in found]


def cells(percent: int) -> int:
    return 20 if percent == 100 else min(19, max(1, round(percent / 5))) if percent > 0 else 0


def metric_colour(percent: int, normal: str) -> str:
    return LOW if percent < 10 else FULL if percent == 100 else normal


def draw(label: str, palette: str, sample: dict) -> str:
    data = dual.compose(label, palette)
    mapping = dual.PALETTES[palette]
    globals_ = data['preset_root']['globals_list']
    shapes: list[str] = []

    def colour(donor: str) -> tuple[str, float]:
        value = mapping.get(donor.upper(), donor)
        return '#' + value[3:], int(value[1:3], 16) / 255

    def box(x: float, y: float, width: float, height: float, fill: str, radius: float = 0) -> None:
        rgb, alpha = colour(fill)
        shapes.append(f'<rect x="{x:.2f}" y="{y:.2f}" width="{width:.2f}" height="{height:.2f}" '
                      f'rx="{radius:.2f}" fill="{rgb}" fill-opacity="{alpha:.3f}"/>')

    def path(layout: list[float], shape_path: str, fill: str) -> None:
        x, y, width, height = layout
        for px, py, pw, ph in rectangles(shape_path):
            box(x + px * width / 100, y + py * height / 100, pw * width / 100, ph * height / 100, fill)

    def glyph(char: str, big: bool) -> str:
        if big:
            return globals_[f'p{DIGITS.index(char):03d}' if char in DIGITS else 'p013']['value']
        return globals_[f'p{14 + ALPHABET.index(char):03d}' if char in ALPHABET else 'p013']['value']

    for item in data['preset_root']['viewgroup_items']:
        title = item['internal_title']
        if title.startswith('TOUCH'):
            continue
        if title.startswith('CASE') or title == 'SCANLINES':
            # These keep the theme's own full-card geometry.
            if item['shape_type'] == 'RECT':
                box(item['position_offset_x'] * 2, item['position_offset_y'] * 2, item['shape_width'] * 2,
                    item['shape_height'] * 2, item['paint_color'], item['shape_corners'] * 2)
            else:
                path([0, 0, 1440, 600], item['shape_path'], item['paint_color'])
            continue
        layout = item['layout']
        tag, _, rest = title.partition(' / ')
        reading = sample.get(tag)
        index = int(match.group(1)) - 1 if (match := re.search(r'(\d+)(?: of 20)?$', title)) else 0
        if 'text' in item or title == 'STATUS MARK':
            path(layout, item['shape_path'], item['paint_color'])
        elif title.startswith('RULE'):
            box(*layout, item['paint_color'])
        elif title.startswith('PC SOURCE DATA AGE'):
            path(layout, glyph(sample['age'][index:index + 1] or ' ', False), DIM)
        elif title.startswith('FETCH CONTROL'):
            path(layout, glyph(sample['fetch'][index:index + 1] or ' ', False), DIM)
        elif rest.startswith('PERCENT'):
            text = f'{reading["percent"]}%'
            path(layout, glyph(text[index:index + 1] or ' ', True), metric_colour(reading['percent'], BRIGHT))
        elif rest.startswith('STATE'):
            state = reading['state']
            path(layout, glyph(state[index:index + 1] or ' ', False),
                 LABEL if state == 'REMAINING' else FULL if state == 'FULL' else ALERT)
        elif rest.startswith('CELL'):
            filled = index < cells(reading['percent'])
            box(*layout, metric_colour(reading['percent'], FILLED) if filled else EMPTY)
        elif rest.startswith('RESET'):
            path(layout, glyph(reading['reset'][index:index + 1] or ' ', False), LABEL)
        else:
            raise ValueError(f'Preview does not know how to draw {title!r}.')
    return ('<svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 1440 600" width="1440" height="600">\n'
            + '\n'.join(shapes) + '\n</svg>\n')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__.split('\n\n')[0])
    parser.add_argument('--output', type=Path, default=dual.ROOT/'local'/'dual')
    parser.add_argument('--label', default='USAGE')
    parser.add_argument('--palette', default='ember', choices=sorted(dual.PALETTES))
    args = parser.parse_args()
    args.output.mkdir(parents=True, exist_ok=True)
    for name, sample in SAMPLES.items():
        target = args.output/f'ember-dual-{name}.svg'
        target.write_text(draw(args.label, args.palette, sample), encoding='utf-8')
        print(f'Wrote {target}')
    print('Sample data only. This does not evaluate Kustom formulas or prove Android rendering.')
