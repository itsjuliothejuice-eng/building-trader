"""
Audit one channel's own track record against what actually happened.

    python tools/telegram/audit_channel.py "Evening Trader"
    python tools/telegram/audit_channel.py "Evening Trader" --days 90

For every call the channel made, it checks:
  - what really happened (from real prices, the same method as the scorecard)
  - whether the channel ever posted a result for it (within 14 days, same coin)
  - what that result post claimed, and with how much leverage

Then it compares the calls they announced with the ones they went quiet on.
The classic trick is that winners get a victory post and losers get silence, so a
"transparent" results thread can show 80% wins from a coin-flip channel.

Writes reports/telegram/audit_<channel>.md and .csv (git-ignored).
"""

import argparse
import csv
import re
import statistics as st
from datetime import datetime, timedelta, timezone
from pathlib import Path

import store
from extract import extract_all
from score import Prices, score_call, REPORTS

RE_PCT = re.compile(r'([+-]?\d{1,4}(?:\.\d+)?)\s*%')
RE_LEV = re.compile(r'(\d{1,3})\s*x\b', re.I)
RE_LOSS = re.compile(r'\b(stop(?:ped)?[\s-]*(?:loss|out|hit)|sl\s*hit|loss|closed?\s+(?:in|at)\s+(?:loss|minus))\b', re.I)
WINDOW = timedelta(days=14)


def claim_of(text):
    """(claimed %, leverage, says_loss) from a result post."""
    pcts = [float(p) for p in RE_PCT.findall(text or '')]
    lev = [int(x) for x in RE_LEV.findall(text or '') if 1 < int(x) <= 125]
    return (max(pcts, key=abs) if pcts else None, max(lev) if lev else None, bool(RE_LOSS.search(text or '')))


def mean(xs):
    return round(st.mean(xs), 2) if xs else None


