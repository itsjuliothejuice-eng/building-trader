# Handoff: cloud session → local session (2026-10-13)

Read `CLAUDE.md` first (rules, setup, what's running), then `docs/RESEARCH_LOG.md` (every study and its result).
This file is the short version of where things stand, for a session that starts without the earlier conversation.

## Where things stand

- **Money:** all of it stays in the bank. Nothing goes live until a system passes every gate **and** 60+ days of paper trading.
- **The only approved system:** the BTC+ETH trend system (Studies 1–3): spot, 2/3 size, $5,000 fake money.
  It's paper trading on this laptop via `tools/paper/paper_trader.py` (`run_paper.bat`). Started 2026-09-29.
- **Second paper test (Study 10):** `tools/hyperliquid/copy_paper.py` follows 20 fixed Hyperliquid traders hourly with $5,000 fake money.
  First check ran 2026-10-11 ($4,996.29). It needs `tools\hyperliquid\run_copy.bat` running (and a `shell:startup` shortcut) to keep checking hourly.
- **Telegram collector:** `tools/telegram/collector.py` (`run_collector.bat`) keeps saving ~30 channels. Rescore around December with `--days 60`.
- **Coinbase:** a View-only key in `.env`; `python tools/coinbase_account.py` reads balances, fee tier and fills. Never set up a Trade key.

## Upcoming reviews

| When | What | How |
|---|---|---|
| Twice a month | Health check of both paper tests | `python tools/paper/paper_trader.py --report` and `python tools/hyperliquid/copy_paper.py --report`; confirm both loops are still running |
| ~2026-12-01 | 60-day review of the BTC+ETH paper system | Compare `data/paper/daily.csv` with what the backtest would have done over the same days (RESEARCH_LOG, "Paper trader build") |
| 2026-12-09 | Study 10 verdict | The four pre-registered criteria in RESEARCH_LOG, Study 10 |
| December | Telegram rescore | `python tools/telegram/score.py --days 60` |

## What's been ruled out (don't re-test without a new reason)

37 tested versions across 10 studies. Everything short-term failed:
- daily trading
- dip-buying (Simon Ree's Bounce 2.0)
- spreading the trend rules across altcoins
- Telegram channels
- copying Polymarket wallets
- Polymarket favorites and long shots
- Kalshi long shots
- using Polymarket crypto bets as a Coinbase signal

Only slow BTC+ETH trend-following held up. Hyperliquid's top traders came closest of the copy ideas (Study 9), which is why Study 10 exists.
Each new trial raises the bar for the next one (the deflated Sharpe counts all of them), so prefer waiting for the paper results over new studies.

## How to work in this repo

- **Branch:** `claude/admiring-euler-9hzeli` holds all the work (PR #1 to `main`). Run `git pull` before starting.
- **New studies:** pre-register in RESEARCH_LOG before running, use `tools/quantcheck.py`, and `log_trial()` every variant.
- **Data:** `data/` and `Data/` are git-ignored. The laptop's `data/paper/` and `data/copy/` are the real paper records; never delete them.
- **Secrets:** never print `.env` or `data/telegram/*.session`.
- **The user:** Julio, Equipment and Workforce Coordinator at BGW (Port of Brownsville). He's also building the `bgw-daily-update` skill
  for fleet work, which is separate from this repo.
