"""
Turn Telegram messages into structured trade calls.

Each message is classified as:
  CALL        a trade idea posted BEFORE the move: ticker plus direction,
              entry, targets or stop
  RESULT      a victory lap posted AFTER the move ("✅", "profit", "It was $ZRO")
  COMMENTARY  mentions a coin with levels but no actionable call
  OTHER       everything else (ads, VIP sales, chat)

Parsing is plain pattern matching, so it's free, fast and repeatable. Messages it
can't parse stay in the database for Claude to review by hand.
"""

import json
import re
from dataclasses import dataclass, field, asdict

NOT_TICKERS = {
    'USD', 'USDT', 'USDC', 'BUSD', 'FDUSD', 'EUR', 'VIP', 'TP', 'SL', 'ROI', 'PNL', 'ATH', 'ATL',
    'CEO', 'FOMC', 'CPI', 'ETF', 'SEC', 'FED', 'API', 'NFT', 'DCA', 'TA', 'OTC', 'DM', 'LONG',
    'SHORT', 'BUY', 'SELL', 'ENTRY', 'TARGET', 'STOP', 'LOSS', 'SPOT', 'PERP', 'UTC', 'EST', 'AM', 'PM',
}
NUM = r'(\d+(?:[.,]\d+)?)'

RE_CASHTAG = re.compile(r'[$#]([A-Za-z][A-Za-z0-9]{1,14})\b')
RE_PAIR = re.compile(r'\b([A-Z][A-Z0-9]{1,14})\s*/\s*(?:USDT|USDC|USD|BTC)\b')
RE_COINFIELD = re.compile(r'\b(?:coin|pair|asset)\s*[:\-]\s*\$?([A-Za-z][A-Za-z0-9]{1,14})', re.I)
RE_ENTRY = re.compile(r'\b(?:entry|entries|buy\s*(?:zone|area|price|between)?|entry\s*zone)\s*[:\-@]?\s*' + NUM +
                      r'(?:\s*(?:-|–|to|~|and)\s*' + NUM + r')?', re.I)
RE_TARGET = re.compile(r'\b(?:target|tp)(?:\s*\d{1,2}(?=\s*[:\-=)]|\s+\d))?\s*[:\-=]?\s*' + NUM, re.I)
RE_TARGETS_LIST = re.compile(r'\btargets?\s*[:\-]\s*((?:' + NUM + r'\s*(?:,|-|–|/|\s)\s*)+' + NUM + ')', re.I)
RE_STOP = re.compile(r'\b(?:stop[\s-]*loss|stoploss|sl|stop|invalidation)\s*[:\-=@]?\s*' + NUM, re.I)
RE_LEV = re.compile(r'(?:\b(?:leverage|lev)\s*[:\-]?\s*(?:cross|isolated)?\s*(\d{1,3})\s*x?)|(?:\(?\s*(\d{1,3})\s*(?:-|–)?\s*(\d{1,3})?\s*x\s*\)?)', re.I)
RE_LONG = re.compile(r'\b(long(?![\s-]*term)|buy(?:ing)?|bullish)\b', re.I)
RE_SHORT = re.compile(r'\b(short(?![\s-]*term)|sell(?![\s-]*off)|bearish)\b', re.I)
RE_RESULT = re.compile(r'✅|🎯|\b(profit|hit|reached|smashed|printing|printed|booked|done|results?|'
                       r'it was|knew|pumped|x\s*gains?|gains?)\b', re.I)
RE_PCT = re.compile(r'\d+(?:\.\d+)?\s*%')
RE_STRUCT = re.compile(r'\b(entry|target\s*\d|tp\s*\d|stop[\s-]*loss|sl\s*[:\-])', re.I)


@dataclass
class Parsed:
    kind: str
    symbol: str | None = None
    direction: str | None = None
    entry_low: float | None = None
    entry_high: float | None = None
    targets: list = field(default_factory=list)
    stop: float | None = None
    leverage: int | None = None
    tickers: list = field(default_factory=list)

    def row(self):
        d = asdict(self)
        d['targets'] = json.dumps(d['targets'])
        d['tickers'] = json.dumps(d['tickers'])
        return d


