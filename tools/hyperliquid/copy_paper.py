"""
Study 10: paper-copy the 20 "proven" Hyperliquid traders onto the coins Coinbase lists as CDE perps.

FAKE MONEY ONLY. Reads public Hyperliquid data; never logs in, needs no key, places no orders.

    python tools/hyperliquid/copy_paper.py            # check once: update every slice to its trader's positions
    python tools/hyperliquid/copy_paper.py --loop     # keep running, check every hour
    python tools/hyperliquid/copy_paper.py --report   # results so far, each trader's own forward P&L, vs the paper system

Rules are pre-registered in docs/RESEARCH_LOG.md (Study 10). Picks are fixed in picks.json.
Files (git-ignored): data/copy/state.json, data/copy/trades.csv, data/copy/hourly.csv
"""
import argparse
import csv
import json
import os
import time
from datetime import datetime, timezone
from pathlib import Path

import requests

ROOT = Path(__file__).resolve().parents[2]
PICKS = json.loads((Path(__file__).parent / 'picks.json').read_text())['traders']
INFO = 'https://api.hyperliquid.xyz/info'
DIR = ROOT / 'data' / 'copy'
STATE = DIR / 'state.json'
START = '2026-10-10'
START_CASH = 5_000.0
FEE, SLIP, FUNDING_PER_DAY = 0.0010, 0.0005, 0.0001    # Coinbase CDE Intro taker, slippage, funding placeholder
LEV_CAP, DRIFT = 1.0, 0.10                              # per slice
MAX_DD = -0.27
# Hyperliquid coin -> Coinbase CDE perp (CLAUDE.md list). 'k' coins on Hyperliquid are per 1,000 units, so prices
# differ in scale but returns are the same.
COINBASE_PERPS = {c: c for c in ('AAVE ADA AVAX BCH BNB BTC DOGE DOT ENA ETH HBAR HYPE LINK LTC NEAR ONDO PAXG '
                                 'SOL SUI XLM XRP ZEC').split()}
COINBASE_PERPS.update({'kPEPE': 'PEPE', 'kSHIB': 'SHIB'})

_s = requests.Session()
if os.getenv('CCXT_CA_BUNDLE'):
    _s.verify = os.getenv('CCXT_CA_BUNDLE')


def info(body):
    for attempt in range(6):
        try:
            r = _s.post(INFO, json=body, timeout=30)
            if r.status_code == 429 or r.status_code >= 500:
                raise requests.HTTPError(str(r.status_code))
            r.raise_for_status()
            return r.json()
        except requests.RequestException:
            time.sleep(2 ** attempt)
    raise RuntimeError(f'Hyperliquid API kept failing for {body["type"]}')


def now():
    return datetime.now(timezone.utc)


def new_state():
    per = START_CASH / len(PICKS)
    return {'started': now().isoformat(), 'last_check': None, 'peak': START_CASH, 'halted': False,
            'slices': {p['address']: {'cash': per, 'units': {}} for p in PICKS}}


def load_state():
    return json.loads(STATE.read_text()) if STATE.exists() else new_state()


def save_state(st):
    DIR.mkdir(parents=True, exist_ok=True)
    tmp = STATE.with_suffix('.tmp')
    tmp.write_text(json.dumps(st, indent=1))
    tmp.replace(STATE)


def log(name, row):
    path = DIR / name
    new = not path.exists()
    with path.open('a', newline='') as f:
        w = csv.DictWriter(f, fieldnames=list(row))
        if new:
            w.writeheader()
        w.writerow(row)


def slice_equity(sl, mids):
    return sl['cash'] + sum(u * float(mids[c]) for c, u in sl['units'].items())


def targets(user, mids):
    """Target weights (fraction of the slice) and the share of the trader's exposure that we can copy."""
    cs = info({'type': 'clearinghouseState', 'user': user})
    acct = float(cs['marginSummary']['accountValue'])
    w, total, copyable = {}, 0.0, 0.0
    for ap in cs.get('assetPositions', []):
        p = ap['position']
        notional = float(p['szi']) * float(mids.get(p['coin'], 0) or 0)
        total += abs(notional)
        if p['coin'] in COINBASE_PERPS and acct > 0:
            w[p['coin']] = notional / acct
            copyable += abs(notional)
    gross = sum(abs(x) for x in w.values())
    if gross > LEV_CAP:
        w = {c: x * LEV_CAP / gross for c, x in w.items()}
    return w, (copyable / total if total else None), acct


def trade(st, user, coin, delta_units, price, reason):
    sl = st['slices'][user]
    fill = price * (1 + SLIP * (1 if delta_units > 0 else -1))
    fee = abs(delta_units) * fill * FEE
    sl['cash'] -= delta_units * fill + fee
    sl['units'][coin] = sl['units'].get(coin, 0.0) + delta_units
    if abs(sl['units'][coin]) < 1e-12:
        del sl['units'][coin]
    log('trades.csv', {'time': now().isoformat(timespec='seconds'), 'trader': user[:10], 'coin': COINBASE_PERPS[coin],
                       'units': round(delta_units, 8), 'price': round(fill, 6), 'notional_usd': round(delta_units * fill, 2),
                       'fee_usd': round(fee, 4), 'reason': reason})


