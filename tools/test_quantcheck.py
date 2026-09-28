"""Sanity tests for quantcheck: run `python tools/test_quantcheck.py`."""
import sys
from pathlib import Path
import numpy as np
import pandas as pd
sys.path.insert(0, str(Path(__file__).parent))
import quantcheck as q


def fake_prices(n=1500, seed=0):
    rng = np.random.default_rng(seed)
    close = 100 * np.exp(np.cumsum(rng.normal(0, 0.03, n)))
    idx = pd.date_range('2020-01-01', periods=n, freq='D', tz='UTC')
    return pd.DataFrame({'open': np.r_[100, close[:-1]], 'close': close}, index=idx)


def test_costs_per_side():
    p = fake_prices(10)
    p['open'] = 100.0
    sig = pd.Series([1, 1, 0, 0, 0, 0, 0, 0, 0, 0.0], index=p.index)
    bt = q.backtest(p, sig, q.Config(fee_bps=120, slippage_bps=5))
    assert abs(bt['cost'].sum() - 2 * 0.0125) < 1e-12, bt['cost'].sum()


def test_fills_next_open():
    p = fake_prices(5)
    sig = pd.Series([1, 0, 0, 0, 0.0], index=p.index)
    bt = q.backtest(p, sig, q.Config(fee_bps=0, slippage_bps=0))
    expected = np.log(p['open'].iloc[2] / p['open'].iloc[1])  # decided bar 0, filled open of bar 1
    assert abs(bt['net'].sum() - expected) < 1e-12


def test_long_only_blocks_shorts():
    p = fake_prices(50)
    bt = q.backtest(p, pd.Series(-1.0, index=p.index), q.Config())
    assert (bt['position'] == 0).all()


def test_misaligned_signal_rejected():
    p = fake_prices(50)
    sig = pd.Series(1.0, index=p.index.tz_convert('America/Chicago').tz_localize(None))
    try:
        q.backtest(p, sig, q.Config())
    except ValueError:
        return
    raise AssertionError('misaligned signal was accepted')


def test_causal_catches_lookahead():
    p = fake_prices()
    cheat = lambda d: (d['close'].shift(-1) > d['close']).astype(float)
    honest = lambda d: (d['close'] > d['close'].rolling(20).mean()).astype(float)
    centered = lambda d: (d['close'] > d['close'].rolling(21, center=True).mean()).astype(float)
    assert not q.causal_check(p, cheat)['pass']
    assert not q.causal_check(p, centered)['pass']
    assert q.causal_check(p, honest)['pass']


def test_noise_is_rejected():
    p = fake_prices()
    cfg = q.Config()
    sharpes, best = [], None
    for w in range(5, 105, 5):
        bt = q.backtest(p, (p['close'] > p['close'].rolling(w).mean()).astype(float), cfg)
        m = q.metrics(bt, cfg)
        sharpes.append(m['sharpe_per_bar'])
        if best is None or m['sharpe_per_bar'] > best[0]:
            best = (m['sharpe_per_bar'], bt['net'])
    assert not q.deflated_sharpe(best[1], sharpes)['pass']


if __name__ == '__main__':
    for name, fn in list(globals().items()):
        if name.startswith('test_'):
            fn()
            print('ok  ', name)
    print('all tests passed')
