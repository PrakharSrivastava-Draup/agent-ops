# Railway Deployment Checklist

## ✅ Files Created for Railway

- [x] `Procfile` - Defines how to start the application
- [x] `railway.json` - Railway-specific configuration
- [x] `nixpacks.toml` - Alternative build configuration
- [x] `.railwayignore` - Files to exclude from deployment
- [x] `runtime.txt` - Python version specification
- [x] `RAILWAY_DEPLOYMENT.md` - Complete deployment guide
- [x] `railway.env.example` - Environment variables template

## 📋 Pre-Deployment Checklist

### 1. Code Preparation
- [ ] All code is committed to Git
- [ ] Code is pushed to GitHub (or your Git provider)
- [ ] `requirements.txt` is up to date
- [ ] No sensitive data in code (use environment variables)

### 2. Railway Account Setup
- [ ] Create Railway account at [railway.app](https://railway.app)
- [ ] Install Railway CLI (optional): `npm i -g @railway/cli`
- [ ] Login to Railway: `railway login`

### 3. Environment Variables
Copy from `railway.env.example` and set in Railway dashboard:

**Required:**
- [ ] `APP_SECRET_KEY` - Generate a random string

**LLM Provider (at least one):**
- [ ] `OPENAI_API_KEY` - Your OpenAI API key
- [ ] OR `CURSOR_API_KEY` - Your Cursor API key

**Optional but Recommended:**
- [ ] `GITHUB_TOKEN` - For GitHub agent operations
- [ ] `AWS_ACCESS_KEY_ID` - For Jenkins SSM and AWS operations
- [ ] `AWS_SECRET_ACCESS_KEY` - For Jenkins SSM and AWS operations
- [ ] `AWS_REGION` - Default: `us-east-2`
- [ ] `JENKINS_SSM_PARAMETER` - Default: `jenkins`

**Optional:**
- [ ] `JIRA_BASE_URL` - For JIRA agent operations
- [ ] `JIRA_USERNAME` - For JIRA agent operations
- [ ] `JIRA_API_TOKEN` - For JIRA agent operations
- [ ] `LOG_LEVEL` - Default: `INFO`

### 4. Deployment Steps

**Via Dashboard:**
1. [ ] Go to [railway.app](https://railway.app)
2. [ ] Click "New Project"
3. [ ] Select "Deploy from GitHub repo"
4. [ ] Choose your repository
5. [ ] Railway will auto-detect Python and build
6. [ ] Add environment variables in Variables tab
7. [ ] Wait for deployment to complete
8. [ ] Check logs to verify app started correctly

**Via CLI:**
1. [ ] Run `railway init` in project directory
2. [ ] Run `railway variables set KEY=value` for each variable
3. [ ] Run `railway up` to deploy

### 5. Post-Deployment Verification

- [ ] Check Railway logs for startup errors
- [ ] Visit `https://your-app.railway.app/docs` - Should show FastAPI docs
- [ ] Test health endpoint: `https://your-app.railway.app/api/agents`
- [ ] Test execute_task endpoint with a simple task
- [ ] Monitor Railway dashboard for resource usage

### 6. Important Notes

**Database:**
- SQLite database (`data/users.db`) is ephemeral on Railway
- Consider using Railway PostgreSQL or external database for production

**Logs:**
- View logs in Railway dashboard
- Logs are captured from stdout/stderr
- File-based logs (`logs/app.log`) are ephemeral

**Port:**
- Railway automatically sets `PORT` environment variable
- `Procfile` uses `${PORT:-8000}` to handle this

**AWS Credentials:**
- Ensure AWS credentials have `ssm:GetParameter` permission
- Verify region matches your SSM parameter location

## 🚀 Quick Deploy Command

```bash
# If using Railway CLI
railway login
railway init
railway variables set APP_SECRET_KEY=$(openssl rand -hex 32)
railway variables set OPENAI_API_KEY=your-key-here
railway up
```

## 📚 Additional Resources

- [Railway Documentation](https://docs.railway.app)
- [Railway Discord](https://discord.gg/railway)
- See `RAILWAY_DEPLOYMENT.md` for detailed instructions

