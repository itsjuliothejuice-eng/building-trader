---
name: algotrader
description: Quant trading guidance for Indian equity markets (NSE, Zerodha Kite API). Covers bot generation, universe curation, signal generation, backtest/live parity, exits, position sizing and common production failures. Use when building or reviewing an equities trading bot, especially one targeting Zerodha/NSE.
---

# AlgoTrader

Knowledge base and CLI from javajack/skill-algotrader (vendored under `vendor/skill-algotrader`).

- `KNOWLEDGE.md` (in this folder): core playbook covering signals, exits, risk and Zerodha integration. Read the relevant section before answering.
- `NUANCES.md`: production gotchas and failure patterns.
- `algotrader.py`: CLI (`wizard`, `universe`, `signal <symbol>`, `check`, `optimize`). Run with `python .claude/skills/algotrader/algotrader.py <cmd>` after `pip install -r .claude/skills/algotrader/requirements.txt`.
- `templates/`, `examples/`: starting code.

Safety rules:
- Generated bots default to `--mode paper`. Never start one with `--mode live` unless the user explicitly asks in this conversation.
- Never write Kite API keys or access tokens into files that get committed; use a git-ignored `.env`.
- The strategy is built for NSE market hours and instruments; say so if the user's market differs.
