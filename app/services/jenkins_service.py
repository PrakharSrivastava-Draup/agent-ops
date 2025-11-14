"""
Jenkins service for triggering Jenkins pipeline jobs.
Fetches credentials from AWS SSM Parameter Store and triggers jobs.
"""

from __future__ import annotations

import json
from typing import Any, Dict, Optional

import boto3
import requests
from botocore.exceptions import BotoCoreError, ClientError
from requests.auth import HTTPBasicAuth
from urllib.parse import urljoin

from app.utils.logging import get_logger

logger = get_logger("JenkinsService")


class JenkinsServiceError(Exception):
    """Raised when Jenkins operations fail."""


class JenkinsService:
    """Service for interacting with Jenkins API."""

    def __init__(
        self,
        aws_region: str = "us-east-2",
        ssm_parameter_name: str = "jenkins",
        aws_access_key_id: Optional[str] = None,
        aws_secret_access_key: Optional[str] = None,
        aws_session_token: Optional[str] = None,
    ) -> None:
        """
        Initialize Jenkins service.

        Args:
            aws_region: AWS region for SSM Parameter Store
            ssm_parameter_name: Name of SSM parameter containing Jenkins credentials
            aws_access_key_id: Optional AWS access key (uses default credentials if not provided)
            aws_secret_access_key: Optional AWS secret key
            aws_session_token: Optional AWS session token (required for temporary credentials)
        """
        self.aws_region = aws_region
        self.ssm_parameter_name = ssm_parameter_name
        self.logger = logger

        # Initialize boto3 session
        session_kwargs: Dict[str, Any] = {"region_name": aws_region}
        if aws_access_key_id and aws_secret_access_key:
            session_kwargs.update(
                {
                    "aws_access_key_id": aws_access_key_id,
                    "aws_secret_access_key": aws_secret_access_key,
                }
            )
            # Add session token if provided (required for temporary credentials)
            if aws_session_token:
                session_kwargs["aws_session_token"] = aws_session_token
        self.boto_session = boto3.Session(**session_kwargs)

    def get_jenkins_credentials_from_ssm(self) -> tuple[str, str]:
        """
        Fetch Jenkins username and password/token from AWS SSM Parameter Store.

        Expects JSON format: {"username": "...", "password": "..."}

        Returns:
            tuple: (username, password/token)

        Raises:
            JenkinsServiceError: If credentials cannot be fetched or parsed
        """
        try:
            ssm_client = self.boto_session.client("ssm")
            response = ssm_client.get_parameter(
                Name=self.ssm_parameter_name, WithDecryption=True
            )
            value = response["Parameter"]["Value"]

            # Parse as JSON
            try:
                creds = json.loads(value)
                if isinstance(creds, dict):
                    username = creds.get("username") or creds.get("user")
                    password = creds.get("password") or creds.get("token")
                    if username and password:
                        self.logger.info(
                            "jenkins_credentials_fetched",
                            parameter_name=self.ssm_parameter_name,
                            username=username,
                        )
                        return username, password
                    else:
                        raise JenkinsServiceError(
                            f"JSON must contain 'username' and 'password' fields. "
                            f"Found keys: {list(creds.keys())}"
                        )
                else:
                    raise JenkinsServiceError(
                        f"SSM parameter '{self.ssm_parameter_name}' must be a JSON object, got {type(creds)}"
                    )
            except json.JSONDecodeError as e:
                raise JenkinsServiceError(
                    f"SSM parameter '{self.ssm_parameter_name}' must be valid JSON. Error: {e}"
                ) from e
        except (ClientError, BotoCoreError) as e:
            self.logger.error(
                "ssm_fetch_failed",
                parameter_name=self.ssm_parameter_name,
                error=str(e),
            )
            raise JenkinsServiceError(
                f"Failed to fetch credentials from SSM: {e}"
            ) from e
        except JenkinsServiceError:
            raise
        except Exception as e:
            self.logger.error(
                "unexpected_error_fetching_credentials", error=str(e), error_type=type(e).__name__
            )
            raise JenkinsServiceError(f"Unexpected error fetching credentials: {e}") from e

    def trigger_jenkins_job(
        self,
        jenkins_url: str,
        build_with_params: bool = False,
        parameters: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Trigger a Jenkins job.

        Args:
            jenkins_url: Full URL to the Jenkins job
            build_with_params: Whether to use buildWithParameters endpoint
            parameters: Optional dictionary of build parameters

        Returns:
            dict: Response with status, message, and optional queue_url

        Raises:
            JenkinsServiceError: If job trigger fails
        """
        # Get credentials from SSM
        username, password = self.get_jenkins_credentials_from_ssm()

        # Determine the endpoint based on whether parameters are provided
        if build_with_params and parameters:
            endpoint = "buildWithParameters"
        else:
            endpoint = "build"

        # Construct the full URL
        job_url = urljoin(jenkins_url.rstrip("/") + "/", endpoint)

        self.logger.info(
            "triggering_jenkins_job",
            jenkins_url=jenkins_url,
            endpoint=endpoint,
            job_url=job_url,
            has_parameters=bool(parameters),
            parameter_keys=list(parameters.keys()) if parameters else [],
            username=username,
        )

        # Set up authentication (matching original jenkis.py script - no CSRF tokens)
        auth = HTTPBasicAuth(username, password)

        # Prepare request
        try:
            if build_with_params and parameters:
                # POST with parameters - Jenkins buildWithParameters expects query string params
                # Match the original jenkis.py script behavior exactly
                self.logger.debug(
                    "jenkins_request_details",
                    url=job_url,
                    params=parameters,
                    has_auth=True,
                )
                response = requests.post(
                    job_url,
                    auth=auth,
                    params=parameters,  # Query string parameters (as in original script)
                    timeout=30,
                    verify=False,  # Note: SSL verification disabled
                )
                self.logger.info(
                    "jenkins_response_received",
                    status_code=response.status_code,
                    response_headers=dict(response.headers),
                )
            else:
                # Simple POST to trigger build
                response = requests.post(
                    job_url,
                    auth=auth,
                    timeout=30,
                    verify=False,  # Note: SSL verification disabled
                )

            # Check response
            if response.status_code == 201:
                result = {
                    "success": True,
                    "status_code": response.status_code,
                    "message": "Jenkins job triggered successfully",
                }
                if "Location" in response.headers:
                    result["queue_url"] = response.headers["Location"]
                self.logger.info("jenkins_job_triggered", status_code=201, queue_url=result.get("queue_url"))
                return result
            elif response.status_code == 200:
                result = {
                    "success": True,
                    "status_code": response.status_code,
                    "message": "Jenkins job triggered successfully",
                }
                self.logger.info("jenkins_job_triggered", status_code=200)
                return result
            else:
                error_msg = f"Failed to trigger Jenkins job. Status: {response.status_code}, Response: {response.text}"
                self.logger.error(
                    "jenkins_job_trigger_failed",
                    status_code=response.status_code,
                    response_text=response.text[:500],  # Limit log size
                )
                raise JenkinsServiceError(error_msg)
        except requests.exceptions.RequestException as e:
            self.logger.error("jenkins_request_failed", error=str(e), error_type=type(e).__name__)
            raise JenkinsServiceError(f"Request to Jenkins failed: {e}") from e

