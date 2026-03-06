@echo off
REM Build frontend, generate SSL cert if needed, and start with HTTPS
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

REM Generate self-signed cert if it doesn't exist
if not exist backend\cert.pem (
    echo === Generating SSL certificate ===
    python generate-cert.py
    if %errorlevel% neq 0 (
        echo Cert generation failed! Install cryptography: pip install cryptography
        pause
        exit /b 1
    )
)

echo.
echo === Starting HTTPS server ===
echo Access from this machine : https://localhost:8000
echo Access from LAN devices  : https://YOUR_IP:8000
echo.
cd backend
python -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --ssl-keyfile key.pem --ssl-certfile cert.pem
pause
