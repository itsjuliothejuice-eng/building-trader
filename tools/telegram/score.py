"""
Score every Telegram call against real prices and grade each channel.

    python tools/telegram/score.py            # extract + score + write reports
    python tools/telegram/score.py --days 30  # only calls from the last 30 days

For each CALL it measures, from the first hourly open AFTER the post (you
can't buy before you read it), with Coinbase fees and no leverage:
  - return after 1h, 24h and 7d, net of a 2.5% round trip (1.20% fee + 0.05% slippage, per side)
  - whether target 1 or the stop was hit first (same hour = stop, to be conservative)
  - the 24h run-up BEFORE the post (large = the coin was pumped before you were told)
  - whether the stated entry was already gone when the call went out
  - whether you can even trade it on Coinbase

Channel red flags: results posted with no earlier call, levels edited after
posting, deleted messages, and high pre-call run-ups.

Writes reports/telegram/scorecard.md, scorecard.csv and calls.csv (git-ignored).
"""

import argparse
import csv
import json
import os
import statistics as st
from datetime import datetime, timedelta, timezone
from pathlib import Path

import ccxt

import store
from extract import extract_all

ROOT = Path(__file__).resolve().parents[2]
REPORTS = ROOT / 'reports' / 'telegram'
EXCHANGES = ['coinbase', 'kraken', 'kucoin', 'mexc', 'okx', 'bitget']   # Binance blocks US users
ROUND_TRIP = 2 * (1.20 + 0.05) / 100
HOUR = 3_600_000
HORIZONS = {'1h': 1, '24h': 24, '7d': 168}
PUMP = 0.15                                  # >15% run-up in the 24h before the call


class Prices:
    def __init__(self, con):
        self.con, self.ex, self.cache = con, {}, {}

    def _exchange(self, name):
        if name not in self.ex:
            e = getattr(ccxt, name)({'enableRateLimit': True})
            if os.getenv('CCXT_CA_BUNDLE'):
                e.validateServerSsl = os.getenv('CCXT_CA_BUNDLE')
            try:
                e.load_markets()
            except Exception as err:
                print(f'  {name} unavailable: {type(err).__name__}')
                e = None
            self.ex[name] = e
        return self.ex[name]

    def find(self, sym):
        """-> (exchange, market, on_coinbase) or None"""
        if sym in self.cache:
            return self.cache[sym]
        hit, cb = None, self._exchange('coinbase')
        on_cb = bool(cb) and any(f'{sym}/{q}' in cb.markets for q in ('USD', 'USDC'))
        for name in EXCHANGES:
            e = self._exchange(name)
            if not e:
                continue
            for q in ('USD', 'USDT', 'USDC'):
                m = f'{sym}/{q}'
                if m in e.markets and e.markets[m].get('spot', True) and e.markets[m].get('active') is not False:
                    hit = (name, m, on_cb)
                    break
            if hit:
                break
        self.cache[sym] = hit
        return hit

    def candles(self, exchange, market, start, end):
        """Hourly [ts, open, high, low, close] between start and end (ms), cached in SQLite."""
        q = 'SELECT ts, open, high, low, close FROM candles WHERE exchange=? AND symbol=? AND ts>=? AND ts<? ORDER BY ts'
        rows = self.con.execute(q, (exchange, market, start, end)).fetchall()
        if len(rows) >= (end - start) // HOUR - 2:
            return [tuple(r) for r in rows]
        e, since = self._exchange(exchange), start
        while since < end:
            batch = e.fetch_ohlcv(market, '1h', since=since, limit=300)
            if not batch:
                since += 300 * HOUR
                continue
            self.con.executemany('INSERT OR REPLACE INTO candles VALUES (?,?,?,?,?,?,?)',
                                 [(exchange, market, *c[:5]) for c in batch])
            since = max(batch[-1][0] + HOUR, since + HOUR)
        self.con.commit()
        return [tuple(r) for r in self.con.execute(q, (exchange, market, start, end)).fetchall()]


