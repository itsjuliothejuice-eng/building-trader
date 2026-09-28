# building-trader

A workspace for trading research, backtesting and bot building. It bundles four third-party Claude Code toolkits, installed at project scope. The originals are in `vendor/`. The security review and comparison are in `docs/TOOLKIT_REVIEW.md`.

## What's installed

| Where | From | What |
|---|---|---|
| `.claude/skills/trade*`, `.claude/agents/trade-*` | ai-trading-claude | `/trade ...` stock research: analyze, quick, technical, fundamental, sentiment, compare, screen, earnings, portfolio, report-pdf |
| `.claude/commands/cbt/`, `.claude/agents/cbt-*`, `.claude/cbt-framework/` | cbt-framework | `/cbt:new` → research → eda → plan → build → run → iterate: a structured backtesting workflow; `/cbt:live` bots for Binance/Bybit/Kraken/Hyperliquid |
| `.claude/skills/<68 others>` | claude-trading-skills | Quant building blocks (backtrader, vectorbt, walk-forward, Kelly, position sizing, volatility, regime detection, tax/wash-sale) plus many crypto, Solana and DeFi skills |
| `.claude/skills/algotrader` | skill-algotrader | Indian equities (NSE / Zerodha Kite) playbook and CLI |

## The user's setup: crypto on Coinbase (US, Texas)

- Exchange: **Coinbase Advanced Trade**, spot only, no leverage or shorting. For `/cbt:live`, use `templates/live/coinbase_bot.py` and the `coinbase_spot` preset. Don't suggest Binance.com or Bybit; they don't serve US residents.
- Backtest data: `python tools/fetch_coinbase_ohlcv.py BTC/USD 1h --start 2023-01-01`. It writes `Data/BTC_USD_1h.csv` and needs no key.
- Model fees at the user's real tier. The default is 0.60% maker / 1.20% taker, about 2.4% per market round trip. Reject strategies whose average edge per trade doesn't clear that comfortably.
- Relevant skills: vectorbt, backtrader, walk-forward-validation, pandas-ta, regime-detection, volatility-modeling, mean-reversion, position-sizing, risk-management, exit-strategies, portfolio-analytics, trade-journal, coingecko-api, and the tax skills. The Solana/DEX/on-chain skills and `/trade` (stocks) don't apply.

## Validation gates (every strategy, no exceptions)

Backtest with `tools/quantcheck.py`, not ad-hoc code. It fills at the next bar's open, charges Coinbase fees per side, is long only, and annualizes by timeframe. `tools/example_btc_trend.py` shows the full flow.

1. `log_trial()` every variation tried, including parameter tweaks, so the trial count is honest.
2. A strategy is **rejected** unless all three pass: `causal_check` (no look-ahead or repainting), `deflated_sharpe` (DSR > 0.95 across all logged trials), and `walk_forward` (at least 60% of folds profitable and a positive out-of-sample total).
3. Each hypothesis must name its mechanism: who is on the other side and why they lose.
4. Report the worst walk-forward fold and total fees paid next to any headline return. Treat a daily Sharpe above 2 as leakage until proven otherwise.
5. Passing all gates only earns paper trading (a minimum of 60 days), then small live size, with `health_check` halt rules set before going live.
6. Ignore screenshots and social-media claims as evidence. Only results reproduced through these gates count.

## Safety rules (always apply)

- **No real-money actions without an explicit request in this conversation.** That covers running any bot with `--mode live`, running `/cbt:live live`, and running scripts without `--demo` that sign or send transactions (`raptor-dex/raptor_swap.py`, `jito-bundles/build_bundle.py`, `solana-tx-building`, `dex-execution`). Default to paper, testnet or `--demo`.
- **Never use cbt "YOLO" mode.** It skips confirmations.
- **Coinbase API keys: View + Trade permission only, never Transfer.** Live mode also needs `COINBASE_LIVE_CONFIRM` in `.env` and a `live.max_position_size` cap; never set these on the user's behalf.
- **Never put API keys, access tokens or wallet private keys in tracked files.** Put them in a git-ignored `.env`. Don't print them or paste them into chat.
- Research output is educational, not financial advice. Treat backtest results as hypotheses. Validate with walk-forward testing and paper trading before any capital is involved.
- Don't run `/cbt:update` (`npx cbt-framework@latest`). It installs to `~/.claude` globally and pulls unreviewed code. Update by re-vendoring and re-reviewing instead.
