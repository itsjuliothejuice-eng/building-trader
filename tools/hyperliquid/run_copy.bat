@echo off
REM Copy paper test (Study 10): follows 20 Hyperliquid traders hourly with FAKE MONEY. No account, no key, no orders.
REM Double-click, or add a shortcut to shell:startup like the paper trader.
cd /d "%~dp0..\.."
set PYTHONUTF8=1
:loop
python tools\hyperliquid\copy_paper.py --loop
echo Copy paper test stopped. Restarting in 60 seconds... (close this window to quit)
timeout /t 60 /nobreak >nul
goto loop
