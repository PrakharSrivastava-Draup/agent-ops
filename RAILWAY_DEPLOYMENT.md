# Railway Deployment Guide

This guide will help you deploy this FastAPI application to Railway.

## Prerequisites

1. A Railway account (sign up at [railway.app](https://railway.app))
2. GitHub repository with your code (or use Railway's GitHub integration)
3. All required environment variables (see below)

## Deployment Steps

### Option 1: Deploy via Railway Dashboard (Recommended)

1. **Create a New Project**
   - Go to [railway.app](https://railway.app)
   - Click "New Project"
   - Select "Deploy from GitHub repo" (or "Empty Project" if deploying manually)

2. **Configure the Service**
   - Railway will auto-detect Python from `requirements.txt`
   - The `Procfile` will be used to start the application
   - Railway will automatically set the `PORT` environment variable

3. **Set Environment Variables**
   - Go to your project → Variables tab
   - Add all required environment variables (see list below)

4. **Deploy**
   - Railway will automatically build and deploy on push to your main branch
   - Or click "Deploy" to trigger a manual deployment

### Option 2: Deploy via Railway CLI

1. **Install Railway CLI**
   ```bash
   npm i -g @railway/cli
   ```

2. **Login to Railway**
   ```bash
   railway login
   ```

3. **Initialize Railway in your project**
   ```bash
   railway init
   ```

4. **Set environment variables**
   ```bash
   railway variables set APP_SECRET_KEY=your-secret-key
   railway variables set OPENAI_API_KEY=your-openai-key
   # ... add all other variables
   ```

5. **Deploy**
   ```bash
   railway up
   ```

## Required Environment Variables

Add these in Railway's dashboard under **Variables**:

### Required
```bash
APP_SECRET_KEY=your-random-secret-key-here
```

### LLM Provider (at least one required)
```bash
OPENAI_API_KEY=your-openai-api-key
# OR
CURSOR_API_KEY=your-cursor-api-key
```

### Optional - GitHub
```bash
GITHUB_TOKEN=your-github-token
```

### Optional - AWS (for Jenkins SSM and AWS operations)
```bash
AWS_ACCESS_KEY_ID=your-aws-access-key
AWS_SECRET_ACCESS_KEY=your-aws-secret-key
AWS_SESSION_TOKEN=your-aws-session-token  # Optional, for temporary credentials
AWS_REGION=us-east-2  # Default: us-east-2
JENKINS_SSM_PARAMETER=jenkins  # Default: jenkins
```

### Optional - JIRA
```bash
JIRA_BASE_URL=https://your-domain.atlassian.net
JIRA_USERNAME=your-jira-email
JIRA_API_TOKEN=your-jira-api-token
```

### Optional - Logging
```bash
LOG_LEVEL=INFO  # Default: INFO
LOG_FILE=logs/app.log  # Default: logs/app.log
LOG_MAX_BYTES=10485760  # Default: 10MB
LOG_BACKUP_COUNT=5  # Default: 5
```

### Optional - User Database
```bash
USER_DB_PATH=data/users.db  # Default: data/users.db
```

## Important Notes

1. **Port Configuration**: Railway automatically provides a `PORT` environment variable. The `Procfile` uses this to start the server.

2. **Database Files**: The `data/users.db` file is ephemeral on Railway. If you need persistent storage, consider:
   - Using Railway's PostgreSQL service
   - Using an external database (AWS RDS, etc.)
   - Using Railway's volume feature for persistent storage

3. **Log Files**: Log files in `logs/` are also ephemeral. Consider:
   - Using Railway's built-in logging (viewable in dashboard)
   - Sending logs to an external service (Datadog, Logtail, etc.)
   - Using structured logging to stdout (which Railway captures)

4. **AWS Credentials**: For Jenkins SSM Parameter Store access, ensure your AWS credentials have:
   - `ssm:GetParameter` permission for the Jenkins credentials parameter
   - Access to the specified region (default: us-east-2)

5. **Build Time**: Railway will automatically:
   - Detect Python from `requirements.txt`
   - Install dependencies
   - Start the app using the `Procfile`

## Post-Deployment

1. **Check Logs**: View logs in Railway dashboard to ensure the app started correctly
2. **Test Endpoints**: 
   - Health check: `https://your-app.railway.app/docs`
   - API docs: `https://your-app.railway.app/docs`
3. **Monitor**: Use Railway's metrics dashboard to monitor resource usage

## Troubleshooting

### App won't start
- Check logs in Railway dashboard
- Verify all required environment variables are set
- Ensure `APP_SECRET_KEY` is set (required)

### Port errors
- Railway automatically sets `PORT`, but verify the Procfile uses `${PORT:-8000}`
- Check that the app binds to `0.0.0.0` not `127.0.0.1`

### AWS/SSM errors
- Verify AWS credentials are correct
- Check IAM permissions for SSM Parameter Store
- Verify the SSM parameter name matches `JENKINS_SSM_PARAMETER`

### Database errors
- If using SQLite (`data/users.db`), remember it's ephemeral
- Consider migrating to PostgreSQL for persistent storage

## Custom Domain (Optional)

1. Go to your project → Settings → Domains
2. Add a custom domain
3. Railway will provide DNS instructions

## Scaling

Railway automatically scales based on traffic. You can:
- Set resource limits in project settings
- Configure auto-scaling rules
- Monitor usage in the metrics dashboard