def main(name, days=None):
    con = store.connect()
    extract_all(con)
    chats = con.execute('SELECT DISTINCT chat_id, chat_title FROM messages WHERE chat_title LIKE ?', (f'%{name}%',)).fetchall()
    if not chats:
        raise SystemExit(f'No channel matching "{name}". Check the spelling in reports/telegram/scorecard.md.')
    if len(chats) > 1:
        print('Several channels match; auditing all of them together:', ', '.join(c['chat_title'] for c in chats))
    ids = [c['chat_id'] for c in chats]
    title = chats[0]['chat_title']
    since = (datetime.now(timezone.utc) - timedelta(days=days)).isoformat() if days else ''
    q = f"SELECT * FROM calls WHERE chat_id IN ({','.join('?' * len(ids))}) AND posted_utc >= ? ORDER BY posted_utc"

    calls = [dict(r) for r in con.execute(q, (*ids, since)) if r['kind'] == 'CALL']
    # Result posts: anything classified RESULT, plus edits of the call itself that add results (✅ / % profit)
    results = [dict(r) for r in con.execute(q, (*ids, since)) if r['kind'] == 'RESULT']
    texts = {(r['chat_id'], r['msg_id']): r for r in con.execute(
        f"SELECT chat_id, msg_id, text_first, text_latest FROM messages WHERE chat_id IN ({','.join('?' * len(ids))})", ids)}

    px, now_ms = Prices(con), int(datetime.now(timezone.utc).timestamp() * 1000)
    print(f'auditing {len(calls)} calls and {len(results)} result posts from {title}...')
    for c in calls:
        try:
            c.update(score_call(c, px, now_ms))
        except Exception as err:
            c['status'] = f'error: {type(err).__name__}'
        t = datetime.fromisoformat(c['posted_utc'])
        c['claims'] = []
        for r in results:
            rt = datetime.fromisoformat(r['posted_utc'])
            if r['symbol'] == c['symbol'] and t < rt <= t + WINDOW:
                c['claims'].append(claim_of(texts[(r['chat_id'], r['msg_id'])]['text_latest']))
        latest = texts[(c['chat_id'], c['msg_id'])]['text_latest']
        if latest != texts[(c['chat_id'], c['msg_id'])]['text_first'] and ('✅' in latest or RE_PCT.search(latest)):
            c['claims'].append(claim_of(latest))           # the call was edited to show a result
        c['announced'] = bool(c['claims'])

    scored = [c for c in calls if c.get('status') == 'scored' and 'net_7d' in c]
    ann = [c for c in scored if c['announced']]
    quiet = [c for c in scored if not c['announced']]
    stopped = [c for c in scored if c.get('outcome') == 'stop']
    claims = [cl for c in ann for cl in c['claims'] if cl[0] is not None]
    unmatched = [r for r in results if not any(
        r['symbol'] == c['symbol'] and datetime.fromisoformat(c['posted_utc']) < datetime.fromisoformat(r['posted_utc'])
        <= datetime.fromisoformat(c['posted_utc']) + WINDOW for c in calls)]

    lines = [f'# Audit: {title}', '',
             f'{len(calls)} calls, {len(scored)} with 7 days of real prices; {len(results)} result posts.', '',
             '| | Calls | Real 7-day result (avg, after fees, no leverage) | Real win rate (7d) |',
             '|---|---|---|---|',
             f'| **Announced** with a result post | {len(ann)} | {mean([c["net_7d"] for c in ann])}% | '
             f'{round(100 * sum(c["net_7d"] > 0 for c in ann) / len(ann)) if ann else "-"}% |',
             f'| **Never mentioned again** | {len(quiet)} | {mean([c["net_7d"] for c in quiet])}% | '
             f'{round(100 * sum(c["net_7d"] > 0 for c in quiet) / len(quiet)) if quiet else "-"}% |',
             f'| **All calls** | {len(scored)} | {mean([c["net_7d"] for c in scored])}% | '
             f'{round(100 * sum(c["net_7d"] > 0 for c in scored) / len(scored)) if scored else "-"}% |', '',
             '**What they claimed vs reality**', '',
             f'- Calls that hit their stop: {len(stopped)}. Of those, a result post admitting the loss: '
             f'{sum(1 for c in stopped if any(cl[2] for cl in c["claims"]))}; never mentioned: '
             f'{sum(1 for c in stopped if not c["announced"])}.',
             f'- Average % claimed in result posts: {mean([cl[0] for cl in claims])}%; leverage mentioned in '
             f'{sum(1 for cl in claims if cl[1])} of {len(claims)} claims (median {st.median([cl[1] for cl in claims if cl[1]]) if any(cl[1] for cl in claims) else "-"}x).',
             f'- Same announced calls, measured without leverage after fees: {mean([c["net_7d"] for c in ann])}% on average.',
             f'- Result posts for coins with no call in the 14 days before: {len(unmatched)}.', '',
             '**How to read it:** if "announced" calls look far better than "never mentioned" ones, the results thread is',
             'showing the best part of the record, not all of it. Compare their thread\'s win rate to "All calls".',
             'Calls parsed only from text; calls posted as images can be missed. Edits and deletions before the',
             'collector started are invisible.']
    REPORTS.mkdir(parents=True, exist_ok=True)
    slug = re.sub(r'[^A-Za-z0-9]+', '_', name).strip('_')
    (REPORTS / f'audit_{slug}.md').write_text('\n'.join(lines), encoding='utf-8')
    with (REPORTS / f'audit_{slug}.csv').open('w', newline='', encoding='utf-8') as f:
        w = csv.writer(f)
        w.writerow(['posted_utc', 'symbol', 'direction', 'status', 'net_24h', 'net_7d', 'outcome', 'announced', 'claims (pct, lev, says_loss)'])
        for c in calls:
            w.writerow([c['posted_utc'], c['symbol'], c['direction'], c.get('status'), c.get('net_24h'), c.get('net_7d'),
                        c.get('outcome'), c['announced'], c['claims']])
    print('\n'.join(lines))
    print(f'\nwrote {REPORTS / f"audit_{slug}.md"} and .csv')


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('channel', help='part of the channel name, e.g. "Evening Trader"')
    ap.add_argument('--days', type=int, help='only calls from the last N days')
    a = ap.parse_args()
    main(a.channel, a.days)
