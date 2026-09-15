#!/usr/bin/env python3
"""Create an explicitly synthetic DEMO snapshot. This never reads real account data."""
import argparse
from datetime import datetime, timedelta, timezone
from pathlib import Path
from connector import atomic_write

if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--remaining', type=float, default=64)
    parser.add_argument('--output', type=Path, default=Path('local/usage.json'))
    args = parser.parse_args()
    if not 0 <= args.remaining <= 100:
        parser.error('Remaining must be 0..100')
    now = datetime.now(timezone.utc)
    atomic_write(args.output, {'demo': True, 'weekly': {'available': True,
        'remaining': args.remaining, 'resetsAt': (now+timedelta(days=3)).isoformat(timespec='seconds')},
        'refreshedAt': now.isoformat(timespec='seconds')})
    print(f'SYNTHETIC DEMO ONLY: wrote {args.remaining}% to {args.output}')
    print('Use a DEMO-labeled preset. This is a snapshot and will become stale; no polling is started.')
