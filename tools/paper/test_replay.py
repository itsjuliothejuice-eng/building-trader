"""
Parity check: replay history through the paper trader one day at a time
(decide on closed candles, fill at the next day's open) and compare with the backtest.

    python tools/paper/test_replay.py            # needs Data/BTC_USD_1d.csv and Data/ETH_USD_1d.csv
"""
import sys
import tempfile
from pathlib import Path

import numpy as np
import pandas as pd

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
sys.path.insert(0, str(HERE.parent))
import paper_trader as pt
import quantcheck as q
from study_trend import trend_signal
from study_portfolio import two_halves, summary

START = '2019-01-01'


def main(data_dir='Data', kill_switch=None):
    tmp = Path(tempfile.mkdtemp())
    # Parity is checked with the kill switch off: the backtest has none. Its effect is reported separately.
    pt.KILL_SWITCH = float(kill_switch) if kill_switch else -1.0
    pt.DIR, pt.STATE = tmp, tmp / 'state.json'
    raw = {c: q.load_csv(f'{data_dir}/{c}_USD_1d.csv')[['open', 'high', 'low', 'close']] for c in pt.COINS}
    common = raw['BTC'].index.intersection(raw['ETH'].index)
    raw = {c: d.loc[common] for c, d in raw.items()}
    days = common[(common >= START)][:-1]

    st = pt.new_state()
    equity = []
    for i, day in enumerate(days):
        hist = {c: raw[c].loc[:day] for c in pt.COINS}                 # closed candles up to `day`
        nxt = common[common.get_loc(day) + 1]
        px = {c: float(raw[c].loc[nxt, 'open']) for c in pt.COINS}     # fill at next open
        pt.step(st, hist, px, verbose=False)
        equity.append((nxt, pt.equity(st, px)))
    paper = pd.Series(dict(equity))

    # backtest over the same window, same rules, spot fees, 2/3 size
    prices = {c: raw[c].loc[:] for c in pt.COINS}
    full = {c: (trend_signal(prices[c], False, True).fillna(0) * pt.SIZE) for c in pt.COINS}
    window = {c: prices[c].loc[days[0]:] for c in pt.COINS}
    net, eq = two_halves(window, lambda c, p: full[c].loc[p.index], lambda c: q.Config.coinbase_spot(timeframe='1d'))
    cfg = q.Config(timeframe='1d')
    b = summary(net, eq, cfg)

    pn = np.log(paper).diff().dropna()
    pe = paper / pt.START_CASH
    pm = summary(pn, pe.iloc[1:], cfg)
    trades = len(pd.read_csv(tmp / 'trades.csv'))
    print(f'replay {days[0].date()} to {days[-1].date()}: {len(days)} decision days, {trades} paper trades, '
          f'kill switch {pt.KILL_SWITCH:.0%}{" (fired " + str(st["last_decision_day"]) + ")" if st["halted"] else ""}\n')
    print(f"{'':12}{'Sharpe':>8}{'CAGR':>9}{'Max DD':>9}")
    print(f"{'backtest':12}{b['sharpe']:>8}{b['cagr_pct']:>8}%{b['max_drawdown_pct']:>8}%")
    print(f"{'paper bot':12}{pm['sharpe']:>8}{pm['cagr_pct']:>8}%{pm['max_drawdown_pct']:>8}%")
    ok = abs(pm['sharpe'] - b['sharpe']) <= 0.15 and abs(pm['cagr_pct'] - b['cagr_pct']) <= 3
    print('\nPARITY OK' if ok else '\nPARITY FAILED: the bot does not reproduce the backtest')
    return ok


if __name__ == '__main__':
    sys.exit(0 if main(*sys.argv[1:]) else 1)
