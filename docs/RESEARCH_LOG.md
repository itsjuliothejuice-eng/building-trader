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
| Account kill switch | ~~−20% hard stop~~ → review alarm at −20%, hard stop at −27% (decision 2026-10-02 below) |
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

---

## Paper trader build and replay check, 2026-09-30

User chose a **$5,000** paper account, spot version (Study 3's recommendation). Code: `tools/paper/`.

**Replay check** (`tools/paper/test_replay.py`): 2019-01-01 to 2026-09-27, one decision per day on closed candles,
filled at the next day's open, run through the bot's own code:

| | Sharpe | CAGR | Max DD | Result |
|---|---|---|---|---|
| Backtest (quantcheck) | 0.95 | 19.2% | −21.1% | |
| Bot, trades only on signal changes | 0.92 | 23.0% | **−26.7%** | mismatch |
| **Bot + drift rebalance at 10 points** (threshold set before testing) | **0.99** | **21.1%** | **−21.8%** | **match** |

**Finding: `quantcheck` assumes free daily rebalancing.** It holds exposure exactly at target between trades.
A real account drifts: rallies push exposure up, and drawdowns get deeper than tested. The bot now rebalances when
a half drifts more than 10 points from target, which reproduces the tested risk. Future studies should keep this
in mind: the paper-trader replay is the realistic check.

**Finding: the −20% kill switch fires once in the replay, on 2022-11-09** (the FTX collapse, near the bottom of the
bear market), at −21.2%. If left halted, it would miss the 2023–24 recovery (CAGR 13.9% instead of 21.1%). The
system's own worst drawdown (−21.8%) sits right at the switch.
**Open decision for the user:** keep −20% as a hard stop, or make −20% a mandatory review and set the hard stop
at about −27% (1.25× the tested worst), so it fires only if the system does worse than its own 7–10 year history.
The bot currently uses the user's −20% hard stop, plus a warning at −15%.

**Paper trading started:** first decision on the 2026-09-29 close: BTC half 42% invested, ETH half 33%, the rest cash.
Review after 60+ decision days.

## Decision 2026-10-02: −20% becomes a review alarm, hard stop at −27% (user took the recommendation)

| Level (from high-water mark) | What happens |
|---|---|
| −15% | Information only. Normal: replay shows it on 963 of 2,827 days |
| −20% | **Review required**: keep following the rules, flag daily until reviewed with Claude (`--ack`) |
| −27% | **Hard stop**: sell everything, halt until `--resume` (1.25× the tested worst, −21.8%) |

Replay 2019–2026 with these levels: PARITY OK (Sharpe 0.99, CAGR 21.1%, max DD −21.8%). The review fired once
(2022-11-09) and the hard stop never fired. This changes the risk rule, not the trading rule, so the 60-day paper clock
is not reset. The ground-rules table's "−20% kill switch" is superseded by this entry.

---

## Study 4: daily-trading strategies on BTC and ETH perps (pre-registered 2026-10-06)

**Question:** can a strategy that makes a fresh decision every day, holding for about a day, beat its costs
on the user's account? The user asked whether we can "trade every day". This answers it with data.

**Setup:** CDE perps (long and short allowed), 1x (no leverage), Intro fees (0.10% + $0.12/contract per side),
5 bps slippage, 1 bp/day funding on open positions, daily candles, fills at the next day's open. Data:
Coinbase BTC since 2016, ETH since May 2016. Each rule decides at the daily close from closed candles only.
No parameters are tuned; the values below are set before running.

| Rule | Position for the next day | Mechanism (who loses) |
|---|---|---|
| A. Fade big moves | If yesterday moved more than 1× its 30-day typical daily move, bet the other way (down day → long, up day → short); else flat | Panic sellers and FOMO buyers who pay for instant execution; overreaction reverses |
| B. Daily breakout | Long if the close is above the prior 20-day high, short if below the prior 20-day low; else flat | Stop-loss cascades and late chasers push breakouts further |
| C. Follow yesterday | Long after an up day, short after a down day | Slow-reacting traders; underreaction continues |

A and C are opposites. Testing both is deliberate: one will look better by chance, and the deflated Sharpe accounts for that.

**Trials:** 3 rules × 2 coins = **6 new**, for 19 in total including Studies 1–2.

**Pass criteria (set now):** all three gates (causal; DSR > 0.95 over 19 trials; ≥60% of 180-day walk-forward
folds profitable with a positive total), **and** beat buy-and-hold of the same coin on Sharpe and max drawdown.
Fees paid and trades per year are reported for every rule.

**Expectation, written in advance:** all fail after fees. A rule that passes earns its own paper test; it does not replace the current one.

### Study 4 results: all 6 rejected

| Coin | Rule | Sharpe | CAGR | Max DD | Trades/yr | Fees paid (cumulative, % of account) |
|---|---|---|---|---|---|---|
| BTC | Buy & hold (spot) | 0.73 | 63% | −84% | — | 1% |
| BTC | A. Fade big moves | −0.82 | −27% | −97% | 139 | 280% |
| BTC | B. Daily breakout | 0.03 | 1% | −60% | 54 | 100% |
| BTC | C. Follow yesterday | −1.53 | −65% | **−100%** | 191 | 715% |
| ETH | Buy & hold (spot) | 0.55 | 67% | −94% | — | 1% |
| ETH | A. Fade big moves | −0.83 | −38% | −99% | 145 | 331% |
| ETH | B. Daily breakout | −0.33 | −12% | −81% | 52 | 109% |
| ETH | C. Follow yesterday | −1.34 | −71% | **−100%** | 193 | 815% |

Every rule failed the deflated Sharpe (DSR 0.000), walk-forward (2–11 of 19 folds) and the benchmark. All passed the causal check, so the failures are real, not coding errors.

**Diagnostic, not a trial: the same rules with zero fees.** Sharpe ranged from −0.55 to +0.36. Even free, none came close
to holding the coin (0.73 / 0.55). The best, BTC breakout, made 11%/yr gross against 63% for holding. **No edge existed before
costs, and fees then turned a coin flip into a steady loss.** Daily direction in BTC and ETH is, for these rules,
indistinguishable from noise.

**Conclusion:** daily trading is closed as a research direction for this account. The approved system (Study 2,
about 12–14 trades/yr per coin) stays the plan. The trial log now holds 19 trials, all counted in future deflated Sharpes.

---

## Channel audit: Evening Trader (incl. "Performance Tracking - Evening Trader"), 2026-10-06

Run by the user with `tools/telegram/audit_channel.py`, after considering their premium service.

| | Calls | Real 7-day avg (after fees, no leverage) | Real win rate |
|---|---|---|---|
| Announced with a result post | 108 | +1.37% | 56% |
| Never mentioned again | 175 | +0.31% | 40% |
| All calls | 283 | +0.71% | 46% |

- 66 calls hit their stop. 1 result post admitted a loss, and 54 were never mentioned.
- Result posts claimed **+81% on average**; the same calls really moved **+1.4%**. Leverage was stated in 1 of 168 claims.
- 94 result posts were for coins with no visible call in the 14 days before (premium-only or hindsight; can't be verified).
- Earlier scorecard luck test on their calls: t = 0.50 (indistinguishable from chance), worst call −91%.

**Verdict:** the results thread is selective: wins are shown, stops are not, and percentages are inflated about 60×.
Not transparent, no demonstrated edge. Premium service: don't buy.

---

## Study 5: Simon Ree's "Bounce 2.0" on many coins (pre-registered 2026-10-08)

**Question:** does "trade only the strongest trends, buy the pullback to the 21-day EMA, exit at a fixed target or
the pullback's stop" beat the approved paper system once it's spread across many coins? The user asked not to be
limited to BTC, so two coin lists run side by side. Source: Simon Ree, *The Tao of Trading* (2021), Bounce 2.0.

**Mechanism (who loses):** in an established trend, short-term holders sell a dip out of fear or to lock in profits.
Trend-following funds and dip buyers step in at the moving average and resume the trend. The counterparty is the
weak-handed seller at the pullback low. Risk: the trend ends and the "dip" is the first leg of a fall. The stop
is there for that case.

**Indicators (daily closes):** EMA 8/21/34/55/89; ATR(14), Wilder; ADX(13); slow Stochastic %K(8) smoothed 3; RSI(2), Wilder.

**Rules, long side (short side mirrored):**

| Step | Rule |
|---|---|
| Trend | EMA 8 > 21 > 34 > 55 > 89 today, ADX(13) ≥ 20, and EMA 34 > EMA 89 on each of the last 84 days (~4 months) |
| Market filter | BTC close above its 200-day simple average (below, for shorts) |
| Pullback (setup) | Stochastic ≤ 40 (≥ 60 short), low ≤ EMA21 + 1 ATR, close ≥ EMA21 − 1 ATR; counts for 5 days |
| Trigger, version R | RSI(2) crosses back above 10 (below 90 short) |
| Trigger, version H | Close above the high of the lowest-low candle of the previous 4 days (below the low of the highest-high candle, short) |
| Entry | Next day's open. Skipped if that open is already past the stop or the target |
| Stop | Lowest low of the last 5 days (highest high, short). Gap through it → filled at the open |
| Target | EMA21 + 2 ATR at the signal day (− for short). Stop and target hit the same day → counted as the stop |
| Exit | Only stop or target. No other exits |
| Size | Risk 1% of equity to the stop, fees included. Max 20% of equity per coin, total ≤ 100% (no leverage), one position per coin. More signals than room → highest ADX first |

**Universe at each date (decided only from data available that day):** at least 365 days of candles and 30-day
average Coinbase dollar volume ≥ $1M.
- **List A:** the 24 coins with CDE perps (1000PEPE/1000SHIB → PEPE/SHIB). A coin with no Coinbase spot history is left out and named.
  Costs: 0.10% + $0.12 per contract per side (contract values from Coinbase, 2026-10-08), 5 bps slippage, 1 bp/day funding on open positions.
- **List B:** every active Coinbase USD spot coin, minus stablecoins and tokens pegged to another asset
  (wrapped/staked BTC, ETH and SOL, and gold tokens). Long only. Costs: 0.90% taker per side, 10 bps slippage (thinner coins).
  All exits are charged as taker (conservative).

**Trials:** List A × {long only, long and short} × {R, H} = 4, plus List B × long only × {R, H} = 2, so **6 new and 25 in total**.

**Period:** 2017-01-01 to the latest closed day. Walk-forward uses six-month (180-day) folds starting 2018-01-01. The rules are fixed,
so this tests consistency over time.

**Pass criteria (set now):**
1. Causal: every coin's signals unchanged on truncated history.
2. Deflated Sharpe > 0.95 over 25 trials.
3. Walk-forward: ≥ 60% of folds profitable, positive total.
4. **Beats the paper system** (Study 2 rules, 2/3 size, spot fees) on the same dates. Sharpe must be at least
   **0.20 higher**, a margin added because both lists contain only coins that survived to today, and max drawdown no worse than −27%.

Reported for each version: worst fold, total fees, trades per year, win rate, average win and loss in R, year by year,
and the result without its 3 best coins. For List A, a diagnostic (not a trial) reports how many signals a $5,000 account
could actually take in whole contracts.

**Survivorship bias:** only coins listed today can be downloaded. Coins that died are missing, which flatters List B most.
The +0.20 Sharpe margin is a rough allowance for this, not a correction.

**Expectation, written in advance:** List B most likely fails on fees (1.8% per round trip against targets of about 2 ATR).
List A is a genuine unknown. A version that passes earns its own paper test. It doesn't replace the current one, and the
current 60-day paper test continues untouched.

### Study 5 results: all 6 rejected

Data: Coinbase daily candles for 402 USD spot coins, downloaded 2026-10-08 (`tools/fetch_coinbase_universe.py`).
- **List A:** 22 coins. BNB and HYPE have no Coinbase spot history, so they're left out.
- **List B:** 296 coins with at least a year of history. Excluded: CBETH, LSETH, JITOSOL, MSOL (pegged), PAXG (gold), and the stablecoins PAX, USD1, USDS, USDT.
- **Period:** 2017-01-01 to 2026-10-07. Code: `tools/study_bounce.py`; simulator checks in `tools/test_study_bounce.py`.

| Version | Sharpe | CAGR | Max DD | Trades/yr | Win rate | Avg trade | Fees paid | Folds profitable | Worst fold |
|---|---|---|---|---|---|---|---|---|---|
| **Paper system (Study 2, 2/3 size, spot)** | **1.30** | **28.7%** | **−21.8%** | ~25 | | | | | |
| A long only, R | −0.49 | −1.8% | −21.5% | 5 | 25% | −0.34R | 3% | 2/17 | −5.2% |
| A long only, H | −0.39 | −1.1% | −10.6% | 10 | 61% | −0.10R | 3% | 3/17 | −4.3% |
| A long+short, R | −0.27 | −1.7% | −32.2% | 15 | 33% | −0.10R | 10% | 3/17 | −6.7% |
| A long+short, H | −0.50 | −3.2% | −34.6% | 31 | 58% | −0.09R | 13% | 5/17 | −10.6% |
| B spot long only, R | −0.77 | −5.4% | −44.2% | 14 | 25% | −0.39R | 26% | 1/17 | −14.5% |
| B spot long only, H | −0.86 | −5.8% | −44.3% | 30 | 49% | −0.19R | 35% | 2/17 | −18.9% |

(R = 1% of equity, the amount risked per trade. Fees paid = cumulative, as % of equity.)

Every version passed the causal check, so the code doesn't peek ahead. Every version failed the deflated Sharpe (DSR 0.000 after 25 trials),
walk-forward and the benchmark, mostly by a wide margin. None came close to the extra +0.20 Sharpe margin.

**Diagnostic, not a trial: the same six versions with zero fees, slippage and funding.** Sharpe ranged from −0.13 to −0.44, and every
version still lost money. As in Study 4, there's no edge before costs. Spot fees then turn a small loss into a large one (List B: −5% to −6%/yr).

**Why it fails, from the trade records:**
- **Version H wins often but small:** a 49–61% win rate, but the average win is 0.45R and the average loss about 0.9R.
  The target (EMA21 + 2 ATR) sits close to the entry, because the trigger only fires after price has already bounced. The stop (the pullback
  low) sits further away. Winning 6 times out of 10 at about half a unit, while losing a full unit, loses money.
- **Version R wins big but rarely:** the average win is 1.3–1.4R, but only 25–33% of trades win. RSI(2) back above 10 fires early in a
  fall that often keeps going.
- **No coin carried it:** the best coin in each version added at most +6% over ten years, so removing the top 3 coins makes it worse, not better.
  Losses were spread across BTC, ETH, LTC and LINK, the most-traded coins.
- **Shorts added drawdown** (−32% to −35%) without adding return, the same finding as Study 1.
- **$5,000 whole-contract check (List A):** 95–100% of trades were in coins whose single contract fits the $1,000-per-coin cap.
  Contract size isn't what holds it back. The rules are.

**Conclusion:** "buy the dip to the 21 EMA in the strongest trends" has no edge on Coinbase coins, whether on 22 coins or 296, long
or short, with either trigger, even before fees. That matches Study 4: in this data, short holding periods (days) are noise, while
the paper system's slow trend-following (weeks to months) is the only thing that has held up. **Survivorship bias would only make the true
List B result worse.** The trial log now holds 25 trials. The paper test continues unchanged.

---

## Study 6: the approved trend rules on many coins (pre-registered 2026-10-08)

**Question:** the paper system's slow trend rules are the only thing that has held up, but only on BTC and ETH.
Do the same rules do better spread across many coins? And does it help to hold only the strongest-trending ones?

**Mechanism (who loses):** the same as Study 1. Prices trend for weeks to months because news spreads slowly, buyers chase
past winners and forced sellers push falling prices further. The counterparty is the late chaser and the panic seller.
The "strongest coins" version adds cross-sectional momentum: coins that outperformed the others keep doing so for a while.
This is a documented crypto factor (Liu, Tsyvinski & Wu, *Journal of Finance*, 2022).

**Per-coin rules: exactly Study 2's, unchanged** (`trend_signal`, long only, vol control). Four lookbacks (20/60/120/250 days),
40%/yr vol target capped at 1x, 25-point buffer, at **2/3 size** like the paper system.

**Universe at each date** (same as Study 5, decided only from data available that day): at least 365 days of candles and 30-day average
Coinbase dollar volume ≥ $1M.
- **List A:** the 22 perp coins with Coinbase spot history.
- **List B:** 296 spot coins (stablecoins, pegged and gold tokens excluded).

**Two ways to split the account (2 lists × 2 = 4 trials, 29 in total):**

| Version | How |
|---|---|
| **Equal** | Every eligible coin gets an equal slice (1/N of 2/3 of the account) and runs the trend rules in its slice. Cash when its trend is off |
| **Top 10** | Every 7 days, rank eligible coins with the trend on by their average return over 20/60/120/250 days and hold the top 10, each in a 1/10 slice running the trend rules. A coin that drops out is sold at the next weekly ranking; one whose trend turns off goes to cash at once |

**Execution (realistic, unlike `quantcheck`'s free rebalancing):** decide at the close, trade at the next open. Holdings drift with
prices, and a coin is traded only when its exposure is more than 10% of its slice away from target. This is the paper trader's rule.
Spot only (whole perp contracts are far too big for slices of a $5,000 account). Fees: 0.90% per side, plus 5 bps slippage (List A)
or 10 bps (List B).

**Engine check (not a trial):** the paper system itself (BTC+ETH, two halves) run through the new engine must come out close to its
`quantcheck` result. Otherwise the engine is wrong, and nothing else counts.

**Period, walk-forward and pass criteria: the same as Study 5.**
- 2017-01-01 to the latest day, with 180-day folds from 2018-01-01.
- Causal check (every coin's signal and the weekly ranking recomputed on truncated history).
- DSR > 0.95 over 29 trials.
- ≥ 60% of folds profitable, positive total.
- **Beat the paper system by ≥ 0.20 Sharpe** (survivorship margin), with max drawdown no worse than −27%.

Reported: worst fold, fees, trades per year, year by year, the result without the 3 best coins, and an equal-weight buy-and-hold
of the same list for context.

**Survivorship bias:** worse here than in Study 5 for List B, because "hold the winners" benefits most from never seeing the coins that died.
Trend rules do sell falling coins, which limits the damage, but they still buy some coins that later die.

**Expectation, written in advance:** List A "equal" is the most likely to pass, as a broader version of what already works.
List B is more likely to look good on paper and be flattered by survivorship. A version that passes earns its own paper test next to
the current one. It does not replace it.

### Study 6 results: all 4 rejected; BTC and ETH carry everything

Code: `tools/study_many_trend.py`. Period: 2017-01-01 to 2026-10-06, on the same 22 / 296 coins as Study 5.

**Engine check: OK.** The paper system run through the new engine (with real drift) gave Sharpe 1.34 and max DD −21.9%, against `quantcheck`'s 1.30 and −21.8%.

| Version | Sharpe | CAGR | Max DD | Trades/yr | Fees paid | Folds profitable | Worst fold | DSR |
|---|---|---|---|---|---|---|---|---|
| **Paper system (BTC+ETH, 2/3)** | **1.30** | **28.7%** | **−21.8%** | ~25 | | | | |
| List A equal-weight buy & hold | 0.52 | 52.3% | −88.7% | | | | | |
| List B equal-weight buy & hold | 0.22 | 20.0% | −93.7% | | | | | |
| A equal | 1.13 | 21.0% | −23.3% | 151 | 24% | 8/17 | −14.2% | 0.027 |
| A top 10 | 0.87 | 10.8% | −23.4% | 129 | 23% | 8/17 | −8.1% | 0.003 |
| B equal | 0.95 | 16.4% | −22.9% | 502 | 25% | 5/17 | −14.5% | 0.007 |
| B top 10 | 0.45 | 6.2% | −34.9% | 175 | 30% | 6/17 | −10.9% | 0.000 |

All four passed the causal check and failed the deflated Sharpe, walk-forward and the benchmark.

**Without the 3 best coins** (BTC, ETH and LTC, or ZEC/XLM in the top-10 versions), Sharpe fell to **0.08–0.62**. Most of each version's profit
came from BTC and ETH. The other 20 or 294 coins mostly diluted it.

| Year | 2017 | 2018 | 2019 | 2020 | 2021 | 2022 | 2023 | 2024 | 2025 | 2026 |
|---|---|---|---|---|---|---|---|---|---|---|
| Paper system | +259% | −16% | +20% | +61% | +50% | −12% | +22% | +20% | +2% | +3% |
| A equal | +172% | −13% | +13% | +39% | +26% | −9% | +15% | +29% | −3% | +7% |
| B equal | +171% | −13% | +13% | +24% | +28% | −9% | +13% | +8% | −8% | +4% |

**What it means:**
- **The trend rules protect on any list.** Every version kept max drawdown at −23% to −35%, where holding the same coins lost 89–94%.
  The rules work as a safety device on altcoins too.
- **But altcoins trend less cleanly than BTC and ETH,** so giving them a slice lowers returns in most years. The paper system won
  7 of the 9 full years. "Equal" lost to it in almost every year from 2019 on.
- **Holding only the 10 strongest coins was worse, not better.** "Strongest over the last 1–12 months" often meant "about to reverse",
  and the weekly rotation cost fees. The cross-sectional momentum factor didn't survive Coinbase spot costs and these rules.
- **Survivorship bias flatters every alt version,** so the true gap to the paper system is larger than shown.

**Conclusion:** concentrating on BTC and ETH isn't a limitation of the paper system; it's where its edge comes from. No change to the
paper test. The trial log now holds 29 trials.

---

## Study 7: Polymarket, copying winning wallets vs a structural edge (pre-registered 2026-10-09)

**Question (user request):** analyze profitable Polymarket wallets from the last 90 days and build an edge.

**Can the user trade it? (checked 2026-10-09)**
- The international Polymarket site blocks US persons. We won't use a VPN or proxy to get around that.
- Polymarket US (CFTC-regulated) is rolling out state by state with a limited market list.
- Kalshi is legal in the US, and Coinbase offers Kalshi-run prediction markets.

So anything found here is a **hypothesis to retest on a venue the user can legally use**, then paper trade. Money stays in the bank either way.

**Data:** Polymarket's public APIs (no account, no key).
- Gamma: markets and their resolutions.
- CLOB `prices-history`: prices over time.
- Data API: each wallet's `closed-positions` and `positions`.

**Accounting trap found before any analysis:** `closed-positions` lists only positions that were sold or redeemed. A losing bet
that's never redeemed stays in `positions` with value $0. A wallet's profit from `closed-positions` alone therefore leaves out
most of its losses. This study counts both: `closed-positions.realizedPnl` plus, for resolved markets still in `positions`,
`realizedPnl + cashPnl`.

**Windows:**
- Formation (F): markets whose scheduled end date is 2026-07-11 to 2026-08-24 (days −90 to −46).
- Test (T): 2026-08-25 to 2026-10-08 (days −45 to −1).

### Part A: do winning wallets keep winning? (the condition for copy-trading to work)

**Mechanism claimed by copy-traders:** some wallets have skill or inside information, and copying them captures it. Against it: with
hundreds of thousands of wallets, many look brilliant over 45 days by luck, the same selection effect as the Telegram channels.

**Pool, chosen without looking at the test window:**
- Draw 300 markets at random (seed 7) from markets ending in F with volume ≥ $10,000.
- Take the wallets in each one's 500 most recent trades. Cap the pool at 3,000 wallets, drawn at random (seed 7).
- For each wallet, compute profit per resolved market, dated by the market's end date.
- Wallets with more than 5,000 positions in their history (bots and market makers) can't be fetched in full. They're counted and left out, since they can't be copied anyway.

**Measures:** ROI = profit ÷ amount bought, per window.
1. Spearman correlation between F and T ROI, among wallets with ≥ 10 resolved markets in each window.
2. The top 50 wallets by F profit (≥ 10 markets in F): their mean and median T ROI vs the whole pool.

**Pass (copying is worth a follow-up study):** correlation > 0 with p < 0.01, **and** the top 50 have positive median T ROI
**and** mean T ROI above the pool's (t > 2.33). Even a pass only shows persistence. It doesn't show that copying a wallet minutes
later, at worse prices, still makes money.

### Part B: favorite–longshot bias (the structural edge from the literature)

**Mechanism:** buyers overpay for long shots (cheap "lottery tickets"), so favorites are slightly underpriced. The counterparty is the
retail long-shot buyer. This is documented on Kalshi (Whelan) and in betting markets for decades.

**Markets:** every market whose scheduled end date is 2026-07-11 to 2026-10-08, resolved cleanly (final price exactly 0/1),
with volume ≥ $10,000. Excluded: 5-, 15- and 60-minute "Up or Down" crypto markets (a speed game, not this mechanism).

**Rule:** at a set time before the **scheduled** end date (what a trader knows in advance), if one side is priced in the band, buy that side.
- The market must still be open then. Markets that resolved earlier are skipped, as they would be in real life.
- Price = last CLOB price-history point at or before the decision time.

**Costs (taker, conservative):**
- Entry at price + $0.01 (spread), plus Polymarket's taker fee: feeRate × p × (1 − p) per share, using the market's fee category
  (crypto 0.07, sports/culture/economics/weather/other 0.05, politics/finance/tech/mentions 0.04, geopolitics 0).
- A maker version (entry at the price, no fee, fill not guaranteed) is shown as a diagnostic only.

**Trials (4):** decision time {24 hours, 7 days} before the scheduled end × favorite band {0.80–0.95, 0.95–0.99}.

**Statistics:**
- Markets in one event (e.g. brackets of one election) move together, so each event counts once: the average return of its trades.
- t-test across events. One-sided p < 0.0125 (4 trials) means t > 2.24.

**Pass:** at least 200 events, net return per $1 > 0 with t > 2.24, **and** positive in both halves (end dates in F and in T).
A calibration table (price bucket vs actual win rate) is reported for context.

### Part C: what the winners actually do (descriptive, not a gate)

For the top 50 wallets by F profit: market categories, typical entry prices, number of markets, profit concentration
(share from the single best market), and maker/taker rebates received.

**Expectation, written in advance:** Part A fails (past winners regress, as with the Telegram channels). Part B is the most
likely to show something, with a small edge at the 0.80–0.95 band. Whether it survives the spread and fees is the real question.

### Part D (added 2026-10-09, before any data was pulled): does Polymarket's crypto crowd predict BTC/ETH on Coinbase?

**User's question:** even without trading Polymarket, why not use its crypto bets as a signal to trade the same coins on Coinbase?
Nothing prevents that: reading public data is legal. The question is whether the bets carry information the coin price doesn't already have.

**Markets:** Polymarket's daily "Bitcoin Up or Down on <date>" and "Ethereum Up or Down on <date>", every day available through 2026-10-08.
- Window: noon ET to noon ET the next day.
- Resolution: "Up" if the Binance close at the end of the window is above the close at the start.

**Signal (decided 1 hour into the window, from data available then):**
- P_crowd = Polymarket's "Up" price at start + 1h.
- P_fair = the chance of finishing up if the price just wanders randomly from here:
  Φ(ln(S/S0) / (σ√τ)), where S/S0 is the Coinbase move since the window started, σ is the trailing 30-day hourly volatility and τ is the hours left.
- **Edge signal = P_crowd − P_fair.** It's the part of the crowd's view that isn't just "price is already up or down".

**Information test:** correlation between the edge signal and the Coinbase return from start + 1h to the window's end.

**Trade (2 trials, BTC and ETH):**
- If the edge signal > +0.05, go long the CDE perp from the next hourly open to the window's end. If < −0.05, short. Else stay flat.
- 1x, at the user's perp fees (0.10% + $0.12/contract per side), 5 bps slippage, funding ignored (under a day).
- Coinbase hourly candles. Logged with `log_trial`; the deflated Sharpe counts every trial so far.

**Pass:** correlation t > 1.96 (one-sided p < 0.025 over 2 coins), the trade's net mean return > 0 in both halves of the sample,
and DSR > 0.95 across all logged trials.

**Expectation:** fails. Polymarket's short crypto markets are mostly priced by bots that follow exchange prices, so information
should flow from Coinbase/Binance into Polymarket, not the other way.

### Study 7 Part D results: rejected. The Polymarket crowd adds nothing to the coin price

Code: `tools/polymarket/study_crowd_signal.py`. The daily "Up or Down" markets were found from 2025-08-02 to 2026-10-07 (425 BTC days, 426 ETH days).

| | BTC | ETH |
|---|---|---|
| Forecast error 1h into the day (Brier; lower is better): Polymarket crowd | 0.2447 | 0.2435 |
| Same, for "random walk from the current price" (no crowd at all) | **0.2444** | **0.2429** |
| Crowd's extra view vs the rest of the day's move | r = −0.07, t = −1.47 | r = −0.07, t = −1.45 |
| Trades (signal beyond ±0.05) | 45 | 29 |
| Average per trade after perp fees | −0.74% | −0.29% |
| Total | −28.5% | −8.0% |
| DSR (31 trials) | 0.000 | 0.003 |

**Verdict:** the crowd's price is no better a forecast than the coin's own price move, and its "extra opinion" points slightly the wrong way
(not significant). Trading on it lost money in both halves for BTC. Information flows from exchange prices into Polymarket, not out of it.
**There's nothing to copy into Coinbase trades from these markets.** Trial log: 31.

### Study 7 Part B results: all 4 rejected. Favorites were *overpriced*, the opposite of the literature

Code: `tools/polymarket/study_calibration.py`. 112,267 markets with $10k+ volume ended in the window. Of those, 73,654 were cleanly
resolved and not Up/Down crypto (29,425 events), and 53,019 had a price 24 hours before their scheduled end.

| Trial | Markets | Events | Win rate | Avg price | Return per $1 (taker) | t | Half 1 / Half 2 | Maker (diagnostic) |
|---|---|---|---|---|---|---|---|---|
| 24h before, favorite 0.80–0.95 | 9,889 | 6,457 | 80.3% | 0.874 | **−10.6%** | −20.0 | −10.5% / −10.6% | −9.0% |
| 24h before, favorite 0.95–0.99 | 4,041 | 2,836 | 94.1% | 0.972 | −5.1% | −11.2 | −5.1% / −5.1% | −4.0% |
| 7d before, favorite 0.80–0.95 | 5,015 | 3,453 | 82.6% | 0.871 | −7.2% | −10.3 | −7.8% / −6.7% | −5.5% |
| 7d before, favorite 0.95–0.99 | 1,344 | 843 | 98.0% | 0.972 | −0.4% | −0.9 | −0.3% / −0.5% | +0.7% |

**Calibration, 24h before (all 53,019 markets):** price vs how often that side won.

| Price | 0–0.05 | 0.05–0.10 | 0.10–0.20 | 0.20–0.35 | 0.35–0.50 | 0.50–0.65 | 0.65–0.80 | 0.80–0.90 | 0.90–0.95 | 0.95–1.0 |
|---|---|---|---|---|---|---|---|---|---|---|
| Avg price | 0.014 | 0.073 | 0.149 | 0.275 | 0.428 | 0.558 | 0.715 | 0.842 | 0.926 | 0.982 |
| Actually won | 0.032 | 0.141 | 0.221 | 0.333 | 0.442 | 0.546 | 0.684 | 0.771 | 0.849 | 0.967 |

The same shape appears in markets with $250k+ volume (4,654), $1M+ (1,101), and markets whose price moved in the last 3 hours (27,132),
so it isn't only stale prices in thin markets. Sports are two-thirds of the favorite trades and lost −10% per $1. Weather lost −9%.

**What it means:**
- **Buying favorites loses money on Polymarket a day or a week before the end.** The pre-registered edge is rejected.
- **The data points the other way: long shots won about twice as often as priced** (7% priced, 14% won). That's a *new* hypothesis,
  not a finding. It was spotted after looking at the data, it's large enough to treat as suspected leakage until proven otherwise,
  and the price-history mid can be a price nobody could actually buy at. **Needed before believing it:** a separate pre-registered study,
  in a different period, using prices people actually paid (trade prints), on a venue the user can legally use.

### Study 7 Parts A and C results: copying winners rejected; most "wallet profit" figures leave out the losses

Code: `tools/polymarket/study_wallets.py`.
- **Pool:** 24,303 wallets traded in the 300 sampled formation markets (95 Up/Down crypto, 205 other). 3,000 were drawn at random.
- **Excluded:** 426 had more than 5,000 positions (bots and market makers).
- **Analyzed:** 2,574 had resolved positions.

| | Result | Needed |
|---|---|---|
| Wallets active in both windows (≥ 10 markets each) | 1,360 | |
| Rank correlation of ROI, formation vs test | **0.30** (p < 0.0001) | > 0, p < 0.01: **pass** |
| Wallets profitable | 29% formation, 30% test | |
| Top 50 by formation profit: formation | +$2.73M, median ROI +6.7% | |
| Same 50 in the test window (46 still active) | **−$1.39M**, mean ROI −5.3%, median −1.0%, 43% profitable | median > 0: **fail** |
| Whole pool, test window | mean ROI −10.7%, median −3.9% | |
| Top 50 vs pool | t = 1.86 | > 2.33: **fail** |

**Verdict: rejected.** The 50 biggest winners of July and August, followed into September and October, **lost $1.39 million together**.
More than half of them lost money. They lost less than the average wallet, but not by a margin that rules out luck. The 0.30 rank
correlation shows wallets keep their *style* (consistent losers keep losing), but that isn't enough to make copying the top profitable.

**Part C, what the 50 formation winners did:**
- 83% of their positions were sports, 4% crypto Up/Down.
- The median wallet had 452 resolved positions, and its single best market made 36% of its window profit.
- Median entry price was 0.54; 25% of entries were at 0.80+ and 12% below 0.20.

They're high-volume sports bettors whose results swing on a few big games. That's not a repeatable edge you can see in the data.

**The accounting trap, measured:** across all 2,574 wallets, `closed-positions` alone shows **+$39.6M** profit. The losing bets that were
never sold or redeemed add **−$43.6M**. The true total is **−$3.4M**. Any wallet tracker, "smart money" list or screenshot built from
closed positions shows a winner where the real result is a loss.

## Study 7 conclusion (2026-10-09)

| Part | Question | Answer |
|---|---|---|
| A | Copy the wallets that won the last 45 days? | **No.** The top 50 lost $1.39M in the next 45 days |
| B | Buy favorites (the literature's edge)? | **No.** −5% to −11% per $1 a day before; favorites are overpriced here |
| D | Use Polymarket crypto bets to trade BTC/ETH on Coinbase? | **No.** No better than the price itself; trading it lost money |
| Lead | Long shots won about twice as often as priced | Unproven; needs its own pre-registered study (different period, real trade prices, a legal US venue) |

No edge to trade. The paper test of the BTC+ETH trend system is unchanged.

---

## Study 8: are long shots underpriced on Kalshi? (pre-registered 2026-10-09)

**Why:** Study 7 found, *after looking at the data*, that Polymarket long shots priced about 7¢ won about 14% of the time.
That lead needs testing on data it didn't come from, at prices people actually paid, on a venue the user can legally use.
**Kalshi:** CFTC-regulated and US-legal; Coinbase's prediction markets run on it.

**Mechanism, if real:** a day before resolution, the crowd is overconfident. It pushes the favorite too high, and whoever sells
the long shot cheaply is the one who loses. **Against it:** Whelan's study of 300k+ Kalshi contracts found the opposite (long shots
*over*priced, buyers losing about 60% of stake under 10¢). My expectation is that this fails.

**Data:** Kalshi's public API (no account, no key): settled markets and every trade print, including which side the taker bought.
Excluded:
- multi-leg combo markets (parlays)
- markets under 5,000 contracts of volume

Markets that weren't open 24 hours before close, such as hourly and 15-minute markets, drop out on their own.

**Periods:**
- **Test:** markets closing 2026-04-12 to 2026-07-10. This period doesn't overlap the Polymarket window.
- **Replication:** markets closing 2026-07-11 to 2026-10-08, on Kalshi.

**Rule:**
- Decision time = 24 hours before the market's close time.
- In the 6 hours before then, take the last trade's YES price y. If y is in the band, the long shot is YES. If 1 − y is in the band, it's NO.
- **Entry price:** the volume-weighted price takers actually paid to buy the long-shot side in that 6-hour window.
  With no such buys, the trade is skipped: there's no proof it could have been filled.
- **Fee:** Kalshi taker 0.07 × p × (1 − p) per contract. That's the standard rate; rounding up to the cent makes small orders a bit worse.
- Settled on Kalshi's own `result`.

**Trials (2):** long-shot band {0.03–0.10, 0.10–0.20}.

**Statistics:** each event (e.g. one game or one day's temperature) counts once, as the average return of its trades. One-sided t-test,
p < 0.025 (2 trials), so t > 1.96.

**Pass:**
- ≥ 200 events
- net return per $1 > 0 with t > 1.96
- positive in both halves of the test period
- positive in the replication period

**Caveat set now:** for markets that can close early, the listed close time may be the actual close rather than the scheduled one,
which would leak timing. Results are also reported separately for markets that can't close early.

**Change before any results (2026-10-09, data collection only):** Kalshi's public rate limit (about 3 requests a second) makes checking
trades for every market infeasible: about 100k markets would take ~9 hours. Every qualifying market is listed, then **6,000 per period are
drawn at random (seed 8)** for the trade lookup. Random sampling doesn't bias the result; it only widens the error bars. Measured sustained limit: about 1.2 requests a second, so the sample was cut to **3,000 per period**, still before any result
was seen (listing all markets alone takes ~4 hours).

### Study 8 results: rejected. The long-shot "edge" flips sign with the period

Code: `tools/kalshi/study_longshots.py`.
- **Universe:** 107,453 qualifying markets in the test period and 183,677 in the replication period, 3,000 drawn at random from each.
- **Data issues:** no series were skipped for errors. Every long-shot trade came from markets that can close early, so the
  "can't close early" check had nothing to compare.
- **Price:** what takers actually paid, plus Kalshi's fee.

| Period | Band | Markets | Events | Avg paid | Won | Return per $1 | t | Half 1 / Half 2 |
|---|---|---|---|---|---|---|---|---|
| **Test** (Apr 12–Jul 10) | 3–10¢ | 243 | 233 | 8.2¢ | 4.5% | **−33%** | −1.33 | −59% / −8% |
| **Test** | 10–20¢ | 245 | 241 | 16.9¢ | 14.7% | **−11%** | −0.74 | −7% / −15% |
| Replication (Jul 11–Oct 8) | 3–10¢ | 159 | 156 | 6.7¢ | 10.7% | +60% | 1.55 | +88% / +34% |
| Replication | 10–20¢ | 154 | 154 | 14.7¢ | 17.5% | +15% | 0.70 | +9% / +21% |

**Verdict: both bands rejected.** In the test period, which the idea didn't come from, Kalshi long shots **lost** money, matching
Whelan's finding. In July–October, the same months where Polymarket showed the pattern, they looked profitable again.
- **Not significant either way:** t = 1.55 and 0.70.
- **Driven by a few contract types:** NFL touchdown and spread props at the start of football season.

**What it means:** the long-shot effect seen on Polymarket isn't a stable edge. It belongs to one stretch of time, so it's luck or a
seasonal quirk. Buying it in the spring would have lost a third of every dollar in the cheapest band. No tradeable edge. Study 7's lead is closed.

---

## Study 9: is there a proven lead trader worth copying? Hyperliquid (pre-registered 2026-10-10)

**User request:** find a proven lead trader to copy trade.

**Where to look:**
- **Copy-trading leaderboards on Binance, Bybit, Bitget and OKX:** closed to US residents, and the exchange curates them.
  Closed or blown-up accounts disappear, so they can't be audited.
- **Hyperliquid** (perp exchange on its own chain): every fill, fee and P&L for every address is public.
  Its leaderboard lists 47,216 accounts. It's also closed to US persons, so a trader found here could only be *followed*
  (e.g. on Coinbase CDE perps for shared coins), not copied on-platform. The point here is to learn whether "proven" traders exist at all.
- **eToro US CopyTrader:** phased US rollout (waitlist), so Texas availability is unconfirmed.

**Mechanism copy traders claim:** some traders have skill that persists. Against it, the same selection effect as Studies 7 and the
Telegram scorecard: out of 47,000 accounts, many look brilliant over two months by luck and leverage.

**Data:** Hyperliquid public API, no account. The pool comes from today's leaderboard:
- **Eligible:** all-time volume ≥ $100,000.
- **Sample:** 1,000 addresses at random (seed 9).
- **Bias:** this favors survivors, since accounts that blew up and left may be missing. So it **flatters** copying. A failure is conclusive;
  a pass would need a survivor-free re-test.

**Windows:**
- Formation F: 2026-06-12 to 2026-08-10 (60 days).
- Test T: 2026-08-11 to 2026-10-09 (60 days).

**Profit per window:** realized P&L from fills (`closedPnl` − fees). Unrealized P&L and funding are left out, which limits the result to closed trades.

**Excluded:** traders whose fills since F began exceed the API's 10,000-fill limit (high-frequency bots, which can't be copied) and traders
with fewer than 20 closing fills in a window.

**Two definitions of "proven" (2 trials):**
1. **Top 20 by formation profit.**
2. **Strict:** profitable in *both* 30-day halves of F, all-time P&L > 0, ≥ 100 closing fills in F. If more than 20 qualify, take the top 20 by F profit.

**Pass (worth a follow-the-trades study on Coinbase):**
- Spearman correlation of window profits > 0 with p < 0.01, across traders active in both windows.
- **And**, for a definition: median test profit > 0, more than 60% profitable in T, and mean test profit above the pool's, t > 2.24
  (one-sided p < 0.0125, 2 trials).

**Expectation:** fails, like every leaderboard tested so far. If it passes, it only shows persistence. Copying with a delay on another
exchange is a separate test.

### Study 9 results: rejected, but the closest any copy idea has come

Code: `tools/hyperliquid/study_lead_traders.py`. The leaderboard had 47,213 accounts, 43,339 of them with $100k+ volume, and 1,000 were sampled.
- 70 were over the fill limit (bots).
- 930 were analyzed; 293 were active in formation (≥ 20 closing fills) and 216 in both windows.

| | Result | Needed |
|---|---|---|
| Rank correlation of profit, formation vs test | 0.14 (p = 0.019) | p < 0.01: **fail, narrowly** |
| Traders profitable | formation 42%, test 52% | |
| Pool, test window | mean +$16,380, median +$179 | |
| **Top 20 by formation profit** | F: +$5.49M. **T: +$4.06M, 70% profitable**, median +$43k | t vs pool 1.55 (needs 2.24): **reject** |
| **Strict "proven"** (31 qualified, top 20) | F: +$4.25M. **T: +$4.33M, 70% profitable**, median +$43k | t vs pool 1.73 (needs 2.24): **reject** |

**Verdict: both rejected under the pre-set bar.** Unlike Polymarket (Study 7, where the top 50 lost $1.39M) and the Telegram channels,
Hyperliquid's winners mostly **kept winning**: 14 of 20 were profitable again. Three things stop this from counting as proven:
1. **Not distinguishable from luck at the bar set in advance** (t = 1.55–1.73 vs 2.24; correlation p = 0.019 vs 0.01).
2. **A few whales carry it.** Two accounts made +$1.35M and +$1.98M of the test profit, while others lost up to −$466k.
   The median winner made far less than the average.
3. **The pool flatters it.** It came from today's leaderboard, so accounts that blew up and left are missing, which pushes
   toward exactly this kind of persistence.

**Also:** these are mostly large accounts ($100k–$60M) trading perps with leverage, and Hyperliquid is closed to US persons. Following them would mean
reproducing their trades on Coinbase CDE perps, with a delay, at a different size. That's untested.

**The honest next step, if any, is a forward test, which has neither of the biases above.** Fix the 20 "strict" picks now, using only
data through 2026-10-09. Then track their real trades for 60 days, paper-copied onto the coins Coinbase lists, next to the current paper system. A trader is
"proven" only if that forward record holds up.

---

## Study 10: forward paper-copy of the 20 "proven" Hyperliquid traders (pre-registered 2026-10-10)

**Why forward:** Study 9's backtest was flattered by survivorship (a pool from today's leaderboard) and missed its bar.
A forward test can't be flattered: the picks are fixed *before* the outcome exists.

**Picks (fixed, never changed):** the 20 traders from Study 9's strict rule, chosen on data through 2026-10-09, saved in
`tools/hyperliquid/picks.json`. A trader who stops trading or empties the account stays in the test as cash; nobody is swapped in.

**Paper copy (fake money; no account, no key, no orders):** `tools/hyperliquid/copy_paper.py`, run hourly on the user's laptop.
- **Account:** $5,000, split into 20 equal slices of $250, one per trader.
- **Which positions:** each hour, read each trader's open perp positions on Hyperliquid (public). Mirror only the coins that have a Coinbase CDE perp:
  AAVE ADA AVAX BCH BNB BTC DOGE DOT ENA ETH HBAR HYPE LINK LTC NEAR ONDO PAXG PEPE SHIB SOL SUI XLM XRP ZEC.
  Positions in other coins are skipped, and the share of their exposure we could copy is reported.
- **Size:** same weight as theirs: position ÷ their account value, × the slice's equity.
- **Leverage cap 1x per slice** (CLAUDE.md default). If their copyable exposure is more than 1× their account, the slice is scaled down to 1×.
- **Trading:** a slice trades a coin when its exposure is more than 10% of the slice away from target, or the trader closed the position.
- **Costs (Coinbase CDE, Intro tier):** 0.10% fee + 0.05% slippage per side, and 1 bp/day funding on open positions.
- **Prices:** Hyperliquid mid prices at each check (close to Coinbase's).
- **Simplifications:** fractional sizes. Real whole-contract execution would need a much larger account than $250 per trader (Study 3).
  The copy lag (up to 1 hour) is part of the test, because that's what a human or bot copying from Texas would face.

**Also tracked:** each pick's own realized forward P&L on Hyperliquid (fills since 2026-10-10).

**Review at 60 days (2026-12-09). The copy only "passes" if all of these hold:**
1. The paper-copy account is up after costs.
2. It beats the BTC+ETH paper system over the same days, on both return and worst drawdown.
3. At least 12 of the 20 picks are profitable on their own forward P&L.
4. The paper-copy account never fell more than 27% from its high (the same hard stop as the paper system).

Passing earns a longer forward test, not money: the 60-day minimum in `CLAUDE.md` applies to the copy method itself. Nothing here changes the BTC+ETH paper test.
