"""
Study 6: the approved trend rules (Study 2) on many coins (pre-registered in docs/RESEARCH_LOG.md).

    python tools/fetch_coinbase_universe.py     # once; ~400 coins into Data/universe/
    python tools/study_many_trend.py

"equal": every eligible coin gets an equal slice and runs the trend rules in it.
"top10": every 7 days hold the 10 eligible coins with the strongest trend, one slice each.
Spot fees, 2/3 size, decide at the close, trade at the next open, holdings drift and are
traded only when 10%+ of a slice off target (the paper trader's rule).
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import quantcheck as q
from study_bounce import (START, FOLDS_FROM, MIN_HISTORY, MIN_DOLLAR_VOL, PERP_CONTRACT_USD,
                          load_universe, excluded, stats, folds, paper_system)
from study_trend import trend_signal, LOOKBACKS

SIZE, DRIFT, TOP, RANK_EVERY = 2 / 3, 0.10, 10, 7
FEE = 0.009


def coin_inputs(d):
    """Trend target (0..1), momentum score and eligibility for one coin, from closed candles only."""
    c, v = d['close'], d['volume']
    return pd.DataFrame({
        'signal': trend_signal(d, False, True),
        'mom': sum(c / c.shift(n) - 1 for n in LOOKBACKS) / len(LOOKBACKS),
        'eligible': (np.arange(len(d)) + 1 >= MIN_HISTORY) & ((c * v).rolling(30).mean() >= MIN_DOLLAR_VOL),
    })


def target_weights(data, mode, cal, filter_eligible=True):
    """Target weight per coin, decided at each day's close. Rows = cal, columns = coins."""
    coins = sorted(data)
    inp = {c: coin_inputs(data[c]).reindex(cal).ffill() for c in coins}   # a skipped candle keeps yesterday's view
    sig = pd.DataFrame({c: inp[c]['signal'] for c in coins})
    mom = pd.DataFrame({c: inp[c]['mom'] for c in coins})
    elig = pd.DataFrame({c: inp[c]['eligible'] for c in coins}).fillna(False).astype(bool) if filter_eligible \
        else pd.DataFrame(True, index=cal, columns=coins)
    live = elig & sig.notna()
    if mode == 'equal':
        n = live.sum(axis=1).replace(0, np.nan)
        w = sig.fillna(0).where(live, 0).div(n, axis=0) * SIZE
        slice_ = SIZE / n
    elif mode == 'top10':
        member = pd.DataFrame(False, index=cal, columns=coins)
        current = []
        for i, day in enumerate(cal):
            if i % RANK_EVERY == 0:
                ok = live.loc[day] & (sig.loc[day] > 0)
                current = mom.loc[day][ok].nlargest(TOP).index.tolist()
            member.loc[day, current] = True
        w = sig.fillna(0).where(member & live, 0) * SIZE / TOP
        slice_ = pd.Series(SIZE / TOP, index=cal)
    elif mode == 'hold':
        n = live.sum(axis=1).replace(0, np.nan)
        w = live.astype(float).div(n, axis=0)
        slice_ = 1 / n
    return w.fillna(0.0), slice_.fillna(1.0)


def simulate(data, w, slice_, slip):
    """Units drift with prices; a coin trades at the open only when 10%+ of a slice off target."""
    coins, cal = list(w.columns), w.index
    O = np.column_stack([data[c]['open'].reindex(cal).values for c in coins])
    C = np.column_stack([data[c]['close'].reindex(cal).values for c in coins])
    W, S = w.values, slice_.values
    units, cash, last = np.zeros(len(coins)), 1.0, np.full(len(coins), np.nan)
    flow = np.zeros(len(coins))
    equity, fees, trades = [], 0.0, 0
    for t in range(len(cal)):
        if t > 0:
            px = np.where(np.isnan(O[t]), last, O[t])
            val = np.nan_to_num(units * px)
            eq = cash + val.sum()
            cur, tgt = val / eq, W[t - 1]
            need = (~np.isnan(O[t])) & ((np.abs(cur - tgt) > DRIFT * S[t - 1]) | ((tgt == 0) & (units > 0)))
            for j in sorted(np.flatnonzero(need), key=lambda j: tgt[j] - cur[j]):   # sells first
                dv = (tgt[j] - cur[j]) * eq
                if dv > 0:
                    dv = min(dv, cash / (1 + FEE + slip))
                    if dv <= 0:
                        continue
                    fill = O[t, j] * (1 + slip)
                    units[j] += dv / fill
                else:
                    fill = O[t, j] * (1 - slip)
                    sell_units = units[j] if tgt[j] == 0 else min(units[j], -dv / fill)
                    dv = -sell_units * fill
                    units[j] -= sell_units
                cost = abs(dv) * FEE
                cash -= dv + cost
                flow[j] -= dv + cost
                fees += (cost + abs(dv) * slip) / eq * 100
                trades += 1
        last = np.where(np.isnan(C[t]), last, C[t])
        equity.append(cash + np.nan_to_num(units * last).sum())
    eqs = pd.Series(equity, index=cal)
    pnl = pd.Series(flow + np.nan_to_num(units * last), index=coins)
    return np.log(eqs).diff().fillna(np.log(eqs.iloc[0])), fees, trades, pnl


