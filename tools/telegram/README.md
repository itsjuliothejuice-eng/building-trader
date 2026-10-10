# Telegram call tracker

Collects every message from your crypto Telegram groups, extracts the trade calls,
and grades each channel on what prices actually did afterwards.

```
collector.py  ->  data/telegram/telegram.db  ->  score.py  ->  reports/telegram/scorecard.md
(runs 24/7)       (messages, edits, deletions)   (on demand)   (read it, or ask Claude)
```

## One-time setup (Windows, PowerShell, from the repo folder)

1. `pip install -r tools/telegram/requirements.txt`
2. Go to https://my.telegram.org, log in, open **API development tools**, and create an app
   (any name). Copy the **api_id** and **api_hash** into `.env` in the repo folder:
   ```
   TELEGRAM_API_ID=1234567
   TELEGRAM_API_HASH=your_hash_here
   ```
   Never paste these into chat or commit them.
3. `copy tools\telegram\channels.example.yaml tools\telegram\channels.yaml` and add non-trading chats to `exclude`.
4. `python tools/telegram/collector.py` and enter your phone number and the code Telegram sends.
   It fetches a year of history (`backfill_days` in channels.yaml), then keeps listening. Leave the window open.

To run it automatically: double-click `tools\telegram\run_collector.bat`, or add it to
Task Scheduler with the trigger **At log on**.

## Optional: market-cap tags (CoinMarketCap)

Add your free key to `.env` as `CMC_API_KEY=...`. The scorecard then tags each call with the coin's market cap
**today** (the free plan has no history) and shows each channel's share of calls on coins under $100M. It refreshes
at most once a day (about 25 of the plan's ~10,000 monthly credits). Without a key, the column is just blank.

## Getting the scorecard

`python tools/telegram/score.py` (or `--days 30`), then open `reports/telegram/scorecard.md`.
Or just ask Claude in this repo: "score my Telegram channels".

## Audit one channel's own track record

```
python tools/telegram/audit_channel.py "Evening Trader"
```
Splits the channel's calls into ones they later announced with a result post and ones they never mentioned again,
measures both with real prices, and compares their claimed % (and leverage) with what actually happened.
Writes `reports/telegram/audit_<name>.md`. Use it before paying for any premium group.

## What the scorecard means

Each call is entered at the first hourly open **after** the post (you can't buy before you
read it). It is unleveraged and charged Coinbase's 2.5% round trip.

| Column | Why it matters |
|---|---|
| Mean 7d net, Worst 7d | The real edge after fees. Below 0 means following the channel loses money |
| Target before stop % | How often target 1 came first. High here with a negative mean = small wins, big losses |
| Pumped before call % | The coin rose >15% in the 24h *before* the post. Members may be the organizers' exit |
| Entry already gone % | The stated entry was unreachable by the time you could act |
| Results with no prior call | Victory posts for coins that were never called: hindsight marketing |
| Edited levels / Deleted | Rewriting or deleting calls after the fact (only seen for messages caught live) |
| Tradeable on your Coinbase % | Whether you could take the trade: longs on spot or a CDE perp, shorts only on a perp |
| Tiny coins (<$100M now) % | Calls on small, thin coins: prime pump-and-dump territory (needs `CMC_API_KEY`) |

A channel graded **WORTH TESTING** still has to pass `tools/quantcheck.py` before any money is involved.

## Privacy and safety

- `data/telegram/collector.session` is a **login key to your whole Telegram account**. It is
  git-ignored. Never copy, upload or share it. If it leaks, go to Telegram
  Settings > Devices and terminate the session.
- Messages and reports stay on your PC (`data/` and `reports/` are git-ignored).
- The collector is read-only: it never sends, joins, reacts or forwards.
- Delisted coins, and coins only on Binance, may show `no_price_data`. Binance blocks US connections.
