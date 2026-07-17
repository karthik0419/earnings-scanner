@echo off
cd /d "%~dp0"
echo =============================================
echo  SWING SCANNER V3 — Earnings Momentum
echo  %date% %time%
echo =============================================
echo.
python scanner.py --top 20 --min-score 40
pause
