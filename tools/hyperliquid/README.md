# Copy paper test: 20 Hyperliquid traders (Study 10, fake money)

Is there a trader worth copying? Study 9 found Hyperliquid's best traders of June–July mostly kept winning in August–October,
but not by enough to rule out luck. This is the forward test: the 20 picks are **fixed** in `picks.json`, chosen on data
through 2026-10-09, and followed with a simulated **$5,000** account for 60 days.

**It never logs in, needs no key and places no orders.** It reads public Hyperliquid data only.

- **Account:** $250 per trader.
- **What it copies:** each hour it copies their open positions in the coins Coinbase lists as CDE perps, at their size relative to their account.
- **Leverage:** never more than 1x per trader slice.
- **Costs:** Coinbase CDE fees (0.10% + 0.05% slippage per side) plus funding.
- Positions in coins Coinbase doesn't list are skipped. The report shows how much of their trading that covers.
- **Hard stop:** if the copy account falls 27% from its high, it closes everything and stops.

## Start it (Windows, from the repo folder)

```powershell
git pull
python tools/hyperliquid/copy_paper.py          # first check: copies their current positions
```
To keep it running, double-click `tools\hyperliquid\run_copy.bat` (it checks hourly and restarts itself).
Add a shortcut to it in `shell:startup` to start it with Windows, like the paper trader.

## Check on it

```powershell
python tools/hyperliquid/copy_paper.py --report
```
The report shows:
- the copy account vs the BTC+ETH paper system
- each trader's own profit since 2026-10-10

Logs: `data/copy/trades.csv` (every paper trade) and `data/copy/hourly.csv` (equity, exposure, drawdown).

## The verdict (2026-12-09)

To pass, all four must hold:
- the copy account is up after costs
- it beats the BTC+ETH paper system on return **and** worst drop
- at least 12 of 20 traders are profitable on their own
- the account never hit the −27% stop

Passing earns a longer test, not money. Checked offline by `tools/hyperliquid/test_copy_paper.py` (6 checks).
