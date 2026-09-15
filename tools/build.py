#!/usr/bin/env python3
"""Package editable, sanitized Kustom JSON; optional native pixel-header customization.
Python 3.10+, standard library only. Does not call any service or change your phone.
"""
from __future__ import annotations
import argparse
import copy
import hashlib
import json
from pathlib import Path
import re
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[1]
PLACEHOLDER = 'https://example.invalid/usage.json'
FIXED_ZIP_TIME = (2026, 9, 15, 0, 0, 0)


def transform_path(path: str, sx: float, tx: float) -> str:
    """Horizontally transform the limited M/L/h/v/Z paths used by our pixel glyphs."""
    tokens = re.findall(r'[MLhvZ]|-?\d+(?:\.\d+)?', path)
    i, pieces = 0, []
    def fmt(n: float) -> str:
        return f'{n:.6f}'.rstrip('0').rstrip('.') or '0'
    while i < len(tokens):
        cmd = tokens[i]; i += 1
        if cmd in ('M', 'L'):
            x, y = float(tokens[i]), float(tokens[i + 1]); i += 2
            pieces.append(f'{cmd}{fmt(x*sx+tx)} {fmt(y)}')
        elif cmd in ('h', 'v'):
            n = float(tokens[i]); i += 1
            pieces.append(cmd + fmt(n*sx if cmd == 'h' else n))
        elif cmd == 'Z':
            pieces.append('Z')
        else:
            raise ValueError(f'Unsupported SVG token: {cmd}')
    return ''.join(pieces)


def header_path(data: dict, label: str) -> str:
    """Compose existing native glyph paths. No font or image assets are introduced."""
    root = data['preset_root']
    selector = next(x for x in root['viewgroup_items']
                    if x.get('internal_title') == 'QUOTA / DATA STATE / 01')
    glyphs = dict(re.findall(r'lv\(c\)="([^"]+)",gv\((p\d+)\)',
                            selector['internal_formulas']['shape_path']))
    if not label or len(label) > 20:
        raise ValueError('Header must contain 1–20 characters.')
    result = ['M0 0L0 0M100 100L100 100']
    for index, char in enumerate(label.upper()):
        if char == ' ':
            continue
        if char not in glyphs:
            raise ValueError(f'Unsupported header character: {char!r}')
        path = root['globals_list'][glyphs[char]]['value']
        result.append(transform_path(path, 1/len(label), index*100/len(label)))
    return ''.join(result)


def customize(original: dict, *, label: str | None = None,
              source_label: str | None = None) -> dict:
    data = copy.deepcopy(original)
    if label:
        path = header_path(data, label)
        for item in data['preset_root']['viewgroup_items']:
            title = item.get('internal_title', '')
            if title == 'HEADER' or title == 'LCD HEADER' or title.startswith('02 / CODEX WEEKLY'):
                item['shape_path'] = path
                # Remove an old formula only if this field has one.
                item.get('internal_formulas', {}).pop('shape_path', None)
                item.get('internal_toggles', {}).pop('shape_path', None)
                item['internal_title'] = 'HEADER / ' + label.upper()
            elif title in {'7 DAY', 'READOUT', 'SUBHEADER', 'LCD ID', 'LCD TAG'}:
                neutral = {'7 DAY': 'LIVE', 'READOUT': 'RESERVE',
                           'SUBHEADER': 'RESOURCE MONITOR', 'LCD ID': 'LIVE',
                           'LCD TAG': 'LOCAL'}[title]
                item['shape_path'] = header_path(data, neutral)
                item.get('internal_formulas', {}).pop('shape_path', None)
                item.get('internal_toggles', {}).pop('shape_path', None)
                item['internal_title'] = 'SECONDARY / ' + neutral
        data['preset_info']['title'] += ' / ' + label.upper()
        data['preset_info']['id'] = uuid.uuid5(uuid.NAMESPACE_URL,
            data['preset_info']['id'] + ':' + label.upper()).hex
    if source_label:
        source_label = source_label.upper()
        if not re.fullmatch(r'[A-Z0-9 ]{1,7}', source_label):
            raise ValueError('Source label must be 1–7 ASCII letters, digits or spaces.')
        # This changes the human-readable footer, not the source timestamp logic.
        data = json.loads(json.dumps(data).replace('PC DATA', source_label))
    return data


def pack(data: dict, src: Path, destination: Path) -> None:
    destination.parent.mkdir(parents=True, exist_ok=True)
    with zipfile.ZipFile(destination, 'w', compression=zipfile.ZIP_DEFLATED) as out:
        payloads = {'preset.json': (json.dumps(data, ensure_ascii=False, indent=2)+'\n').encode()}
        for name in ('preset_thumb_landscape.jpg', 'preset_thumb_portrait.jpg'):
            payloads[name] = (src/name).read_bytes()
        for name, content in payloads.items():
            info = zipfile.ZipInfo(name, FIXED_ZIP_TIME)
            info.compress_type = zipfile.ZIP_DEFLATED
            info.external_attr = 0o644 << 16
            out.writestr(info, content)


def build(output: Path, label: str | None = None, source_label: str | None = None) -> list[Path]:
    paths = []
    for source in sorted((ROOT/'src').glob('*/preset.json')):
        original = json.loads(source.read_text(encoding='utf-8'))
        data = customize(original, label=label, source_label=source_label)
        # No saved account state is ever shipped, even after manual source edits.
        globals_ = data['preset_root']['globals_list']
        globals_['source']['value'] = PLACEHOLDER
        globals_['latch']['value'] = '0~~~~'
        destination = output/(source.parent.name + '.kwgt')
        pack(data, source.parent, destination)
        paths.append(destination)
    output.mkdir(parents=True, exist_ok=True)
    (output/'SHA256SUMS.txt').write_text(''.join(
        hashlib.sha256(p.read_bytes()).hexdigest() + '  ' + p.name + '\n' for p in paths))
    return paths


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--output', type=Path, default=ROOT/'presets')
    parser.add_argument('--label', help='Optional pixel header, e.g. API RESERVE. Max 20 ASCII characters.')
    parser.add_argument('--source-label', help='Optional footer label, e.g. SOURCE. Max 7 characters.')
    args = parser.parse_args()
    try:
        paths = build(args.output, args.label, args.source_label)
    except (ValueError, OSError, KeyError) as error:
        parser.exit(1, f'Build failed: {error}\n')
    print(f'Built {len(paths)} presets in {args.output}')
    if args.label or args.source_label:
        print('Custom titles use original sample thumbnails. Verify custom layout on your phone.')
