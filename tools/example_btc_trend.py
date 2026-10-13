"""
Worked example: run one classic idea through all three gates.

Hypothesis (mechanism, not pattern): crypto trends persist because news
spreads slowly and late buyers chase price, so holding BTC only while it's
above its N-day average should avoid the worst crashes while keeping most
of the gains. The counterparty is the late momentum chaser and the panic seller.

    python tools/fetch_coinbase_ohlcv.py BTC/USD 1d --start 2016-01-01
    python tools/example_btc_trend.py
"""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).parent))
import quantcheck as q

WINDOWS = list(range(20, 220, 10))   # every variation we try gets counted


def signal(d, window=100):
    return (d['close'] > d['close'].rolling(window).mean()).astype(float)


def fit(train):
    cfg = q.Config()
    return {'window': max(WINDOWS, key=lambda w: q.metrics(q.backtest(train, signal(train, w), cfg), cfg).get('sharpe', -9))}


def main(path='Data/BTC_USD_1d.csv'):
    p = q.load_csv(path)
    cfg = q.Config(timeframe='1d')
    print(f"{len(p)} daily bars {p.index[0].date()} to {p.index[-1].date()}, fees {cfg.fee_bps} bps/side\n")

    sharpes, best = [], None
    for w in WINDOWS:
        bt = q.backtest(p, signal(p, w), cfg)
        m = q.metrics(bt, cfg)
        q.log_trial('btc_trend_sma', {'window': w}, m)
        sharpes.append(m['sharpe_per_bar'])
        if best is None or m['sharpe'] > best[1]['sharpe']:
            best = (w, m, bt)

    hold = q.metrics(q.backtest(p, pd.Series(1.0, index=p.index), cfg), cfg)
    keys = ['sharpe', 'cagr_pct', 'max_drawdown_pct', 'longest_drawdown_days', 'trades', 'fees_paid_pct']
    print('buy & hold      ', {k: hold[k] for k in keys})
    print(f'best SMA {best[0]:<6} ', {k: best[1][k] for k in keys}, '\n')

    gates = [
        q.causal_check(p, lambda d: signal(d, best[0])),
        q.deflated_sharpe(best[2]['net'], sharpes),
        q.walk_forward(p, fit, signal, cfg, train_bars=730, test_bars=180),
    ]
    print(q.report(gates))
    print('\nwalk-forward folds:\n', gates[2]['folds'].to_string(index=False))


if __name__ == '__main__':
    main(*sys.argv[1:])
