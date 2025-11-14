#!/bin/bash
# Curl commands to trigger Jenkins pipeline

# ============================================================================
# Option 1: Via API Endpoint (Recommended - handles credentials from SSM)
# ============================================================================

# Basic trigger (no parameters)
curl -X POST "http://localhost:8000/api/jenkins/trigger?jenkins_url=https://13.59.177.177/jenkins/job/Devops/job/User/job/ProvideAccess-Pipeline/" \
  -H "Content-Type: application/json"

# Trigger with parameters (user onboarding)
curl -X POST "http://localhost:8000/api/jenkins/trigger?jenkins_url=https://13.59.177.177/jenkins/job/Devops/job/User/job/ProvideAccess-Pipeline/" \
  -H "Content-Type: application/json" \
  -d '{
    "parameters": {
      "Option": ["AWS", "GitHub"],
      "userEmail": "test@draup.com",
      "cc_email": "test@draup.com",
      "awsIAMUserGroup": "AWS",
      "githubTeam": "GitHub",
      "env_name": "dev",
      "useremail": "test@draup.com"
    }
  }'

# ============================================================================
# Option 2: Direct to Jenkins (requires credentials and CSRF token)
# ============================================================================
# Replace USERNAME and PASSWORD with your Jenkins credentials

JENKINS_BASE_URL="https://13.59.177.177/jenkins"
JENKINS_URL="${JENKINS_BASE_URL}/job/Devops/job/User/job/ProvideAccess-Pipeline/buildWithParameters"
USERNAME="your-jenkins-username"
PASSWORD="your-jenkins-api-token"

# Step 1: Get CSRF crumb token
CRUMB=$(curl -s -u "${USERNAME}:${PASSWORD}" \
  --insecure \
  "${JENKINS_BASE_URL}/crumbIssuer/api/xml?xpath=concat(//crumbRequestField,\":\",//crumb)" | \
  cut -d: -f2)

echo "CSRF Crumb: ${CRUMB}"

# Step 2: Trigger job with CSRF token
curl -X POST "${JENKINS_URL}" \
  -u "${USERNAME}:${PASSWORD}" \
  -H "Jenkins-Crumb: ${CRUMB}" \
  --insecure \
  -G \
  --data-urlencode "Option=AWS" \
  --data-urlencode "Option=GitHub" \
  --data-urlencode "userEmail=test@draup.com" \
  --data-urlencode "cc_email=test@draup.com" \
  --data-urlencode "awsIAMUserGroup=AWS" \
  --data-urlencode "githubTeam=GitHub" \
  --data-urlencode "env_name=dev" \
  --data-urlencode "useremail=test@draup.com"

# Alternative: Using query string directly (still needs CSRF token)
curl -X POST "${JENKINS_URL}?Option=AWS&Option=GitHub&userEmail=test@draup.com&cc_email=test@draup.com&awsIAMUserGroup=AWS&githubTeam=GitHub&env_name=dev&useremail=test@draup.com" \
  -u "${USERNAME}:${PASSWORD}" \
  -H "Jenkins-Crumb: ${CRUMB}" \
  --insecure

