"""
Paper trader for the approved system (docs/RESEARCH_LOG.md, Studies 2 and 3):
BTC + ETH trend portfolio, long only, volatility control, 2/3 size, SPOT,
two half-accounts, Intro-tier spot fees, and the -20% account kill switch.

FAKE MONEY ONLY. It never logs in, never needs an API key, never places an order.
It reads public Coinbase prices and keeps a simulated account on disk.

    python tools/paper/paper_trader.py            # check once: act on any newly closed daily candle
    python tools/paper/paper_trader.py --loop     # keep running, check every hour
    python tools/paper/paper_trader.py --report   # performance so far vs the backtest's expectations
    python tools/paper/paper_trader.py --resume   # restart after the kill switch fired (after reviewing why)

Decisions use the exact same signal function as the backtest (tools/study_trend.py).
Each day, after the UTC daily candle closes, it computes the target position from
closed candles only, then fills at the current price, the same as "next open" in the backtest.

Files (git-ignored): data/paper/state.json, data/paper/trades.csv, data/paper/daily.csv, data/paper/history/*.csv
"""

import argparse
import csv
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
from study_trend import trend_signal          # the SAME rules that were backtested

COINS = ('BTC', 'ETH')
START_CASH = 5_000.0
SIZE = 2 / 3
FEE = 0.0090                 # Intro-tier spot taker, per side
SLIPPAGE = 0.0005            # per side, same as the backtest
KILL_SWITCH = -0.20          # sell everything and halt, from the high-water mark (user's rule, 2026-09-30)
WARN_AT = -0.15              # loud warning to review, no selling
MIN_TRADE_USD = 1.0          # Coinbase minimum order
DRIFT_REBALANCE = 0.10       # rebalance when a half drifts >10 points from target (set before testing)
DIR = ROOT / 'data' / 'paper'
HIST = DIR / 'history'
STATE = DIR / 'state.json'


# ------------------------------------------------------------------ prices

def exchange():
    import ccxt
    e = ccxt.coinbase({'enableRateLimit': True})
    if os.getenv('CCXT_CA_BUNDLE'):
        e.validateServerSsl = os.getenv('CCXT_CA_BUNDLE')
    return e


def closed_daily(e, coin) -> pd.DataFrame:
    """Full daily history (cached on disk), closed candles only."""
    HIST.mkdir(parents=True, exist_ok=True)
    path = HIST / f'{coin}_USD_1d.csv'
    df = pd.read_csv(path, index_col=0, parse_dates=True) if path.exists() else None
    since = int(df.index[-1].timestamp() * 1000) if df is not None else e.parse8601('2016-01-01T00:00:00Z')
    rows, now = [], e.milliseconds()
    while since < now:                              # pages can come back short; walk to today regardless
        batch = e.fetch_ohlcv(f'{coin}/USD', '1d', since=since, limit=300)
        rows += batch
        since = batch[-1][0] + 86_400_000 if batch else since + 300 * 86_400_000
    if rows:
        new = pd.DataFrame(rows, columns=['timestamp', 'open', 'high', 'low', 'close', 'volume'])
        new.index = pd.to_datetime(new.pop('timestamp'), unit='ms', utc=True)
        df = new if df is None else pd.concat([df, new])
        df = df[~df.index.duplicated(keep='last')].sort_index()
    today = pd.Timestamp.now(tz='UTC').normalize()
    df = df[df.index < today]                     # drop today's still-forming candle
    df.to_csv(path)
    return df


def targets_from_history(hist: dict) -> tuple:
    """Target fraction of each half-account, from closed candles on common days (as backtested)."""
    common = hist[COINS[0]].index
    for c in COINS[1:]:
        common = common.intersection(hist[c].index)
    last_day = common[-1]
    tg = {c: float(trend_signal(hist[c].loc[common], False, True).fillna(0).iloc[-1]) * SIZE for c in COINS}
    return last_day, tg


# ------------------------------------------------------------------ account

def new_state():
    return {'started_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
            'start_cash': START_CASH, 'halted': False, 'last_decision_day': None,
            'high_water': START_CASH, 'fees_paid': 0.0,
            'halves': {c: {'cash': START_CASH / 2, 'qty': 0.0, 'target': 0.0} for c in COINS}}


