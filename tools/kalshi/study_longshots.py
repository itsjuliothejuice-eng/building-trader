"""
Study 8: are long shots underpriced on Kalshi 24h before close? (pre-registered in docs/RESEARCH_LOG.md)

    python tools/kalshi/study_longshots.py

Public Kalshi data only (no account, no key). Entry = the price takers actually paid for the long-shot side
in the 6 hours before the decision. Settled on Kalshi's own result.
"""
import hashlib
import json
import os
import random
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd
import requests

BASE = 'https://api.elections.kalshi.com/trade-api/v2'
CACHE = Path('Data/kalshi/cache')
OUT = Path('Data/kalshi')
PERIODS = {'test': ('2026-04-12', '2026-07-11'), 'replication': ('2026-07-11', '2026-10-09')}   # [start, end)
BANDS = {'0.03-0.10': (0.03, 0.10), '0.10-0.20': (0.10, 0.20)}
MIN_VOLUME, HOURS_BEFORE, WINDOW_H, T_NEEDED, FEE = 5000, 24, 6, 1.96, 0.07
SAMPLE = 6000   # markets per period checked for trades (random, seed 8): Kalshi's public rate limit

_s = requests.Session()
_last, PACE = 0.0, 0.3
CUTOFF = '2026-08-10'   # Kalshi moves markets/trades before this to /historical
if os.getenv('CCXT_CA_BUNDLE'):
    _s.verify = os.getenv('CCXT_CA_BUNDLE')


def get(path, params):
    key = hashlib.sha1((path + json.dumps(params, sort_keys=True)).encode()).hexdigest()
    f = CACHE / key[:2] / f'{key}.json'
    if f.exists():
        return json.loads(f.read_text())
    global _last
    for attempt in range(10):
        wait = _last + PACE - time.time()                 # Kalshi's public limit: stay near 3 requests/second
        if wait > 0:
            time.sleep(wait)
        _last = time.time()
        try:
            r = _s.get(BASE + path, params=params, timeout=30)
        except requests.RequestException:
            time.sleep(3)
            continue
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(3)
            continue
        if r.status_code == 404:                      # e.g. no trades for this ticker on this endpoint
            return {}
        r.raise_for_status()
        break
    else:
        raise RuntimeError(f'{path}: kept failing')
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(r.text)
    return r.json()


def ts(s):
    return int(datetime.fromisoformat(s.replace('Z', '+00:00')).timestamp())


def all_markets(first, last):
    """
    Settled single-leg markets closing in [first, last). Kalshi's historical endpoint has no date filter, so
    each series is paged newest-first until closes are older than `first`. Series that only list hourly or
    15-minute markets are skipped: none of their markets is open 24h before it closes.
    """
    lo, hi = ts(first + 'T00:00:00Z'), ts(last + 'T00:00:00Z')
    series = [x for x in get('/series', {'limit': 10000}).get('series', [])
              if x.get('frequency') not in ('hourly', 'fifteen_min')]
    found = {}
    for i, sr in enumerate(series):
        for path, extra in (('/historical/markets', {}),):
            cursor = None
            while True:
                p = {'series_ticker': sr['ticker'], 'limit': 1000, **extra}
                if cursor:
                    p['cursor'] = cursor
                page = get(path, p)
                ms = page.get('markets', [])
                for m in ms:
                    c = ts(m['close_time'])
                    if (lo <= c < hi and m.get('result') in ('yes', 'no') and not m.get('mve_collection_ticker')
                            and float(m.get('volume_fp') or 0) >= MIN_VOLUME):
                        found[m['ticker']] = m
                cursor = page.get('cursor')
                if not cursor or not ms or min(ts(m['close_time']) for m in ms) < lo:
                    break
        if i % 100 == 0:
            print(f'\r  series {i:,}/{len(series):,}: {len(found):,} markets', end='', flush=True)
    print()
    cursor = None                                        # settled after the cutoff: the live endpoint has a date filter
    while True:
        p = {'status': 'settled', 'limit': 1000, 'mve_filter': 'exclude', 'min_close_ts': ts(CUTOFF + 'T00:00:00Z') - 86400 * 3,
             'max_close_ts': hi - 1}
        if cursor:
            p['cursor'] = cursor
        page = get('/markets', p)
        for m in page.get('markets', []):
            if (m.get('result') in ('yes', 'no') and not m.get('mve_collection_ticker')
                    and float(m.get('volume_fp') or 0) >= MIN_VOLUME and lo <= ts(m['close_time']) < hi):
                found[m['ticker']] = m
        cursor = page.get('cursor')
        print(f'\r  live settled markets: {len(found):,}', end='', flush=True)
        if not cursor or not page.get('markets'):
            break
    print()
    return list(found.values())


