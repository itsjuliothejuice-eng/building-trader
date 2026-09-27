# building-trader

A workspace for trading research, backtesting and bot building. It bundles four third-party Claude Code toolkits, installed at project scope. The originals are in `vendor/`. The security review and comparison are in `docs/TOOLKIT_REVIEW.md`.

## What's installed

| Where | From | What |
|---|---|---|
| `.claude/skills/trade*`, `.claude/agents/trade-*` | ai-trading-claude | `/trade ...` stock research: analyze, quick, technical, fundamental, sentiment, compare, screen, earnings, portfolio, report-pdf |
| `.claude/commands/cbt/`, `.claude/agents/cbt-*`, `.claude/cbt-framework/` | cbt-framework | `/cbt:new` → research → eda → plan → build → run → iterate: a structured backtesting workflow; `/cbt:live` bots for Binance/Bybit/Kraken/Hyperliquid |
| `.claude/skills/<68 others>` | claude-trading-skills | Quant building blocks (backtrader, vectorbt, walk-forward, Kelly, position sizing, volatility, regime detection, tax/wash-sale) plus many crypto, Solana and DeFi skills |
| `.claude/skills/algotrader` | skill-algotrader | Indian equities (NSE / Zerodha Kite) playbook and CLI |

## Safety rules (always apply)

- **No real-money actions without an explicit request in this conversation.** That covers running any bot with `--mode live`, running `/cbt:live live`, and running scripts without `--demo` that sign or send transactions (`raptor-dex/raptor_swap.py`, `jito-bundles/build_bundle.py`, `solana-tx-building`, `dex-execution`). Default to paper, testnet or `--demo`.
- **Never use cbt "YOLO" mode.** It skips confirmations.
- **Never put API keys, access tokens or wallet private keys in tracked files.** Put them in a git-ignored `.env`. Don't print them or paste them into chat.
- Research output is educational, not financial advice. Treat backtest results as hypotheses. Validate with walk-forward testing and paper trading before any capital is involved.
- Don't run `/cbt:update` (`npx cbt-framework@latest`). It installs to `~/.claude` globally and pulls unreviewed code. Update by re-vendoring and re-reviewing instead.
