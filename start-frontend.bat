@echo off
REM Start the Research Tinder frontend dev server
cd /d "%~dp0frontend"
echo Starting Research Tinder frontend on http://localhost:5173
npm run dev -- --host
pause
