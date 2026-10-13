"""
Study 4: daily-trading rules on BTC and ETH CDE perps (pre-registered in docs/RESEARCH_LOG.md).

    python tools/study_daily.py          # needs Data/BTC_USD_1d.csv and Data/ETH_USD_1d.csv
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import quantcheck as q
from study_trend import CONTRACT_USD


def fade_big_moves(d):
    r = d['close'].pct_change()
    typical = r.rolling(30).std()
    sig = pd.Series(0.0, index=d.index)
    sig[r > typical] = -1.0
    sig[r < -typical] = 1.0
    return sig.where(typical.notna())


def daily_breakout(d):
    hi = d['high'].rolling(20).max().shift(1)
    lo = d['low'].rolling(20).min().shift(1)
    sig = pd.Series(0.0, index=d.index)
    sig[d['close'] > hi] = 1.0
    sig[d['close'] < lo] = -1.0
    return sig.where(hi.notna())


def follow_yesterday(d):
    r = d['close'].pct_change()
    return np.sign(r).where(r.notna())


RULES = {'A. fade big moves': fade_big_moves, 'B. daily breakout': daily_breakout, 'C. follow yesterday': follow_yesterday}


def main(data_dir='Data'):
    prior = pd.read_csv('experiments/trials.csv')
    prior = prior[prior['name'].isin(['study1_trend', 'study2_portfolio'])].drop_duplicates(['name', 'params'], keep='last')
    trial_srs = prior['sharpe_per_bar'].tolist()

    runs, rows = {}, []
    for coin in ('BTC', 'ETH'):
        p = q.load_csv(f'{data_dir}/{coin}_USD_1d.csv')
        perp = q.Config.coinbase_perp(contract_value_usd=CONTRACT_USD[coin], timeframe='1d')
        spot = q.Config.coinbase_spot(timeframe='1d')
        hold = q.metrics(q.backtest(p, pd.Series(1.0, index=p.index), spot), spot)
        rows.append({'coin': coin, 'rule': 'buy & hold (spot)', **hold, 'trades_per_year': 0})
        for name, fn in RULES.items():
            bt = q.backtest(p, fn(p).fillna(0), perp)
            m = q.metrics(bt, perp)
            q.log_trial('study4_daily', {'coin': coin, 'rule': name}, m)
            trial_srs.append(m['sharpe_per_bar'])
            rows.append({'coin': coin, 'rule': name, **m, 'trades_per_year': round(m['trades'] / (m['n_bars'] / 365))})
            runs[(coin, name)] = (p, perp, bt, m, hold)

    cols = ['coin', 'rule', 'sharpe', 'cagr_pct', 'max_drawdown_pct', 'fees_paid_pct', 'trades_per_year', 'time_in_market_pct']
    print(pd.DataFrame(rows)[cols].to_string(index=False))
    print(f'\ntrials counted for the deflated Sharpe: {len(trial_srs)}')

    for (coin, name), (p, cfg, bt, m, hold) in runs.items():
        fn = RULES[name]
        gates = [
            q.causal_check(p, fn),
            q.deflated_sharpe(bt['net'], trial_srs),
            q.walk_forward(p, lambda train: {}, lambda d: fn(d).fillna(0), cfg, train_bars=365, test_bars=180),
            {'gate': 'BENCHMARK', 'pass': m['sharpe'] > hold['sharpe'] and m['max_drawdown_pct'] > hold['max_drawdown_pct'],
             'detail': f"Sharpe {m['sharpe']} vs hold {hold['sharpe']}, max DD {m['max_drawdown_pct']}% vs {hold['max_drawdown_pct']}%"},
        ]
        print(f"\n{coin} {name}: {'PASS ALL' if all(g['pass'] for g in gates) else 'REJECT'}")
        for g in gates:
            print(f"   {'PASS' if g['pass'] else 'FAIL'}  {g['gate']:<13} {g['detail']}")


if __name__ == '__main__':
    main(*sys.argv[1:])
