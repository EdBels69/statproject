#!/bin/bash

echo "Starting StatProject..."

# Check if port 8000 is free (Backend)
if lsof -Pi :8000 -sTCP:LISTEN -t >/dev/null ; then
    echo "Warning: Port 8000 is busy. Attempting to kill..."
    lsof -ti:8000 | xargs kill -9
fi

# Check if port 5173 is free (Frontend)
if lsof -Pi :5173 -sTCP:LISTEN -t >/dev/null ; then
    echo "Warning: Port 5173 is busy. Attempting to kill..."
    lsof -ti:5173 | xargs kill -9
fi

# Start Backend in background (Host 0.0.0.0)
echo "-> Launching Backend..."
source backend/venv/bin/activate
nohup uvicorn app.main:app --app-dir backend --host 0.0.0.0 --port 8000 --reload > backend.log 2>&1 &
BACKEND_PID=$!
echo "   Backend PID: $BACKEND_PID"

# Start Frontend (Host 0.0.0.0)
echo "-> Launching Frontend..."
cd frontend
nohup npm run dev -- --host > frontend.log 2>&1 &
FRONTEND_PID=$!
echo "   Frontend PID: $FRONTEND_PID"

echo ""
echo "✅ Application started!"
echo "   Frontend: http://localhost:5173"
echo "   Backend:  http://localhost:8000"
echo ""
echo "Logs are being written to backend.log and frontend/frontend.log"
echo "To stop everything, run: kill $BACKEND_PID $FRONTEND_PID"
