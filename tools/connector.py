#!/usr/bin/env python3
"""Normalize local JSON into the small widget payload, without copying credentials.
This is a schema adapter, not an API client. Your existing connector writes the input.
"""
from __future__ import annotations
import argparse
from datetime import datetime
import json
import math
import os
from pathlib import Path
import tempfile
from typing import Any


def field(document: Any, path: str) -> Any:
    """Dotted keys and numeric list indices; keys containing dots need custom code."""
    value = document
    for part in path.split('.'):
        if isinstance(value, list) and part.isdigit():
            value = value[int(part)]
        elif isinstance(value, dict):
            value = value[part]
        else:
            raise ValueError(f'Cannot traverse field {path!r}')
    return value


def number(value: Any) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError('Expected a finite JSON number, not a string or boolean.')
    return float(value)


def timestamp(value: Any) -> str | None:
    if value is None or value == '':
        return None
    if not isinstance(value, str):
        raise ValueError('Timestamps must be ISO-8601 strings with timezone, or null.')
    try:
        parsed = datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError as exc:
        raise ValueError('Invalid timestamp.') from exc
    if parsed.tzinfo is None or not 2000 <= parsed.year <= 2099:
        raise ValueError('Timestamp needs a timezone and a year between 2000 and 2099.')
    return parsed.isoformat(timespec='seconds')


def normalize(document: dict, mapping: dict) -> dict:
    allowed = {'value', 'mode', 'total', 'available', 'updated', 'reset'}
    if set(mapping) - allowed:
        raise ValueError('Unknown mapping key(s): ' + ', '.join(sorted(set(mapping)-allowed)))
    available = field(document, mapping['available']) if mapping.get('available') else True
    if not isinstance(available, bool):
        raise ValueError('Availability must be a JSON boolean.')
    updated = timestamp(field(document, mapping['updated'])) if mapping.get('updated') else None
    reset = timestamp(field(document, mapping['reset'])) if mapping.get('reset') else None
    value = None
    mode = mapping.get('mode', 'remaining')
    if mode not in ('remaining', 'used', 'fraction', 'ratio'):
        raise ValueError('Mode must be remaining, used, fraction or ratio.')
    if available:
        raw = number(field(document, mapping['value']))
        if mode == 'remaining':
            value = raw
        elif mode == 'used':
            value = 100 - raw
        elif mode == 'fraction':
            value = 100 * raw
        else:
            total = number(field(document, mapping['total']))
            if total <= 0:
                raise ValueError('Total capacity must be positive.')
            value = raw / total * 100
        if not math.isfinite(value) or not 0 <= value <= 100:
            raise ValueError('Remaining percentage is outside 0..100; refusing to clamp invalid data.')
    # Only these four fields cross the boundary. Never relay arbitrary upstream JSON.
    return {'weekly': {'available': available, 'remaining': value, 'resetsAt': reset},
            'refreshedAt': updated}


def atomic_write(path: Path, document: dict) -> None:
    path = path.expanduser().resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = None
    try:
        with tempfile.NamedTemporaryFile('w', encoding='utf-8', dir=path.parent,
                prefix='.usage-', suffix='.tmp', delete=False) as output:
            temporary = Path(output.name)
            json.dump(document, output, ensure_ascii=False, allow_nan=False, indent=2)
            output.write('\n'); output.flush(); os.fsync(output.fileno())
        os.replace(temporary, path)
    finally:
        if temporary and temporary.exists():
            temporary.unlink()


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--input', type=Path, required=True)
    parser.add_argument('--mapping', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    try:
        if args.input.stat().st_size > 1_048_576:
            raise ValueError('Input exceeds 1 MiB.')
        if args.input.resolve() == args.output.resolve() or args.mapping.resolve() == args.output.resolve():
            raise ValueError('Output must not overwrite the input or mapping.')
        payload = normalize(json.loads(args.input.read_text(encoding='utf-8-sig')),
                            json.loads(args.mapping.read_text(encoding='utf-8-sig')))
        atomic_write(args.output, payload)
    except (OSError, ValueError, KeyError, IndexError, TypeError) as error:
        # Keep an older export unchanged: its original timestamp can become visibly stale.
        parser.exit(1, f'Adapter failed; existing output was not replaced: {error}\n')
    print(f'Wrote widget payload to {args.output}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
