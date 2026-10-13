"""Tiny read-only client for Polymarket's public APIs (no account, no key). Caches responses on disk."""
import hashlib
import json
import os
import time
from pathlib import Path

import requests

GAMMA = 'https://gamma-api.polymarket.com'
DATA = 'https://data-api.polymarket.com'
CLOB = 'https://clob.polymarket.com'
CACHE = Path('Data/polymarket/cache')

_s = requests.Session()
if os.getenv('CCXT_CA_BUNDLE'):
    _s.verify = os.getenv('CCXT_CA_BUNDLE')


def get(url, params=None, cache=True, pause=0.12):
    """GET JSON with retries. cache=True stores the answer forever (use only for data that can't change)."""
    key = hashlib.sha1((url + json.dumps(params or {}, sort_keys=True)).encode()).hexdigest()
    path = CACHE / key[:2] / f'{key}.json'
    if cache and path.exists():
        return json.loads(path.read_text())
    for attempt in range(6):
        try:
            r = _s.get(url, params=params, timeout=30)
            if r.status_code == 429 or r.status_code >= 500:
                raise requests.HTTPError(str(r.status_code))
            r.raise_for_status()
            out = r.json()
            break
        except (requests.RequestException, ValueError):
            if attempt == 5:
                raise
            time.sleep(2 ** attempt)
    time.sleep(pause)
    if cache:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(out))
    return out


# Taker fee rate per share = rate * p * (1 - p). docs.polymarket.com fees page, read 2026-10-09.
FEE_RATE = {'crypto': 0.07, 'sports': 0.05, 'finance': 0.04, 'politics': 0.04, 'economics': 0.05, 'culture': 0.05,
            'weather': 0.05, 'mentions': 0.04, 'tech': 0.04, 'geopolitics': 0.0}


def fee_rate(market):
    if not market.get('feesEnabled'):
        return 0.0
    kind = (market.get('feeType') or '').split('_')[0]
    return FEE_RATE.get(kind, 0.05)


def is_updown(market):
    q = (market.get('question') or '').lower()
    return 'up or down' in q or 'updown' in (market.get('slug') or '')


def outcome_yes(market):
    """1.0 if YES won, 0.0 if NO won, None if not cleanly resolved."""
    try:
        p = [float(x) for x in json.loads(market['outcomePrices'])]
    except (KeyError, ValueError, TypeError):
        return None
    if p in ([1.0, 0.0], [0.0, 1.0]):
        return p[0]
    return None
