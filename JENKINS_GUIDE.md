# Jenkins Pipeline API Guide

This guide explains how to use the Jenkins API endpoint to trigger Jenkins pipeline jobs for user onboarding (AWS, GitHub, Confluence, Database access).

---

## 🎯 What This Does

The Jenkins API allows you to trigger a Jenkins pipeline that automatically provisions access for newly onboarded users to:
- **AWS** (IAM users, groups, permissions)
- **GitHub** (team membership, repository access)
- **Confluence** (space access)
- **Database** (user creation, permissions)

---

## 🔑 Required Credentials

### Initial Setup - What You Need:

1. **AWS Credentials** (to access SSM Parameter Store)
   - `AWS_ACCESS_KEY_ID` - Your AWS access key
   - `AWS_SECRET_ACCESS_KEY` - Your AWS secret key
   - **OR** use AWS CLI configured credentials (`~/.aws/credentials`)
   - **OR** use IAM role (if running on EC2)

2. **AWS SSM Parameter Store Access**
   - The script fetches Jenkins credentials from AWS SSM Parameter Store
   - Parameter name: `jenkins` (default, configurable)
   - Region: `us-east-2` (default, configurable)
   - The parameter should contain JSON:
     ```json
     {
       "username": "your-jenkins-username",
       "password": "your-jenkins-api-token"
     }
     ```