def trades(ticker, lo, hi):
    out = []
    paths = ['/historical/trades'] if hi < ts(CUTOFF + 'T00:00:00Z') else ['/historical/trades', '/markets/trades']
    for path in paths:
        cursor = None
        while True:
            p = {'ticker': ticker, 'min_ts': lo, 'max_ts': hi, 'limit': 1000}
            if cursor:
                p['cursor'] = cursor
            page = get(path, p)
            out += page.get('trades', [])
            cursor = page.get('cursor')
            if not cursor or not page.get('trades'):
                break
    seen, uniq = set(), []
    for t in out:
        if t['trade_id'] not in seen:
            seen.add(t['trade_id'])
            uniq.append(t)
    return sorted(uniq, key=lambda t: t['created_time'])


def evaluate(m):
    close = ts(m['close_time'])
    dec = close - HOURS_BEFORE * 3600
    if ts(m['open_time']) > dec - WINDOW_H * 3600:
        return None
    tr = trades(m['ticker'], dec - WINDOW_H * 3600, dec)
    if not tr:
        return None
    y = float(tr[-1]['yes_price_dollars'])
    rows = []
    for band, (lo, hi) in BANDS.items():
        for side, price in (('yes', y), ('no', 1 - y)):
            if lo <= price < hi:
                buys = [(float(t[f'{side}_price_dollars']), float(t['count_fp'])) for t in tr if t['taker_side'] == side]
                if not buys:
                    continue
                p = sum(a * b for a, b in buys) / sum(b for _, b in buys)
                cost = p + FEE * p * (1 - p)
                won = float(m['result'] == side)
                rows.append({'band': band, 'ticker': m['ticker'], 'event': m['event_ticker'],
                             'series': m['event_ticker'].split('-')[0], 'close': m['close_time'][:10],
                             'can_close_early': m.get('can_close_early'), 'side': side, 'last_price': price,
                             'paid': p, 'won': won, 'ret': (won - cost) / cost, 'contracts_seen': sum(b for _, b in buys)})
    return rows


def report(df, label):
    print(f'\n{label}')
    out = []
    for band in BANDS:
        d = df[df['band'] == band]
        if d.empty:
            out.append({'band': band, 'markets': 0})
            continue
        ev = d.groupby('event').agg(ret=('ret', 'mean'), close=('close', 'max'))
        t = ev['ret'].mean() / (ev['ret'].std(ddof=1) / np.sqrt(len(ev))) if len(ev) > 1 else 0.0
        mid = ev['close'].sort_values().iloc[len(ev) // 2]
        out.append({'band': band, 'markets': len(d), 'events': len(ev), 'avg_paid': round(d['paid'].mean(), 3),
                    'won_%': round(d['won'].mean() * 100, 1), 'ret_per_$1_%': round(ev['ret'].mean() * 100, 1),
                    't': round(t, 2), 'half1_%': round(ev[ev['close'] < mid]['ret'].mean() * 100, 1),
                    'half2_%': round(ev[ev['close'] >= mid]['ret'].mean() * 100, 1)})
    res = pd.DataFrame(out)
    print(res.to_string(index=False))
    return res


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    results = {}
    every = all_markets(PERIODS['test'][0], PERIODS['replication'][1])
    for name, (start, end) in PERIODS.items():
        ms = sorted((m for m in every if start <= m['close_time'][:10] < end
                     and ts(m['open_time']) <= ts(m['close_time']) - (HOURS_BEFORE + WINDOW_H) * 3600), key=lambda m: m['ticker'])
        n_all = len(ms)
        random.seed(8)
        ms = random.sample(ms, min(SAMPLE, len(ms)))
        print(f'{name}: {n_all:,} markets closing {start} to {end} that were open 30h+ before close; checking {len(ms):,} at random')
        rows = []
        for i, m in enumerate(ms):
            r = evaluate(m)
            if r:
                rows += r
            if i % 200 == 0:
                print(f'\r  trades checked {i:,}/{len(ms):,}, long-shot trades {len(rows):,}', end='', flush=True)
        print()
        df = pd.DataFrame(rows)
        df.to_csv(OUT / f'longshots_{name}.csv', index=False)
        results[name] = (df, report(df, f'{name.upper()} ({start} to {end})'))
        if len(df):
            report(df[df['can_close_early'] == False], f'{name}: only markets that cannot close early')   # noqa: E712
            print('\n  by series (top 10 by trades, both bands):')
            print(df.groupby('series').agg(trades=('ret', 'size'), won=('won', 'mean'), paid=('paid', 'mean'),
                                           ret=('ret', 'mean')).sort_values('trades', ascending=False).head(10).round(3).to_string())

    test, rep = results['test'][1], results['replication'][1]
    print('\nVERDICT (pre-registered: >= 200 events, t > 1.96, both halves > 0, replication > 0)')
    for band in BANDS:
        a = test[test['band'] == band].iloc[0]
        b = rep[rep['band'] == band].iloc[0]
        ok = (a.get('events', 0) >= 200 and a.get('ret_per_$1_%', -1) > 0 and a.get('t', 0) > T_NEEDED
              and a.get('half1_%', -1) > 0 and a.get('half2_%', -1) > 0 and b.get('ret_per_$1_%', -1) > 0)
        print(f"  long shots {band}: {'PASS' if ok else 'REJECT'}")


if __name__ == '__main__':
    main()
