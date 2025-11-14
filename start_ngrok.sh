#!/bin/bash
# Quick script to start ngrok tunnel

echo "🔍 Checking if FastAPI app is running on port 8000..."
if ! lsof -ti:8000 > /dev/null 2>&1; then
    echo "⚠️  FastAPI app is not running on port 8000"
    echo ""
    echo "Please start it first with:"
    echo "  uvicorn app.main:app --host 0.0.0.0 --port 8000"
    echo ""
    read -p "Press Enter to start ngrok anyway (it will wait for the app) or Ctrl+C to cancel..."
fi

echo "🚀 Starting ngrok tunnel to port 8000..."
echo "📊 View requests at: http://localhost:4040"
echo "🛑 Press Ctrl+C to stop"
echo ""

ngrok http 8000
