"""
Market-cap tags from CoinMarketCap (free Basic plan).

Needs CMC_API_KEY in the repo's .env. Without a key, every coin is tagged 'unknown'
and the scorecard still works.

Limitation: the free plan only has the CURRENT market cap, not the cap on the
day of a call, so tags say "now". Coins that were pumped and dumped usually end
up tiny, which is the point of the tag.

The top 5,000 coins by market cap are fetched at most once a day (25 of the plan's
~10,000 monthly credits) and cached in data/telegram/cmc_listings.json.
"""

import json
import os
import time
from pathlib import Path

import requests
from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[2]
CACHE = ROOT / 'data' / 'telegram' / 'cmc_listings.json'
URL = 'https://pro-api.coinmarketcap.com/v1/cryptocurrency/listings/latest'
MAX_AGE = 24 * 3600

# (upper bound in USD, label); checked smallest first
CLASSES = [(10e6, 'nano (<$10M)'), (100e6, 'micro ($10M-100M)'), (1e9, 'small ($100M-1B)'),
           (10e9, 'mid ($1B-10B)'), (float('inf'), 'large ($10B+)')]
TINY = 100e6     # "tiny coin" threshold used in the scorecard


def size_class(cap):
    if cap is None:
        return 'not in top 5,000'
    return next(label for bound, label in CLASSES if cap < bound)


class MarketCaps:
    def __init__(self):
        load_dotenv(ROOT / '.env')
        self.key = os.getenv('CMC_API_KEY')
        self.by_symbol = {}
        self.status = 'no CMC_API_KEY in .env: market-cap tags skipped'
        if self.key:
            try:
                self._load()
            except Exception as err:
                self.status = f'CoinMarketCap unavailable ({type(err).__name__}): market-cap tags skipped'

    def _load(self):
        data = None
        if CACHE.exists() and time.time() - CACHE.stat().st_mtime < MAX_AGE:
            data = json.loads(CACHE.read_text())
        if data is None:
            r = requests.get(URL, params={'limit': 5000, 'convert': 'USD'},
                             headers={'X-CMC_PRO_API_KEY': self.key, 'Accept': 'application/json'}, timeout=30)
            body = r.json()
            if r.status_code != 200:
                raise RuntimeError(body.get('status', {}).get('error_message', r.status_code))
            data = [{'symbol': c['symbol'].upper(), 'name': c['name'], 'rank': c.get('cmc_rank'),
                     'cap': (c.get('quote', {}).get('USD') or {}).get('market_cap')} for c in body['data']]
            CACHE.parent.mkdir(parents=True, exist_ok=True)
            CACHE.write_text(json.dumps(data))
        # Several coins can share a ticker; keep the biggest (lowest rank), the one a channel most likely means.
        for c in sorted(data, key=lambda c: c['rank'] or 10**9, reverse=True):
            self.by_symbol[c['symbol']] = c
        self.status = f'CoinMarketCap: {len(data):,} coins loaded (market cap as of today)'

    def tag(self, symbol: str) -> dict:
        if not self.key or not self.by_symbol:
            return {'mcap_now_usd': None, 'cmc_rank': None, 'size_now': 'unknown'}
        c = self.by_symbol.get(symbol.upper().removeprefix('1000'))
        cap = c['cap'] if c else None
        return {'mcap_now_usd': round(cap) if cap else None, 'cmc_rank': c['rank'] if c else None,
                'size_now': size_class(cap)}
