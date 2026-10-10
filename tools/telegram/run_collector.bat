@echo off
REM Starts the Telegram collector and restarts it if it stops (e.g. network drop).
REM Double-click this, or add it to Windows Task Scheduler "At log on".
cd /d "%~dp0..\.."
set PYTHONUTF8=1
:loop
python tools\telegram\collector.py
echo Collector stopped. Restarting in 60 seconds... (close this window to quit)
timeout /t 60 /nobreak >nul
goto loop
