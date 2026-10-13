"""
Study 5: Simon Ree's Bounce 2.0 on many coins (pre-registered in docs/RESEARCH_LOG.md).

    python tools/fetch_coinbase_universe.py     # once; ~400 coins into Data/universe/
    python tools/study_bounce.py

List A: the 24 coins with Coinbase CDE perps (perp fees, long only and long/short).
List B: every Coinbase USD spot coin except stablecoins and pegged tokens (spot fees, long only).
Each version is a portfolio: 1% risk per trade, max 20% per coin, never more than 100% invested.
Decisions use closed daily candles; entries fill at the next open; stops and targets fill intraday.
"""
import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).parent))
import quantcheck as q
from study_portfolio import two_halves
from study_trend import trend_signal

UNIVERSE = 'Data/universe'
START, FOLDS_FROM, FOLD = '2017-01-01', '2018-01-01', 180
RISK, MAX_COIN, MIN_ROOM = 0.01, 0.20, 0.02
MIN_HISTORY, MIN_DOLLAR_VOL = 365, 1e6

# One CDE perp contract in USD, from Coinbase 2026-10-08 (price x contract size)
PERP_CONTRACT_USD = {
    'AAVE': 855, 'ADA': 249, 'AVAX': 106, 'BCH': 297, 'BNB': 755, 'BTC': 825, 'DOGE': 437, 'DOT': 111,
    'ENA': 1086, 'ETH': 253, 'HBAR': 472, 'HYPE': 862, 'LINK': 650, 'LTC': 323, 'NEAR': 2516, 'ONDO': 497,
    'PAXG': 4128, 'PEPE': 403, 'SHIB': 54, 'SOL': 563, 'SUI': 552, 'XLM': 993, 'XRP': 702, 'ZEC': 1212}

PERP = dict(fee=0.0010, slip=0.0005, funding=0.0001, per_contract=0.12)
SPOT = dict(fee=0.0090, slip=0.0010, funding=0.0, per_contract=0.0)

# Pegged by design (gold); stablecoins and wrapped/staked BTC/ETH/SOL are found from prices in excluded()
GOLD = {'PAXG', 'XAUT'}


# ------------------------------------------------------------------ indicators

def ema(x, n):
    return x.ewm(span=n, adjust=False).mean()


def wilder(x, n):
    return x.ewm(alpha=1 / n, adjust=False).mean()