3. **Jenkins API Token** (stored in SSM)
   - You need a Jenkins username and API token
   - To create a Jenkins API token:
     1. Log into Jenkins
     2. Click your username (top right)
     3. Click "Configure"
     4. Under "API Token", click "Add new Token"
     5. Copy the token (you'll only see it once!)

### Environment Variables

Add these to your `.env` file:

```bash
# AWS Credentials (for SSM access)
AWS_ACCESS_KEY_ID=your-aws-access-key-id
AWS_SECRET_ACCESS_KEY=your-aws-secret-access-key

# Optional: Override defaults
AWS_REGION=us-east-2
JENKINS_SSM_PARAMETER=jenkins
```

**Note**: If you're using AWS CLI credentials or IAM roles, you don't need to set `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` in `.env`.

---

## 🚀 How to Run

### Option 1: Using the API (Recommended)

1. **Start the FastAPI server**:
   ```bash
   uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
   ```

2. **Trigger Jenkins job via API**:

   **Simple build (no parameters)**:
   ```bash
   curl -X POST "http://localhost:8000/api/jenkins/trigger?jenkins_url=https://13.59.177.177/jenkins/job/Devops/job/User/job/ProvideAccess-Pipeline/" \
     -H "Content-Type: application/json"
   ```

   **Build with parameters**:
   ```bash
   curl -X POST "http://localhost:8000/api/jenkins/trigger?jenkins_url=https://13.59.177.177/jenkins/job/Devops/job/User/job/ProvideAccess-Pipeline/" \
     -H "Content-Type: application/json" \
     -d '{
       "parameters": {
         "Option": ["AWS", "GitHub"],
         "userEmail": "newuser@example.com",
         "cc_email": "manager@example.com",
         "awsIAMUserGroup": "Developers",
         "githubTeam": "engineering",
         "env_name": "dev",
         "useremail": "newuser@example.com"
       }
     }'
   ```

3. **Using the Interactive API Docs**:
   - Open browser: http://localhost:8000/docs
   - Find `/api/jenkins/trigger` endpoint
   - Click "Try it out"
   - Fill in:
     - `jenkins_url`: Your Jenkins job URL
     - `parameters`: JSON object with build parameters (optional)
   - Click "Execute"

### Option 2: Using the Original Script Directly

1. **Make sure you have AWS credentials configured**:
   ```bash
   # Option A: Set environment variables
   export AWS_ACCESS_KEY_ID=your-key
   export AWS_SECRET_ACCESS_KEY=your-secret
   export AWS_DEFAULT_REGION=us-east-2

   # Option B: Use AWS CLI configure
   aws configure
   ```

2. **Run the script**:
   ```bash
   python3 jenkis.py
   ```

3. **Modify the script** (`jenkis.py`) to change:
   - `JENKINS_URL`: The Jenkins job URL
   - `BUILD_PARAMETERS`: The parameters to pass to the job
   - `SSM_PARAMETER_NAME`: SSM parameter name (default: "jenkins")
   - `AWS_REGION`: AWS region (default: "us-east-2")

---

## 📋 API Endpoint Details

### POST `/api/jenkins/trigger`

**Query Parameters**:
- `jenkins_url` (required): Full URL to the Jenkins job
  - Example: `https://13.59.177.177/jenkins/job/Devops/job/User/job/ProvideAccess-Pipeline/`

**Request Body** (JSON, optional):
```json
{
  "parameters": {
    "Option": ["AWS", "GitHub"],
    "userEmail": "user@example.com",
    "cc_email": "cc@example.com",
    "awsIAMUserGroup": "Developers",
    "githubTeam": "engineering",
    "env_name": "dev",
    "useremail": "user@example.com"
  }
}
```

**Response** (200 OK):
```json
{
  "success": true,
  "status_code": 201,
  "message": "Jenkins job triggered successfully",
  "queue_url": "https://jenkins.example.com/queue/item/12345/"
}
```

**Error Response** (500 Internal Server Error):
```json
{
  "detail": "Failed to trigger Jenkins job: <error message>"
}
```

---

## 🔧 Common Parameters

Based on your script, here are common parameters for the `ProvideAccess-Pipeline`:

| Parameter | Type | Description | Example |
|-----------|------|-------------|---------|
| `Option` | Array | Services to provision | `["AWS", "GitHub"]` |
| `userEmail` | String | User's email address | `"user@example.com"` |
| `cc_email` | String | CC email for notifications | `"manager@example.com"` |
| `awsIAMUserGroup` | String | AWS IAM group name | `"Developers"` |
| `githubTeam` | String | GitHub team name | `"engineering"` |
| `env_name` | String | Environment name | `"dev"` |
| `useremail` | String | User email (duplicate?) | `"user@example.com"` |

---

## 🐛 Troubleshooting

### Error: "Failed to fetch credentials from SSM"

**Possible causes**:
1. AWS credentials not configured
2. SSM parameter doesn't exist
3. No permission to access SSM parameter
4. Wrong region

**Solutions**:
```bash
# Check AWS credentials
aws sts get-caller-identity

# Check if parameter exists
aws ssm get-parameter --name jenkins --region us-east-2

# Check your IAM permissions (need ssm:GetParameter)
```

### Error: "Failed to trigger Jenkins job"

**Possible causes**:
1. Jenkins URL is incorrect
2. Jenkins credentials are invalid
3. Jenkins job doesn't exist
4. Network connectivity issues

**Solutions**:
- Verify Jenkins URL is correct
- Check SSM parameter contains valid credentials
- Test Jenkins URL in browser
- Check network/firewall rules

### Error: "ModuleNotFoundError: No module named 'requests'"

**Solution**:
```bash
pip install -r requirements.txt
```

---

## 📝 Example: Complete User Onboarding

Here's a complete example for onboarding a new developer:

```bash
curl -X POST "http://localhost:8000/api/jenkins/trigger?jenkins_url=https://13.59.177.177/jenkins/job/Devops/job/User/job/ProvideAccess-Pipeline/" \
  -H "Content-Type: application/json" \
  -d '{
    "parameters": {
      "Option": ["AWS", "GitHub", "Confluence"],
      "userEmail": "john.doe@company.com",
      "cc_email": "manager@company.com",
      "awsIAMUserGroup": "Developers",
      "githubTeam": "backend-team",
      "env_name": "dev",
      "useremail": "john.doe@company.com"
    }
  }'
```

---

## 🔒 Security Notes

1. **Jenkins Credentials**: Stored securely in AWS SSM Parameter Store (encrypted)
2. **SSL Verification**: Currently disabled (`verify=False`) - consider enabling for production
3. **AWS Credentials**: Never commit credentials to git - use environment variables or IAM roles
4. **API Access**: Consider adding authentication to the API endpoint in production

---

## 📚 Related Files

- **API Route**: `app/api/jenkins_routes.py`
- **Service**: `app/services/jenkins_service.py`
- **Original Script**: `jenkis.py`
- **Configuration**: `app/config.py`

---

## 🆘 Getting Help

1. Check logs: Look at console output when running the server
2. Check AWS: Verify SSM parameter exists and is accessible
3. Test Jenkins: Try triggering the job manually in Jenkins UI
4. Check network: Ensure you can reach Jenkins server

---

**Last Updated**: After Jenkins API integration
**Status**: ✅ API endpoint ready to use

