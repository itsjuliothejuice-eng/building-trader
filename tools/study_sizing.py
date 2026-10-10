"""
Study 3: whole-contract rounding and minimum account size (pre-registered in docs/RESEARCH_LOG.md).

Runs the Study 2 portfolio at 2/3 size three ways: ideal fractional (reference),
CDE perps rounded to whole contracts at several account sizes, and spot (fractional,
higher fees).

    python tools/study_sizing.py
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import quantcheck as q
from study_trend import trend_signal, CONTRACT_USD
from study_portfolio import COINS, two_halves, summary, fold_report

SIZE = 2 / 3
ACCOUNTS = (1_000, 2_000, 3_000, 5_000, 10_000, 20_000, 50_000)


def rounded(target: pd.Series, step: float) -> pd.Series:
    """Round a target fraction of the half-account to whole contracts; step = one contract / half-account."""
    return (np.floor(target / step + 0.5) * step).clip(upper=1.0)   # never above 1x of the half


def main(data_dir='Data'):
    raw = {c: q.load_csv(f'{data_dir}/{c}_USD_1d.csv') for c in COINS}
    common = raw[COINS[0]].index
    for c in COINS[1:]:
        common = common.intersection(raw[c].index)
    prices = {c: d.loc[common] for c, d in raw.items()}
    cfg = q.Config(timeframe='1d')
    sig = {c: trend_signal(prices[c], False, True).fillna(0) * SIZE for c in COINS}

    perp = lambda c: q.Config.coinbase_perp(contract_value_usd=CONTRACT_USD[c], timeframe='1d')
    spot = lambda c: q.Config.coinbase_spot(timeframe='1d')
    rows = []

    def add(label, net, eq):
        s = summary(net, eq, cfg)
        f = fold_report(net)
        rows.append({'version': label, 'sharpe': s['sharpe'], 'cagr_pct': s['cagr_pct'],
                     'max_dd_pct': s['max_drawdown_pct'],
                     'folds_profitable': f"{(f['return_pct'] > 0).sum()}/{len(f)}",
                     'worst_fold_pct': f['return_pct'].min()})
        return s

    ideal = add('ideal fractional (perp fees)', *two_halves(prices, lambda c, p: sig[c], perp))
    hold = add('50/50 buy & hold (spot)', *two_halves(prices, lambda c, p: pd.Series(1.0, index=p.index), spot))
    spot_s = add('spot, fractional', *two_halves(prices, lambda c, p: sig[c], spot))

    minimum = None
    for acct in ACCOUNTS:
        steps = {c: CONTRACT_USD[c] / (acct / 2) for c in COINS}
        s = add(f'perp, ${acct:,} account', *two_halves(prices, lambda c, p: rounded(sig[c], steps[c]), perp))
        ok = s['sharpe'] >= 0.9 * ideal['sharpe'] and s['max_drawdown_pct'] >= -22
        rows[-1]['meets_rule'] = 'yes' if ok else 'no'
        if ok and minimum is None:
            minimum = acct
    print(pd.DataFrame(rows).fillna('').to_string(index=False))

    print(f"\nMinimum perp account (Sharpe within 10% of ideal and max DD no worse than -22%): "
          f"{'$' + format(minimum, ',') if minimum else 'none of the sizes tested'}")
    beats = spot_s['sharpe'] > hold['sharpe'] and spot_s['max_drawdown_pct'] > hold['max_drawdown_pct']
    print(f"Spot version beats 50/50 buy & hold on Sharpe and drawdown: {'yes' if beats else 'no'}")
    for c in COINS:
        print(f"  one {c} PERP contract = ${CONTRACT_USD[c]} = {CONTRACT_USD[c] / 1000:.0%} of a $2,000 half-account")


if __name__ == '__main__':
    main(*sys.argv[1:])
