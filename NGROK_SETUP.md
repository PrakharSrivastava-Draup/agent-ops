# Ngrok Setup Guide

Ngrok requires a free account and authtoken to create tunnels. Follow these steps:

## Step 1: Sign up for ngrok (Free)

1. Go to [https://dashboard.ngrok.com/signup](https://dashboard.ngrok.com/signup)
2. Sign up with your email (free account is sufficient)
3. Verify your email

## Step 2: Get your authtoken

1. After signing up, go to [https://dashboard.ngrok.com/get-started/your-authtoken](https://dashboard.ngrok.com/get-started/your-authtoken)
2. Copy your authtoken (it looks like: `2abc123def456ghi789jkl012mno345pqr678stu901vwx_1A2B3C4D5E6F7G8H9I0J`)

## Step 3: Configure ngrok

Run this command with your authtoken:

```bash
ngrok config add-authtoken YOUR_AUTHTOKEN_HERE
```

## Step 4: Start your FastAPI app (if not running)

```bash
cd "/Users/prakharsrivastava/Agent Ops"
uvicorn app.main:app --host 0.0.0.0 --port 8000
```

Or if you have a script:
```bash
python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Step 5: Start ngrok tunnel

In a new terminal:

```bash
ngrok http 8000
```

You'll see output like:
```
Session Status                online
Account                       Your Name (Plan: Free)
Version                       3.x.x
Region                        United States (us)
Latency                       -
Web Interface                 http://127.0.0.1:4040
Forwarding                    https://abc123.ngrok-free.app -> http://localhost:8000
```

## Step 6: Use your ngrok URL

Your temporary public URL will be shown in the "Forwarding" line, for example:
- `https://abc123.ngrok-free.app`

You can now:
- Access your API: `https://abc123.ngrok-free.app/api/agents`
- View API docs: `https://abc123.ngrok-free.app/docs`
- Test endpoints: `https://abc123.ngrok-free.app/api/execute_task`

## Quick Start Script

After setting up your authtoken, you can use this script:

```bash
#!/bin/bash
# Start ngrok tunnel

# Check if app is running on port 8000
if ! lsof -ti:8000 > /dev/null; then
    echo "⚠️  FastAPI app is not running on port 8000"
    echo "Start it with: uvicorn app.main:app --host 0.0.0.0 --port 8000"
    exit 1
fi

# Start ngrok
echo "🚀 Starting ngrok tunnel..."
ngrok http 8000
```

## View ngrok Web Interface

While ngrok is running, you can view requests in real-time at:
- http://localhost:4040

This shows all HTTP requests going through the tunnel.

## Notes

- **Free tier**: URLs change each time you restart ngrok (unless you use a static domain)
- **Session duration**: Free tier has session limits, but sufficient for testing
- **HTTPS**: All ngrok URLs use HTTPS automatically
- **Security**: Be careful - your local app is now publicly accessible!

## Stop ngrok

Press `Ctrl+C` in the terminal where ngrok is running, or:
```bash
pkill ngrok
```

