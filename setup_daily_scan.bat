@echo off
:: Setup daily scan at 6:30 PM (after market close)
:: Usage: setup_daily_scan.bat +972501234567

set PHONE=%1
set PYTHON=C:\Users\Ido\AppData\Local\Programs\Python\Python39\python.exe
set SCRIPT=C:\Users\Ido\stock_screener\daily_scan.py

if "%PHONE%"=="" (
    echo Usage: setup_daily_scan.bat +972501234567
    echo Running without WhatsApp alerts...
    schtasks /create /tn "ReversalIQ Daily Scan" /tr "\"%PYTHON%\" \"%SCRIPT%\"" /sc daily /st 18:30 /f
) else (
    echo Setting up daily scan with WhatsApp alerts to %PHONE%
    schtasks /create /tn "ReversalIQ Daily Scan" /tr "\"%PYTHON%\" \"%SCRIPT%\" %PHONE%" /sc daily /st 18:30 /f
)

echo.
echo Done! Daily scan scheduled at 6:30 PM.
echo To change the time: schtasks /change /tn "ReversalIQ Daily Scan" /st HH:MM
echo To delete: schtasks /delete /tn "ReversalIQ Daily Scan" /f
echo To run now: schtasks /run /tn "ReversalIQ Daily Scan"
pause
