# Credentials Setup Guide for Jenkins Flow

This guide explains exactly what credentials you need and where to put them to run the Jenkins pipeline API.

---

## 📁 Step 1: Create `.env` File

Create a `.env` file in the **root directory** of the project (`/Users/prakharsrivastava/Agent Ops/.env`).

---

## 🔑 Required Credentials for Jenkins Flow

### 1. **APP_SECRET_KEY** (Required)
- **What it is**: A random secret string for application security
- **Where to get it**: Generate a random string (any random string works for development)
- **How to generate**:
  ```bash
  # Option 1: Using Python
  python3 -c "import secrets; print(secrets.token_urlsafe(32))"
  
  # Option 2: Using OpenSSL
  openssl rand -hex 32
  
  # Option 3: Just use any random string
  # Example: "my-dev-secret-key-12345"
  ```
- **Add to `.env`**:
  ```bash
  APP_SECRET_KEY=your-generated-random-string-here
  ```

### 2. **AWS Credentials** (Required for Jenkins)
- **What they are**: AWS credentials to access AWS SSM Parameter Store
- **Where to get them**:
  - From your AWS IAM user/role
  - Or use existing AWS CLI credentials (`~/.aws/credentials`)
- **Add to `.env`**:
  ```bash
  AWS_ACCESS_KEY_ID=AKIAIOSFODNN7EXAMPLE
  AWS_SECRET_ACCESS_KEY=wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY
  AWS_REGION=us-east-2
  ```

**OR** if you have AWS CLI configured, you can skip these and use:
```bash
aws configure
# Enter your credentials there
```

### 3. **AWS SSM Parameter** (Required for Jenkins)
- **What it is**: AWS Systems Manager Parameter Store contains Jenkins credentials
- **Parameter Name**: `jenkins` (default, can be changed)
- **Parameter Format**: JSON string containing:
  ```json
  {
    "username": "your-jenkins-username",
    "password": "your-jenkins-api-token"
  }
  ```
- **Where to create it**:
  1. Go to AWS Console → Systems Manager → Parameter Store
  2. Click "Create parameter"
  3. Name: `jenkins`
  4. Type: `SecureString`
  5. Value: 
     ```json
     {"username": "your-jenkins-username", "password": "your-jenkins-api-token"}
     ```
  6. Click "Create parameter"

- **Optional: Override parameter name in `.env`**:
  ```bash
  JENKINS_SSM_PARAMETER=jenkins
  ```

