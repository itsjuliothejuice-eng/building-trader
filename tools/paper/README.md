# Paper trader: BTC + ETH trend system (fake money)

Runs the approved system from `docs/RESEARCH_LOG.md` (Studies 2 and 3) with a simulated **$5,000**
account, at live Coinbase prices. It **never logs in, needs no API key and places no orders.**

- Rules: long-only trend + volatility control, BTC and ETH half-accounts, 2/3 size, **spot**,
  Intro spot fees (0.90% + 0.05% slippage per side).
- It acts once a day, after the daily candle closes at **00:00 UTC (7 PM Central)**.
  It trades when the rule's target changes, or when a position drifts more than 10 points off target.
- Risk levels, measured from the account's high (user's decision 2026-10-02):
  - **−15%: information only.** This is normal: in the 2019–2026 replay the account was this far down on about 1 day in 3.
  - **−20%: stop and review.** It keeps following the rules, but shows `REVIEW REQUIRED` daily until you check the
    numbers with Claude and run `--ack`. In the replay this happened once (Nov 2022, the FTX crash).
  - **−27%: hard stop.** It sells everything and halts until `--resume`. That's 1.25× the worst drop ever seen in testing,
    so firing means the system is behaving worse than in 7–10 years of history. It never fired in the replay.

## Start it (Windows, from the repo folder)

```powershell
git pull
python tools/paper/paper_trader.py          # first run: loads 10 years of prices, makes today's decision
```
To keep it running, double-click `tools\paper\run_paper.bat` (it checks hourly and restarts itself).
To start it automatically with Windows, add a shortcut to it in `shell:startup`, the same as the Telegram collector.

## Check on it

```powershell
python tools/paper/paper_trader.py --report
```
The logs are in `data/paper/`: `trades.csv` (every paper trade), `daily.csv` (every decision, equity, drawdown).

## What "working" looks like

About 1 trade per coin per month. Losing months are normal, and a 6-month losing stretch happens about 1 time in 3.
After 60+ days we compare `daily.csv` with what the backtest would have done over the same days.
If the kill switch fires, don't just resume: we review first.

## Verified before handing over

`python tools/paper/test_replay.py` replays 2019–2026 through the bot one day at a time (decide on closed
candles, fill at the next open) and matches the backtest: Sharpe 0.99 vs 0.95, CAGR 21.1% vs 19.2%,
max drawdown −21.8% vs −21.1%.
