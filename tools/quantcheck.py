"""
quantcheck: honest backtesting and validation for Coinbase spot strategies.

Every strategy must pass three gates before any real money:
  1. CAUSAL      the signal gives the same answer with future bars removed
                 (catches look-ahead and repainting indicators)
  2. DEFLATED    the best Sharpe beats what luck alone would produce, given
                 how many variations were tried (Bailey & Lopez de Prado 2014)
  3. WALK-FORWARD it makes money on data it was never fitted to, in most folds

Adapted from a widely shared article's design, with its bugs fixed:
- fills happen at the NEXT bar's open, not the close you just saw
- fees are per side and default to Coinbase's lowest tier (1.20% taker)
- long only (a Coinbase spot account can't short)
- bars per year come from the timeframe (4h = 2190, not 365)
- walk-forward works with short test windows and keeps indicator history
- the deflated Sharpe uses per-bar units and the spread of your real trials

Known simplification: between target changes, exposure is held exactly at target (free daily
rebalancing). A real account drifts. tools/paper/test_replay.py is the realistic check.

Price input: DataFrame with UTC DatetimeIndex and 'open' and 'close' columns,
e.g. from tools/fetch_coinbase_ohlcv.py:
    df = load_csv('Data/BTC_USD_1d.csv')
"""

from dataclasses import dataclass
from pathlib import Path
import csv
import json

import numpy as np
import pandas as pd

BARS_PER_YEAR = {'1m': 525_600, '5m': 105_120, '15m': 35_040, '30m': 17_520,
                 '1h': 8_760, '2h': 4_380, '4h': 2_190, '6h': 1_460, '1d': 365}
EULER = 0.5772156649
TRIALS_FILE = Path('experiments/trials.csv')


@dataclass
class Config:
    timeframe: str = '1d'
    initial_capital: float = 1_000.0
    fee_bps: float = 90.0       # PER SIDE. Coinbase spot taker, Intro tier (maker 50). User's fee screen 2026-09-30.
    slippage_bps: float = 5.0   # per side, on top of the fee
    long_only: bool = True      # spot cannot short; CDE perps/futures can
    leverage: float = 1.0       # max |position| as a multiple of equity
    funding_bps_per_day: float = 0.0   # perps: average funding paid on open positions

    @property
    def bars_per_year(self) -> int:
        return BARS_PER_YEAR[self.timeframe]

    @classmethod
    def coinbase_spot(cls, **kw):
        return cls(**kw)

    @classmethod
    def coinbase_perp(cls, contract_value_usd: float, fee_bps: float = 10.0, per_contract_usd: float = 0.12,
                      leverage: float = 1.0, funding_bps_per_day: float = 1.0, **kw):
        """
        Coinbase Derivatives (CDE) perp or monthly future: shorting allowed.
        Fees from the user's Intro tier (2026-09-30): 0.10% taker per side (maker 0.095%)
        plus $0.12 per contract per side, which is folded in using contract_value_usd
        (e.g. BTC PERP 0.01 BTC ~ $840). Funding is charged hourly; the 1 bp/day default
        is a placeholder, so check the product's recent funding.
        Keep leverage low: a 1/leverage move against you wipes the position.
        """
        per_side = fee_bps + per_contract_usd / contract_value_usd * 1e4
        return cls(fee_bps=per_side, long_only=False, leverage=leverage,
                   funding_bps_per_day=funding_bps_per_day, **kw)


def load_csv(path: str) -> pd.DataFrame:
    df = pd.read_csv(path, parse_dates=['timestamp'], index_col='timestamp')
    df.index = df.index.tz_localize('UTC') if df.index.tz is None else df.index.tz_convert('UTC')
    return df.sort_index()


def _check_alignment(prices: pd.DataFrame, signal: pd.Series):
    if prices.index.tz is None or str(prices.index.tz) != 'UTC':
        raise ValueError('prices index must be UTC (use load_csv)')
    if not prices.index.is_monotonic_increasing or prices.index.has_duplicates:
        raise ValueError('prices index must be sorted with no duplicates')
    if not signal.index.equals(prices.index):
        raise ValueError('signal index must match prices index exactly (timezone or bar misalignment)')


# --------------------------------------------------------------- backtest

