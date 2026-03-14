#!/bin/bash

# Port Definitions
API_PORT=8000
WEB_PORT=5173

echo "🚀 Starting Sinopac Quant Pro Local Development..."

# Ensure we are in the root directory
cd "$(dirname "$0")"

# 1. Start Backend (API)
echo "📦 Starting Backend API on port $API_PORT..."
python3 -m uvicorn api.main:app --host 0.0.0.0 --port $API_PORT --reload > /tmp/backend.log 2>&1 &
BACKEND_PID=$!

# 2. Start Frontend (Vite)
echo "🎨 Starting Frontend (Vite) on port $WEB_PORT..."
cd web
npm run dev -- --port $WEB_PORT &
FRONTEND_PID=$!

echo ""
echo "✅ Local Environment is Up!"
echo "   - Backend: http://localhost:$API_PORT"
echo "   - Frontend: http://localhost:$WEB_PORT"
echo ""
echo "Press Ctrl+C to stop all services."

# Trap Ctrl+C to kill background processes
trap "kill $BACKEND_PID $FRONTEND_PID; exit" INT
wait
