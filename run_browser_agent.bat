@echo off
echo --- Launching Candy Browser Agent ☄️ ---
echo.

REM Optional: Check for virtualenv or just assume python path
REM pip install -r requirements.txt (skipped for speed, assumed installed)

echo Starting Backend Server...
echo Open your browser to: http://127.0.0.1:8000
echo.

uvicorn backend.main:app --host 127.0.0.1 --port 8000

pause
