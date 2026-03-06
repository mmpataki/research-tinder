#!/bin/bash
# Build frontend, generate SSL cert if needed, and start with HTTPS
set -e

cd "$(dirname "$0")"

echo "=== Building frontend ==="
cd frontend
npm run build
cd ..

echo "=== Copying build to backend/static ==="
rm -rf backend/static
cp -r frontend/dist backend/static

# Generate self-signed cert if it doesn't exist
if [ ! -f backend/cert.pem ]; then
    echo "=== Generating SSL certificate ==="
    python3 generate-cert.py
fi

echo ""
echo "=== Starting HTTPS server ==="
echo "Access from this machine : https://localhost:8000"
echo "Access from LAN devices  : https://YOUR_IP:8000"
echo ""
cd backend
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --ssl-keyfile key.pem --ssl-certfile cert.pem
