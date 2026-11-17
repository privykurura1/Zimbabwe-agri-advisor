@echo off
title Murimi Fara - Offline Farm Advisor
cd /d "%~dp0"

echo Starting Murimi Fara 2.0 (no AI model to load - it starts in seconds)...
echo.
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else (
    echo Warning: venv not found. Trying to run with system Python instead.
)

REM --host 0.0.0.0 lets phones on this computer's Wi-Fi/hotspot use it too.
REM Keep the window that opens running while you use Murimi Fara.
start "Murimi Fara - DO NOT CLOSE while using the app" cmd /k python -m uvicorn app:app --host 0.0.0.0 --port 8000

timeout /t 4 /nobreak >nul
start "" "http://127.0.0.1:8000/"

echo Murimi Fara is open in your browser.
echo Phones on this Wi-Fi: open the address shown at the top of the page.
echo You can close THIS window now.
pause
