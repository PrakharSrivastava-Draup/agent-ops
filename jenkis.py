#!/usr/bin/env python3
"""
Script to trigger a Jenkins job
Fetches token from AWS SSM and authenticates with Jenkins API
"""
 
import sys
import json
import requests
import boto3
from requests.auth import HTTPBasicAuth
from urllib.parse import urljoin
 
 
def get_jenkins_credentials_from_ssm(
    parameter_name: str = "jenkins", region: str = "us-east-2"
) -> tuple:
    """
    Fetch Jenkins username and password/token from AWS SSM Parameter Store
    Expects JSON format: {"username": "...", "password": "..."}
 
    Returns:
        tuple: (username, password/token)
    """
    try:
        ssm_client = boto3.client("ssm", region_name=region)
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
 
    # Prepare request
    if build_with_params and parameters:
        # POST with parameters
        response = requests.post(
            job_url,
            auth=auth,
            params=parameters,
            timeout=30,
            verify=False,
        )
    else:
        # Simple POST to trigger build
        response = requests.post(
            job_url,
            auth=auth,
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
    SSM_PARAMETER_NAME = "jenkins"
    AWS_REGION = "us-east-2"
 
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
    username, password = get_jenkins_credentials_from_ssm(
        SSM_PARAMETER_NAME, AWS_REGION
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