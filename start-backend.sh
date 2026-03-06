#!/bin/bash
# Start the Research Tinder backend
cd "$(dirname "$0")/backend"
echo "Starting Research Tinder backend on http://localhost:8000"
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
