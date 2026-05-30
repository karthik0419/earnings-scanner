@echo off
cd /d "%~dp0"
echo =============================================
echo  EARNINGS MOMENTUM BACKTESTER
echo  %date% %time%
echo =============================================
echo.
python backtest.py --stocks nifty500.txt --top 100
pause
