"""
Download daily candles for EVERY active Coinbase USD spot market (Study 5's wide list). No API key needed.

    python tools/fetch_coinbase_universe.py                 # all USD spot coins, from 2016, into Data/universe/
    python tools/fetch_coinbase_universe.py --coins BTC ETH # just these

Re-running only fetches days newer than what's already saved. About 400 coins x 12 pages,
so the first run takes 10-20 minutes. Writes Data/universe/<COIN>_USD_1d.csv
(same columns as fetch_coinbase_ohlcv.py).

Only coins listed TODAY can be downloaded. Coins that were delisted are missing, so any
test on this list looks better than reality (survivorship bias).
"""

import argparse
import csv
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import ccxt

PAGE = 300
DAY = 86_400_000


def load_existing(path):
    if not path.exists():
        return {}
    with path.open() as f:
        rows = list(csv.reader(f))[1:]
    return {int(datetime.strptime(r[0], '%Y-%m-%d %H:%M:%S').replace(tzinfo=timezone.utc).timestamp() * 1000):
            [float(x) for x in r[1:]] for r in rows}


def fetch(ex, symbol, path, start_ms):
    rows = load_existing(path)
    since = max(rows) + DAY if rows else start_ms
    end = ex.milliseconds() // DAY * DAY                 # today's candle isn't closed yet
    while since < end:
        for _ in range(4):
            try:
                batch = ex.fetch_ohlcv(symbol, '1d', since=since, limit=PAGE)
                break
            except (ccxt.NetworkError, ccxt.ExchangeNotAvailable):
                time.sleep(5)
        else:
            raise RuntimeError(f'{symbol}: network kept failing')
        for t, *ohlcv in batch:
            if t < end:
                rows[t] = ohlcv
        since += PAGE * DAY                              # Coinbase skips empty days; always advance a page
    with path.open('w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        for t in sorted(rows):
            w.writerow([datetime.fromtimestamp(t / 1000, timezone.utc).strftime('%Y-%m-%d %H:%M:%S'), *rows[t]])
    return len(rows)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument('--coins', nargs='*', help='default: every active USD spot market')
    ap.add_argument('--start', default='2016-01-01')
    ap.add_argument('--out', default='Data/universe')
    a = ap.parse_args()

    ex = ccxt.coinbase({'enableRateLimit': True})
    if os.getenv('CCXT_CA_BUNDLE'):
        ex.validateServerSsl = os.getenv('CCXT_CA_BUNDLE')
    markets = ex.load_markets()
    symbols = sorted(s for s, m in markets.items() if m['spot'] and m['quote'] == 'USD' and m['active'])
    if a.coins:
        wanted = {c.upper() for c in a.coins}
        symbols = [s for s in symbols if markets[s]['base'] in wanted]
        missing = wanted - {markets[s]['base'] for s in symbols}
        if missing:
            print('not on Coinbase spot:', ' '.join(sorted(missing)))
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    start = ex.parse8601(f'{a.start}T00:00:00Z')
    for i, s in enumerate(symbols, 1):
        path = out / f"{markets[s]['base']}_USD_1d.csv"
        try:
            n = fetch(ex, s, path, start)
            print(f'[{i}/{len(symbols)}] {s}: {n} days')
        except Exception as err:
            print(f'[{i}/{len(symbols)}] {s}: FAILED ({type(err).__name__}: {err})')


if __name__ == '__main__':
    main()