def signals(d, btc_close):
    """Per-coin signal frame from closed candles only. btc_close: BTC closes on any calendar."""
    o, h, l, c, v = (d[k] for k in ('open', 'high', 'low', 'close', 'volume'))
    e8, e21, e34, e55, e89 = (ema(c, n) for n in (8, 21, 34, 55, 89))
    pc = c.shift(1)
    tr = pd.concat([h - l, (h - pc).abs(), (l - pc).abs()], axis=1).max(axis=1)
    atr = wilder(tr, 14)
    up, dn = h.diff(), -l.diff()
    pdm = up.where((up > dn) & (up > 0), 0.0)
    mdm = dn.where((dn > up) & (dn > 0), 0.0)
    tr13 = wilder(tr, 13)
    pdi, mdi = 100 * wilder(pdm, 13) / tr13, 100 * wilder(mdm, 13) / tr13
    adx = wilder(100 * (pdi - mdi).abs() / (pdi + mdi).replace(0, np.nan), 13)
    ll8, hh8 = l.rolling(8).min(), h.rolling(8).max()
    stoch = (100 * (c - ll8) / (hh8 - ll8).replace(0, np.nan)).rolling(3).mean()
    dc = c.diff()
    rsi = 100 - 100 / (1 + wilder(dc.clip(lower=0), 2) / wilder(-dc.clip(upper=0), 2).replace(0, np.nan))

    btc = btc_close.reindex(btc_close.index.union(d.index)).ffill()
    btc_up = (btc > btc.rolling(200).mean()).reindex(d.index)
    btc_dn = (btc < btc.rolling(200).mean()).reindex(d.index)

    # high of the lowest-low candle (and low of the highest-high candle) among the previous 4 days
    hv, lv = h.values, l.values
    lo_hi, hi_lo = np.full(len(d), np.nan), np.full(len(d), np.nan)
    for t in range(4, len(d)):
        w = slice(t - 4, t)
        lo_hi[t] = hv[w][np.argmin(lv[w])]
        hi_lo[t] = lv[w][np.argmax(hv[w])]

    eligible = (np.arange(len(d)) + 1 >= MIN_HISTORY) & ((c * v).rolling(30).mean() >= MIN_DOLLAR_VOL)
    trend_up = (e8 > e21) & (e21 > e34) & (e34 > e55) & (e55 > e89) & (adx >= 20) & \
               ((e34 > e89).astype(float).rolling(84).min() == 1)
    trend_dn = (e8 < e21) & (e21 < e34) & (e34 < e55) & (e55 < e89) & (adx >= 20) & \
               ((e34 < e89).astype(float).rolling(84).min() == 1)
    armed_up = ((stoch <= 40) & (l <= e21 + atr) & (c >= e21 - atr)).astype(float).rolling(5).max() == 1
    armed_dn = ((stoch >= 60) & (h >= e21 - atr) & (c <= e21 + atr)).astype(float).rolling(5).max() == 1
    base_up = eligible & trend_up & armed_up & btc_up
    base_dn = eligible & trend_dn & armed_dn & btc_dn
    return pd.DataFrame({
        'long_R': base_up & (rsi.shift(1) < 10) & (rsi >= 10),
        'long_H': base_up & (c > lo_hi),
        'short_R': base_dn & (rsi.shift(1) > 90) & (rsi <= 90),
        'short_H': base_dn & (c < hi_lo),
        'stop_long': l.rolling(5).min(), 'stop_short': h.rolling(5).max(),
        'target_long': e21 + 2 * atr, 'target_short': e21 - 2 * atr,
        'adx': adx, 'eligible': eligible,
    })


# ------------------------------------------------------------------ universe

def load_universe():
    data = {}
    for f in sorted(Path(UNIVERSE).glob('*_USD_1d.csv')):
        if f.stat().st_size < 100:               # listed, but no candles yet
            continue
        d = q.load_csv(str(f))
        d = d[~d.index.duplicated()]
        if len(d) >= MIN_HISTORY and (d[['open', 'high', 'low', 'close']] > 0).all().all():
            data[f.name.split('_')[0]] = d
    return data


def excluded(data):
    """Stablecoins (median price within 3% of $1 over the last year) and tokens pegged to BTC/ETH/SOL
    (price ratio to one of them varies < 5%), plus gold tokens."""
    out = {}
    for coin, d in data.items():
        c = d['close'].iloc[-365:]
        if (c / 1 - 1).abs().median() < 0.03 or 0.8 < c.median() < 1.25 and c.std() / c.mean() < 0.05:
            out[coin] = 'stablecoin'
        elif coin in GOLD:
            out[coin] = 'gold token'
        else:
            for ref in ('BTC', 'ETH', 'SOL'):
                if coin != ref and ref in data:
                    r = (c / data[ref]['close']).dropna()
                    if len(r) > 100 and r.std() / r.mean() < 0.05:
                        out[coin] = f'pegged to {ref}'
    return out


# ------------------------------------------------------------------ portfolio simulation

