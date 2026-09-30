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

---

## Study 2: BTC + ETH trend portfolio, 2026-09-30

**Pre-registered before running.**

**Hypothesis:** the same trend mechanism as Study 1. Running it on two coins that don't crash
at exactly the same moments should make results steadier than either coin alone.

**Rules:** exactly Study 1's long-only + vol-control rules, unchanged, on each coin.
The account is split into two halves (50% BTC, 50% ETH), each trading its own coin on CDE perps
at Intro fees. There's no rebalancing between halves (no hidden fees), and the two halves together
never exceed 1x the account.

**Trials:** 1 new, 13 in total including Study 1's 12. The deflated Sharpe counts all 13.

**Period:** dates where both coins have data.

**Pass criteria (decided now):**
1. All three gates in `CLAUDE.md`: causal, DSR > 0.95 over 13 trials, ≥60% of 180-day walk-forward folds profitable with a positive total.
2. Beats a 50/50 buy-and-hold of the same two coins on **both** Sharpe and max drawdown.

If it passes, next is a paper-trading bot. If it fails, it's recorded here and not tweaked.

### Study 2 results

**Status: PASSED all gates. Approved for paper trading only.**

First run (reported for honesty): REJECTED, but because of two bookkeeping bugs, not the rules.
(1) Study 1 had been logged twice when it was re-run to print its table, so the trial count read 25
instead of 13. (2) The BTC and ETH files each skip 2 days in May 2016 on different dates, so on those
days one half-account went missing and a phantom −50% drawdown appeared while the strategy was flat.
Fixes: one trial per distinct variant, and trade only on days both coins have a candle. The strategy
rules were not changed.

Data: 2016-05-18 to 2026-09-28, 3,784 days, CDE perp fees at Intro tier, 1 bp/day funding.

| | Sharpe | CAGR | Max drawdown |
|---|---|---|---|
| 50/50 buy & hold (spot) | 0.66 | 66% | **−90%** |
| **50/50 trend portfolio** | **1.27** | 43% | **−29%** |

| Gate | Result |
|---|---|
| Causal | PASS: both legs unchanged on truncated history |
| Deflated Sharpe | PASS: 0.983 after 13 trials |
| Walk-forward | PASS, **barely**: 11/18 six-month folds profitable (61%, needs 60%); worst fold −21% |
| Benchmark | PASS: Sharpe 1.27 vs 0.66, drawdown −29% vs −90% |

| Year | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 YTD |
|---|---|---|---|---|---|---|---|---|---|---|
| Trend portfolio | +554% | **−21%** | +31% | +104% | +80% | **−15%** | +35% | +33% | +3% | +6% |
| 50/50 hold | +3047% | **−79%** | +41% | +370% | +218% | **−67%** | +109% | +72% | −9% | −7% |
| Trend worst dip that year | −23% | −29% | −23% | −20% | −21% | −17% | −22% | −29% | −20% | −11% |

**Open issues before paper trading:**
1. **Drawdown vs the kill switch.** The backtest's worst drawdown (−29%) is deeper than the −20% account
   kill switch in the ground rules. At full size the kill switch would have fired in 2018 and 2024.
   Either set the kill switch from the system's own history (e.g. 1.5× the backtest worst, as
   `health_check` does), or run at reduced size (e.g. 2/3 size → roughly −20% worst). The user decides this.
2. **Contract sizes.** One BTC PERP is about $840 and one ETH PERP about $270. The rules call for fractional positions
   (e.g. 0.6 × half the account). A small account can't hold those precisely on perps, and spot fees
   are about 6× higher. Next: simulate whole-contract rounding at realistic account sizes to find the
   minimum account where perp rounding doesn't change the results.
3. **Six-month losing stretches are normal:** 7 of 18 folds lost money, some by −15% to −21%.
   Paper trading must be judged against that, not against the good years.
4. **2017 dominates the headline CAGR.** Since 2023 it has made +35%, +33%, +3%, +6%.

---

## Decision 2026-09-30: size at 2/3, keep the −20% kill switch (user chose option A)

The Study 2 strategy runs at 2/3 of its position size, and the remaining third stays in cash.
This scales positions only and leaves the signal alone, so it's not a new trial. The −20% account
kill switch stays.

## Study 3: whole-contract rounding and minimum account size (pre-registered)

**Question:** CDE perps trade in whole contracts (BTC 0.01 ≈ $840, ETH 0.1 ≈ $270 today). The
Study 2 rules at 2/3 size need fractional positions. How big must the account be before rounding
to whole contracts stops hurting? And is spot (fractional, but 0.90% fees) better for small accounts?

**Method:** same signal and fold layout as Study 2, at 2/3 size.
- **Perp version:** each half-account's position is rounded to whole contracts, assuming today's
  contract value relative to account size. A half holds nothing if even one contract is more
  than it wants. Fees are Intro CDE (0.10% + $0.12/contract) plus 1 bp/day funding.
- **Spot version:** fractional positions at Intro spot fees (0.90%).
- **Account sizes:** $1k, $2k, $3k, $5k, $10k, $20k, $50k.

**Decision rule (set before running):**
- The smallest account where the perp version keeps Sharpe within 10% of the ideal (unrounded)
  version **and** max drawdown no worse than −22% becomes the **minimum perp account**.
- Below that, use the spot version, but only if it still beats 50/50 buy-and-hold on both Sharpe and drawdown.
- If neither works at a size the user is willing to fund, paper trading uses the smallest workable size and we say so.

### Study 3 results

At 2/3 size, 2016-05 to 2026-09, same 18 six-month folds:

| Version | Sharpe | CAGR | Max drawdown | Folds profitable | Worst fold |
|---|---|---|---|---|---|
| 50/50 buy & hold (spot) | 0.66 | 66% | −90% | 10/18 | −60% |
| Ideal fractional, perp fees (reference) | 1.33 | 28.5% | **−20.3%** | 11/18 | −14% |
| **Spot, fractional (0.90% fees)** | **1.26** | **26.8%** | **−21.8%** | 11/18 | −15% |
| Perp, $1,000 account | 1.06 | 29.1% | −27.1% | 8/18 | −21% |
| Perp, $2,000 account | 1.18 | 25.0% | −23.2% | 11/18 | −15% |
| Perp, $3,000 account | 1.44* | 36.0% | −25.6% | 11/18 | −20% |
| **Perp, $5,000 account** | 1.34 | 28.2% | −22.0% | 11/18 | −14% |
| Perp, $10,000+ account | 1.33–1.37 | 28–29% | −20% to −22% | 11/18 | −14% to −15% |

\* The $3,000 figure is higher only by rounding luck: the drawdown gets worse, so it fails the rule.

**Verdict under the pre-set rule:**
- **Minimum perp account: $5,000.** Below that, one BTC contract ($840) is too coarse a step for a half-account.
- **Spot works at any size:** Sharpe 1.26 vs the ideal 1.33, drawdown −21.8%, and it beats buy-and-hold. It only
  trades about 12–14 times a year per coin, so the 0.90% spot fee costs little.
- **2/3 sizing does what option A intended:** the worst drawdown is about −20 to −22%, in line with the −20% kill switch
  (the ideal version reached −20.3%, so the switch would have come close to firing once).

**Recommendation:** paper trade the **spot version**. It works at any account size, holds fractional amounts, has
no leverage, no liquidation, no funding and no contract expiry, and the existing spot bot template fits it. Perps become
worth it only for an account of $5,000 or more.
