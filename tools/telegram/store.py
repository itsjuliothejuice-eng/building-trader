"""SQLite storage shared by the collector, extractor and scorer."""

import sqlite3
from datetime import datetime, timezone
from pathlib import Path

DATA_DIR = Path(__file__).resolve().parents[2] / 'data' / 'telegram'
DB_PATH = DATA_DIR / 'telegram.db'

SCHEMA = """
CREATE TABLE IF NOT EXISTS messages (
    chat_id        INTEGER NOT NULL,
    msg_id         INTEGER NOT NULL,
    chat_title     TEXT,
    chat_username  TEXT,
    date_utc       TEXT NOT NULL,     -- when the channel posted it
    first_seen_utc TEXT NOT NULL,     -- when we first saw it
    backfilled     INTEGER NOT NULL,  -- 1 = fetched from history, so earlier edits are invisible
    text_first     TEXT,              -- text as first seen
    text_latest    TEXT,
    edit_count     INTEGER DEFAULT 0,
    last_edit_utc  TEXT,
    reply_to       INTEGER,
    has_media      INTEGER,
    views          INTEGER,
    PRIMARY KEY (chat_id, msg_id)
);
CREATE TABLE IF NOT EXISTS edits (
    chat_id INTEGER, msg_id INTEGER, seen_utc TEXT, edit_date_utc TEXT, text TEXT
);
CREATE TABLE IF NOT EXISTS deletions (
    chat_id INTEGER, msg_id INTEGER, seen_utc TEXT
);
CREATE TABLE IF NOT EXISTS candles (
    exchange TEXT, symbol TEXT, ts INTEGER, open REAL, high REAL, low REAL, close REAL,
    PRIMARY KEY (exchange, symbol, ts)
);
"""


def now_utc() -> str:
    return datetime.now(timezone.utc).isoformat(timespec='seconds')


def iso(dt) -> str | None:
    if dt is None:
        return None
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc).isoformat(timespec='seconds')


def connect(path: Path = DB_PATH) -> sqlite3.Connection:
    path.parent.mkdir(parents=True, exist_ok=True)
    con = sqlite3.connect(path)
    con.row_factory = sqlite3.Row
    con.executescript(SCHEMA)
    return con


def save_new(con, *, chat_id, msg_id, chat_title, chat_username, date, text,
             reply_to, has_media, views, backfilled, edit_date=None):
    """Insert a message the first time we see it. Never overwrites text_first."""
    cur = con.execute(
        """INSERT OR IGNORE INTO messages
           (chat_id, msg_id, chat_title, chat_username, date_utc, first_seen_utc, backfilled,
            text_first, text_latest, last_edit_utc, reply_to, has_media, views)
           VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)""",
        (chat_id, msg_id, chat_title, chat_username, iso(date), now_utc(), int(backfilled),
         text, text, iso(edit_date), reply_to, int(bool(has_media)), views))
    con.commit()
    return cur.rowcount == 1


def save_edit(con, *, chat_id, msg_id, text, edit_date):
    row = con.execute('SELECT text_latest FROM messages WHERE chat_id=? AND msg_id=?',
                      (chat_id, msg_id)).fetchone()
    if row is None or row['text_latest'] == text:
        return False
    con.execute('INSERT INTO edits VALUES (?,?,?,?,?)', (chat_id, msg_id, now_utc(), iso(edit_date), text))
    con.execute("""UPDATE messages SET text_latest=?, edit_count=edit_count+1, last_edit_utc=?
                   WHERE chat_id=? AND msg_id=?""", (text, iso(edit_date), chat_id, msg_id))
    con.commit()
    return True


def save_deletion(con, *, chat_id, msg_id):
    con.execute('INSERT INTO deletions VALUES (?,?,?)', (chat_id, msg_id, now_utc()))
    con.commit()


def last_msg_id(con, chat_id) -> int:
    row = con.execute('SELECT MAX(msg_id) m FROM messages WHERE chat_id=?', (chat_id,)).fetchone()
    return row['m'] or 0
