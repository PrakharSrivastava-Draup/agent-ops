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
from urllib.parse import urljoin, urlparse

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
        self.aws_access_key_id = aws_access_key_id
        self.aws_secret_access_key = aws_secret_access_key
        self.aws_session_token = aws_session_token
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

    def get_jenkins_crumb(self, jenkins_base_url: str, username: str, password: str) -> Optional[str]:
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
            self.logger.info("csrf_crumb_fetch_attempt", url=crumb_url, status_code=response.status_code)
            if response.status_code == 200:
                crumb = response.text.strip()
                self.logger.info("csrf_crumb_raw_response", response_text=crumb[:100])
                if ":" in crumb:
                    crumb_value = crumb.split(":", 1)[1]
                    self.logger.info("csrf_crumb_extracted", crumb_length=len(crumb_value))
                    return crumb_value
                else:
                    self.logger.warning("csrf_crumb_no_colon", response_text=crumb[:100])
            else:
                self.logger.warning("csrf_crumb_fetch_failed", status_code=response.status_code, response_text=response.text[:200])
            return None
        except Exception as e:
            self.logger.error("failed_to_fetch_crumb", error=str(e), error_type=type(e).__name__)
            return None

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
        self.logger.info("trigger_jenkins_job_started", jenkins_url=jenkins_url, build_with_params=build_with_params, has_parameters=bool(parameters))
        username, password = self.get_jenkins_credentials_from_ssm()
        self.logger.info("credentials_obtained", username=username[:3] + "***" if username else None)

        # Determine the endpoint based on whether parameters are provided
        if build_with_params and parameters:
            endpoint = "buildWithParameters"
        else:
            endpoint = "build"

        # Construct the full URL
        job_url = urljoin(jenkins_url.rstrip("/") + "/", endpoint)

        # Extract base URL for CSRF token (e.g., https://13.59.177.177/jenkins)
        parsed = urlparse(jenkins_url)
        # Extract base path (everything before /job/)
        path_parts = parsed.path.split('/job/')
        base_path = path_parts[0] if path_parts else '/jenkins'
        jenkins_base_url = f"{parsed.scheme}://{parsed.netloc}{base_path}"

        # Get CSRF crumb token
        self.logger.info("fetching_csrf_token", base_url=jenkins_base_url, jenkins_url=jenkins_url)
        crumb = self.get_jenkins_crumb(jenkins_base_url, username, password)
        self.logger.info("csrf_fetch_complete", crumb_obtained=bool(crumb), base_url=jenkins_base_url)
        headers = {}
        if crumb:
            headers["Jenkins-Crumb"] = crumb
            self.logger.info("csrf_crumb_fetched", has_crumb=True, crumb_length=len(crumb), crumb_preview=crumb[:20] + "..." if len(crumb) > 20 else crumb)
        else:
            self.logger.warning("csrf_crumb_not_fetched", base_url=jenkins_base_url, username=username[:3] + "***" if username else None)

        self.logger.info(
            "triggering_jenkins_job",
            jenkins_url=jenkins_url,
            endpoint=endpoint,
            job_url=job_url,
            has_parameters=bool(parameters),
            parameter_keys=list(parameters.keys()) if parameters else [],
            username=username,
            has_csrf_token=bool(crumb),
            csrf_in_headers=bool(headers.get("Jenkins-Crumb")),
        )

        # Set up authentication
        auth = HTTPBasicAuth(username, password)

        # Prepare request
        try:
            if build_with_params and parameters:
                # POST with parameters - Jenkins buildWithParameters expects query string params
                # Convert list parameters to multiple query params (e.g., Option=AWS&Option=GitHub)
                # requests library handles this automatically, but we ensure lists are properly formatted
                formatted_params = {}
                for key, value in parameters.items():
                    if isinstance(value, list):
                        # For lists, requests will create multiple params with same key
                        formatted_params[key] = value
                    else:
                        formatted_params[key] = value
                
                self.logger.info(
                    "jenkins_request_details",
                    url=job_url,
                    params=formatted_params,
                    has_auth=True,
                    has_csrf_header=bool(headers.get("Jenkins-Crumb")),
                    csrf_header_value=headers.get("Jenkins-Crumb", "")[:20] + "..." if headers.get("Jenkins-Crumb") else None,
                )
                response = requests.post(
                    job_url,
                    auth=auth,
                    params=formatted_params,  # Query string parameters (as in original script)
                    headers=headers,
                    timeout=30,
                    verify=False,  # Note: SSL verification disabled
                )
                self.logger.info(
                    "jenkins_response_received",
                    status_code=response.status_code,
                    response_headers=dict(response.headers),
                    response_text_preview=response.text[:200] if response.status_code != 201 else None,
                )
            else:
                # Simple POST to trigger build
                response = requests.post(
                    job_url,
                    auth=auth,
                    headers=headers,
                    timeout=30,
                    verify=False,  # Note: SSL verification disabled
                )

            # Check response
            self.logger.info(
                "jenkins_response_check",
                status_code=response.status_code,
                has_location_header="Location" in response.headers,
                response_preview=response.text[:300] if response.status_code != 201 and response.status_code != 200 else None,
            )
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
                # Log detailed error information
                self.logger.error(
                    "jenkins_job_trigger_failed",
                    status_code=response.status_code,
                    response_headers=dict(response.headers),
                    response_text_preview=response.text[:500],
                    request_url=job_url,
                    has_csrf_header=bool(headers.get("Jenkins-Crumb")),
                )
                error_msg = f"Failed to trigger Jenkins job. Status: {response.status_code}, Response: {response.text[:500]}"
                raise JenkinsServiceError(error_msg)
        except requests.exceptions.RequestException as e:
            self.logger.error("jenkins_request_failed", error=str(e), error_type=type(e).__name__)
            raise JenkinsServiceError(f"Request to Jenkins failed: {e}") from e

