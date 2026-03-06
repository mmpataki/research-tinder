@echo off
REM Build the frontend for production and serve everything from the backend
cd /d "%~dp0"

echo === Building frontend ===
cd frontend
call npm run build
if %errorlevel% neq 0 (
    echo Frontend build failed!
    pause
    exit /b 1
)
cd ..

echo === Copying build to backend\static ===
if exist backend\static rmdir /s /q backend\static
xcopy /e /i /q frontend\dist backend\static

echo === Starting backend (serving frontend from /static) ===
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000
pause
