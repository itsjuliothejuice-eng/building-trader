# Paper trader: BTC + ETH trend system (fake money)

Runs the approved system from `docs/RESEARCH_LOG.md` (Studies 2 and 3) with a simulated **$5,000**
account, at live Coinbase prices. It **never logs in, needs no API key and places no orders.**

- Rules: long-only trend + volatility control, BTC and ETH half-accounts, 2/3 size, **spot**,
  Intro spot fees (0.90% + 0.05% slippage per side).
- It acts once a day, after the daily candle closes at **00:00 UTC (7 PM Central)**.
  It trades when the rule's target changes, or when a position drifts more than 10 points off target.
- Warns at −15% from the account's high, and at −20% sells everything and halts until you run `--resume`.

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
