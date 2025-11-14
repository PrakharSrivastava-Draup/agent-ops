#!/bin/bash
# Quick script to get current ngrok URL

echo "🔍 Fetching current ngrok URL..."
URL=$(curl -s http://localhost:4040/api/tunnels 2>/dev/null | python3 -c "
import sys, json
try:
    data = json.load(sys.stdin)
    tunnels = data.get('tunnels', [])
    if tunnels:
        print(tunnels[0]['public_url'])
    else:
        print('No active tunnels')
except:
    print('Ngrok not running or API not accessible')
" 2>/dev/null)

if [ -z "$URL" ] || [ "$URL" = "No active tunnels" ] || [ "$URL" = "Ngrok not running or API not accessible" ]; then
    echo "❌ Ngrok is not running or not accessible"
    echo ""
    echo "Start ngrok with:"
    echo "  ngrok http 8000"
    echo ""
    echo "Or use:"
    echo "  ./start_ngrok.sh"
else
    echo "✅ Current ngrok URL:"
    echo "   $URL"
    echo ""
    echo "📋 Use this URL to access your API:"
    echo "   $URL/docs"
    echo "   $URL/api/execute_task"
fi
