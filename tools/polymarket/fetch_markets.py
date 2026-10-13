"""
Download every closed Polymarket market whose scheduled end date falls in a range (public Gamma API).

    python tools/polymarket/fetch_markets.py 2026-07-11 2026-10-08

Writes Data/polymarket/markets_<start>_<end>.jsonl. Volume >= $10,000 only (pre-registered in Study 7).
"""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

from pm_api import GAMMA, get

MIN_VOLUME = 10_000


def main(start, end):
    d0, d1 = date.fromisoformat(start), date.fromisoformat(end)
    out = Path(f'Data/polymarket/markets_{start}_{end}.jsonl')
    out.parent.mkdir(parents=True, exist_ok=True)
    n = 0
    with out.open('w') as f:
        day = d0
        while day <= d1:
            offset = 0
            while True:
                page = get(f'{GAMMA}/markets', {'closed': 'true', 'limit': 100, 'offset': offset,
                                                'volume_num_min': MIN_VOLUME,
                                                'end_date_min': f'{day}T00:00:00Z',
                                                'end_date_max': f'{day + timedelta(days=1)}T00:00:00Z'})
                for m in page:
                    if m.get('endDate', '')[:10] == str(day):      # boundaries belong to one day only
                        f.write(json.dumps(m) + '\n')
                        n += 1
                if len(page) < 100:
                    break
                offset += 100
            print(f'\r{day}: {n:,} markets', end='', flush=True)
            day += timedelta(days=1)
    print(f'\nwrote {out}')


if __name__ == '__main__':
    main(*sys.argv[1:3])
