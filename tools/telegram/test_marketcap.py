"""Market-cap tag tests with a fake CoinMarketCap response (no key or internet needed).
Run: python tools/telegram/test_marketcap.py"""
import json, os, sys, tempfile
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import marketcap as mc

tmp = Path(tempfile.mkdtemp())
mc.CACHE = tmp / 'cmc_listings.json'
mc.CACHE.write_text(json.dumps([
    {'symbol': 'BTC', 'name': 'Bitcoin', 'rank': 1, 'cap': 1.6e12},
    {'symbol': 'SOL', 'name': 'Solana', 'rank': 6, 'cap': 6.0e10},
    {'symbol': 'ZRO', 'name': 'LayerZero', 'rank': 150, 'cap': 4.0e8},
    {'symbol': 'BULLA', 'name': 'Bulla', 'rank': 2900, 'cap': 3.1e6},
    {'symbol': 'ZRO', 'name': 'Some ZRO copycat', 'rank': 4800, 'cap': 2.0e4},   # ticker collision
    {'symbol': 'PEPE', 'name': 'Pepe', 'rank': 30, 'cap': 1.8e9},
]))

os.environ.pop('CMC_API_KEY', None)
mc.load_dotenv = lambda *a, **k: None                  # don't read the real .env in tests
none = mc.MarketCaps()
assert none.tag('BTC')['size_now'] == 'unknown' and 'no CMC_API_KEY' in none.status
print('ok   no key -> tags skipped, scorecard still works')

os.environ['CMC_API_KEY'] = 'test'
m = mc.MarketCaps()
assert m.tag('BTC')['size_now'] == 'large ($10B+)'
assert m.tag('ZRO')['size_now'] == 'small ($100M-1B)', 'ticker collision should pick the biggest coin'
assert m.tag('BULLA')['size_now'] == 'nano (<$10M)'
assert m.tag('1000PEPE')['size_now'] == 'mid ($1B-10B)'
assert m.tag('NOTACOIN')['size_now'] == 'not in top 5,000'
print('ok   size classes, ticker collisions, 1000-prefix, unknown coins')
print('all market-cap tests passed')