def causal(data, mode, cuts=4):
    cal = pd.date_range(pd.Timestamp(START, tz='UTC'), max(d.index[-1] for d in data.values()), freq='D')
    full, _ = target_weights(data, mode, cal)
    for k in np.linspace(len(cal) // 3, len(cal) - 1, cuts).astype(int):
        cut = cal[k]
        part_data = {c: d.loc[:cut] for c, d in data.items() if d.index[0] <= cut}
        part, _ = target_weights(part_data, mode, cal[:k + 1])
        a = full.loc[:cut, part.columns]
        if not np.allclose(a.values, part.values, rtol=1e-9, atol=1e-12):
            bad = a.index[np.argwhere(~np.isclose(a.values, part.values, rtol=1e-9, atol=1e-12))[0][0]]
            return {'gate': 'CAUSAL', 'pass': False, 'detail': f'weights changed after future data added, first at {bad.date()}'}
    return {'gate': 'CAUSAL', 'pass': True, 'detail': f'{len(data)} coins: signals and rankings unchanged on truncated history'}


def run(data, mode, slip, end, filter_eligible=True):
    cal = pd.date_range(pd.Timestamp(START, tz='UTC'), end, freq='D')
    w, s = target_weights(data, mode, cal, filter_eligible)
    net, fees, trades, pnl = simulate(data, w, s, slip)
    return net, fees, trades, pnl


def main():
    data = load_universe()
    drop = excluded(data)
    list_a = {c: data[c] for c in PERP_CONTRACT_USD if c in data}
    list_b = {c: d for c, d in data.items() if c not in drop}
    paper_net = paper_system(data)
    end = min(paper_net.index[-1], data['BTC'].index[-1])
    paper_net = paper_net.loc[:end]
    paper = stats(paper_net)
    print(f'List A {len(list_a)} coins, List B {len(list_b)} coins, {START} to {end.date()}\n')

    # Engine check: the paper system itself through this engine (BTC+ETH halves, no eligibility filter)
    common = data['BTC'].index.intersection(data['ETH'].index)
    pair = {c: data[c].loc[common] for c in ('BTC', 'ETH')}
    chk_net, *_ = run(pair, 'equal', 0.0005, end, filter_eligible=False)
    chk = stats(chk_net)
    engine_ok = abs(chk['sharpe'] - paper['sharpe']) <= 0.15
    print(f"engine check: paper system via quantcheck Sharpe {paper['sharpe']}, max DD {paper['max_drawdown_pct']}%; "
          f"via this engine (with drift) Sharpe {chk['sharpe']}, max DD {chk['max_drawdown_pct']}%  "
          f"-> {'OK' if engine_ok else 'MISMATCH, results invalid'}\n")

    prior = pd.read_csv(q.TRIALS_FILE)
    prior = prior[~prior['name'].eq('study6_many_trend')].drop_duplicates(['name', 'params'], keep='last')
    trials = prior['sharpe_per_bar'].tolist()

    versions = {'A equal': (list_a, 'equal', 0.0005), 'A top 10': (list_a, 'top10', 0.0005),
                'B equal': (list_b, 'equal', 0.0010), 'B top 10': (list_b, 'top10', 0.0010)}
    runs, context = {}, {}
    for name, (coins, mode, slip) in versions.items():
        net, fees, trades, pnl = run(coins, mode, slip, end)
        m = stats(net)
        q.log_trial('study6_many_trend', {'version': name}, m)
        trials.append(m['sharpe_per_bar'])
        runs[name] = (net, fees, trades, pnl, m)
    for lst, coins, slip in (('A', list_a, 0.0005), ('B', list_b, 0.0010)):
        context[lst] = stats(run(coins, 'hold', slip, end)[0])

    yrs = len(paper_net) / 365
    print(f"{'':28}{'Sharpe':>7}{'CAGR':>8}{'MaxDD':>8}{'Trades/yr':>10}{'Fees':>7}")
    print(f"{'paper system (BTC+ETH, 2/3)':28}{paper['sharpe']:>7}{paper['cagr_pct']:>7}%{paper['max_drawdown_pct']:>7}%")
    for lst in 'AB':
        h = context[lst]
        print(f"{f'{lst} equal-weight buy & hold':28}{h['sharpe']:>7}{h['cagr_pct']:>7}%{h['max_drawdown_pct']:>7}%")
    for name, (net, fees, trades, pnl, m) in runs.items():
        print(f"{name:28}{m['sharpe']:>7}{m['cagr_pct']:>7}%{m['max_drawdown_pct']:>7}%{trades / yrs:>10.0f}{fees:>6.0f}%")
    print(f'\ntrials counted for the deflated Sharpe: {len(trials)}')

    causal_res = {(lst, mode): causal(coins, mode) for lst, coins in (('A', list_a), ('B', list_b)) for mode in ('equal', 'top10')}
    for name, (net, fees, trades, pnl, m) in runs.items():
        coins, mode, slip = versions[name]
        fr = folds(net)
        pos = int((fr['return_pct'] > 0).sum())
        gates = [
            {'gate': 'ENGINE', 'pass': engine_ok, 'detail': f"paper system reproduced within 0.15 Sharpe ({chk['sharpe']} vs {paper['sharpe']})"},
            causal_res[(name[0], mode)],
            q.deflated_sharpe(net, trials),
            {'gate': 'WALK-FORWARD', 'pass': pos / len(fr) >= 0.6 and net.loc[FOLDS_FROM:].sum() > 0,
             'detail': f"{pos}/{len(fr)} folds profitable, worst fold {fr['return_pct'].min()}%, "
                       f"total since {FOLDS_FROM[:4]} {(np.exp(net.loc[FOLDS_FROM:].sum()) - 1) * 100:.0f}%"},
            {'gate': 'BEATS PAPER', 'pass': m['sharpe'] >= paper['sharpe'] + 0.20 and m['max_drawdown_pct'] >= -27,
             'detail': f"Sharpe {m['sharpe']} vs paper {paper['sharpe']} (+0.20 needed), max DD {m['max_drawdown_pct']}% (limit -27%)"},
        ]
        print(f"\n{name}: {'PASS ALL' if all(g['pass'] for g in gates) else 'REJECT'}")
        for g in gates:
            print(f"   {'PASS' if g['pass'] else 'FAIL'}  {g['gate']:<13} {g['detail']}")
        top3 = pnl.nlargest(3).index.tolist()
        wo = stats(run({c: d for c, d in coins.items() if c not in top3}, mode, slip, end)[0])
        print(f"   best coins {', '.join(f'{c} {v * 100:+.0f}%' for c, v in pnl.nlargest(3).items())}; "
              f"worst {', '.join(f'{c} {v * 100:+.0f}%' for c, v in pnl.nsmallest(3).items())}")
        print(f"   without {', '.join(top3)}: Sharpe {wo['sharpe']}, CAGR {wo['cagr_pct']}%, max DD {wo['max_drawdown_pct']}%")
        yearly = {y: round((np.exp(net[str(y)].sum()) - 1) * 100) for y in sorted(set(net.index.year))}
        print('   by year: ' + '  '.join(f'{y} {v:+d}%' for y, v in yearly.items()))
    pyear = {y: round((np.exp(paper_net[str(y)].sum()) - 1) * 100) for y in sorted(set(paper_net.index.year))}
    print('\npaper system by year: ' + '  '.join(f'{y} {v:+d}%' for y, v in pyear.items()))


if __name__ == '__main__':
    main()
