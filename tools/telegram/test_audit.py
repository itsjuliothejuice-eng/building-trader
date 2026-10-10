"""Audit test: a channel that announces its winner and goes quiet on losers (needs internet for prices).
Run: python tools/telegram/test_audit.py"""
import csv, sys, tempfile
from datetime import datetime, timezone
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
import store, score

tmp = Path(tempfile.mkdtemp())
store.DB_PATH = tmp / 'telegram.db'
_connect = store.connect
store.connect = lambda path=store.DB_PATH: _connect(path)
import audit_channel as audit
audit.REPORTS = score.REPORTS = tmp / 'reports'
con = store.connect()
D = lambda s: datetime.fromisoformat(s).replace(tzinfo=timezone.utc)


def msg(mid, when, text):
    store.save_new(con, chat_id=-7, msg_id=mid, chat_title='Evening Test Group', chat_username=None, date=D(when),
                   text=text, reply_to=None, has_media=False, views=1, backfilled=False)


msg(1, '2026-09-10T14:20', 'COIN: $SOL/USDT\nLONG\nEntry: 99 - 101\nTarget 1: 105\nTarget 2: 110\nStop loss: 95')
msg(2, '2026-09-12T09:05', 'COIN: $ETH/USDT\nLONG\nEntry 2500\nTarget 1: 2600\nStop loss: 2450')
msg(3, '2026-09-14T18:00', 'Short $DOGE here, SL 0.095, TP1 0.08')
msg(4, '2026-09-16T12:00', '$ETH target 1 hit ✅ 40% profit (20x)')
msg(5, '2026-09-20T12:00', '$XRP smashed it 🔥 55% profit (10x) ✅')        # never called

audit.main('Evening Test')
rows = list(csv.DictReader(open(tmp / 'reports' / 'audit_Evening_Test.csv')))
by = {r['symbol']: r for r in rows}
assert by['ETH']['announced'] == 'True' and '40.0' in by['ETH']['claims (pct, lev, says_loss)']
assert by['SOL']['announced'] == 'False' and by['DOGE']['announced'] == 'False'
report = (tmp / 'reports' / 'audit_Evening_Test.md').read_text()
assert 'Result posts for coins with no call in the 14 days before: 1' in report
print('\naudit test passed')