def score_call(c, px, now_ms):
    found = px.find(c['symbol'])
    if not found:
        return {'status': 'no_price_data'}
    exchange, market, on_cb = found
    posted = int(datetime.fromisoformat(c['posted_utc']).timestamp() * 1000)
    first = (posted // HOUR + 1) * HOUR                       # first full hour after the post
    bars = px.candles(exchange, market, first - 25 * HOUR, min(first + 169 * HOUR, now_ms))
    after = [b for b in bars if b[0] >= first]
    before = [b for b in bars if b[0] < first]
    if not after:
        return {'status': 'too_recent', 'exchange': exchange, 'on_coinbase': on_cb}

    sign = -1 if c['direction'] == 'short' else 1
    entry = after[0][1]
    targets, stop = json.loads(c['targets'] or '[]'), c['stop']
    if c['entry_low']:
        ref, band = c['entry_low'], (0.8, 1.25)       # a real entry is near the market
    else:
        ref, band = stop or (targets[0] if targets else None), (0.5, 2.0)
    if ref and not band[0] < entry / ref < band[1]:
        # Levels nowhere near the real price: a different coin with the same ticker, or a typo.
        return {'status': 'price_mismatch', 'exchange': exchange, 'on_coinbase': on_cb, 'entry_price': entry}
    out = {'status': 'scored', 'exchange': exchange, 'on_coinbase': on_cb, 'entry_price': entry}

    for label, h in HORIZONS.items():
        if len(after) >= h:
            gross = sign * (after[h - 1][4] / entry - 1)
            out[f'net_{label}'] = round((gross - ROUND_TRIP) * 100, 2)

    if len(before) >= 24:
        out['runup_24h_before'] = round(sign * (before[-1][4] / before[-24][4] - 1) * 100, 2)

    lo, hi = c['entry_low'], c['entry_high'] or c['entry_low']
    if lo:
        out['entry_gone'] = int(entry > hi * 1.01 if sign > 0 else entry < lo * 0.99)

    outcome, reached = 'open', 0            # first event decides; same hour = stop
    for _, _, h, l, _ in after[:168]:
        best, worst = (h, l) if sign > 0 else (l, h)
        if stop and (worst <= stop if sign > 0 else worst >= stop):
            if reached == 0:
                outcome = 'stop'
            break
        while reached < len(targets) and (best >= targets[reached] if sign > 0 else best <= targets[reached]):
            reached += 1
        if reached:
            outcome = 'target'
    out['outcome'] = outcome if (targets or stop) else 'no_levels'
    out['targets_hit'] = f'{reached}/{len(targets)}' if targets else ''
    return out


def grade(s):
    if s['scored'] < 20:
        return 'TOO FEW CALLS'
    if s['mean_net_7d'] is None or s['mean_net_7d'] <= 0:
        return 'NO EDGE'
    if s['pumped_pct'] >= 30 or s['unbacked_results'] > s['calls']:
        return 'SUSPICIOUS'
    return 'WORTH TESTING'


def main(days=None):
    con = store.connect()
    extract_all(con)
    px, now_ms = Prices(con), int(datetime.now(timezone.utc).timestamp() * 1000)
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat() if days else ''

    calls = [dict(r) for r in con.execute(
        "SELECT * FROM calls WHERE kind='CALL' AND posted_utc>=? ORDER BY posted_utc", (since,))]
    print(f'scoring {len(calls)} calls...')
    for i, c in enumerate(calls, 1):
        try:
            c.update(score_call(c, px, now_ms))
        except Exception as err:
            c.update({'status': f'error: {type(err).__name__}'})
        if i % 25 == 0:
            print(f'  {i}/{len(calls)}')

    results = [dict(r) for r in con.execute("SELECT * FROM calls WHERE kind='RESULT' AND posted_utc>=?", (since,))]
    deletions = dict(con.execute('SELECT chat_id, COUNT(*) FROM deletions GROUP BY chat_id').fetchall())
    titles = dict(con.execute('SELECT chat_id, MAX(chat_title) FROM messages GROUP BY chat_id').fetchall())

    cards = []
    for chat_id, title in titles.items():
        mine = [c for c in calls if c['chat_id'] == chat_id]
        scored = [c for c in mine if c.get('status') == 'scored']
        res = [r for r in results if r['chat_id'] == chat_id]
        unbacked = 0
        for r in res:
            t = datetime.fromisoformat(r['posted_utc'])
            if not any(c['symbol'] == r['symbol'] and t - timedelta(days=14) <= datetime.fromisoformat(c['posted_utc']) < t
                       for c in mine):
                unbacked += 1
        n7 = [c['net_7d'] for c in scored if 'net_7d' in c]
        n24 = [c['net_24h'] for c in scored if 'net_24h' in c]
        levels = [c for c in scored if c.get('outcome') in ('target', 'stop')]
        runups = [c['runup_24h_before'] for c in scored if 'runup_24h_before' in c]
        s = {
            'channel': title, 'calls': len(mine), 'scored': len(scored),
            'on_coinbase_pct': round(100 * sum(c['on_coinbase'] for c in scored) / len(scored)) if scored else 0,
            'win_7d_pct': round(100 * sum(x > 0 for x in n7) / len(n7)) if n7 else None,
            'median_net_24h': round(st.median(n24), 2) if n24 else None,
            'mean_net_7d': round(st.mean(n7), 2) if n7 else None,
            'worst_7d': min(n7) if n7 else None,
            'target_before_stop_pct': round(100 * sum(c['outcome'] == 'target' for c in levels) / len(levels)) if levels else None,
            'pumped_pct': round(100 * sum(r >= PUMP * 100 for r in runups) / len(runups)) if runups else 0,
            'entry_gone_pct': round(100 * sum(c.get('entry_gone', 0) for c in scored) / len(scored)) if scored else 0,
            'results_posted': len(res), 'unbacked_results': unbacked,
            'edited_levels': sum(c['edited_levels'] for c in mine),
            'deleted_msgs': deletions.get(chat_id, 0),
            'history_only_pct': round(100 * sum(c['backfilled'] for c in mine) / len(mine)) if mine else 0,
        }
        s['verdict'] = grade(s)
        cards.append(s)
    cards.sort(key=lambda s: (s['mean_net_7d'] is None, -(s['mean_net_7d'] or 0)))
    write_reports(calls, cards)


def write_reports(calls, cards):
    REPORTS.mkdir(parents=True, exist_ok=True)
    cols = ['chat_title', 'posted_utc', 'symbol', 'direction', 'leverage', 'entry_low', 'entry_high', 'targets',
            'stop', 'status', 'exchange', 'on_coinbase', 'entry_price', 'entry_gone', 'runup_24h_before',
            'net_1h', 'net_24h', 'net_7d', 'outcome', 'targets_hit', 'edited_levels', 'backfilled', 'msg_id']
    with (REPORTS / 'calls.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.DictWriter(f, cols, extrasaction='ignore')
        w.writeheader()
        w.writerows(calls)
    with (REPORTS / 'scorecard.csv').open('w', newline='', encoding='utf-8') as f:
        if cards:
            w = csv.DictWriter(f, list(cards[0]))
            w.writeheader()
            w.writerows(cards)

    fmt = lambda v: '' if v is None else v
    lines = [
        f'# Telegram channel scorecard ({datetime.now(timezone.utc):%Y-%m-%d %H:%M} UTC)', '',
        'Returns are % per call, unleveraged, entered at the first hourly open after the post, '
        'minus a 2.5% Coinbase round trip. Leverage multiplies losses the same as gains.', '',
        '| Channel | Verdict | Calls | Scored | 7d win % | Mean 7d net | Worst 7d | Median 24h | '
        'Target before stop % | Pumped before call % | Entry already gone % | On Coinbase % | '
        'Results with no prior call | Edited levels | Deleted |',
        '|' + '---|' * 15,
    ]
    for s in cards:
        lines.append('| ' + ' | '.join(str(fmt(s[k])) for k in [
            'channel', 'verdict', 'calls', 'scored', 'win_7d_pct', 'mean_net_7d', 'worst_7d', 'median_net_24h',
            'target_before_stop_pct', 'pumped_pct', 'entry_gone_pct', 'on_coinbase_pct',
            'unbacked_results', 'edited_levels', 'deleted_msgs']) + ' |')
    lines += ['', '**How to read it**',
              '- *Verdict* needs 20+ scored calls. "WORTH TESTING" only means it goes through tools/quantcheck.py next.',
              '- *Pumped before call*: share of calls where the coin already rose >15% in the 24h before the post.',
              '- *Results with no prior call*: victory posts for coins the channel never called beforehand.',
              '- *Edited levels / Deleted*: only caught for messages seen live; history-only calls may hide earlier edits.']
    (REPORTS / 'scorecard.md').write_text('\n'.join(lines), encoding='utf-8')
    print(f'wrote {REPORTS / "scorecard.md"}')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--days', type=int, help='only score calls from the last N days')
    main(ap.parse_args().days)
