"""
End-to-end check with made-up messages about real coins, scored against real
prices (needs internet). Run: python tools/telegram/test_pipeline.py
"""
import csv, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import store, score

tmp = Path(tempfile.mkdtemp())
store.DB_PATH, score.REPORTS = tmp / 'telegram.db', tmp / 'reports'
_connect = store.connect
store.connect = lambda path=store.DB_PATH: _connect(path)
con = store.connect()
D = lambda s: datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


def msg(chat, title, mid, when, text, backfilled=False):
    store.save_new(con, chat_id=chat, msg_id=mid, chat_title=title, chat_username=None, date=D(when),
                   text=text, reply_to=None, has_media=False, views=1, backfilled=backfilled)


msg(-1, 'Signals A', 1, '2026-09-10T14:20', 'COIN: $SOL/USDT (5x)\nDirection: LONG\nEntry: 99 - 101\nTarget 1: 105\nTarget 2: 110\nStop loss: 95')
msg(-1, 'Signals A', 2, '2026-09-12T09:05', 'COIN: $ETH/USDT\nLONG\nEntry 2500\nTarget 1: 2600\nStop loss: 2450')
store.save_edit(con, chat_id=-1, msg_id=2, text='COIN: $ETH/USDT\nLONG\nEntry 2500\nTarget 1: 2600 ✅\nStop loss: 2300',
                edit_date=D('2026-09-15T00:00'))
msg(-1, 'Signals A', 3, '2026-09-14T18:00', 'Short $DOGE here, SL 0.095, TP1 0.08')
msg(-1, 'Signals A', 4, '2026-09-20T10:00', 'Target 1 hit on $SOL ✅ 35% profit (10x)')
msg(-1, 'Signals A', 6, '2026-09-15T10:00', 'Buy $SOL entry 140, target 150, stop 130')   # wrong prices
store.save_deletion(con, chat_id=-1, msg_id=5)
msg(-2, 'Yaga Calls Result', 1, '2026-09-23T09:40', '$ZRO 🔥🔥 Enjoy the day')
msg(-2, 'Yaga Calls Result', 2, '2026-09-26T12:00', 'Buy $BULLA now, entry 0.094, target 0.11', backfilled=True)

score.main()
calls = {(r['chat_title'], r['posted_utc'][:10], r['symbol']): r for r in csv.DictReader(open(tmp / 'reports/calls.csv'))}
cards = {r['channel']: r for r in csv.DictReader(open(tmp / 'reports/scorecard.csv'))}
assert calls[('Signals A', '2026-09-15', 'SOL')]['status'] == 'price_mismatch'
assert calls[('Signals A', '2026-09-12', 'ETH')]['edited_levels'] == '1'
assert calls[('Yaga Calls Result', '2026-09-26', 'BULLA')]['on_coinbase'] == 'False'
assert ('Signals A', '2026-09-20', 'SOL') not in calls, 'victory post scored as a call'
assert cards['Signals A']['deleted_msgs'] == '1'
assert cards['Yaga Calls Result']['unbacked_results'] == '1'
assert all(r['status'] in ('scored', 'price_mismatch') for r in calls.values()), calls
print((tmp / 'reports/scorecard.md').read_text())
print('pipeline test passed')