def run_once(verbose=True):
    st = load_state()
    mids = info({'type': 'allMids'})
    t = now()
    if st['last_check']:                                   # funding for the time since the last check
        hours = (t - datetime.fromisoformat(st['last_check'])).total_seconds() / 3600
        for sl in st['slices'].values():
            sl['cash'] -= sum(abs(u) * float(mids[c]) for c, u in sl['units'].items()) * FUNDING_PER_DAY * hours / 24
    total = sum(slice_equity(sl, mids) for sl in st['slices'].values())
    st['peak'] = max(st['peak'], total)
    if total / st['peak'] - 1 <= MAX_DD and not st['halted']:
        st['halted'] = True
        for user, sl in st['slices'].items():
            for c, u in list(sl['units'].items()):
                trade(st, user, c, -u, float(mids[c]), 'hard stop -27%')
        print(f'HARD STOP: the copy account is {total / st["peak"] - 1:.1%} from its high. Everything closed; review with Claude.')
    coverage = []
    if not st['halted']:
        for user, sl in st['slices'].items():
            try:
                w, cov, acct = targets(user, mids)
            except RuntimeError as err:
                print(f'  {user[:10]}: skipped this hour ({err})')
                continue
            if cov is not None:
                coverage.append(cov)
            eq = slice_equity(sl, mids)
            for c in set(w) | set(sl['units']):
                price = float(mids[c])
                cur = sl['units'].get(c, 0.0) * price
                tgt = w.get(c, 0.0) * max(eq, 0.0)
                if (c not in w and cur != 0) or abs(tgt - cur) > DRIFT * max(eq, 0.0):
                    trade(st, user, c, (tgt - cur) / price, price, 'trader closed' if c not in w else 'follow')
            time.sleep(0.3)
    st['last_check'] = t.isoformat()
    total = sum(slice_equity(sl, mids) for sl in st['slices'].values())
    st['peak'] = max(st['peak'], total)
    gross = sum(abs(u) * float(mids[c]) for sl in st['slices'].values() for c, u in sl['units'].items())
    row = {'time': t.isoformat(timespec='seconds'), 'equity': round(total, 2), 'drawdown_pct': round((total / st['peak'] - 1) * 100, 2),
           'gross_exposure_pct': round(gross / total * 100, 1) if total else 0,
           'copyable_share_pct': round(sum(coverage) / len(coverage) * 100, 1) if coverage else None}
    log('hourly.csv', row)
    save_state(st)
    if verbose:
        print(f"{row['time']}  copy account ${total:,.2f} ({(total / START_CASH - 1) * 100:+.2f}%), "
              f"exposure {row['gross_exposure_pct']}%, drawdown {row['drawdown_pct']}%, "
              f"copyable share of their positions {row['copyable_share_pct']}%")


def forward_pnl(user):
    start = int(datetime.fromisoformat(START).replace(tzinfo=timezone.utc).timestamp() * 1000)
    pnl, n = 0.0, 0
    while True:
        page = info({'type': 'userFillsByTime', 'user': user, 'startTime': start})
        pnl += sum(float(f['closedPnl']) - float(f['fee']) for f in page)
        n += len(page)
        if len(page) < 2000:
            return pnl, n
        start = max(f['time'] for f in page) + 1


def report():
    st = load_state()
    mids = info({'type': 'allMids'})
    days = (now() - datetime.fromisoformat(st['started'])).total_seconds() / 86400
    total = sum(slice_equity(sl, mids) for sl in st['slices'].values())
    print(f'Copy account after {days:.1f} days: ${total:,.2f} ({(total / START_CASH - 1) * 100:+.2f}%), '
          f'high ${st["peak"]:,.2f}{"  HALTED" if st["halted"] else ""}')
    paper = ROOT / 'data' / 'paper' / 'daily.csv'
    if paper.exists():
        import pandas as pd
        d = pd.read_csv(paper)
        d = d[d.iloc[:, 0].astype(str) >= st['started'][:10]]
        if len(d) and 'equity' in d:
            print(f'BTC+ETH paper system over the same days: {(d["equity"].iloc[-1] / d["equity"].iloc[0] - 1) * 100:+.2f}%')
    print(f'\n{"trader":<12}{"slice now":>11}{"own fwd P&L":>16}{"fills":>8}')
    wins = 0
    for p in PICKS:
        u = p['address']
        try:
            pnl, n = forward_pnl(u)
        except RuntimeError:
            pnl, n = float('nan'), 0
        wins += pnl > 0
        print(f'{u[:10]:<12}{slice_equity(st["slices"][u], mids):>11,.2f}{pnl:>16,.0f}{n:>8}')
        time.sleep(0.3)
    print(f'\n{wins} of {len(PICKS)} picks profitable on their own since {START} (needs 12+ at the 60-day review).')
    print('Review on 2026-12-09 against the criteria in docs/RESEARCH_LOG.md (Study 10).')


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument('--loop', action='store_true', help='keep running and check every hour')
    ap.add_argument('--report', action='store_true', help='show results so far')
    a = ap.parse_args()
    if a.report:
        return report()
    while True:
        try:
            run_once()
        except Exception as err:                       # keep the loop alive through network blips
            print(f'{now():%Y-%m-%d %H:%M} check failed: {type(err).__name__}: {err}')
            if not a.loop:
                raise
        if not a.loop:
            break
        time.sleep(3600)


if __name__ == '__main__':
    main()
