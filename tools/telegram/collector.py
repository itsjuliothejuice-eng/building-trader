"""
Telegram collector: saves every message from your crypto groups and channels
into data/telegram/telegram.db. READ ONLY: it never sends, joins or reacts.

Setup (once):
  1. Get api_id and api_hash at https://my.telegram.org -> API development tools.
  2. Add them to .env in the repo root (git-ignored, never share them):
       TELEGRAM_API_ID=1234567
       TELEGRAM_API_HASH=0123456789abcdef0123456789abcdef
  3. Copy tools/telegram/channels.example.yaml to tools/telegram/channels.yaml
     and list your groups (or leave `include: all`).
  4. pip install -r tools/telegram/requirements.txt
  5. python tools/telegram/collector.py
     The first run asks for your phone number and the login code Telegram sends you.

What it does:
  - Backfills history (default 90 days) for each chat, then keeps listening live.
  - Saves the FIRST version of each message and every later edit separately,
    so a channel quietly changing an entry price or adding ✅ is caught.
  - Records deletions, so deleted losing calls are counted.
  - On restart it catches up on anything missed while it was off.

The login session file (data/telegram/collector.session) gives full access to
your Telegram account. It is git-ignored. Never copy or share it.
"""

import argparse
import asyncio
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path

import yaml
from dotenv import load_dotenv
from telethon import TelegramClient, events
from telethon.tl.types import Channel, Chat
from telethon.utils import get_peer_id

import store

HERE = Path(__file__).resolve().parent
CATCH_UP_SECONDS = 15 * 60
ROOT = HERE.parents[1]
load_dotenv(ROOT / '.env')
logging.basicConfig(level=logging.INFO, format='%(asctime)s %(message)s')
log = logging.getLogger('collector')


def load_config() -> dict:
    path = HERE / 'channels.yaml'
    if not path.exists():
        path = HERE / 'channels.example.yaml'
    return yaml.safe_load(path.read_text()) or {}


def wanted(entity, cfg) -> bool:
    include = cfg.get('include', 'all')
    exclude = {str(x).lower().lstrip('@') for x in cfg.get('exclude') or []}
    names = {str(entity.id), (getattr(entity, 'username', None) or '').lower(),
             (getattr(entity, 'title', None) or '').lower()}
    if names & exclude:
        return False
    if include == 'all':
        return True
    inc = {str(x).lower().lstrip('@').replace('https://t.me/', '') for x in include}
    return bool(names & inc)


def row_from(msg, chat, backfilled: bool) -> dict:
    return dict(
        chat_id=get_peer_id(chat), msg_id=msg.id,
        chat_title=getattr(chat, 'title', None),
        chat_username=getattr(chat, 'username', None),
        date=msg.date, text=msg.message or '',
        reply_to=msg.reply_to.reply_to_msg_id if msg.reply_to else None,
        has_media=msg.media is not None, views=getattr(msg, 'views', None),
        backfilled=backfilled, edit_date=msg.edit_date,
    )


async def backfill(client, con, chat, days: int, quiet: bool = False, older: bool = False):
    """Fetch messages newer than what we have; with older=True also reach back to `days` ago."""
    since = datetime.now(timezone.utc) - timedelta(days=days)
    chat_id = get_peer_id(chat)
    n = 0
    async for msg in client.iter_messages(chat, min_id=store.last_msg_id(con, chat_id)):
        if msg.date < since:
            break
        n += store.save_new(con, **row_from(msg, chat, backfilled=True))
    oldest = store.first_msg_id(con, chat_id)
    if older and oldest > 1:
        async for msg in client.iter_messages(chat, offset_id=oldest):   # walks backwards from our oldest
            if msg.date < since:
                break
            n += store.save_new(con, **row_from(msg, chat, backfilled=True))
    if n or not quiet:
        log.info(f'backfilled {n:5} messages  {getattr(chat, "title", chat.id)}')


async def main(days: int, no_live: bool):
    api_id, api_hash = os.getenv('TELEGRAM_API_ID'), os.getenv('TELEGRAM_API_HASH')
    if not api_id or not api_hash:
        raise SystemExit('Set TELEGRAM_API_ID and TELEGRAM_API_HASH in .env (see top of this file).')

    cfg = load_config()
    con = store.connect()
    store.DATA_DIR.mkdir(parents=True, exist_ok=True)
    client = TelegramClient(str(store.DATA_DIR / 'collector'), int(api_id), api_hash)
    await client.start()

    chats = {}
    async for d in client.iter_dialogs():
        if isinstance(d.entity, (Channel, Chat)) and wanted(d.entity, cfg):
            chats[get_peer_id(d.entity)] = d.entity  # marked id, same as event.chat_id
    log.info(f'watching {len(chats)} chats')

    days = days or cfg.get('backfill_days', 90)
    log.info(f'history: going back {days} days')
    for chat in chats.values():
        await backfill(client, con, chat, days, older=True)

    if no_live:
        return

    @client.on(events.NewMessage(chats=list(chats)))
    async def on_new(ev):
        chat = chats.get(ev.chat_id) or await ev.get_chat()
        store.save_new(con, **row_from(ev.message, chat, backfilled=False))

    @client.on(events.MessageEdited(chats=list(chats)))
    async def on_edit(ev):
        chat = chats.get(ev.chat_id) or await ev.get_chat()
        if not store.save_new(con, **row_from(ev.message, chat, backfilled=True)):
            store.save_edit(con, chat_id=get_peer_id(chat), msg_id=ev.message.id,
                            text=ev.message.message or '', edit_date=ev.message.edit_date)

    @client.on(events.MessageDeleted())
    async def on_delete(ev):
        # Channels report their id; small groups don't, so those deletions are skipped.
        if ev.chat_id and ev.chat_id in chats:
            for mid in ev.deleted_ids:
                store.save_deletion(con, chat_id=ev.chat_id, msg_id=mid)

    async def catch_up_loop():
        # Live events can be missed while the laptop sleeps or the network drops.
        # Every 15 minutes, re-fetch anything newer than what we have.
        while True:
            await asyncio.sleep(CATCH_UP_SECONDS)
            for chat in list(chats.values()):
                try:
                    await backfill(client, con, chat, days, quiet=True)
                except Exception as err:
                    log.warning(f'catch-up failed for {getattr(chat, "title", chat.id)}: {err}')

    asyncio.get_running_loop().create_task(catch_up_loop())
    log.info('live: listening for new messages, edits and deletions (Ctrl+C to stop)')
    await client.run_until_disconnected()


if __name__ == '__main__':
    ap = argparse.ArgumentParser()
    ap.add_argument('--days', type=int, help='days of history to fetch (overrides backfill_days in channels.yaml)')
    ap.add_argument('--no-live', action='store_true', help='backfill/catch up, then exit')
    a = ap.parse_args()
    asyncio.run(main(a.days, a.no_live))