def _num(s):
    return float(s.replace(',', '.')) if s else None


def tickers(text: str) -> list:
    found = []
    for rx in (RE_COINFIELD, RE_PAIR, RE_CASHTAG):
        for m in rx.findall(text):
            t = m.upper()
            if t not in NOT_TICKERS and not t.isdigit() and t not in found:
                found.append(t)
    return found


def parse(text: str, chat_title: str = '') -> Parsed:
    text = text or ''
    ts = tickers(text)
    if not ts:
        return Parsed('OTHER')

    targets = [_num(x) for x in RE_TARGET.findall(text)]
    if not targets:
        m = RE_TARGETS_LIST.search(text)
        if m:
            targets = [_num(x) for x in re.findall(NUM, m.group(1))]
    em = RE_ENTRY.search(text)
    entry_low, entry_high = (_num(em.group(1)), _num(em.group(2))) if em else (None, None)
    if entry_low and entry_high and entry_high < entry_low:
        entry_low, entry_high = entry_high, entry_low
    sm = RE_STOP.search(text)
    stop = _num(sm.group(1)) if sm else None

    lev = None
    for m in RE_LEV.finditer(text):
        vals = [int(v) for v in m.groups() if v]
        if vals and max(vals) <= 125:
            lev = max(vals)
            break

    longw, shortw = bool(RE_LONG.search(text)), bool(RE_SHORT.search(text))
    direction = 'long' if longw and not shortw else 'short' if shortw and not longw else None
    if direction is None and targets and (entry_low or stop):
        ref = entry_low or stop
        direction = 'long' if targets[0] > ref else 'short'
    if direction is None and re.search(r'direction\s*[:\-]\s*long', text, re.I):
        direction = 'long'

    structured = bool(RE_STRUCT.search(text)) and bool(entry_low or stop or len(targets) >= 2)
    looks_result = ('result' in chat_title.lower()
                    or bool(RE_RESULT.search(text)) and (bool(RE_PCT.search(text)) or '✅' in text))

    if structured:
        kind = 'CALL'          # a structured signal stays a CALL even after ✅ are edited in
    elif looks_result:
        kind = 'RESULT'
    elif direction:
        kind = 'CALL'
    elif re.search(NUM, text):
        kind = 'COMMENTARY'
    else:
        kind = 'OTHER'

    return Parsed(kind, ts[0], direction, entry_low, entry_high, targets, stop, lev, ts)


def extract_all(con):
    """(Re)build the calls table from every stored message. Classifies on the FIRST text seen."""
    con.execute('DROP TABLE IF EXISTS calls')
    con.execute("""CREATE TABLE calls (
        chat_id INTEGER, msg_id INTEGER, chat_title TEXT, posted_utc TEXT, backfilled INTEGER,
        edited_levels INTEGER, kind TEXT, symbol TEXT, direction TEXT, entry_low REAL,
        entry_high REAL, targets TEXT, stop REAL, leverage INTEGER, tickers TEXT,
        PRIMARY KEY (chat_id, msg_id))""")
    rows = con.execute('SELECT * FROM messages').fetchall()
    n = 0
    for r in rows:
        first = parse(r['text_first'], r['chat_title'] or '')
        if first.kind == 'OTHER':
            continue
        latest = parse(r['text_latest'], r['chat_title'] or '') if r['edit_count'] else first
        edited = int((first.entry_low, first.stop, first.targets) != (latest.entry_low, latest.stop, latest.targets))
        d = first.row()
        con.execute("""INSERT INTO calls VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                    (r['chat_id'], r['msg_id'], r['chat_title'], r['date_utc'], r['backfilled'], edited,
                     d['kind'], d['symbol'], d['direction'], d['entry_low'], d['entry_high'],
                     d['targets'], d['stop'], d['leverage'], d['tickers']))
        n += 1
    con.commit()
    return n


if __name__ == '__main__':
    import store
    con = store.connect()
    n = extract_all(con)
    for k, c in con.execute('SELECT kind, COUNT(*) c FROM calls GROUP BY kind'):
        print(f'{k:11} {c}')
    print(f'{n} messages classified')
