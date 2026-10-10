"""Offline checks for copy_paper.py (no network). Run: python tools/hyperliquid/test_copy_paper.py"""
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))
import copy_paper as cp

tmp = Path(tempfile.mkdtemp())
cp.DIR, cp.STATE = tmp, tmp / 'state.json'
cp.time.sleep = lambda s: None
A = cp.PICKS[0]['address']
cp.PICKS = [{'address': A}]                       # one trader -> the whole $5,000 is one slice
cp.FEE = cp.SLIP = cp.FUNDING_PER_DAY = 0.0
world = {'mids': {'BTC': '100', 'TNSR': '1'}, 'acct': '1000', 'pos': []}


def fake_info(body):
    if body['type'] == 'allMids':
        return world['mids']
    return {'marginSummary': {'accountValue': world['acct']},
            'assetPositions': [{'position': {'coin': c, 'szi': str(s)}} for c, s in world['pos']]}


cp.info = fake_info
eq = lambda: cp.slice_equity(cp.load_state()['slices'][A], world['mids'])

# 1. Trader is 50% long BTC (5 BTC x $100 on a $1,000 account) -> slice holds $2,500 of BTC
world['pos'] = [('BTC', 5)]
cp.run_once(verbose=False)
st = cp.load_state()
assert abs(st['slices'][A]['units']['BTC'] * 100 - 2500) < 1e-6, st
# 2. BTC +10% -> equity +$250 (no trade needed: drift is under 10% of the slice)
world['mids'] = {'BTC': '110', 'TNSR': '1'}
cp.run_once(verbose=False)
assert abs(eq() - 5250) < 1e-6, eq()
# 3. A coin Coinbase doesn't list is ignored, and leverage above 1x is scaled down to 1x
world['pos'] = [('BTC', 20), ('TNSR', 5000)]       # BTC 2.2x of the account, TNSR not copyable
cp.run_once(verbose=False)
st = cp.load_state()
assert 'TNSR' not in st['slices'][A]['units']
assert abs(st['slices'][A]['units']['BTC'] * 110 - eq()) < 1e-6   # exactly 1x
# 4. Trader closes -> we close
world['pos'] = []
cp.run_once(verbose=False)
assert cp.load_state()['slices'][A]['units'] == {}
# 5. Shorts are copied with the right sign
world['pos'] = [('BTC', -2)]                        # -22% of the account
cp.run_once(verbose=False)
assert cp.load_state()['slices'][A]['units']['BTC'] < 0
# 6. The -27% hard stop closes everything and halts
world['pos'] = [('BTC', 9)]                         # ~ 1x long (capped)
cp.run_once(verbose=False)
world['mids'] = {'BTC': '70', 'TNSR': '1'}
cp.run_once(verbose=False)
st = cp.load_state()
assert st['halted'] and st['slices'][A]['units'] == {}, st
print('all 6 checks passed')
