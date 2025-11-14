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
DEFAULT_JENKINS_URL = "https://13.59.177.177/jenkins/job/Devops/job/User/job/ProvideAccess-Pipeline/"


class JenkinsAgent(BaseAgent):
    """Agent for triggering Jenkins ProvideAccess-Pipeline for user onboarding."""

    def __init__(
        self,
        jenkins_service: JenkinsService,
        jenkins_url: str = DEFAULT_JENKINS_URL,
    ) -> None:
        """
        Initialize Jenkins agent.

        Args:
            jenkins_service: JenkinsService instance for triggering jobs
            jenkins_url: URL to the ProvideAccess-Pipeline job
        """
        super().__init__("JenkinsAgent")
        self.jenkins_service = jenkins_service
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

        # Build Jenkins parameters (matching original jenkis.py script)
        parameters: dict[str, Any] = {
            "Option": sorted(list(services_set)),  # Jenkins expects sorted list
            "userEmail": user_email,
            "env_name": env_name or "dev",  # Default to "dev" as in original script
        }

        # Add optional parameters
        if cc_email:
            parameters["cc_email"] = cc_email
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
        try:
            result = await asyncio.to_thread(
                self.jenkins_service.trigger_jenkins_job,
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

