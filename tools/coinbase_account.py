"""
Read-only view of your Coinbase account, for Claude and for you.

    python tools/coinbase_account.py            # balances, fee tier, recent fills
    python tools/coinbase_account.py --fills 50 # more fills

It REFUSES to run if the API key can trade or transfer. While money stays in the
bank (see docs/RESEARCH_LOG.md), the key must be View-only.

Setup (once):
  1. https://portal.cdp.coinbase.com -> API keys -> Create API key
     Permissions: View ONLY (leave Trade and Transfer unticked).
     Add your home IP to the allowlist if offered.
  2. Put both values in .env in the repo folder (never in chat, never committed):
       COINBASE_VIEW_KEY=organizations/.../apiKeys/...
       COINBASE_VIEW_SECRET="-----BEGIN EC PRIVATE KEY-----\n...\n-----END EC PRIVATE KEY-----\n"
  3. pip install -r tools/requirements.txt

Prints numbers only. Never prints the key.
"""

import argparse
import os
import sys
from pathlib import Path

import ccxt
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]


class UnsafeKey(Exception):
    pass


def check_view_only(perms: dict):
    """Raise unless the key can view and can neither trade nor transfer."""
    if not perms.get('can_view'):
        raise UnsafeKey('this key cannot view the account; create it with View permission')
    bad = [p for p in ('can_trade', 'can_transfer') if perms.get(p)]
    if bad:
        raise UnsafeKey(f"this key has {' and '.join(b.replace('can_', '').upper() for b in bad)} permission. "
                        'Delete it at portal.cdp.coinbase.com and create a View-only key. '
                        'Nothing was read.')


def connect():
    load_dotenv(ROOT / '.env')
    key, secret = os.getenv('COINBASE_VIEW_KEY'), (os.getenv('COINBASE_VIEW_SECRET') or '').replace('\\n', '\n')
    if not key or not secret:
        raise SystemExit('Add COINBASE_VIEW_KEY and COINBASE_VIEW_SECRET to .env (see the top of this file).')
    e = ccxt.coinbase({'apiKey': key, 'secret': secret, 'enableRateLimit': True})
    if os.getenv('CCXT_CA_BUNDLE'):
        e.validateServerSsl = os.getenv('CCXT_CA_BUNDLE')
    check_view_only(e.v3PrivateGetBrokerageKeyPermissions())
    return e


def main(n_fills=20):
    try:
        e = connect()
    except UnsafeKey as err:
        print(f'REFUSED: {err}')
        sys.exit(2)

    print('Key permissions: View only (OK)\n')
    bal = e.fetch_balance()
    rows = [(c, v) for c, v in (bal.get('total') or {}).items() if v]
    print('Balances')
    if not rows:
        print('  (none)')
    for c, v in sorted(rows):
        print(f'  {c:<8} {v:,.8f}'.rstrip('0').rstrip('.'))

    fees = e.v3PrivateGetBrokerageTransactionSummary()
    tier = fees.get('fee_tier') or {}
    print('\nFee tier')
    print(f"  {tier.get('pricing_tier', '?')}: maker {float(tier.get('maker_fee_rate', 0)) * 100:.3f}%, "
          f"taker {float(tier.get('taker_fee_rate', 0)) * 100:.3f}%  (30-day volume ${float(fees.get('total_volume', 0)):,.2f})")

    try:
        fills = e.fetch_my_trades(limit=n_fills)
    except Exception as err:
        print(f'\nRecent fills: unavailable ({type(err).__name__})')
    else:
        print(f'\nRecent fills ({len(fills)})')
        for t in fills[-n_fills:]:
            fee = (t.get('fee') or {}).get('cost') or 0
            print(f"  {t['datetime'][:19]}  {t['side']:<4} {t['symbol']:<12} {t['amount']:.6g} @ {t['price']:,.4f}  fee {fee:.2f}")


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--fills', type=int, default=20)
    main(ap.parse_args().fills)
