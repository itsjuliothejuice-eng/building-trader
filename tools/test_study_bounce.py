"""Checks for the Study 5 portfolio simulator. Run: python tools/test_study_bounce.py"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import study_bounce as sb

ZERO = dict(fee=0.0, slip=0.0, funding=0.0, per_contract=0.0)
IDX = pd.date_range(sb.START, periods=6, freq='D', tz='UTC')


def frames(bars, entry_day=0, stop=90.0, target=120.0, side='long'):
    p = pd.DataFrame(bars, columns=['open', 'high', 'low', 'close'], index=IDX[:len(bars)])
    s = pd.DataFrame(index=p.index, data={'long_R': False, 'short_R': False, 'stop_long': stop, 'stop_short': stop,
                                          'target_long': target, 'target_short': target, 'adx': 30.0})
    s.loc[p.index[entry_day], f'{side}_R'] = True
    return {'X': s}, {'X': p}


def run(bars, cost=ZERO, **kw):
    sig, px = frames(bars, **kw)
    cols = ('short_R',) if kw.get('side') == 'short' else ('long_R',)
    net, tr, fees = sb.simulate(sig, px, cols, cost)
    return np.exp(net.sum()) - 1, tr, fees


flat = [100, 101, 99, 100]
# 1. stop hit: lose 1% of equity (stop 10 below a 100 entry -> 0.1 units of equity... sized to 1% risk)
r, tr, _ = run([flat, [100, 101, 89, 95], flat, flat])
assert abs(r + 0.01) < 1e-9 and tr['hit'].tolist() == ['stop'], (r, tr)
# 2. target hit: +2% (target 20 above, risk 10)
r, tr, _ = run([flat, [100, 121, 99, 110], flat, flat])
assert abs(r - 0.02) < 1e-9 and tr['hit'].tolist() == ['target'], r
# 3. both in one day -> counted as the stop
r, tr, _ = run([flat, [100, 125, 85, 100], flat, flat])
assert abs(r + 0.01) < 1e-9, r
# 4. gap below the stop on a later day -> filled at that open (worse than the stop)
r, tr, _ = run([flat, flat, [80, 82, 78, 80], flat])
assert abs(r + 0.02) < 1e-9, r
# 5. entry skipped when the next open is already past the stop
r, tr, _ = run([flat, [85, 86, 84, 85], flat, flat])
assert r == 0 and tr.empty
# 6. short side mirrors: stop at 110, target at 80
r, tr, _ = run([flat, [100, 101, 79, 90], flat, flat], side='short', stop=110.0, target=80.0)
assert abs(r - 0.02) < 1e-9, r
# 7. fees: same stop-out with 0.9% per side costs more than 1% total, but sizing includes fees -> about 1%
r, _, fees = run([flat, [100, 101, 89, 95], flat, flat], cost=dict(ZERO, fee=0.009))
assert -0.0105 < r < -0.0095 and fees > 0, r
# 8. position cap: a stop 0.5% away would mean 200% of equity; capped at 20%
calm = [100, 101, 99.6, 100]
r, _, _ = run([flat, calm, calm, calm], stop=99.5)
assert abs(r) < 1e-9
r, _, _ = run([flat, [100, 101, 99.0, 99], flat, flat], stop=99.5)
assert abs(r - 0.20 * (99.5 / 100 - 1)) < 1e-9, r

# 9. indicators are causal on random prices
rng = np.random.default_rng(0)
n = 600
c = pd.Series(100 * np.exp(np.cumsum(rng.normal(0.002, 0.03, n))), index=pd.date_range('2018-01-01', periods=n, tz='UTC'))
d = pd.DataFrame({'open': c.shift(1).fillna(100), 'close': c, 'volume': 1e5})
d['high'] = d[['open', 'close']].max(axis=1) * 1.01
d['low'] = d[['open', 'close']].min(axis=1) * 0.99
res = sb.causal({'X': d}, d, ['X'])
assert res['pass'], res
# and a planted look-ahead is caught
orig = sb.signals
sb.signals = lambda dd, b: orig(dd, b).assign(adx=dd['close'].shift(-1))
assert not sb.causal({'X': d}, d, ['X'])['pass']
sb.signals = orig
print('all 9 checks passed')
