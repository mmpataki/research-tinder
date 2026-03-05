#!/bin/bash
# Build the frontend for production and serve everything from the backend
set -e

cd "$(dirname "$0")"

echo "=== Building frontend ==="
cd frontend
npm run build
cd ..

echo "=== Copying build to backend/static ==="
rm -rf backend/static
cp -r frontend/dist backend/static

echo "=== Starting backend (serving frontend from /static) ==="
cd backend
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