def simulate(sig, prices, cols, cost, contract_usd=None):
    """
    sig: {coin: signal frame}; prices: {coin: OHLC}; cols: which signal columns, e.g. ('long_R',) or
    ('long_R', 'short_R'). Returns (daily log returns, trades DataFrame, fees as % of equity summed).
    """
    coins = sorted(sig)
    cal = pd.date_range(pd.Timestamp(START, tz='UTC'), max(p.index[-1] for p in prices.values()), freq='D')
    A = lambda df, k: np.column_stack([df[c][k].reindex(cal).values for c in coins])
    O, H, L, C = (A(prices, k) for k in ('open', 'high', 'low', 'close'))
    S = {k: A(sig, k).astype(float) for k in ('stop_long', 'stop_short', 'target_long', 'target_short', 'adx')}
    want = {k: np.nan_to_num(A(sig, k).astype(float)) > 0 for k in cols}
    fee_side = {c: cost['fee'] + (cost['per_contract'] / contract_usd[c] if contract_usd else 0) for c in coins}

    cash, pos, pending, last = 1.0, {}, [], np.full(len(coins), np.nan)
    equity, trades, fees_pct = [], [], 0.0
    eq = 1.0
    for t in range(len(cal)):
        # 1. entries decided at yesterday's close, at today's open
        for adx, j, side, stop, tgt in sorted(pending, reverse=True):
            o = O[t, j]
            if np.isnan(o) or (side == 1 and not stop < o < tgt) or (side == -1 and not tgt < o < stop):
                continue
            fee = fee_side[coins[j]]
            fill = o * (1 + side * cost['slip'])
            units = RISK * eq / (abs(fill - stop) + fill * 2 * fee)
            gross = sum(p['units'] * last[k] for k, p in pos.items())
            cap = min(MAX_COIN * eq, eq - gross)
            if cap < MIN_ROOM * eq:
                continue
            units = min(units, cap / fill)
            cash -= side * units * fill + units * fill * fee
            fees_pct += units * (fill * fee + o * cost['slip']) / eq * 100
            pos[j] = dict(side=side, units=units, stop=stop, target=tgt, entry=fill, day=cal[t], risk=RISK * eq)
            last[j] = o
        pending = []
        # 2. stops and targets during the day (both hit -> stop)
        for j, p in list(pos.items()):
            o, h, l = O[t, j], H[t, j], L[t, j]
            if np.isnan(o):
                continue
            s, st, tg = p['side'], p['stop'], p['target']
            if s == 1:
                px, why = (o, 'stop') if o <= st else (st, 'stop') if l <= st else \
                          (o, 'target') if o >= tg else (tg, 'target') if h >= tg else (None, None)
            else:
                px, why = (o, 'stop') if o >= st else (st, 'stop') if h >= st else \
                          (o, 'target') if o <= tg else (tg, 'target') if l <= tg else (None, None)
            if px is None:
                continue
            fee = fee_side[coins[j]]
            fill = px * (1 - s * cost['slip'])
            cash += s * p['units'] * fill - p['units'] * fill * fee
            fees_pct += p['units'] * (fill * fee + px * cost['slip']) / eq * 100
            pnl = s * p['units'] * (fill - p['entry']) - p['units'] * (fill + p['entry']) * fee
            trades.append(dict(coin=coins[j], side='long' if s == 1 else 'short', entry_day=p['day'], exit_day=cal[t],
                               r=pnl / p['risk'], pnl_pct=pnl / eq * 100, hit=why))
            del pos[j]
        # 3. funding on open positions, then mark at the close
        for j, p in pos.items():
            if not np.isnan(C[t, j]):
                cash -= p['units'] * C[t, j] * cost['funding']
                fees_pct += p['units'] * C[t, j] * cost['funding'] / eq * 100
        last = np.where(np.isnan(C[t]), last, C[t])
        eq = cash + sum(p['side'] * p['units'] * last[j] for j, p in pos.items())
        equity.append(eq)
        # 4. new signals at today's close
        for k in cols:
            side = 1 if k.startswith('long') else -1
            for j in np.flatnonzero(want[k][t]):
                if j not in pos:
                    which = 'long' if side == 1 else 'short'
                    pending.append((S['adx'][t, j], j, side, S[f'stop_{which}'][t, j], S[f'target_{which}'][t, j]))
    eqs = pd.Series(equity, index=cal)
    net = np.log(eqs).diff().fillna(np.log(eqs.iloc[0]))
    return net, pd.DataFrame(trades), fees_pct


