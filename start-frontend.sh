#!/bin/bash
# Start the Research Tinder frontend dev server
cd "$(dirname "$0")/frontend"
echo "Starting Research Tinder frontend on http://localhost:5173"
npm run dev --host
