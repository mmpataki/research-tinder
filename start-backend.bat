@echo off
REM Start the Research Tinder backend
cd /d "%~dp0backend"
echo Starting Research Tinder backend on http://localhost:8000
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
pause