def backtest(prices: pd.DataFrame, signal: pd.Series, cfg: Config) -> pd.DataFrame:
    """
    signal[t] = target position (0..1, or -1..1 if long_only=False), decided
    from data up to and including bar t's close. It is filled at bar t+1's
    OPEN and earns open-to-open returns from there.
    """
    _check_alignment(prices, signal)
    lo = 0.0 if cfg.long_only else -cfg.leverage
    position = signal.shift(1).fillna(0).clip(lo, cfg.leverage)   # held from open of bar t
    ret = prices['open'].shift(-1) / prices['open'] - 1           # open t -> open t+1
    turnover = position.diff().abs().fillna(position.abs())
    cost = turnover * (cfg.fee_bps + cfg.slippage_bps) / 1e4
    cost = cost + position.abs() * cfg.funding_bps_per_day / 1e4 * 365 / cfg.bars_per_year
    # Worst move against the position inside the bar (needs high/low); a leveraged
    # position that loses everything inside a bar is liquidated, not recovered.
    if {'high', 'low'} <= set(prices.columns):
        adverse = np.where(position > 0, prices['low'] / prices['open'] - 1,
                           np.where(position < 0, 1 - prices['high'] / prices['open'], 0.0))
        intrabar = position.abs() * np.minimum(adverse, 0)
    else:
        intrabar = pd.Series(0.0, index=prices.index)
    simple = (position * ret - cost).clip(lower=-0.999999)
    net = np.log1p(simple).iloc[:-1]                              # last bar has no next open
    out = pd.DataFrame({'position': position, 'turnover': turnover, 'cost': cost,
                        'intrabar_worst': intrabar}).iloc[:-1]
    out['net'] = net
    if (out['intrabar_worst'] <= -1).any():                       # account wiped inside a bar
        wipe = out.index[(out['intrabar_worst'] <= -1).argmax()]
        out.loc[wipe:, 'net'] = 0.0
        out.loc[wipe, 'net'] = np.log(1e-6)
    out['equity'] = cfg.initial_capital * np.exp(net.cumsum())
    return out


def metrics(bt: pd.DataFrame, cfg: Config) -> dict:
    r = bt['net']
    if len(r) < 30:
        return {'error': 'insufficient_data', 'n_bars': len(r)}
    per_bar_sr = r.mean() / r.std() if r.std() > 0 else 0.0
    equity = np.exp(r.cumsum())
    dd = equity / equity.cummax() - 1
    under = (dd < 0).astype(int)
    longest = int(under.groupby((under != under.shift()).cumsum()).sum().max())
    years = len(r) / cfg.bars_per_year
    trades = int((bt['turnover'] > 0).sum())
    out = {
        'sharpe': round(per_bar_sr * np.sqrt(cfg.bars_per_year), 2),
        'sharpe_per_bar': per_bar_sr,
        'total_return_pct': round((np.exp(r.sum()) - 1) * 100, 1),
        'cagr_pct': round((np.exp(r.sum() / years) - 1) * 100, 1),
        'max_drawdown_pct': round(dd.min() * 100, 1),
        'longest_drawdown_days': round(longest * 365 / cfg.bars_per_year, 1),
        'fees_paid_pct': round(bt['cost'].sum() * 100, 1),
        'trades': trades,
        'time_in_market_pct': round((bt['position'] != 0).mean() * 100, 1),
        'worst_intrabar_loss_pct': round(bt['intrabar_worst'].min() * 100, 1),
        'liquidated': bool((bt['intrabar_worst'] <= -1).any()),
        'n_bars': len(r),
    }
    return {k: v if isinstance(v, int) else float(v) for k, v in out.items()}


# ------------------------------------------------------------ gate 1: causal

def causal_check(prices: pd.DataFrame, signal_fn, n_cuts: int = 5) -> dict:
    """
    Recompute the signal on truncated history. If any bar's signal changes
    once later data is added, the signal peeks into the future.
    """
    full = signal_fn(prices)
    start = len(prices) // 3
    bad = []
    for k in np.linspace(start, len(prices) - 1, n_cuts).astype(int):
        part = signal_fn(prices.iloc[:k])
        a, b = full.iloc[:k], part
        diff = ~((a == b) | (a.isna() & b.isna()))
        if diff.any():
            bad.append(str(diff[diff].index[0]))
    return {'gate': 'CAUSAL', 'pass': not bad,
            'detail': 'no look-ahead found' if not bad else f'signal changed after future data added, first at {bad[0]}'}


# --------------------------------------------------------- gate 2: deflated

def log_trial(name: str, params: dict, m: dict):
    """Record EVERY variation you backtest. The deflated Sharpe reads this file."""
    TRIALS_FILE.parent.mkdir(parents=True, exist_ok=True)
    new = not TRIALS_FILE.exists()
    with TRIALS_FILE.open('a', newline='') as f:
        w = csv.writer(f)
        if new:
            w.writerow(['name', 'params', 'sharpe_per_bar', 'sharpe', 'n_bars'])
        w.writerow([name, json.dumps(params, sort_keys=True), m['sharpe_per_bar'], m['sharpe'], m['n_bars']])


