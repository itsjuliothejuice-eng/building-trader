"""
Download historical candles from Coinbase for backtesting. No API key needed.

    python tools/fetch_coinbase_ohlcv.py BTC/USD 1h --start 2023-01-01
    python tools/fetch_coinbase_ohlcv.py ETH/USD 1d --start 2020-01-01 --out Data

Writes <out>/<BASE>_<QUOTE>_<timeframe>.csv with columns
timestamp,open,high,low,close,volume (UTC), which the cbt DataLoader reads.
Timeframes: 1m 5m 15m 30m 1h 2h 6h 1d.
"""

import argparse
import csv
import time
from datetime import datetime, timezone
from pathlib import Path

import ccxt

PAGE = 300  # Coinbase max candles per request


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('symbol', help='e.g. BTC/USD')
    ap.add_argument('timeframe', help='1m 5m 15m 30m 1h 2h 6h 1d')
    ap.add_argument('--start', required=True, help='YYYY-MM-DD (UTC)')
    ap.add_argument('--end', help='YYYY-MM-DD (UTC), default now')
    ap.add_argument('--out', default='Data', help='output folder (default Data)')
    args = ap.parse_args()

    ex = ccxt.coinbase({'enableRateLimit': True})
    ex.load_markets()
    if args.symbol not in ex.markets:
        raise SystemExit(f"{args.symbol} is not a Coinbase market")
    if args.timeframe not in ex.timeframes:
        raise SystemExit(f"timeframe must be one of {list(ex.timeframes)}")

    step = ex.parse_timeframe(args.timeframe) * 1000
    since = ex.parse8601(f"{args.start}T00:00:00Z")
    end = ex.parse8601(f"{args.end}T00:00:00Z") if args.end else ex.milliseconds()

    rows = {}
    while since < end:
        batch = ex.fetch_ohlcv(args.symbol, args.timeframe, since=since, limit=PAGE)
        if batch:
            for r in batch:
                if r[0] < end:
                    rows[r[0]] = r
        # Coinbase skips candles with no trades, so always advance a full page
        since += PAGE * step
        print(f"\r{len(rows):,} candles through {datetime.fromtimestamp(min(since, end) / 1000, timezone.utc):%Y-%m-%d}", end='')
        time.sleep(ex.rateLimit / 1000)
    print()

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    path = out / f"{args.symbol.replace('/', '_')}_{args.timeframe}.csv"
    with path.open('w', newline='') as f:
        w = csv.writer(f)
        w.writerow(['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        for ts in sorted(rows):
            t, o, h, l, c, v = rows[ts]
            w.writerow([datetime.fromtimestamp(t / 1000, timezone.utc).strftime('%Y-%m-%d %H:%M:%S'), o, h, l, c, v])
    print(f"Saved {len(rows):,} candles to {path}")


if __name__ == '__main__':
    main()
