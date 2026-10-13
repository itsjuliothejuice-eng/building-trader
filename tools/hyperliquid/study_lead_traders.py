"""
Study 9: do Hyperliquid's best traders keep winning? (pre-registered in docs/RESEARCH_LOG.md)

    python tools/hyperliquid/study_lead_traders.py

Public data only: the leaderboard and each address's fills (every trade on Hyperliquid is on-chain).
Read-only; no account, no key, no orders.
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
from scipy.stats import spearmanr

LEADERBOARD = 'https://stats-data.hyperliquid.xyz/Mainnet/leaderboard'
INFO = 'https://api.hyperliquid.xyz/info'
CACHE, OUT = Path('Data/hyperliquid/cache'), Path('Data/hyperliquid')
F = ('2026-06-12', '2026-08-11')          # [start, end)
T = ('2026-08-11', '2026-10-10')
N_POOL, MIN_VOLUME, MIN_CLOSES, STRICT_CLOSES, TOP, FILL_CAP = 1000, 100_000, 20, 100, 20, 9_900
T_NEEDED = 2.24

_s = requests.Session()
if os.getenv('CCXT_CA_BUNDLE'):
    _s.verify = os.getenv('CCXT_CA_BUNDLE')
_last = 0.0


def ms(day):
    return int(datetime.fromisoformat(day).replace(tzinfo=timezone.utc).timestamp() * 1000)


def post(body):
    global _last
    key = hashlib.sha1(json.dumps(body, sort_keys=True).encode()).hexdigest()
    f = CACHE / key[:2] / f'{key}.json'
    if f.exists():
        try:
            return json.loads(f.read_text())
        except ValueError:
            f.unlink()
    for attempt in range(10):
        time.sleep(max(0.0, _last + 1.2 - time.time()))   # stay well under the public weight limit
        _last = time.time()
        try:
            r = _s.post(INFO, json=body, timeout=30)
        except requests.RequestException:
            time.sleep(5)
            continue
        if r.status_code == 429 or r.status_code >= 500:
            time.sleep(10)
            continue
        r.raise_for_status()
        break
    else:
        raise RuntimeError(f'{body}: kept failing')
    f.parent.mkdir(parents=True, exist_ok=True)
    f.write_text(r.text)
    return r.json()


def fills(user):
    """All fills from the start of F to the end of T, or None if the API's 10,000-fill window can't reach back that far."""
    out, start, end = [], ms(F[0]), ms(T[1])
    while start < end:
        page = post({'type': 'userFillsByTime', 'user': user, 'startTime': start, 'endTime': end})
        if not page:
            break
        out += page
        if len(out) >= FILL_CAP:
            return None
        if len(page) < 2000:
            break
        start = max(p['time'] for p in page) + 1
    return out


def window_stats(fl, lo, hi):
    d = [x for x in fl if ms(lo) <= x['time'] < ms(hi)]
    pnl = sum(float(x['closedPnl']) - float(x['fee']) for x in d)
    closes = sum(1 for x in d if float(x['closedPnl']) != 0)
    return pnl, closes, sum(abs(float(x['px']) * float(x['sz'])) for x in d)


def perf(row, window):
    return float(dict(row['windowPerformances'])[window]['pnl'])


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    lb = requests.get(LEADERBOARD, timeout=60, verify=_s.verify).json()['leaderboardRows']
    eligible = sorted((r for r in lb if float(dict(r['windowPerformances'])['allTime']['vlm']) >= MIN_VOLUME),
                      key=lambda r: r['ethAddress'])
    random.seed(9)
    pool = random.sample(eligible, N_POOL)
    print(f'leaderboard {len(lb):,} accounts, {len(eligible):,} with ${MIN_VOLUME:,}+ volume; sampled {len(pool)}')

    rows, capped = [], 0
    for i, r in enumerate(pool):
        fl = fills(r['ethAddress'])
        if fl is None:
            capped += 1
        else:
            fp, fc, fv = window_stats(fl, *F)
            tp, tc, tv = window_stats(fl, *T)
            mid = (datetime.fromisoformat(F[0]) + (datetime.fromisoformat(F[1]) - datetime.fromisoformat(F[0])) / 2).date().isoformat()
            h1, _, _ = window_stats(fl, F[0], mid)
            h2, _, _ = window_stats(fl, mid, F[1])
            rows.append({'address': r['ethAddress'], 'name': r.get('displayName'), 'account_value': float(r['accountValue']),
                         'alltime_pnl': perf(r, 'allTime'), 'f_pnl': fp, 'f_closes': fc, 'f_volume': fv,
                         'f_half1': h1, 'f_half2': h2, 't_pnl': tp, 't_closes': tc, 't_volume': tv})
        if i % 50 == 0:
            print(f'\r  {i}/{len(pool)} traders fetched, {capped} over the fill limit', end='', flush=True)
    print()
    df = pd.DataFrame(rows)
    df.to_csv(OUT / 'traders.csv', index=False)

    act = df[(df['f_closes'] >= MIN_CLOSES)]
    both = act[act['t_closes'] >= MIN_CLOSES]
    rho, p_two = spearmanr(both['f_pnl'], both['t_pnl'])
    p_one = p_two / 2 if rho > 0 else 1 - p_two / 2
    pool_t = df[df['t_closes'] >= MIN_CLOSES]['t_pnl']
    print(f'\n{len(df)} traders analyzed; {capped} skipped (over 10,000 fills: bots); '
          f'{len(act)} active in formation; {len(both)} active in both windows')
    print(f'profitable: formation {(act["f_pnl"] > 0).mean() * 100:.0f}%, test {(pool_t > 0).mean() * 100:.0f}%')
    print(f'rank correlation of profit, formation vs test: {rho:.3f} (one-sided p = {p_one:.4f})')
    print(f'pool test profit: mean ${pool_t.mean():,.0f}, median ${pool_t.median():,.0f}')

    strict = act[(act['f_half1'] > 0) & (act['f_half2'] > 0) & (act['alltime_pnl'] > 0) & (act['f_closes'] >= STRICT_CLOSES)]
    picks = {'Top 20 by formation profit': act.nlargest(TOP, 'f_pnl'),
             f'Strict "proven" ({len(strict)} qualified)': strict.nlargest(TOP, 'f_pnl')}
    for name, top in picks.items():
        t = top['t_pnl']
        diff = t.mean() - pool_t.mean()
        se = np.sqrt(t.var(ddof=1) / len(t) + pool_t.var(ddof=1) / len(pool_t)) if len(t) > 1 else np.inf
        tstat = diff / se
        ok = rho > 0 and p_one < 0.01 and t.median() > 0 and (t > 0).mean() > 0.6 and tstat > T_NEEDED
        print(f'\n{name}:')
        print(f'  formation: total ${top["f_pnl"].sum():,.0f}, median ${top["f_pnl"].median():,.0f}')
        print(f'  test:      total ${t.sum():,.0f}, median ${t.median():,.0f}, profitable {(t > 0).mean() * 100:.0f}%, '
              f'still trading {(top["t_closes"] > 0).mean() * 100:.0f}%')
        print(f'  vs pool: t = {tstat:.2f} (needs > {T_NEEDED})  ->  {"PASS" if ok else "REJECT"}')
        print(top[['address', 'f_pnl', 't_pnl', 'f_closes', 't_closes', 'alltime_pnl']].round(0).to_string(index=False))


if __name__ == '__main__':
    main()
