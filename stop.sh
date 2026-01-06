#!/bin/bash
echo "Stopping Pro-CMT..."
lsof -ti:8000 | xargs kill -9 2>/dev/null
lsof -ti:5173 | xargs kill -9 2>/dev/null
echo "Shutdown complete."
