# Ngrok URL Management Guide

## Quick Answer

**You don't need to update `.env` for ngrok!** 

The default CORS configuration allows all origins (`*`), so your API will work with **any** ngrok URL automatically, even when it changes.

## Current Setup

Your FastAPI app is configured with:
```python
cors_origins: ["*"]  # Default - allows all origins
```

This means:
- ✅ Works with any ngrok URL (even when it changes)
- ✅ Works with `https://alanna-tannish-sherilyn.ngrok-free.dev`
- ✅ Works with any future ngrok URL
- ✅ No `.env` updates needed

## Your Current Ngrok URL

**Current URL:** `https://alanna-tannish-sherilyn.ngrok-free.dev`

This URL will change each time you restart ngrok (free tier limitation).

## Options for Handling Changing URLs

### Option 1: Keep Default (Recommended for Development) ✅

**Do nothing!** The default `CORS_ORIGINS=*` works perfectly:
- No `.env` updates needed
- Works with any ngrok URL
- Perfect for development/testing

**Pros:**
- Zero maintenance
- Works immediately with any new ngrok URL
- No configuration needed

**Cons:**
- Less secure (allows all origins)
- Fine for development, but consider restricting for production

### Option 2: Get Static Ngrok Domain (Paid)

If you need a permanent URL, upgrade to ngrok paid plan:

1. Go to [ngrok pricing](https://ngrok.com/pricing)
2. Upgrade to a paid plan ($8/month+)
3. Reserve a static domain: `https://yourname.ngrok-free.app`
4. Use it in your ngrok command:
   ```bash
   ngrok http 8000 --domain=yourname.ngrok-free.app
   ```

Then you can optionally add to `.env`:
```bash
CORS_ORIGINS=https://yourname.ngrok-free.app
```

### Option 3: Update CORS Each Time (Not Recommended)

If you want to restrict CORS to specific origins, you'd need to:

1. Get your current ngrok URL
2. Update `.env`:
   ```bash
   CORS_ORIGINS=https://alanna-tannish-sherilyn.ngrok-free.dev
   ```
3. Restart FastAPI server

**This is tedious and not practical** since the URL changes each time.

### Option 4: Use Railway for Production (Recommended)

For production, deploy to Railway instead:
- Permanent URL: `https://your-app.railway.app`
- No URL changes
- Can set `CORS_ORIGINS=https://your-app.railway.app` in Railway variables
- See `RAILWAY_DEPLOYMENT.md` for details

## Recommended Setup

### For Development (Current)
```bash
# .env - No CORS_ORIGINS needed (uses default "*")
# Just use ngrok as-is
ngrok http 8000
```

### For Production (Railway)
```bash
# Railway Variables
CORS_ORIGINS=https://your-app.railway.app,https://yourdomain.com
```

## Quick Reference

| Scenario | CORS_ORIGINS | Action Needed |
|----------|--------------|---------------|
| Development with ngrok | `*` (default) | None - works automatically |
| Production on Railway | Your Railway URL | Set in Railway variables |
| Static ngrok domain | Your static domain | Set in `.env` or Railway |

## Testing Your Current Setup

Your current ngrok URL should work immediately:

```bash
# Test from command line
curl -X POST "https://alanna-tannish-sherilyn.ngrok-free.dev/api/execute_task" \
  -H "Content-Type: application/json" \
  -d '{"task": "Onboard test@example.com with AWS and GitHub access"}'

# Or visit in browser
https://alanna-tannish-sherilyn.ngrok-free.dev/docs
```

## Summary

**For your current setup:**
- ✅ No `.env` changes needed
- ✅ Current URL works: `https://alanna-tannish-sherilyn.ngrok-free.dev`
- ✅ Future ngrok URLs will work automatically
- ✅ When URL changes, just use the new one - no code changes needed

**When to update `.env`:**
- Only if you want to restrict CORS to specific domains (production)
- Only if you have a static ngrok domain (paid plan)
- For Railway deployment, set in Railway dashboard, not `.env`

