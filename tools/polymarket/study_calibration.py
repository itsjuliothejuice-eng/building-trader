"""
Study 7 Part B: favorite-longshot bias on Polymarket (pre-registered in docs/RESEARCH_LOG.md).

    python tools/polymarket/fetch_markets.py 2026-07-11 2026-10-08
    python tools/polymarket/study_calibration.py Data/polymarket/markets_2026-07-11_2026-10-08.jsonl

Rule: at H before the SCHEDULED end, if one side is priced in the band, buy it (taker: price + $0.01 + fee).
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parents[1]))
from pm_api import CLOB, get, fee_rate, is_updown, outcome_yes

HORIZONS = {'24h': 86_400, '7d': 7 * 86_400}
BANDS = {'0.80-0.95': (0.80, 0.95), '0.95-0.99': (0.95, 0.99)}
SPREAD = 0.01
SPLIT = '2026-08-25'           # first day of the test half
T_NEEDED = 2.24                # one-sided p < 0.0125 (4 trials)


def ts(s):
    t = pd.Timestamp(s)
    return int((t if t.tzinfo else t.tz_localize('UTC')).timestamp())


def history(token, end):
    """Hourly YES prices for the 8 days before the scheduled end (cached forever: the market is closed)."""
    h = get(f'{CLOB}/prices-history', {'market': token, 'startTs': end - 8 * 86_400, 'endTs': end, 'fidelity': 60})
    return h.get('history', [])


def load(path):
    rows = []
    for line in open(path):
        m = json.loads(line)
        y = outcome_yes(m)
        if is_updown(m) or y is None or not m.get('clobTokenIds') or not m.get('closedTime'):
            continue
        rows.append({'id': m['id'], 'question': m['question'], 'event': (m.get('events') or [{}])[0].get('id', m['id']),
                     'token': json.loads(m['clobTokenIds'])[0], 'end': ts(m['endDate']), 'closed': ts(m['closedTime']),
                     'end_date': m['endDate'][:10], 'yes_won': y, 'fee_rate': fee_rate(m),
                     'category': (m.get('feeType') or 'none').split('_')[0], 'volume': float(m.get('volumeNum') or 0)})
    return pd.DataFrame(rows)


def price_at(hist, t):
    before = [p['p'] for p in hist if p['t'] <= t]
    return before[-1] if before else np.nan


def main(path):
    mk = load(path)
    print(f'{len(mk):,} cleanly resolved markets (Up/Down excluded), {mk["event"].nunique():,} events')
    with ThreadPoolExecutor(8) as pool:
        hists = list(pool.map(lambda r: history(r.token, r.end), mk.itertuples()))
    for name, h in HORIZONS.items():
        decide = mk['end'] - h
        mk[f'p_{name}'] = [price_at(hh, t) if c > t else np.nan for hh, t, c in zip(hists, decide, mk['closed'])]

    # Calibration table (context)
    print('\nCalibration at 24h before scheduled end: YES price vs how often YES won')
    b = pd.cut(mk['p_24h'], [0, .02, .05, .1, .2, .35, .5, .65, .8, .9, .95, .98, 1.0001], right=False)
    cal = mk.groupby(b, observed=True).agg(markets=('yes_won', 'size'), avg_price=('p_24h', 'mean'), yes_won=('yes_won', 'mean'))
    print(cal.round(3).to_string())

    results = []
    for hname in HORIZONS:
        for bname, (lo, hi) in BANDS.items():
            p = mk[f'p_{hname}']
            yes_fav, no_fav = p.between(lo, hi, inclusive='left'), (1 - p).between(lo, hi, inclusive='left')
            t = mk[yes_fav | no_fav].copy()
            t['price'] = np.where(yes_fav[t.index], t[f'p_{hname}'], 1 - t[f'p_{hname}'])
            t['won'] = np.where(yes_fav[t.index], t['yes_won'], 1 - t['yes_won'])
            t['fee'] = t['fee_rate'] * t['price'] * (1 - t['price'])
            cost = t['price'] + SPREAD + t['fee']
            t['ret_taker'] = (t['won'] - cost) / cost
            t['ret_maker'] = (t['won'] - t['price']) / t['price']
            ev = t.groupby('event').agg(ret=('ret_taker', 'mean'), maker=('ret_maker', 'mean'), end_date=('end_date', 'max'))
            tstat = ev['ret'].mean() / (ev['ret'].std(ddof=1) / np.sqrt(len(ev))) if len(ev) > 1 else 0
            first, second = ev[ev['end_date'] < SPLIT]['ret'].mean(), ev[ev['end_date'] >= SPLIT]['ret'].mean()
            ok = len(ev) >= 200 and ev['ret'].mean() > 0 and tstat > T_NEEDED and first > 0 and second > 0
            results.append({'trial': f'{hname} before, favorite {bname}', 'markets': len(t), 'events': len(ev),
                            'win_rate_%': round(t['won'].mean() * 100, 1), 'avg_price': round(t['price'].mean(), 3),
                            'taker_ret_%': round(ev['ret'].mean() * 100, 2), 't': round(tstat, 2),
                            'half1_%': round(first * 100, 2), 'half2_%': round(second * 100, 2),
                            'maker_ret_%': round(ev['maker'].mean() * 100, 2),
                            'worst_event_%': round(ev['ret'].min() * 100), 'verdict': 'PASS' if ok else 'REJECT'})
            t.to_csv(f'Data/polymarket/trades_{hname}_{bname}.csv', index=False)
    print('\nFavorite strategy (returns per $1 staked, averaged per event; taker = price + $0.01 + fee)')
    print(pd.DataFrame(results).to_string(index=False))

    # Where does it come from? Category breakdown for the 24h, 0.80-0.95 band
    t = pd.read_csv('Data/polymarket/trades_24h_0.80-0.95.csv')
    print('\nBy category (24h, 0.80-0.95, taker, per market):')
    print(t.groupby('category').agg(markets=('ret_taker', 'size'), win_rate=('won', 'mean'),
                                    avg_price=('price', 'mean'), taker_ret=('ret_taker', 'mean')).round(3).to_string())


if __name__ == '__main__':
    main(sys.argv[1])
