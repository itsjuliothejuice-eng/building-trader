# Trading toolkit review: security and comparison

Reviewed 2026-09-27. Sources were the four uploaded zips: `ai-trading-claude-main`, `cbt-framework-main`, `claude-trading-skills-main` and `skill-algotrader-main`.

## How it was reviewed

- Listed every non-Markdown file in each package (scripts, installers, hooks, workflows).
- Searched all code for shell-outs (`subprocess`, `os.system`, `child_process`, `eval`/`exec`), `curl | sh`, encoded payloads, writes to `~/.ssh` or system files, and `sudo`.
- Pulled every hostname the code contacts, to look for unexpected destinations.
- Searched the Markdown prompts for injection wording ("ignore previous", "don't tell the user", permission bypasses).
- Read every installer and hook, plus each place that signs transactions or places orders.
- Byte-compiled every Python file (all OK) and ran the demo modes of the swap and sizing scripts.

## Security findings

**No malware, credential theft or hidden data exfiltration found.** Every host the code contacts is a legitimate market-data, exchange or blockchain endpoint: Solana RPC, Helius, Birdeye, DexScreener, CoinGecko, DefiLlama, Jupiter, Jito, Kalshi, Binance, NSE India, Zerodha, Telegram, Twilio and the npm registry. No prompt injection found in the skill or agent text.

These are the real risks, ranked:

| # | Package | Risk | Severity | What I did |
|---|---|---|---|---|
| 1 | cbt-framework | `templates/live/*_bot.py` place **real orders** on Binance, Bybit, Kraken and Hyperliquid when started with `mode='live'`. Paper maps to the exchange testnet. | High if misused | Paper is the default; `CLAUDE.md` forbids live mode without an explicit request |
| 2 | cbt-framework | "YOLO mode" skips confirmation steps in `/cbt:build` | Medium | Banned in `CLAUDE.md` |
| 3 | claude-trading-skills | `raptor-dex/raptor_swap.py`, `jito-bundles/build_bundle.py`, `solana-tx-building` and `dex-execution` sign and send Solana transactions using a `PRIVATE_KEY` env var when run without `--demo` | High if misused | Same rule; demo mode verified to send nothing |
| 4 | skill-algotrader | Generated bots can trade live on Zerodha (`--mode live`) using Kite keys from `.env` | High if misused | Same rule; `.env` is git-ignored |
| 5 | cbt-framework | The global installer (`bin/cbt-init.js`) edits `~/.claude/settings.json` to add a SessionStart hook that checks the npm registry on every session. It also writes MCP servers to `~/.claude/.mcp.json`, with the Alpha Vantage key **in the URL, in plain text**. `/cbt:update` runs `npx cbt-framework@latest`, which is unpinned remote code. | Medium (supply chain) | **Not run.** Hooks were left out, and the files were installed at project scope instead |
| 6 | ai-trading-claude | `install.sh`, when piped from curl, clones the GitHub repo live instead of using the reviewed copy | Low | **Not run.** Files were copied from the reviewed zip |
| 7 | all | Many scripts install third-party PyPI packages (ccxt, kiteconnect, solders and others) | Low | Install into a venv; pin versions if you go live |

**Marketing claims are unverified.** skill-algotrader advertises a "65%+ win rate" and "28x performance". Nothing in the package proves either. Treat them as sales copy.

## What each toolkit is for

