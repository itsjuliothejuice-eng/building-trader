@echo off
cd /d "%~dp0"
set INBOX=%USERPROFILE%\Music\SongMixer\inbox
echo Drop Ableton stem folders or bounces into: %INBOX%
python -m songmixer watch "%INBOX%" --genre pop
pause
