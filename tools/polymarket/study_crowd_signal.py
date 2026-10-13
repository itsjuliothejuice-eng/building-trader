"""
Study 7 Part D: does Polymarket's daily "Bitcoin/Ethereum Up or Down" crowd predict the coin on Coinbase,
beyond what the price move already says? (pre-registered in docs/RESEARCH_LOG.md)

    python tools/fetch_coinbase_ohlcv.py BTC/USD 1h --start 2024-11-01   (and ETH/USD)
    python tools/polymarket/study_crowd_signal.py

Signal 1 hour into each noon-to-noon ET window: edge = P_crowd(Up) - P_fair, where P_fair is the chance a
random walk from here finishes above the window's start price. Trade on CDE perps from the next hourly open
to the window's end: long if edge > +0.05, short if < -0.05.
"""
import json
import sys
from datetime import date, timedelta
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import norm, pearsonr

sys.path.insert(0, str(Path(__file__).parent))
sys.path.insert(0, str(Path(__file__).parents[1]))
import quantcheck as q
from pm_api import CLOB, GAMMA, get, outcome_yes

COINS = {'BTC': ('bitcoin', 825), 'ETH': ('ethereum', 253)}   # slug name, CDE contract USD (2026-10-08)
FIRST, LAST = date(2025, 1, 1), date(2026, 10, 8)
THRESH, FEE, SLIP, PER_CONTRACT = 0.05, 0.0010, 0.0005, 0.12
H = 3600


def find_market(name, d):
    for slug in (f"{name}-up-or-down-on-{d.strftime('%B').lower()}-{d.day}-{d.year}",
                 f"{name}-up-or-down-on-{d.strftime('%B').lower()}-{d.day}"):
        ev = get(f'{GAMMA}/events', {'slug': slug})
        for e in ev:
            for m in e.get('markets', []):
                if m.get('endDate', '')[:10] == str(d) and m.get('closed'):
                    return m
    return None


def main():
    trials = pd.read_csv(q.TRIALS_FILE)
    trials = trials[trials['name'] != 'study7_pm_crowd'].drop_duplicates(['name', 'params'], keep='last')
    trial_srs = trials['sharpe_per_bar'].tolist()
    out = {}
    for coin, (name, contract) in COINS.items():
        px = q.load_csv(f'Data/{coin}_USD_1h.csv')
        logret = np.log(px['close']).diff()
        rows = []
        d = FIRST
        while d <= LAST:
            m = find_market(name, d)
            d += timedelta(days=1)
            if not m or outcome_yes(m) is None or not m.get('eventStartTime'):
                continue
            outcomes = json.loads(m['outcomes'])
            up_token = json.loads(m['clobTokenIds'])[outcomes.index('Up')]
            t0 = int(pd.Timestamp(m['eventStartTime']).timestamp())
            t_end = int(pd.Timestamp(m['endDate']).timestamp())
            t1 = t0 + H
            hist = get(f'{CLOB}/prices-history', {'market': up_token, 'startTs': t0, 'endTs': t1, 'fidelity': 1}).get('history', [])
            before = [h['p'] for h in hist if h['t'] <= t1]
            idx = lambda t: pd.Timestamp(t, unit='s', tz='UTC')
            try:
                s0, s1 = px.at[idx(t0), 'open'], px.at[idx(t1), 'open']
                entry, exit_ = px.at[idx(t1 + H), 'open'], px.at[idx(t_end), 'open']
            except KeyError:
                continue
            if not before:
                continue
            sigma = logret.loc[:idx(t1)].iloc[-721:-1].std()
            tau = (t_end - t1) / H
            p_fair = norm.cdf(np.log(s1 / s0) / (sigma * np.sqrt(tau)))
            edge = before[-1] - p_fair
            side = 1 if edge > THRESH else -1 if edge < -THRESH else 0
            cost = 2 * (FEE + SLIP + PER_CONTRACT / contract) if side else 0.0
            rows.append({'date': idx(t0).normalize(), 'p_crowd': before[-1], 'p_fair': p_fair, 'edge': edge,
                         'fwd_ret': np.log(exit_ / s1), 'side': side,
                         'net': side * np.log(exit_ / entry) - cost, 'up_won': outcome_yes(m)})
        df = pd.DataFrame(rows).set_index('date')
        df.to_csv(f'Data/polymarket/crowd_{coin}.csv')
        r, p = pearsonr(df['edge'], df['fwd_ret'])
        tstat = r * np.sqrt((len(df) - 2) / (1 - r ** 2))
        net = df['net']
        m = {'sharpe_per_bar': net.mean() / net.std() if net.std() > 0 else 0.0, 'n_bars': len(net)}
        m['sharpe'] = round(m['sharpe_per_bar'] * np.sqrt(365), 2)
        q.log_trial('study7_pm_crowd', {'coin': coin}, m)
        trial_srs.append(m['sharpe_per_bar'])
        out[coin] = (df, tstat, r, m)

    for coin, (df, tstat, r, m) in out.items():
        half = len(df) // 2
        h1, h2 = df['net'].iloc[:half].mean(), df['net'].iloc[half:].mean()
        dsr = q.deflated_sharpe(df['net'], trial_srs)
        trades = df[df['side'] != 0]
        brier_crowd = ((df['p_crowd'] - df['up_won']) ** 2).mean()
        brier_fair = ((df['p_fair'] - df['up_won']) ** 2).mean()
        ok = tstat > 1.96 and h1 > 0 and h2 > 0 and dsr['pass']
        print(f"\n{coin}: {len(df)} days ({df.index[0].date()} to {df.index[-1].date()}), {len(trades)} trades")
        print(f"  how wrong each forecast was 1h in (Brier score, lower is better): Polymarket crowd {brier_crowd:.4f} vs "
              f"random-walk-from-price {brier_fair:.4f}")
        print(f"  correlation of the crowd's extra view with the rest of the day: r = {r:.3f}, t = {tstat:.2f} (needs > 1.96)")
        print(f"  trade on Coinbase perps: avg {trades['net'].mean() * 100 if len(trades) else 0:.3f}% per trade, "
              f"win rate {(trades['net'] > 0).mean() * 100 if len(trades) else 0:.0f}%, total {(np.exp(df['net'].sum()) - 1) * 100:.1f}%, "
              f"fees {len(trades) * 2 * (FEE + SLIP + PER_CONTRACT / COINS[coin][1]) * 100:.0f}%")
        print(f"  halves: {h1 * 100:.3f}% / {h2 * 100:.3f}% per day; Sharpe {m['sharpe']}; {dsr['detail']}")
        print(f"  verdict: {'PASS' if ok else 'REJECT'}")


if __name__ == '__main__':
    main()
