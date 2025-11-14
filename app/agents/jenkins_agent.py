from __future__ import annotations

import asyncio
from typing import Any, List, Optional

from app.agents.base import AgentError, AgentResponse, BaseAgent
from app.services.jenkins_service import JenkinsService, JenkinsServiceError
from app.utils.logging import get_logger

logger = get_logger("JenkinsAgent")

# Valid services for user onboarding
VALID_SERVICES = {"AWS", "GitHub", "Confluence", "Database"}

# Default Jenkins URL for ProvideAccess-Pipeline
DEFAULT_JENKINS_URL = "https://13.59.177.177/jenkins/job/Devops/job/User/job/ProvideAccessPipeline_hackathon/"


class JenkinsAgent(BaseAgent):
    """Agent for triggering Jenkins ProvideAccess-Pipeline for user onboarding."""

    def __init__(
        self,
        jenkins_service: JenkinsService | None = None,
        jenkins_url: str = DEFAULT_JENKINS_URL,
        aws_region: str = "us-east-2",
        ssm_parameter_name: str = "jenkins",
        aws_access_key_id: str | None = None,
        aws_secret_access_key: str | None = None,
        aws_session_token: str | None = None,
    ) -> None:
        """
        Initialize Jenkins agent.

        Args:
            jenkins_service: Optional JenkinsService instance (for backward compatibility)
            jenkins_url: URL to the ProvideAccess-Pipeline job
            aws_region: AWS region for SSM parameter store
            ssm_parameter_name: SSM parameter name for Jenkins credentials
            aws_access_key_id: AWS access key ID
            aws_secret_access_key: AWS secret access key
            aws_session_token: Optional AWS session token
        """
        super().__init__("JenkinsAgent")
        # Store config for creating fresh service instances on each call
        # This ensures we always use the latest code, same as direct API route
        if jenkins_service is not None:
            # Backward compatibility: extract config from existing service if possible
            # Otherwise, we'll use defaults (not ideal but maintains compatibility)
            self._aws_region = getattr(jenkins_service, 'aws_region', aws_region)
            self._ssm_parameter_name = getattr(jenkins_service, 'ssm_parameter_name', ssm_parameter_name)
            self._aws_access_key_id = getattr(jenkins_service, 'aws_access_key_id', aws_access_key_id)
            self._aws_secret_access_key = getattr(jenkins_service, 'aws_secret_access_key', aws_secret_access_key)
            self._aws_session_token = getattr(jenkins_service, 'aws_session_token', aws_session_token)
        else:
            # Store config for creating fresh service instances
            self._aws_region = aws_region
            self._ssm_parameter_name = ssm_parameter_name
            self._aws_access_key_id = aws_access_key_id
            self._aws_secret_access_key = aws_secret_access_key
            self._aws_session_token = aws_session_token
        self.jenkins_url = jenkins_url
        self._log_info("Initialized Jenkins agent", jenkins_url=jenkins_url)

    async def trigger_provide_access(
        self,
        user_email: str,
        services: List[str],
        cc_email: Optional[str] = None,
        aws_iam_user_group: Optional[str] = None,
        github_team: Optional[str] = None,
        env_name: Optional[str] = None,
        **kwargs: Any,
    ) -> AgentResponse:
        """
        Trigger Jenkins ProvideAccess-Pipeline for user onboarding.

        Args:
            user_email: Email address of the user to onboard
            services: List of services to provision (must be subset of: AWS, GitHub, Confluence, Database)
            cc_email: Optional CC email for notifications
            aws_iam_user_group: Optional AWS IAM user group name
            github_team: Optional GitHub team name
            env_name: Optional environment name (e.g., "dev", "prod")
            **kwargs: Additional parameters to pass to Jenkins

        Returns:
            AgentResponse with pipeline status and queue URL

        Raises:
            AgentError: If validation fails or Jenkins trigger fails
        """
        # Validate user email
        if not user_email or "@" not in user_email:
            raise AgentError(f"Invalid user email: {user_email}")

        # Validate and normalize services
        services_set = {s.strip() for s in services if s.strip()}
        invalid_services = services_set - VALID_SERVICES
        if invalid_services:
            raise AgentError(
                f"Invalid services: {invalid_services}. Valid services are: {sorted(VALID_SERVICES)}"
            )

        if not services_set:
            raise AgentError("At least one service must be provided")

        # Build Jenkins parameters (matching working payload format)
        # Option must be a comma-separated string in an array: ["AWS,GitHub"] not ["AWS", "GitHub"]
        services_str = ",".join(sorted(list(services_set)))
        parameters: dict[str, Any] = {
            "Option": [services_str],  # Jenkins expects comma-separated string in array
            "userEmail": user_email,
            "cc_email": "prakhar.srivastava@draup.com",  # Always set to this value
            "env_name": env_name or "dev",  # Default to "dev" as in original script
        }

        # Add optional parameters (cc_email is always set above, so skip it here)
        if aws_iam_user_group:
            parameters["awsIAMUserGroup"] = aws_iam_user_group
        if github_team:
            parameters["githubTeam"] = github_team

        # Add any additional kwargs
        parameters.update(kwargs)

        # Also add useremail (some Jenkins jobs expect this duplicate)
        if "useremail" not in parameters:
            parameters["useremail"] = user_email

        self._log_info(
            "triggering_provide_access",
            user_email=user_email,
            services=sorted(list(services_set)),
            jenkins_url=self.jenkins_url,
        )

        # Trigger Jenkins job (run in thread pool since JenkinsService is sync)
        # Create a fresh service instance on each call, same as direct API route
        # This ensures we always use the latest code, including CSRF token handling
        try:
            # Create fresh service instance (same pattern as get_jenkins_service() in jenkins_routes.py)
            self._log_info(
                "creating_fresh_jenkins_service",
                has_aws_region=hasattr(self, '_aws_region'),
                has_ssm_param=hasattr(self, '_ssm_parameter_name'),
            )
            jenkins_service = JenkinsService(
                aws_region=getattr(self, '_aws_region', 'us-east-2'),
                ssm_parameter_name=getattr(self, '_ssm_parameter_name', 'jenkins'),
                aws_access_key_id=getattr(self, '_aws_access_key_id', None),
                aws_secret_access_key=getattr(self, '_aws_secret_access_key', None),
                aws_session_token=getattr(self, '_aws_session_token', None),
            )
            self._log_info("fresh_jenkins_service_created")
            result = await asyncio.to_thread(
                jenkins_service.trigger_jenkins_job,
                jenkins_url=self.jenkins_url,
                build_with_params=True,
                parameters=parameters,
            )

            # Format response
            response_data = {
                "success": result.get("success", False),
                "status_code": result.get("status_code"),
                "message": result.get("message", "Jenkins job triggered"),
                "queue_url": result.get("queue_url"),
                "user_email": user_email,
                "services": sorted(list(services_set)),
                "jenkins_url": self.jenkins_url,
            }

            self._log_info(
                "provide_access_triggered",
                user_email=user_email,
                services=sorted(list(services_set)),
                queue_url=result.get("queue_url"),
            )

            return AgentResponse(data=response_data)

        except JenkinsServiceError as e:
            self._log_error("jenkins_trigger_failed", user_email=user_email, error=str(e))
            raise AgentError(f"Failed to trigger Jenkins pipeline: {str(e)}") from e
        except Exception as e:
            self._log_error(
                "unexpected_error",
                user_email=user_email,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise AgentError(f"Unexpected error triggering Jenkins pipeline: {str(e)}") from e