def load_state():
    return json.loads(STATE.read_text()) if STATE.exists() else new_state()


def save_state(st):
    DIR.mkdir(parents=True, exist_ok=True)
    STATE.write_text(json.dumps(st, indent=2))


def equity(st, px: dict) -> float:
    return sum(h['cash'] + h['qty'] * px[c] for c, h in st['halves'].items())


def log_row(name, row):
    path = DIR / name
    new = not path.exists()
    with path.open('a', newline='') as f:
        w = csv.DictWriter(f, list(row))
        if new:
            w.writeheader()
        w.writerow(row)


def rebalance(st, coin, target, price, day, reason):
    """Move one half-account to `target` fraction of its own equity at `price` (plus slippage and fee)."""
    h = st['halves'][coin]
    half_eq = h['cash'] + h['qty'] * price
    want_value = target * half_eq
    delta = want_value - h['qty'] * price
    if abs(delta) < MIN_TRADE_USD:
        h['target'] = target
        return None
    if delta > 0:                                              # buy: pay fee on top, capped by cash
        spend = min(delta, h['cash'] / (1 + FEE))
        fill = price * (1 + SLIPPAGE)
        qty, fee = spend / fill, spend * FEE
        h['cash'] -= spend + fee
        h['qty'] += qty
        side, notional = 'buy', spend
    else:                                                      # sell
        qty = min(-delta / price, h['qty'])
        fill = price * (1 - SLIPPAGE)
        notional = qty * fill
        fee = notional * FEE
        h['qty'] -= qty
        h['cash'] += notional - fee
        side = 'sell'
    h['target'] = target
    st['fees_paid'] += fee
    row = {'time_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'), 'decision_day': day,
           'coin': coin, 'side': side, 'qty': round(qty, 8), 'fill_price': round(fill, 2),
           'notional_usd': round(notional, 2), 'fee_usd': round(fee, 2), 'new_target': round(target, 4),
           'reason': reason}
    log_row('trades.csv', row)
    return row


# ------------------------------------------------------------------ daily step

def step(st, hist: dict, px: dict, verbose=True):
    """One decision: uses closed candles in `hist`, fills at current prices `px`. Returns list of trades."""
    day, targets = targets_from_history(hist)
    day_s = str(day.date())
    if st['last_decision_day'] == day_s:
        return []                                             # already acted on this candle
    missed = ''
    if st['last_decision_day']:
        gap = (day - pd.Timestamp(st['last_decision_day'], tz='UTC')).days
        missed = f' (caught up after {gap - 1} missed day(s))' if gap > 1 else ''

    trades = []
    eq = equity(st, px)
    st['high_water'] = max(st['high_water'], eq)
    dd = eq / st['high_water'] - 1

    if st['halted']:
        note = 'HALTED by kill switch: no trading until --resume'
    elif dd <= KILL_SWITCH:
        st['halted'] = True
        for c in COINS:
            t = rebalance(st, c, 0.0, px[c], day_s, f'KILL SWITCH: drawdown {dd:.1%}')
            trades += [t] if t else []
        note = f'KILL SWITCH FIRED at {dd:.1%} from the high-water mark. Everything sold. Review, then --resume.'
    else:
        for c in COINS:
            h = st['halves'][c]
            half_eq = h['cash'] + h['qty'] * px[c]
            actual = h['qty'] * px[c] / half_eq if half_eq > 0 else 0.0
            # Trade when the rule's target changes, or when price moves have pushed the position
            # more than DRIFT_REBALANCE away from it. The backtest held exposure exactly at target;
            # without this, rallies inflate exposure and drawdowns get deeper than tested.
            if abs(targets[c] - h['target']) > 1e-9:
                reason = 'signal change'
            elif abs(actual - targets[c]) > DRIFT_REBALANCE:
                reason = f'drift rebalance ({actual:.0%} held vs {targets[c]:.0%} target)'
            else:
                continue
            t = rebalance(st, c, targets[c], px[c], day_s, reason)
            trades += [t] if t else []
        note = f'WARNING: drawdown {dd:.1%}, review (kill switch at {KILL_SWITCH:.0%})' if dd <= WARN_AT else 'ok'

    st['last_decision_day'] = day_s
    eq = equity(st, px)
    st['high_water'] = max(st['high_water'], eq)
    log_row('daily.csv', {'decision_day': day_s, 'time_utc': datetime.now(timezone.utc).isoformat(timespec='seconds'),
                          **{f'{c}_price': round(px[c], 2) for c in COINS},
                          **{f'{c}_target': round(st['halves'][c]['target'], 4) for c in COINS},
                          **{f'{c}_value': round(st['halves'][c]['qty'] * px[c], 2) for c in COINS},
                          'cash': round(sum(h['cash'] for h in st['halves'].values()), 2),
                          'equity': round(eq, 2), 'drawdown_pct': round((eq / st['high_water'] - 1) * 100, 2),
                          'fees_paid': round(st['fees_paid'], 2), 'note': note + missed})
    if verbose:
        tgt = ', '.join(f"{c} {st['halves'][c]['target']:.0%}" for c in COINS)
        print(f"[{day_s}] equity ${eq:,.2f}  drawdown {(eq / st['high_water'] - 1):.1%}  targets: {tgt}  "
              f"trades: {len(trades)}  {note}{missed}")
        for t in trades:
            print(f"   PAPER {t['side'].upper()} {t['coin']} ${t['notional_usd']:,.2f} @ {t['fill_price']:,} (fee ${t['fee_usd']})")
    return trades