| | ai-trading-claude | cbt-framework | claude-trading-skills | skill-algotrader |
|---|---|---|---|---|
| **Purpose** | Stock research reports | Strategy backtesting workflow → live bot | Large library of quant and crypto skills | Indian-equity bot playbook |
| **Markets** | US stocks | Crypto (CEX perps and spot) | Crypto/DeFi/Solana-heavy; generic quant; Kalshi/Polymarket | NSE India only |
| **Executes trades?** | No (research only) | Yes (live bots) | Some scripts (Solana swaps, bundles) | Yes (Zerodha) |
| **Size** | 16 skills, 5 agents | 22 commands, 4 agents | 68 skills, ~120 scripts | 1 skill, 2.8k lines of notes |
| **Data** | WebSearch | Exchange APIs (ccxt), optional Alpha Vantage/FRED | Many APIs, several needing keys | NSE site, Kite |
| **Quality** | Well-structured prompts; 6 skills lacked front-matter (fixed) | Most disciplined process: look-ahead-bias checks, state tracking, metrics engine | Broad and good for quant fundamentals; much is crypto-specific | Deep but narrow; useless outside India |
| **Trust risk** | Lowest | Medium (installer, live bots) | Medium (key-signing scripts) | Medium (live bots, unverified claims) |

## Recommendation (updated: crypto on Coinbase)

The goal is trading crypto on Coinbase from the US, which changes the picture:

1. **cbt-framework is the main tool.** Its research → EDA → plan → build → iterate loop, with look-ahead-bias checks, is the right discipline: form a hypothesis, test it, measure it. It's the same way you'd run an in-field experiment. It had no Coinbase support, so I added one (see below). Binance.com and Bybit don't serve US customers, so ignore those templates.
2. **Use the claude-trading-skills that fit centralized-exchange crypto**: vectorbt, backtrader, walk-forward-validation, ohlcv-processing, pandas-ta, regime-detection, volatility-modeling, mean-reversion, correlation-analysis, position-sizing, kelly-criterion, risk-management, exit-strategies, portfolio-analytics, trade-journal, coingecko-api, sentiment-analysis, and the tax skills (cost-basis-engine, crypto-tax-export, wash-sale-detection, tax-liability-tracking). Coinbase issues 1099s. Ignore the Solana/DEX/MEV/pump.fun skills. They're for on-chain trading, and some ask for a wallet private key.
3. **ai-trading-claude is stocks only.** It's harmless to keep, but not useful for crypto.
4. **Drop skill-algotrader.** It's Indian stocks through Zerodha only.

## Coinbase support added

- `.claude/cbt-framework/templates/live/coinbase_bot.py`: the Coinbase Advanced Trade client.
  - **Spot only, long only.** It won't try to short.
  - **Buys are sized in dollars and sells in coins.** The other exchange templates pass a dollar amount where a coin quantity is expected. On a spot exchange, "buy $100" would become "buy 100 BTC." That's a real bug, and this template avoids it.
  - **Paper mode keeps a simulated wallet** and fills at live Coinbase prices, with slippage and fees. It needs no API keys.
  - **Live mode has three locks:** the API keys, a `COINBASE_LIVE_CONFIRM` phrase in `.env`, and a per-order dollar cap.
  - **Other protections:** the kill switch measures total account value, including coins held; tiny leftover coin balances ("dust") are ignored; and orders under the $1 minimum are skipped.
- `.claude/cbt-framework/templates/presets/coinbase_spot.yaml`: fees for the lowest volume tier (0.60% maker, 1.20% taker), no leverage, and a $50 per-order cap.
- `tools/fetch_coinbase_ohlcv.py`: downloads free Coinbase price history for backtests into `Data/`.
- Also fixed: `base_bot.py` crashed on start if the `logs/` folder didn't exist.

**Tested against live Coinbase prices (2026-09-28):**
- A $100 paper buy filled at the market price plus slippage, with the fee charged.
- Shorts were blocked, over-cash orders were capped, and sub-$1 orders were skipped.
- Live mode refused to start without the confirmation phrase.
- The downloader saved 1,002 daily BTC candles.
- A full buy-then-sell round trip on $1,000 lost about **2.5% to fees and slippage**. At Coinbase's lowest fee tier, a strategy has to make more than about 2.5% per trade just to break even. That favors fewer, longer-held trades (daily or 4-hour charts) over rapid trading, and resting limit orders (0.60%) over market orders (1.20%).

**When you create a Coinbase API key:** grant **View + Trade** only. **Never grant Transfer**, so a stolen key can't withdraw your funds. Add an IP allowlist too.
