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

## Recommendation

1. **Keep ai-trading-claude** for research on US tickers (`/trade analyze AAPL`). It's the lowest risk and can't touch money.
2. **Keep cbt-framework** as the backtesting process. Its research → EDA → plan → build → iterate loop, with look-ahead-bias checks, is the right discipline: form a hypothesis, test it, measure it. It's the same way you'd run an in-field experiment. Stay in paper mode.
3. **Use claude-trading-skills selectively**: backtrader, vectorbt, walk-forward-validation, position-sizing, kelly-criterion, risk-management, volatility-modeling, regime-detection, correlation-analysis, trade-journal, wash-sale-detection and tax-liability-tracking. Ignore the Solana/DEX/MEV skills unless you trade crypto on-chain, and never give them a wallet key.
4. **Drop skill-algotrader** unless you trade Indian stocks through Zerodha. It targets NSE hours, instruments and broker only.

If you want a leaner setup, I can delete the unused skills from `.claude/skills/`. The originals stay in `vendor/`.