### 4. **Jenkins API Token** (Required - stored in SSM)
- **What it is**: Jenkins API token for authentication
- **Where to get it**:
  1. Log into Jenkins web UI
  2. Click your username (top right corner)
  3. Click "Configure"
  4. Scroll to "API Token" section
  5. Click "Add new Token" or "Generate"
  6. **Copy the token immediately** (you'll only see it once!)
  7. Use this token as the `password` in the SSM parameter

---

## 📝 Complete `.env` File Template

Create `.env` file in the project root with this content:

```bash
# ============================================
# REQUIRED: Application Secret Key
# ============================================
APP_SECRET_KEY=your-random-secret-key-here

# ============================================
# REQUIRED: AWS Credentials (for SSM access)
# ============================================
AWS_ACCESS_KEY_ID=your-aws-access-key-id
AWS_SECRET_ACCESS_KEY=your-aws-secret-access-key
AWS_REGION=us-east-2

# ============================================
# OPTIONAL: Override Jenkins SSM Parameter Name
# ============================================
JENKINS_SSM_PARAMETER=jenkins

# ============================================
# OPTIONAL: Other service credentials
# (Not needed for Jenkins flow, but may be needed for other features)
# ============================================
# GITHUB_TOKEN=optional-github-token
# JIRA_BASE_URL=optional-jira-url
# JIRA_USERNAME=optional-jira-username
# JIRA_API_TOKEN=optional-jira-token
# OPENAI_API_KEY=optional-openai-key
# CURSOR_API_KEY=optional-cursor-key
# LOG_LEVEL=INFO
```

---

## 🔍 Step-by-Step Setup Process

### Step 1: Generate APP_SECRET_KEY
```bash
cd /Users/prakharsrivastava/Agent\ Ops
python3 -c "import secrets; print(secrets.token_urlsafe(32))"
# Copy the output
```

### Step 2: Get AWS Credentials
- Option A: Use existing AWS CLI credentials
  ```bash
  cat ~/.aws/credentials
  # Copy the access_key_id and secret_access_key
  ```

- Option B: Get from AWS Console
  1. Go to AWS Console → IAM → Users
  2. Click your user → Security credentials tab
  3. Create access key if you don't have one
  4. Copy Access Key ID and Secret Access Key

### Step 3: Create AWS SSM Parameter
```bash
# Using AWS CLI
aws ssm put-parameter \
  --name "jenkins" \
  --type "SecureString" \
  --value '{"username":"your-jenkins-username","password":"your-jenkins-api-token"}' \
  --region us-east-2

# Or create it via AWS Console:
# AWS Console → Systems Manager → Parameter Store → Create parameter
```

### Step 4: Get Jenkins API Token
1. Log into Jenkins: `https://13.59.177.177/jenkins/`
2. Click username (top right) → Configure
3. API Token section → Add new Token → Generate
4. Copy the token

### Step 5: Create `.env` File
```bash
cd /Users/prakharsrivastava/Agent\ Ops
cat > .env << 'EOF'
APP_SECRET_KEY=your-generated-secret-key
AWS_ACCESS_KEY_ID=your-aws-access-key-id
AWS_SECRET_ACCESS_KEY=your-aws-secret-access-key
AWS_REGION=us-east-2
JENKINS_SSM_PARAMETER=jenkins
EOF
```

### Step 6: Verify Setup
```bash
# Test AWS credentials
aws sts get-caller-identity

# Test SSM parameter access
aws ssm get-parameter --name jenkins --region us-east-2 --with-decryption

# Test Python import
python3 -c "from app.config import get_settings; print('Config loaded:', get_settings().app_name)"
```

---

## ✅ Verification Checklist

Before running the server, verify:

- [ ] `.env` file exists in project root
- [ ] `APP_SECRET_KEY` is set in `.env`
- [ ] `AWS_ACCESS_KEY_ID` is set in `.env` (or AWS CLI configured)
- [ ] `AWS_SECRET_ACCESS_KEY` is set in `.env` (or AWS CLI configured)
- [ ] `AWS_REGION` is set (default: us-east-2)
- [ ] AWS SSM parameter `jenkins` exists
- [ ] SSM parameter contains valid JSON with `username` and `password`
- [ ] Jenkins API token is valid and copied correctly

---

## 🚀 Running the Server

Once all credentials are set up:

```bash
cd /Users/prakharsrivastava/Agent\ Ops
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 🐛 Troubleshooting

### Error: "field required (type=value_error.missing)"
- **Cause**: Missing `APP_SECRET_KEY` in `.env`
- **Fix**: Add `APP_SECRET_KEY=your-random-string` to `.env`

### Error: "Failed to fetch credentials from SSM"
- **Cause**: AWS credentials incorrect or SSM parameter doesn't exist
- **Fix**: 
  ```bash
  # Test AWS access
  aws sts get-caller-identity
  
  # Test SSM access
  aws ssm get-parameter --name jenkins --region us-east-2 --with-decryption
  ```

### Error: "No credentials found"
- **Cause**: AWS credentials not configured
- **Fix**: Set `AWS_ACCESS_KEY_ID` and `AWS_SECRET_ACCESS_KEY` in `.env` or run `aws configure`

### Error: "Invalid JSON in SSM parameter"
- **Cause**: SSM parameter value is not valid JSON
- **Fix**: Update SSM parameter with correct JSON format:
  ```json
  {"username": "jenkins-user", "password": "api-token"}
  ```

---

## 📋 Quick Reference

| Credential | Required | Location | Example |
|------------|----------|----------|---------|
| `APP_SECRET_KEY` | ✅ Yes | `.env` file | `APP_SECRET_KEY=abc123...` |
| `AWS_ACCESS_KEY_ID` | ✅ Yes | `.env` file or AWS CLI | `AWS_ACCESS_KEY_ID=AKIA...` |
| `AWS_SECRET_ACCESS_KEY` | ✅ Yes | `.env` file or AWS CLI | `AWS_SECRET_ACCESS_KEY=xyz...` |
| `AWS_REGION` | ✅ Yes | `.env` file | `AWS_REGION=us-east-2` |
| Jenkins SSM Parameter | ✅ Yes | AWS SSM Parameter Store | Parameter name: `jenkins` |
| Jenkins Username | ✅ Yes | Inside SSM parameter JSON | `{"username": "..."}` |
| Jenkins API Token | ✅ Yes | Inside SSM parameter JSON | `{"password": "..."}` |

---

**Last Updated**: After Jenkins API integration
**Status**: Ready for setup

