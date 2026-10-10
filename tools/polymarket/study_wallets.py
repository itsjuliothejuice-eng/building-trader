"""
Study 7 Parts A and C: do Polymarket wallets that won in one 45-day window keep winning in the next?
(pre-registered in docs/RESEARCH_LOG.md)

    python tools/polymarket/study_wallets.py Data/polymarket/markets_2026-07-11_2026-10-08.jsonl

Profit per wallet counts BOTH closed positions and resolved positions still held (losers are rarely redeemed,
so they never show up in closed-positions).
"""
import json
import random
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).parent))
from pm_api import DATA, get, is_updown, outcome_yes

F = ('2026-07-11', '2026-08-24')
T = ('2026-08-25', '2026-10-08')
N_MARKETS, N_WALLETS, MAX_POSITIONS, MIN_MARKETS, TOP = 300, 3000, 5000, 10, 50
OUT = Path('Data/polymarket')


def pool(path):
    ms = [json.loads(l) for l in open(path)]
    form = [m for m in ms if F[0] <= m['endDate'][:10] <= F[1] and outcome_yes(m) is not None]
    random.seed(7)
    sample = random.sample(form, N_MARKETS)
    wallets = set()
    for i, m in enumerate(sample):
        for t in get(f'{DATA}/trades', {'market': m['conditionId'], 'limit': 500}):
            wallets.add(t['proxyWallet'])
        print(f'\rpool: {i + 1}/{N_MARKETS} markets, {len(wallets):,} wallets', end='', flush=True)
    print(f"\n  sampled markets: {sum(is_updown(m) for m in sample)} Up/Down crypto, {sum(not is_updown(m) for m in sample)} other")
    wallets = sorted(wallets)
    random.seed(7)
    return random.sample(wallets, min(N_WALLETS, len(wallets)))


def wallet_markets(w):
    """Per-asset profit and cost for resolved markets, or None if the wallet has > MAX_POSITIONS positions."""
    rows, n = {}, 0
    off = 0
    while True:
        page = get(f'{DATA}/positions', {'user': w, 'limit': 500, 'offset': off, 'sizeThreshold': 0}, cache=False)
        for p in page:
            n += 1
            if p.get('redeemable') or p.get('curPrice') in (0, 1):
                rows[p['asset']] = (p['conditionId'], p.get('endDate') or '', p['realizedPnl'] + p['cashPnl'],
                                    p['totalBought'] * p['avgPrice'], p['avgPrice'], p.get('title', ''), 'held')
        if len(page) < 500 or n > MAX_POSITIONS:
            break
        off += 500
    off = 0
    while n <= MAX_POSITIONS:
        page = get(f'{DATA}/closed-positions', {'user': w, 'limit': 50, 'offset': off}, cache=False)
        for p in page:
            n += 1
            rows.setdefault(p['asset'], (p['conditionId'], p.get('endDate') or '', p['realizedPnl'],
                                         p['totalBought'] * p['avgPrice'], p['avgPrice'], p.get('title', ''), 'closed'))
        if len(page) < 50:
            break
        off += 50
    if n > MAX_POSITIONS:
        return None
    df = pd.DataFrame(rows.values(), columns=['condition', 'end', 'pnl', 'cost', 'avg_price', 'title', 'source'])
    df['wallet'] = w
    return df


def window(df, lo, hi):
    d = df[(df['end'] >= lo) & (df['end'] <= hi)]
    return d['pnl'].sum(), d['cost'].sum(), d['condition'].nunique()


