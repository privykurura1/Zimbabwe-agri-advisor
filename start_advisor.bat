@echo off
title Mudimu - Offline Farm Advisor
cd /d "%~dp0"

echo Starting Mudimu (Offline Farm Advisor)...
echo.

REM Activate the virtual environment if it exists
if exist venv\Scripts\activate.bat (
    call venv\Scripts\activate.bat
) else (
    echo Warning: venv not found. Trying to run with system Python instead.
)

REM Start llama-server first — it loads the model ONCE and keeps it in
REM memory, so questions after the first are answered quickly instead of
REM reloading the whole model every time.
start "Llama Server - DO NOT CLOSE while using the app" cmd /k C:\llama.cpp\llama-server.exe -m model\qwen2.5-3b-instruct-q4_k_m.gguf -t 4 -c 4096 --port 8080

echo Waiting for the model to load into memory (this can take a moment)...
timeout /t 15 /nobreak >nul

REM Start the backend in its own window, so this window can continue.
REM The backend window MUST stay open while using the advisor - if it's
REM closed, the app will show "Advisor not running."
start "Mudimu Advisor - DO NOT CLOSE while using the app" cmd /k uvicorn app:app --port 8000

echo Waiting for the advisor to start...
timeout /t 5 /nobreak >nul

REM Open the interface in the default browser
start "" "index.html"

echo.
echo Mudimu is starting. A browser window should open shortly.
echo Keep the other black window open while you use the advisor.
echo You can close THIS window now.
echo.
pause