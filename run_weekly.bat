@echo off
cd /d "%~dp0"
echo =======================================================
echo  EARNINGS MOMENTUM SCANNER
echo  %date%  %time%
echo =======================================================
echo.
echo  Select scan mode:
echo.
echo    1. Weekly Scan     - 588 stocks, all NSE sectors
echo                         Expected time: 25-35 min
echo                         Run every Saturday
echo.
echo    2. Discovery Scan  - 2131 stocks, full NSE EQ list
echo                         Catches IPOs and below-index stocks
echo                         Expected time: ~90 min
echo                         Run once a month
echo.
echo    3. Daily Scan      - Top sector stocks + backbone
echo                         Expected time: 5-10 min
echo                         Quick weekday check
echo.
set /p choice="Enter choice (1/2/3): "

if "%choice%"=="1" goto weekly
if "%choice%"=="2" goto discovery
if "%choice%"=="3" goto daily

echo Invalid choice. Running weekly by default.
goto weekly

:weekly
echo.
echo  Starting WEEKLY scan (588 stocks, min-score 35)...
echo  Results -> results\scanner_%date:~-4,4%-%date:~-10,2%-%date:~-7,2%.csv
echo.
python scanner.py --mode weekly --top 30 --min-score 35 --delay 2.0 --workers 6
goto done

:discovery
echo.
echo  Starting DISCOVERY scan (2131 stocks, min-score 40)...
echo  This will take ~90 minutes. Go grab a chai.
echo  Results -> results\scanner_%date:~-4,4%-%date:~-10,2%-%date:~-7,2%.csv
echo.
python scanner.py --mode discovery --top 50 --min-score 40 --delay 2.5 --workers 4
goto done

:daily
echo.
echo  Starting DAILY scan (top sectors + backbone, min-score 40)...
echo.
python scanner.py --mode daily --top 20 --min-score 40 --delay 1.0 --workers 8
goto done

:done
echo.
echo  Scan complete. Check results\ folder for output.
echo  Monthly watchlist -> results\watchlist_%date:~-4,4%-%date:~-10,2%.csv
echo.
pause
