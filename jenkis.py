#!/usr/bin/env python3
"""
Script to trigger a Jenkins job
Fetches token from AWS SSM and authenticates with Jenkins API
"""
 
import os
import sys
import json
import requests
import boto3
from requests.auth import HTTPBasicAuth
from urllib.parse import urljoin, urlparse
from dotenv import load_dotenv

# Load environment variables from .env file if it exists
load_dotenv()


def get_jenkins_credentials_from_ssm(
    parameter_name: str = "jenkins", 
    region: str = "us-east-2",
    aws_access_key_id: str = None,
    aws_secret_access_key: str = None,
    aws_session_token: str = None,
) -> tuple:
    """
    Fetch Jenkins username and password/token from AWS SSM Parameter Store
    Expects JSON format: {"username": "...", "password": "..."}

    Args:
        parameter_name: SSM parameter name
        region: AWS region
        aws_access_key_id: Optional AWS access key (uses env vars or default credentials if not provided)
        aws_secret_access_key: Optional AWS secret key
        aws_session_token: Optional AWS session token

    Returns:
        tuple: (username, password/token)
    """
    try:
        # Use provided credentials or fall back to environment variables or default credentials
        session_kwargs = {"region_name": region}
        if aws_access_key_id and aws_secret_access_key:
            session_kwargs.update({
                "aws_access_key_id": aws_access_key_id,
                "aws_secret_access_key": aws_secret_access_key,
            })
            if aws_session_token:
                session_kwargs["aws_session_token"] = aws_session_token
        elif os.getenv("AWS_ACCESS_KEY_ID") and os.getenv("AWS_SECRET_ACCESS_KEY"):
            session_kwargs.update({
                "aws_access_key_id": os.getenv("AWS_ACCESS_KEY_ID"),
                "aws_secret_access_key": os.getenv("AWS_SECRET_ACCESS_KEY"),
            })
            if os.getenv("AWS_SESSION_TOKEN"):
                session_kwargs["aws_session_token"] = os.getenv("AWS_SESSION_TOKEN")
        
        ssm_client = boto3.client("ssm", **session_kwargs)
        response = ssm_client.get_parameter(Name=parameter_name, WithDecryption=True)
        value = response["Parameter"]["Value"]
 
        # Parse as JSON
        try:
            creds = json.loads(value)
            if isinstance(creds, dict):
                username = creds.get("username") or creds.get("user")
                password = creds.get("password") or creds.get("token")
                if username and password:
                    return username, password
                else:
                    raise ValueError(
                        f"JSON must contain 'username' and 'password' fields. "
                        f"Found keys: {list(creds.keys())}"
                    )
            else:
                raise ValueError(
                    f"SSM parameter '{parameter_name}' must be a JSON object, got {type(creds)}"
                )
        except json.JSONDecodeError as e:
            raise ValueError(
                f"SSM parameter '{parameter_name}' must be valid JSON. Error: {e}"
            )
    except ValueError as e:
        print(f"Error parsing credentials from SSM: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"Error fetching credentials from SSM: {e}")
        sys.exit(1)
 
 
def get_jenkins_crumb(jenkins_base_url: str, username: str, password: str) -> str | None:
    """
    Fetch Jenkins CSRF crumb token.

    Args:
        jenkins_base_url: Base URL of Jenkins (e.g., https://13.59.177.177/jenkins)
        username: Jenkins username
        password: Jenkins password/token

    Returns:
        CSRF crumb token or None if not available
    """
    try:
        crumb_url = urljoin(jenkins_base_url.rstrip("/") + "/", "crumbIssuer/api/xml?xpath=concat(//crumbRequestField,\":\",//crumb)")
        auth = HTTPBasicAuth(username, password)
        response = requests.get(crumb_url, auth=auth, timeout=10, verify=False)
        if response.status_code == 200:
            crumb = response.text.strip()
            if ":" in crumb:
                crumb_value = crumb.split(":", 1)[1]
                print(f"✅ CSRF crumb retrieved: {crumb_value[:20]}...")
                return crumb_value
        print(f"⚠️  Could not fetch CSRF crumb (status: {response.status_code})")
        return None
    except Exception as e:
        print(f"⚠️  Error fetching CSRF crumb: {e}")
        return None


def trigger_jenkins_job(
    jenkins_url: str,
    username: str,
    password: str,
    build_with_params: bool = False,
    parameters: dict = None,
) -> bool:
    """
    Trigger a Jenkins job

    Args:
        jenkins_url: Full URL to the Jenkins job
        username: Jenkins username
        token: Jenkins API token
        build_with_params: Whether to use buildWithParameters endpoint
        parameters: Optional dictionary of build parameters
    """
    # Determine the endpoint based on whether parameters are provided
    if build_with_params and parameters:
        endpoint = "buildWithParameters"
    else:
        endpoint = "build"

    # Construct the full URL
    job_url = urljoin(jenkins_url.rstrip("/") + "/", endpoint)

    print(f"Triggering Jenkins job: {job_url}")
    print(f"Username: {username}")

    # Set up authentication
    auth = HTTPBasicAuth(username, password)

    # Get CSRF crumb if available
    # Extract base URL from jenkins_url (e.g., https://13.59.177.177/jenkins)
    parsed = urlparse(jenkins_url)
    jenkins_base_url = f"{parsed.scheme}://{parsed.netloc}{parsed.path.split('/job/')[0]}"
    
    crumb = get_jenkins_crumb(jenkins_base_url, username, password)
    headers = {}
    if crumb:
        headers["Jenkins-Crumb"] = crumb

    # Prepare request
    if build_with_params and parameters:
        # POST with parameters
        response = requests.post(
            job_url,
            auth=auth,
            headers=headers,
            params=parameters,
            timeout=30,
            verify=False,
        )
    else:
        # Simple POST to trigger build
        response = requests.post(
            job_url,
            auth=auth,
            headers=headers,
            timeout=30,
            verify=False,
        )
 
    # Check response
    if response.status_code == 201:
        print("✅ Jenkins job triggered successfully!")
        print(f"   Response: {response.status_code} {response.reason}")
        if "Location" in response.headers:
            print(f"   Queue URL: {response.headers['Location']}")
        return True
    elif response.status_code == 200:
        print("✅ Jenkins job triggered successfully!")
        print(f"   Response: {response.status_code} {response.reason}")
        return True
    else:
        print("❌ Failed to trigger Jenkins job")
        print(f"   Status Code: {response.status_code}")
        print(f"   Response: {response.text}")
        return False
 
 
def main():
    # Configuration
    JENKINS_URL = (
        "https://13.59.177.177/jenkins/job/Devops/job/User/job/ProvideAccess-Pipeline/"
        # "https://13.59.177.177/jenkins/job/Devops/job/User/job/Database/job/CreateUser/"
    )
    SSM_PARAMETER_NAME = os.getenv("JENKINS_SSM_PARAMETER", "jenkins")
    AWS_REGION = os.getenv("AWS_REGION", "us-east-2")

    # Get AWS credentials from environment variables
    AWS_ACCESS_KEY_ID = os.getenv("AWS_ACCESS_KEY_ID")
    AWS_SECRET_ACCESS_KEY = os.getenv("AWS_SECRET_ACCESS_KEY")
    AWS_SESSION_TOKEN = os.getenv("AWS_SESSION_TOKEN")

    # Optional: Build parameters (set to None if not needed)
    # BUILD_PARAMETERS = None
    # Example with parameters:
    BUILD_PARAMETERS = {
        "Option": ["AWS", "GitHub"],
        "userEmail": "test@draup.com",
        "cc_email": "test@draup.com",
        "awsIAMUserGroup": "AWS",
        "githubTeam": "GitHub",
        "env_name": "dev",
        "useremail": "sanchit.agrawal@draup.com",
    }
    # BUILD_PARAMETERS = {"S3_BUCKET": [""]}

    print("=" * 70)
    print("Jenkins Job Trigger Script")
    print("=" * 70)

    # Fetch credentials from SSM
    print(f"\n📥 Fetching Jenkins credentials from SSM parameter: {SSM_PARAMETER_NAME}")
    print(f"   AWS Region: {AWS_REGION}")
    if AWS_ACCESS_KEY_ID:
        print(f"   Using AWS credentials from environment variables")
    else:
        print(f"   Using default AWS credentials (from ~/.aws/credentials or IAM role)")
    
    username, password = get_jenkins_credentials_from_ssm(
        SSM_PARAMETER_NAME, 
        AWS_REGION,
        aws_access_key_id=AWS_ACCESS_KEY_ID,
        aws_secret_access_key=AWS_SECRET_ACCESS_KEY,
        aws_session_token=AWS_SESSION_TOKEN,
    )
    print(f"✅ Credentials retrieved successfully (username: {username})")
 
    # Trigger the job
    print("\n🚀 Triggering Jenkins job...")
    use_params = BUILD_PARAMETERS is not None
    success = trigger_jenkins_job(
        JENKINS_URL,
        username,
        password,
        build_with_params=use_params,
        parameters=BUILD_PARAMETERS,
    )
 
    if success:
        print("\n✅ Job trigger completed successfully!")
        sys.exit(0)
    else:
        print("\n❌ Job trigger failed!")
        sys.exit(1)
 
 
if __name__ == "__main__":
    main()