def run_once():
    e = exchange()
    e.load_markets()
    hist = {c: closed_daily(e, c) for c in COINS}
    px = {c: float(e.fetch_ticker(f'{c}/USD')['last']) for c in COINS}
    st = load_state()
    step(st, hist, px)
    save_state(st)


# ------------------------------------------------------------------ report

def report():
    st = load_state()
    path = DIR / 'daily.csv'
    if not path.exists():
        print('No paper trading days yet.')
        return
    d = pd.read_csv(path)
    first, last = d.iloc[0], d.iloc[-1]
    days = len(d)
    ret = last['equity'] / st['start_cash'] - 1
    hold = np.mean([last[f'{c}_price'] / first[f'{c}_price'] for c in COINS]) - 1
    trades = pd.read_csv(DIR / 'trades.csv') if (DIR / 'trades.csv').exists() else pd.DataFrame()
    print(f"Paper trading since {first['decision_day']} ({days} decision days)")
    print(f"  Equity            ${last['equity']:,.2f}  ({ret:+.1%} on ${st['start_cash']:,.0f})")
    print(f"  50/50 hold        {hold:+.1%} over the same days (before fees)")
    print(f"  Worst drawdown    {d['drawdown_pct'].min():.1f}%   (backtest worst at 2/3 size: about -22%)")
    print(f"  Trades            {len(trades)}   fees paid ${st['fees_paid']:,.2f}")
    print(f"  Kill switch       {'FIRED, halted' if st['halted'] else 'not triggered'}")
    print(f"  Days to go        {max(0, 60 - days)} more before the 60-day review")
    print('\nWhat to expect (from the backtest): about 1 trade per coin per month, losing 6-month stretches')
    print('about 1 in 3, and single-month dips of 5-10% are normal. Judge after 60+ days, not week to week.')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--loop', action='store_true', help='keep running and check every hour')
    ap.add_argument('--report', action='store_true', help='show performance so far')
    ap.add_argument('--resume', action='store_true', help='clear the kill-switch halt')
    a = ap.parse_args()
    if a.report:
        return report()
    if a.resume:
        st = load_state()
        st['halted'] = False
        st['high_water'] = None
        save_state(st)
        print('Kill switch cleared. The high-water mark resets on the next run.')
        return
    while True:
        try:
            st = load_state()
            if st.get('high_water') is None:          # reset after --resume
                st['high_water'] = 0.0
                save_state(st)
            run_once()
        except Exception as err:
            print(f'[{datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC] check failed: {type(err).__name__}: {err}')
        if not a.loop:
            break
        time.sleep(3600)


if __name__ == '__main__':
    main()