def main(path):
    wallets = pool(path)
    with ThreadPoolExecutor(6) as ex:
        res = list(ex.map(wallet_markets, wallets))
    bots = sum(r is None for r in res)
    frames = [r for r in res if r is not None and len(r)]
    allpos = pd.concat(frames, ignore_index=True)
    allpos.to_csv(OUT / 'wallet_positions.csv', index=False)
    print(f'{len(wallets):,} wallets; {bots} skipped (> {MAX_POSITIONS} positions: bots/market makers); {len(frames):,} with resolved positions')

    rows = []
    for w, d in allpos.groupby('wallet'):
        fp, fc, fn = window(d, *F)
        tp, tc, tn = window(d, *T)
        rows.append({'wallet': w, 'f_pnl': fp, 'f_cost': fc, 'f_n': fn, 't_pnl': tp, 't_cost': tc, 't_n': tn})
    w = pd.DataFrame(rows)
    w['f_roi'] = w['f_pnl'] / w['f_cost'].replace(0, np.nan)
    w['t_roi'] = w['t_pnl'] / w['t_cost'].replace(0, np.nan)
    w.to_csv(OUT / 'wallet_windows.csv', index=False)

    both = w[(w['f_n'] >= MIN_MARKETS) & (w['t_n'] >= MIN_MARKETS)].dropna(subset=['f_roi', 't_roi'])
    rho, p_two = spearmanr(both['f_roi'], both['t_roi'])
    p_one = p_two / 2 if rho > 0 else 1 - p_two / 2
    top = w[w['f_n'] >= MIN_MARKETS].nlargest(TOP, 'f_pnl')
    top_t = top[top['t_n'] > 0]
    pool_t = w[w['t_n'] > 0]['t_roi'].dropna()
    diff = top_t['t_roi'].mean() - pool_t.mean()
    se = np.sqrt(top_t['t_roi'].var(ddof=1) / len(top_t) + pool_t.var(ddof=1) / len(pool_t))
    tstat = diff / se
    ok = rho > 0 and p_one < 0.01 and top_t['t_roi'].median() > 0 and tstat > 2.33

    print(f'\nWallets active (>= {MIN_MARKETS} resolved markets) in BOTH windows: {len(both)}')
    print(f'Spearman correlation of ROI, formation vs test: {rho:.3f} (one-sided p = {p_one:.4f})')
    print(f'Share of wallets profitable: formation {(w["f_pnl"] > 0)[w["f_n"] > 0].mean() * 100:.0f}%, '
          f'test {(w["t_pnl"] > 0)[w["t_n"] > 0].mean() * 100:.0f}%')
    print(f'\nTop {TOP} by formation profit: formation ROI median {top["f_roi"].median() * 100:.1f}%, '
          f'total ${top["f_pnl"].sum():,.0f}')
    print(f'  in the test window ({len(top_t)} still active): ROI mean {top_t["t_roi"].mean() * 100:.1f}%, '
          f'median {top_t["t_roi"].median() * 100:.1f}%, profitable {(top_t["t_pnl"] > 0).mean() * 100:.0f}%, '
          f'total ${top_t["t_pnl"].sum():,.0f}')
    print(f'  whole pool test ROI: mean {pool_t.mean() * 100:.1f}%, median {pool_t.median() * 100:.1f}%')
    print(f'  difference t = {tstat:.2f} (needs > 2.33)')
    print(f"\nPart A verdict: {'PASS (worth a copy-lag study)' if ok else 'REJECT: past winners do not reliably keep winning'}")

    # Part C: what the formation winners did (descriptive)
    tp = allpos[allpos['wallet'].isin(top['wallet']) & (allpos['end'] >= F[0]) & (allpos['end'] <= F[1])].copy()
    tp['updown'] = tp['title'].str.lower().str.contains('up or down')
    tp['sports'] = tp['title'].str.contains(r' vs\.? |win on 20\d\d', regex=True)
    best = tp.groupby('wallet')['pnl'].max() / tp.groupby('wallet')['pnl'].sum().where(lambda s: s > 0)
    print(f'\nPart C, top {TOP} formation winners ({len(tp):,} resolved positions):')
    print(f'  median positions per wallet {tp.groupby("wallet").size().median():.0f}; '
          f'median entry price {tp["avg_price"].median():.2f}; '
          f'share of positions entered at 0.80+ {(tp["avg_price"] >= 0.8).mean() * 100:.0f}%, at < 0.20 {(tp["avg_price"] < 0.2).mean() * 100:.0f}%')
    print(f'  crypto Up/Down positions {tp["updown"].mean() * 100:.0f}%, sports-looking {tp["sports"].mean() * 100:.0f}%')
    print(f'  median share of a wallet\'s formation profit from its single best market: {best.median() * 100:.0f}%')
    held_loss = allpos[(allpos['source'] == 'held') & (allpos['pnl'] < 0)]['pnl'].sum()
    closed = allpos[allpos['source'] == 'closed']['pnl'].sum()
    print(f'  (all wallets) profit from closed-positions alone ${closed:,.0f}; losing bets still held (missing from it) '
          f'${held_loss:,.0f}; true total ${allpos["pnl"].sum():,.0f}')


if __name__ == '__main__':
    main(sys.argv[1])
