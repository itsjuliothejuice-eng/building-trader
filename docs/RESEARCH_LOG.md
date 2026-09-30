# Research log

Every study is written down **before** it runs, with its hypothesis, rules and
trial count. Results are recorded whether they're good or bad. Nothing goes
live without passing the gates in `CLAUDE.md`, then 60+ days of paper trading.

## Ground rules (set 2026-09-30, before any money is deposited)

The user lost a previous account trading. Money stays in the bank until a
system has passed every gate **and** paper trading. Rules decided now, while
calm, not in the middle of a trade:

| Rule | Limit |
|---|---|
| Leverage | 1x (none). Never above 2x effective |
| Risk per trade | 1% of account at the stop |
| Account kill switch | Stop all trading at −20% from the high-water mark; review before restarting |
| Starting size when live | Small: money whose total loss would not change anything important |
| Adding money | Only after 3+ months live that match the paper and backtest results |
| Benchmark | Every system must beat simply holding the same asset on a **risk-adjusted** basis (Sharpe and drawdown), after fees |

Fees used everywhere are the user's real Intro tier (2026-09-30): spot 0.50% maker / 0.90% taker;
CDE futures and perps 0.095% maker / 0.10% taker plus $0.12 per contract.

---

## Study 1: trend-following with volatility control (BTC, ETH, SOL), 2026-09-30

**Status: promising, not approved.** One variant passed all gates. The pattern
across every coin is consistent, but the evidence isn't strong enough to trade yet.

**Hypothesis (mechanism):** crypto trends for weeks to months because news
spreads slowly and buyers chase past performance, and forced sellers push falling
prices further. Time-series momentum is one of the most replicated effects in
futures markets (Moskowitz, Ooi & Pedersen, 2012). The counterparty is the late
chaser and the panic seller.

**Rules (nothing fitted):**
- The trend score averages four lookbacks: 20, 60, 120 and 250 days.
- Volatility control targets 40%/yr, capped at 1x.
- Rebalance only when the target changes by more than 25 points.
- Trades run on CDE perps at Intro fees, plus 1 bp/day funding.

**Trials:** 12 = {long only, long/short} × {vol control off, on} × {BTC, ETH, SOL}.
Code: `tools/study_trend.py`. Data: Coinbase daily, BTC and ETH since 2016, SOL since mid-2021.

| Coin | Variant | Sharpe | CAGR | Max drawdown | Fees paid | Gates |
|---|---|---|---|---|---|---|
| BTC | Buy & hold | 0.73 | 63% | **−84%** | 1% | benchmark |
| BTC | Long only + vol control | **1.19** | 42% | **−37%** | 24% | DSR pass; walk-forward 11/19 (58%, needs 60%) |
| ETH | Buy & hold | 0.55 | 67% | **−94%** | 1% | benchmark |
| ETH | Long only + vol control | **1.12** | 44% | **−38%** | 19% | **PASS ALL** (DSR 0.961, 12/19 folds, worst fold −26%) |
| SOL | Buy & hold | 0.21 | 23% | −96% | 1% | benchmark |
| SOL | Long only + vol control | 0.53 | 14% | −38% | 7% | fail (only 5 years of data) |
| All | Long/short variants | lower | lower | mixed | 2–4× more | shorts cost fees and fight crypto's upward drift |

**Year by year, BTC (trend vs holding):**

| Year | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 YTD |
|---|---|---|---|---|---|---|---|---|---|---|
| Trend | +361% | **−28%** | +50% | +114% | +26% | **−16%** | +75% | +61% | −8% | +3% |
| Hold | +1324% | **−73%** | +94% | +305% | +59% | **−64%** | +156% | +121% | −6% | −4% |

**What it means:**
- **It's not a way to beat the market in bull years.** It gave up about half the upside every good year.
- **What it does is survive.** In the two crashes (2018, 2022) it lost 16–28% where holding lost 64–73%. Its worst drawdown was −37% vs −84%. That's the profile to build on, given the goal of never losing everything again.
- **Shorting made everything worse.** Long only is the direction.
- **Caveats:** only 1 of 12 variants passed all three gates, and only just (DSR 0.961 vs 0.95). The rules are fixed, so walk-forward here tests consistency across periods, not out-of-sample fitting. The early years (2016–2017) flatter every return figure.

**Next (Study 2, to be pre-registered):** the same long-only + vol-control rules on a combined BTC+ETH
portfolio, which is a single new trial. If it passes, build the paper-trading bot for it.