def deflated_sharpe(best_returns: pd.Series, trial_sharpes_per_bar=None, n_trials: int = None) -> dict:
    """
    best_returns: per-bar net returns of the strategy you want to trade.
    trial_sharpes_per_bar: per-bar Sharpe of EVERY variation tried (from
    experiments/trials.csv). If omitted, pass n_trials and noise spread is
    assumed to be 1/sqrt(T).
    """
    r = best_returns.dropna()
    T = len(r)
    sr = r.mean() / r.std()
    if trial_sharpes_per_bar is not None and len(trial_sharpes_per_bar) >= 2:
        n = len(trial_sharpes_per_bar)
        sr_std = float(np.std(trial_sharpes_per_bar, ddof=1))
    else:
        n = n_trials or 1
        sr_std = 1 / np.sqrt(T)
    if n < 2:
        return {'gate': 'DEFLATED', 'pass': False, 'detail': 'log at least 2 trials; one trial cannot be deflated honestly'}
    from scipy.stats import norm, skew, kurtosis   # imported here so the paper bot runs without scipy
    expected_max = sr_std * ((1 - EULER) * norm.ppf(1 - 1 / n) + EULER * norm.ppf(1 - 1 / (n * np.e)))
    g3, g4 = skew(r), kurtosis(r, fisher=False)
    denom = np.sqrt(max(1 - g3 * sr + (g4 - 1) / 4 * sr ** 2, 1e-12))
    dsr = float(norm.cdf((sr - expected_max) * np.sqrt(T - 1) / denom))
    return {'gate': 'DEFLATED', 'pass': dsr > 0.95,
            'detail': f'DSR {dsr:.3f} after {n} trials (needs > 0.95)',
            'dsr': dsr, 'n_trials': n}


# ----------------------------------------------------- gate 3: walk-forward

def walk_forward(prices: pd.DataFrame, fit_fn, signal_fn, cfg: Config,
                 train_bars: int = 365, test_bars: int = 90) -> dict:
    """
    fit_fn(train_prices) -> params dict, using ONLY the training window.
    signal_fn(prices, **params) -> signal series.
    Each fold's signal is computed with full PAST history (so indicators are
    warmed up) but params fitted only before the fold. Folds are stitched
    into one out-of-sample run so positions carry over without fake re-entry fees.
    """
    oos = pd.Series(np.nan, index=prices.index)
    folds = []
    i = train_bars
    while i + test_bars <= len(prices):
        params = fit_fn(prices.iloc[i - train_bars:i])
        sig = signal_fn(prices.iloc[:i + test_bars], **params)
        oos.iloc[i:i + test_bars] = sig.iloc[i:i + test_bars].values
        folds.append((prices.index[i], prices.index[i + test_bars - 1], params))
        i += test_bars
    if not folds:
        return {'gate': 'WALK-FORWARD', 'pass': False, 'detail': 'not enough data for one fold'}
    first = prices.index.get_loc(folds[0][0])
    bt = backtest(prices.iloc[first:], oos.iloc[first:].fillna(0), cfg)
    rows = []
    for start, end, params in folds:
        seg = bt.loc[start:end, 'net']
        rows.append({'start': start.date(), 'end': end.date(), 'params': params,
                     'return_pct': round((np.exp(seg.sum()) - 1) * 100, 1)})
    df = pd.DataFrame(rows)
    pos = int((df['return_pct'] > 0).sum())
    ok = pos / len(df) >= 0.6 and metrics(bt, cfg).get('sharpe', 0) > 0
    return {'gate': 'WALK-FORWARD', 'pass': ok,
            'detail': f"{pos}/{len(df)} folds profitable, worst fold {df['return_pct'].min()}%, "
                      f"out-of-sample total {metrics(bt, cfg).get('total_return_pct')}%",
            'folds': df, 'oos': bt}


# ------------------------------------------------------------------ sizing

def position_size(capital: float, entry: float, stop: float, risk_pct: float = 0.01,
                  max_position_pct: float = 0.20, fee_bps: float = 120.0) -> dict:
    """Size so hitting the stop (plus round-trip fees) loses about risk_pct of capital."""
    if stop >= entry:
        raise ValueError('long-only: stop must be below entry')
    risk_per_unit = (entry - stop) + entry * 2 * fee_bps / 1e4
    units = capital * risk_pct / risk_per_unit
    units = min(units, capital * max_position_pct / entry)
    return {'units': round(units, 8), 'dollars': round(units * entry, 2),
            'pct_of_capital': round(units * entry / capital * 100, 1),
            'loss_if_stopped': round(units * risk_per_unit, 2)}


# ------------------------------------------------------------------ live

def health_check(live_returns: pd.Series, backtest_max_dd_pct: float, cfg: Config,
                 min_bars: int = 90) -> dict:
    """Run daily on the live bot. Halt if drawdown exceeds 1.5x the backtest's worst."""
    r = live_returns.dropna()
    equity = np.exp(r.cumsum())
    dd = float(equity.iloc[-1] / equity.cummax().iloc[-1] - 1) * 100 if len(r) else 0.0
    alerts = []
    if dd < backtest_max_dd_pct * 1.5:
        alerts.append(f'DRAWDOWN {dd:.1f}% beyond 1.5x backtest worst ({backtest_max_dd_pct}%)')
    if len(r) >= min_bars and r.mean() <= 0:
        alerts.append(f'NO EDGE: average live return <= 0 over {len(r)} bars')
    return {'current_dd_pct': round(dd, 1), 'alerts': alerts, 'action': 'HALT' if alerts else 'CONTINUE'}


def report(results: list) -> str:
    lines = [f"{'PASS' if g['pass'] else 'FAIL'}  {g['gate']:<13} {g['detail']}" for g in results]
    verdict = 'ALL GATES PASSED: paper trade next' if all(g['pass'] for g in results) else 'REJECTED: do not trade'
    return '\n'.join(lines + [verdict])
