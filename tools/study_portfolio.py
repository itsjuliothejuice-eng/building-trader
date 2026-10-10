"""
Study 2: BTC + ETH trend portfolio (pre-registered in docs/RESEARCH_LOG.md).

Two half-accounts, each running Study 1's long-only + vol-control rules on its
own coin via CDE perps. No rebalancing between halves. One new trial (13 total).

    python tools/study_portfolio.py            # needs Data/BTC_USD_1d.csv and Data/ETH_USD_1d.csv
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import quantcheck as q
from study_trend import trend_signal, CONTRACT_USD

COINS = ('BTC', 'ETH')
TRAIN, TEST = 365, 180          # same fold layout as Study 1


def two_halves(prices, signal_fn, cfg_fn):
    """Equity of two independent half-accounts -> combined per-bar log returns."""
    equity = []
    for coin in COINS:
        p = prices[coin]
        bt = q.backtest(p, signal_fn(coin, p), cfg_fn(coin))
        equity.append(0.5 * np.exp(bt['net'].cumsum()))
    total = pd.concat(equity, axis=1).sum(axis=1)
    net = np.log(total).diff().fillna(np.log(total.iloc[0]))   # first bar vs starting 1.0
    return net, total


def fold_report(net):
    rows, i = [], TRAIN
    while i + TEST <= len(net):
        seg = net.iloc[i:i + TEST]
        rows.append({'start': seg.index[0].date(), 'end': seg.index[-1].date(),
                     'return_pct': round((np.exp(seg.sum()) - 1) * 100, 1)})
        i += TEST
    return pd.DataFrame(rows)


def summary(net, total, cfg):
    per_bar = net.mean() / net.std()
    dd = total / total.cummax() - 1
    years = len(net) / cfg.bars_per_year
    return {'sharpe': round(per_bar * np.sqrt(cfg.bars_per_year), 2), 'sharpe_per_bar': per_bar,
            'cagr_pct': round((total.iloc[-1] ** (1 / years) - 1) * 100, 1),
            'max_drawdown_pct': round(dd.min() * 100, 1), 'n_bars': len(net)}


def main(data_dir='Data'):
    raw = {c: q.load_csv(f'{data_dir}/{c}_USD_1d.csv') for c in COINS}
    start = max(d.index[0] for d in raw.values())
    end = min(d.index[-1] for d in raw.values())
    # Exchanges skip some days; trade only on days both coins have a candle so the halves line up.
    common = raw[COINS[0]].loc[start:end].index
    for c in COINS[1:]:
        common = common.intersection(raw[c].index)
    prices = {c: d.loc[common] for c, d in raw.items()}
    cfg = q.Config(timeframe='1d')
    print(f'{start.date()} to {end.date()}, {len(prices["BTC"])} days\n')

    perp = lambda c: q.Config.coinbase_perp(contract_value_usd=CONTRACT_USD[c], timeframe='1d')
    spot = lambda c: q.Config.coinbase_spot(timeframe='1d')
    strat_net, strat_eq = two_halves(prices, lambda c, p: trend_signal(p, False, True).fillna(0), perp)
    hold_net, hold_eq = two_halves(prices, lambda c, p: pd.Series(1.0, index=p.index), spot)

    s, h = summary(strat_net, strat_eq, cfg), summary(hold_net, hold_eq, cfg)
    print(f"{'':22}{'Sharpe':>8}{'CAGR':>9}{'Max DD':>9}")
    print(f"{'50/50 buy & hold':22}{h['sharpe']:>8}{h['cagr_pct']:>8}%{h['max_drawdown_pct']:>8}%")
    print(f"{'50/50 trend portfolio':22}{s['sharpe']:>8}{s['cagr_pct']:>8}%{s['max_drawdown_pct']:>8}%\n")

    # Study 1's 12 logged trials + this one
    prior = pd.read_csv('experiments/trials.csv')
    # A rerun of identical rules is not a new trial: one entry per distinct variant.
    prior = prior[prior['name'] == 'study1_trend'].drop_duplicates('params', keep='last')['sharpe_per_bar'].tolist()
    q.log_trial('study2_portfolio', {'coins': list(COINS)}, s)
    trials = prior + [s['sharpe_per_bar']]

    folds = fold_report(strat_net)
    pos = int((folds['return_pct'] > 0).sum())
    wf_pass = pos / len(folds) >= 0.6 and strat_net.iloc[TRAIN:].sum() > 0
    gates = [
        {'gate': 'CAUSAL', 'pass': all(q.causal_check(prices[c], lambda d: trend_signal(d, False, True))['pass'] for c in COINS),
         'detail': 'both legs recomputed on truncated history, no change'},
        q.deflated_sharpe(strat_net, trials),
        {'gate': 'WALK-FORWARD', 'pass': wf_pass,
         'detail': f"{pos}/{len(folds)} folds profitable, worst fold {folds['return_pct'].min()}%, "
                   f"total after first year {(np.exp(strat_net.iloc[TRAIN:].sum()) - 1) * 100:.0f}%"},
        {'gate': 'BENCHMARK', 'pass': s['sharpe'] > h['sharpe'] and s['max_drawdown_pct'] > h['max_drawdown_pct'],
         'detail': f"Sharpe {s['sharpe']} vs {h['sharpe']}, max drawdown {s['max_drawdown_pct']}% vs {h['max_drawdown_pct']}%"},
    ]
    print(q.report(gates))
    print('\nfolds:\n' + folds.to_string(index=False))

    print('\nyear by year:')
    for yr in sorted(set(strat_net.index.year)):
        a, b = strat_net[str(yr)], hold_net[str(yr)]
        ea, eb = strat_eq[str(yr)], hold_eq[str(yr)]
        print(f"  {yr}: trend {100 * (np.exp(a.sum()) - 1):7.1f}% (worst dip {100 * (ea / ea.cummax() - 1).min():6.1f}%)"
              f"   hold {100 * (np.exp(b.sum()) - 1):7.1f}% (worst dip {100 * (eb / eb.cummax() - 1).min():6.1f}%)")


if __name__ == '__main__':
    main(*sys.argv[1:])
