@echo off
cd /d "%~dp0"
echo =============================================
echo  EARNINGS MOMENTUM — WEEKLY SATURDAY SCAN
echo  %date% %time%
echo =============================================
echo.
echo This will scan the full NSE universe (~800 stocks).
echo Expected time: 15-25 minutes.
echo.
python scanner.py --mode weekly --top 30 --min-score 35 --delay 2.0
pause