def stats(net):
    eq = np.exp(net.cumsum())
    years = len(net) / 365
    return {'sharpe': round(net.mean() / net.std() * np.sqrt(365), 2) if net.std() > 0 else 0.0,
            'sharpe_per_bar': net.mean() / net.std() if net.std() > 0 else 0.0,
            'cagr_pct': round((eq.iloc[-1] ** (1 / years) - 1) * 100, 1),
            'max_drawdown_pct': round((eq / eq.cummax() - 1).min() * 100, 1), 'n_bars': len(net)}


def folds(net):
    rows, s = [], net.loc[FOLDS_FROM:]
    for i in range(0, len(s) - FOLD + 1, FOLD):
        seg = s.iloc[i:i + FOLD]
        rows.append({'start': seg.index[0].date(), 'end': seg.index[-1].date(),
                     'return_pct': round((np.exp(seg.sum()) - 1) * 100, 1)})
    return pd.DataFrame(rows)


def causal(data, btc, coins, cuts=4):
    """Every coin's signal frame must be identical when recomputed on truncated history (BTC truncated too)."""
    bad = []
    for coin in coins:
        d = data[coin]
        full = signals(d, btc['close'])
        for k in np.linspace(len(d) // 3, len(d) - 1, cuts).astype(int):
            cut = d.index[k - 1]
            part = signals(d.iloc[:k], btc['close'].loc[:cut])
            a = full.iloc[:k].astype(float)
            b = part.astype(float)
            same = np.isclose(a.values, b.values, equal_nan=True, rtol=1e-9, atol=0)
            if not same.all():
                bad.append(f'{coin} at {a.index[np.argwhere(~same)[0][0]].date()}')
                break
    return {'gate': 'CAUSAL', 'pass': not bad,
            'detail': f'{len(coins)} coins unchanged on truncated history' if not bad else f'look-ahead in {bad[:3]}'}


def paper_system(data):
    """The approved paper system (Study 2 rules, 2/3 size, spot fees) on the same dates."""
    common = data['BTC'].index.intersection(data['ETH'].index)
    prices = {c: data[c].loc[common] for c in ('BTC', 'ETH')}
    net, _ = two_halves(prices, lambda c, p: trend_signal(p, False, True).fillna(0) * 2 / 3,
                        lambda c: q.Config.coinbase_spot(timeframe='1d'))
    return net.loc[START:]


def main():
    data = load_universe()
    btc = data['BTC']
    drop = excluded(data)
    list_a = sorted(c for c in PERP_CONTRACT_USD if c in data)
    missing_a = sorted(set(PERP_CONTRACT_USD) - set(data))
    list_b = sorted(c for c in data if c not in drop)
    print(f'List A: {len(list_a)} perp coins with Coinbase spot history' + (f' (missing: {", ".join(missing_a)})' if missing_a else ''))
    print(f'List B: {len(list_b)} spot coins with 365+ days of history; excluded {len(drop)}: '
          + ', '.join(f'{c} ({why})' for c, why in sorted(drop.items())))

    sig = {c: signals(data[c], btc['close']) for c in set(list_a) | set(list_b)}
    paper = stats(paper_system(data))
    end = min(paper_system(data).index[-1], btc.index[-1])

    prior = pd.read_csv(q.TRIALS_FILE)
    prior = prior[~prior['name'].eq('study5_bounce')].drop_duplicates(['name', 'params'], keep='last')
    trials = prior['sharpe_per_bar'].tolist()

    versions = {
        'A long only, R':      (list_a, ('long_R',), PERP),
        'A long only, H':      (list_a, ('long_H',), PERP),
        'A long+short, R':     (list_a, ('long_R', 'short_R'), PERP),
        'A long+short, H':     (list_a, ('long_H', 'short_H'), PERP),
        'B spot long only, R': (list_b, ('long_R',), SPOT),
        'B spot long only, H': (list_b, ('long_H',), SPOT),
    }
    runs = {}
    for name, (coins, cols, cost) in versions.items():
        net, tr, fees = simulate({c: sig[c] for c in coins}, {c: data[c] for c in coins}, cols, cost,
                                 PERP_CONTRACT_USD if cost is PERP else None)
        net = net.loc[:end]
        m = stats(net)
        q.log_trial('study5_bounce', {'version': name}, m)
        trials.append(m['sharpe_per_bar'])
        runs[name] = (net, tr, fees, m, coins, cols, cost)

    print(f"\n{'':22}{'Sharpe':>7}{'CAGR':>8}{'MaxDD':>8}{'Trades/yr':>10}{'Win':>6}{'Avg R':>7}{'Fees':>7}")
    print(f"{'paper system (2/3)':22}{paper['sharpe']:>7}{paper['cagr_pct']:>7}%{paper['max_drawdown_pct']:>7}%")
    for name, (net, tr, fees, m, *_ ) in runs.items():
        yrs = len(net) / 365
        print(f"{name:22}{m['sharpe']:>7}{m['cagr_pct']:>7}%{m['max_drawdown_pct']:>7}%{len(tr) / yrs:>10.0f}"
              f"{(tr['r'] > 0).mean() * 100 if len(tr) else 0:>5.0f}%{tr['r'].mean() if len(tr) else 0:>7.2f}{fees:>6.0f}%")
    print(f'\ntrials counted for the deflated Sharpe: {len(trials)}')

    causal_a = causal(data, btc, list_a)
    causal_b = causal(data, btc, list_b)
    for name, (net, tr, fees, m, coins, cols, cost) in runs.items():
        fr = folds(net)
        pos = int((fr['return_pct'] > 0).sum())
        gates = [
            causal_a if name.startswith('A') else causal_b,
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
        if len(tr):
            by_coin = tr.groupby('coin')['pnl_pct'].sum().sort_values()
            top3 = by_coin.index[-3:].tolist()
            net_wo, *_ = simulate({c: sig[c] for c in coins if c not in top3},
                                  {c: data[c] for c in coins if c not in top3}, cols, cost,
                                  PERP_CONTRACT_USD if cost is PERP else None)
            print(f"   stops {(tr['hit'] == 'stop').mean() * 100:.0f}% / targets {(tr['hit'] == 'target').mean() * 100:.0f}%; "
                  f"avg win {tr.loc[tr['r'] > 0, 'r'].mean():.2f}R, avg loss {tr.loc[tr['r'] <= 0, 'r'].mean():.2f}R")
            print(f"   best coins {', '.join(f'{c} {v:+.0f}%' for c, v in by_coin.iloc[::-1].head(3).items())}; "
                  f"worst {', '.join(f'{c} {v:+.0f}%' for c, v in by_coin.head(3).items())}")
            print(f"   without {', '.join(top3)}: Sharpe {stats(net_wo.loc[:end])['sharpe']}, CAGR {stats(net_wo.loc[:end])['cagr_pct']}%")
            yearly = {y: round((np.exp(net[str(y)].sum()) - 1) * 100) for y in sorted(set(net.index.year))}
            print('   by year: ' + '  '.join(f'{y} {v:+d}%' for y, v in yearly.items()))

    # Diagnostic (not a trial): could a $5,000 account take List A's signals in whole contracts?
    print('\n$5,000 account, whole perp contracts (diagnostic):')
    for name in ('A long only, H', 'A long only, R'):
        tr = runs[name][1]
        if len(tr):
            ok = tr['coin'].map(lambda c: PERP_CONTRACT_USD[c] <= MAX_COIN * 5000)
            print(f'   {name}: {ok.mean() * 100:.0f}% of trades are in coins whose single contract fits the $1,000 '
                  f'per-coin cap ({", ".join(sorted(c for c in PERP_CONTRACT_USD if PERP_CONTRACT_USD[c] > 1000))} never fit)')


if __name__ == '__main__':
    main()
