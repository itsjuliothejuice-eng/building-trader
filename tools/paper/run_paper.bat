@echo off
REM Paper trader: checks every hour, acts once per day after the daily candle closes (00:00 UTC = 7 PM Central).
REM FAKE MONEY ONLY. Double-click, or add a shortcut to shell:startup like the Telegram collector.
cd /d "%~dp0..\.."
set PYTHONUTF8=1
:loop
python tools\paper\paper_trader.py --loop
echo Paper trader stopped. Restarting in 60 seconds... (close this window to quit)
timeout /t 60 /nobreak >nul
goto loop
