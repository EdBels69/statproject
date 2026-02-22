#!/bin/bash

echo "🚀 Initializing Pro-CMT Dev Environment..."

# 1. Backend Setup
echo "📦 [Backend] Checking dependencies..."
cd backend
python3 -m pip install -r requirements.txt
cd ..

# 2. Frontend Setup
echo "📦 [Frontend] Checking dependencies..."
cd frontend
npm install
cd ..

# 3. Cleanup Ports
echo "🧹 Cleaning up old processes..."
lsof -ti:8000 | xargs kill -9 2>/dev/null
lsof -ti:5173 | xargs kill -9 2>/dev/null
lsof -ti:8080 | xargs kill -9 2>/dev/null

# 4. Start Backend
echo "🔥 Starting Backend (Port 8000)..."
# Use nohup to keep running, log to backend.log
cd backend
nohup python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload > ../backend.log 2>&1 &
BACKEND_PID=$!
echo "   PID: $BACKEND_PID"
cd ..

# 5. Start Frontend
echo "✨ Starting Frontend (Port 5173)..."
cd frontend
# VITE_API_URL handles connection to backend
nohup npm run dev -- --host > ../frontend.log 2>&1 &
FRONTEND_PID=$!
echo "   PID: $FRONTEND_PID"
cd ..

echo ""
echo "✅ SYSTEM ONLINE"
echo "------------------------------------------------"
echo "🖥️  UI:      http://localhost:5173"
echo "🔌 API:     http://localhost:8000/docs"
echo "------------------------------------------------"
echo "📝 Logs:    tail -f backend.log frontend.log"
echo "🛑 Stop:    ./stop.sh (or kill $BACKEND_PID $FRONTEND_PID)"
echo ""
