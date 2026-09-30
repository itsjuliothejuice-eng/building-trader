"""
Study 1: trend-following with volatility control on BTC, ETH and SOL.

PRE-REGISTERED (written before looking at results):

Hypothesis and mechanism: crypto prices trend over weeks to months because
information spreads slowly and most buyers chase past performance, and
because forced sellers (liquidations, capitulation) push falling prices
further. Time-series momentum is one of the most replicated effects across
futures markets (Moskowitz, Ooi & Pedersen 2012). The counterparty is the
late chaser and the panic seller.

Rules (no parameter is fitted to the data):
  - trend score = average over lookbacks {20, 60, 120, 250} days of
    +1 if price is above its level N days ago, else 0 (long only) or -1 (long/short)
  - volatility control: scale so the position aims for 40%/yr volatility,
    capped at 1x (never leveraged), using 30-day realized volatility
  - only trade when the target changes by more than 25 percentage points
    (cuts fees)
  - costs: user's Intro-tier CDE perp fees (0.10% + $0.12/contract per side),
    5 bps slippage, 1 bp/day funding charged on every open position

Variants (the trial count): {long only, long/short} x {vol control on, off}
  x {BTC, ETH, SOL} = 12 trials. Nothing else will be tried without logging it.

Benchmark: buy and hold the same coin on spot (one 0.90% buy fee).

    python tools/fetch_coinbase_ohlcv.py BTC/USD 1d --start 2016-01-01   (also ETH/USD, SOL/USD)
    python tools/study_trend.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import quantcheck as q

LOOKBACKS = (20, 60, 120, 250)
TARGET_VOL = 0.40
BUFFER = 0.25
CONTRACT_USD = {'BTC': 840, 'ETH': 270, 'SOL': 600}   # approx value of one CDE perp contract, 2026-09-30


def trend_signal(d, long_short=False, vol_control=True):
    c = d['close']
    votes = [(np.sign(c / c.shift(n) - 1)) for n in LOOKBACKS]
    if not long_short:
        votes = [v.clip(lower=0) for v in votes]
    score = sum(votes) / len(votes)
    if vol_control:
        vol = np.log(c).diff().rolling(30).std() * np.sqrt(365)
        score = score * (TARGET_VOL / vol).clip(upper=1.0)
    score = score.where(c.shift(max(LOOKBACKS)).notna())       # no signal until history exists
    # trade only on big changes in the target
    out, held = [], 0.0
    for x in score.fillna(0).values:
        if abs(x - held) > BUFFER or (x == 0 and held != 0):
            held = x
        out.append(held)
    return pd.Series(out, index=d.index).where(score.notna())


def main(data_dir='Data'):
    rows, trial_srs, runs = [], [], {}
    for coin in ('BTC', 'ETH', 'SOL'):
        p = q.load_csv(f'{data_dir}/{coin}_USD_1d.csv')
        perp = q.Config.coinbase_perp(contract_value_usd=CONTRACT_USD[coin], timeframe='1d')
        spot = q.Config.coinbase_spot(timeframe='1d')
        hold = q.metrics(q.backtest(p, pd.Series(1.0, index=p.index), spot), spot)
        rows.append({'coin': coin, 'variant': 'buy & hold (spot)', **hold})
        for ls in (False, True):
            for vc in (False, True):
                name = f"{'long/short' if ls else 'long only'}{', vol control' if vc else ''}"
                sig = trend_signal(p, ls, vc)
                bt = q.backtest(p, sig.fillna(0), perp)
                m = q.metrics(bt, perp)
                q.log_trial('study1_trend', {'coin': coin, 'long_short': ls, 'vol_control': vc}, m)
                trial_srs.append(m['sharpe_per_bar'])
                rows.append({'coin': coin, 'variant': name, **m})
                runs[(coin, ls, vc)] = (p, perp, bt)

    cols = ['coin', 'variant', 'sharpe', 'cagr_pct', 'max_drawdown_pct', 'longest_drawdown_days',
            'trades', 'fees_paid_pct', 'time_in_market_pct', 'n_bars']
    print(pd.DataFrame(rows)[cols].to_string(index=False))

    print('\nGATES (every variant):')
    for (coin, ls, vc), (p, cfg, bt) in runs.items():
        gates = [
            q.causal_check(p, lambda d: trend_signal(d, ls, vc)),
            q.deflated_sharpe(bt['net'], trial_srs),
            q.walk_forward(p, lambda train: {}, lambda d: trend_signal(d, ls, vc).fillna(0), cfg,
                           train_bars=365, test_bars=180),
        ]
        verdict = 'PASS ALL' if all(g['pass'] for g in gates) else 'REJECT'
        print(f"\n{coin} {'long/short' if ls else 'long only'}{' + vol control' if vc else ''}: {verdict}")
        for g in gates:
            print(f"   {'PASS' if g['pass'] else 'FAIL'}  {g['gate']:<13} {g['detail']}")


if __name__ == '__main__':
    main(*sys.argv[1:])
