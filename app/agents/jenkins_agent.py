from __future__ import annotations

import asyncio
from typing import Any, List, Optional

from app.agents.base import AgentError, AgentResponse, BaseAgent
from app.config import get_settings
from app.services.jenkins_service import JenkinsService, JenkinsServiceError
from app.services.user_db import UserDB, UserDBError
from app.services.user_service import UserService, UserServiceError
from app.utils.logging import get_logger

logger = get_logger("JenkinsAgent")

# Valid services for user onboarding
VALID_SERVICES = {"AWS", "GitHub", "Confluence", "Database"}

# Valid team names (case-sensitive)
VALID_AWS_IAM_USER_GROUPS = {"DraupAppBackend", "DraupAppFrontend", "MathTeam"}
VALID_GITHUB_TEAMS = {"DraupAppBackend", "DraupAppFrontend", "MathTeam"}

# Fixed CC email address
FIXED_CC_EMAIL = "prakhar.srivastava@draup.com"

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

        # Validate aws_iam_user_group if provided (case-sensitive)
        if aws_iam_user_group:
            if aws_iam_user_group not in VALID_AWS_IAM_USER_GROUPS:
                raise AgentError(
                    f"Invalid aws_iam_user_group: '{aws_iam_user_group}'. "
                    f"Valid values are: {sorted(VALID_AWS_IAM_USER_GROUPS)} (case-sensitive)"
                )

        # Validate github_team if provided (case-sensitive)
        if github_team:
            if github_team not in VALID_GITHUB_TEAMS:
                raise AgentError(
                    f"Invalid github_team: '{github_team}'. "
                    f"Valid values are: {sorted(VALID_GITHUB_TEAMS)} (case-sensitive)"
                )

        # Build Jenkins parameters (matching exact payload format)
        # Option must be a comma-separated string in an array: ["AWS,GitHub"] not ["AWS", "GitHub"]
        services_str = ",".join(sorted(list(services_set)))
        parameters: dict[str, Any] = {
            "Option": [services_str],  # Jenkins expects comma-separated string in array
            "userEmail": user_email,
            "cc_email": FIXED_CC_EMAIL,  # Always fixed to this value
        }

        # Add optional parameters (case-sensitive parameter names)
        if aws_iam_user_group:
            parameters["awsIAMUserGroup"] = aws_iam_user_group  # Exact case-sensitive name
        if github_team:
            parameters["githubTeam"] = github_team  # Exact case-sensitive name

        # Add any additional kwargs (but exclude cc_email since it's fixed)
        for key, value in kwargs.items():
            if key not in ("cc_email", "useremail"):  # Don't override fixed values
                parameters[key] = value

        # Also add useremail (some Jenkins jobs expect this duplicate)
        if "useremail" not in parameters:
            parameters["useremail"] = user_email

        self._log_info(
            "triggering_provide_access",
            user_email=user_email,
            services=sorted(list(services_set)),
            jenkins_url=self.jenkins_url,
        )
        
        # Add entry to ai_live_reasoning before triggering Jenkins
        try:
            settings = get_settings()
            user_db = UserDB(db_path=settings.user_db_path)
            services_str = ", ".join(sorted(list(services_set)))
            user_db.append_ai_live_reasoning(
                message=f"Triggering Jenkins pipeline to provision access for services: {services_str}",
                user_email=user_email,
            )
        except Exception as e:
            # Log but don't fail if reasoning update fails
            self._log_error("failed_to_add_reasoning_entry", error=str(e), user_email=user_email)

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

            # Check if Jenkins trigger was successful
            jenkins_success = result.get("success", False)
            
            # Format response
            response_data = {
                "success": jenkins_success,
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
                success=jenkins_success,
            )

            # If Jenkins trigger was successful, wait 5 seconds then update access_items_status in DB
            if jenkins_success:
                # Add entry to ai_live_reasoning after successful Jenkins trigger
                try:
                    settings = get_settings()
                    user_db = UserDB(db_path=settings.user_db_path)
                    services_str = ", ".join(sorted(list(services_set)))
                    user_db.append_ai_live_reasoning(
                        message=f"Successfully triggered Jenkins pipeline for services: {services_str}. Queue URL: {result.get('queue_url', 'N/A')}",
                        user_email=user_email,
                    )
                except Exception as e:
                    # Log but don't fail if reasoning update fails
                    self._log_error("failed_to_add_reasoning_entry", error=str(e), user_email=user_email)
                
                self._log_info(
                    "jenkins_trigger_successful_waiting_5_seconds",
                    user_email=user_email,
                    services=sorted(list(services_set)),
                )
                await asyncio.sleep(5)
                
                try:
                    await self._update_access_items_status(
                        user_email=user_email,
                        services=list(services_set),
                    )
                    
                    # Add entry to ai_live_reasoning after updating access_items_status
                    try:
                        settings = get_settings()
                        user_db = UserDB(db_path=settings.user_db_path)
                        services_str = ", ".join(sorted(list(services_set)))
                        user_db.append_ai_live_reasoning(
                            message=f"Updated access_items_status to 'completed' for services: {services_str}",
                            user_email=user_email,
                        )
                    except Exception as e:
                        # Log but don't fail if reasoning update fails
                        self._log_error("failed_to_add_reasoning_entry", error=str(e), user_email=user_email)
                except Exception as e:
                    # Log error but don't fail the response - Jenkins was successful
                    self._log_error(
                        "access_items_status_update_failed",
                        user_email=user_email,
                        services=list(services_set),
                        error=str(e),
                        error_type=type(e).__name__,
                    )
                    # Add warning to response
                    if response_data.get("warnings") is None:
                        response_data["warnings"] = []
                    response_data["warnings"].append(
                        f"Jenkins trigger succeeded but failed to update access_items_status: {str(e)}"
                    )

            return AgentResponse(
                data=response_data,
                warnings=response_data.get("warnings", []) if response_data.get("warnings") else None,
            )

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

    async def _update_access_items_status(
        self,
        user_email: str,
        services: List[str],
    ) -> None:
        """
        Update access_items_status for successfully triggered services to 'completed'.
        
        Args:
            user_email: User email to identify the user
            services: List of services that were successfully triggered
        """
        try:
            # Get settings and create UserService
            settings = get_settings()
            user_db = UserDB(db_path=settings.user_db_path)
            user_service = UserService(db=user_db)
            
            # Find user by email
            user = user_db.get_user_by_emailid(user_email)
            if not user:
                self._log_warning(
                    "user_not_found_for_access_items_update",
                    user_email=user_email,
                )
                return
            
            # Get current access_items_status
            access_items_status = user.get("access_items_status", [])
            
            # Map Jenkins service names to access item names (case-insensitive)
            # Create a mapping of normalized service names to original service names
            service_normalized_map = {s.lower(): s for s in services}
            
            # Prepare updates for services that match access items
            access_items_updates = []
            for item in access_items_status:
                item_name = item.get("item", "").strip()
                item_status = item.get("status", "").strip()
                
                # Normalize item name for comparison
                item_name_normalized = item_name.lower()
                
                # Check if this item matches any of the triggered services
                if item_name_normalized in service_normalized_map:
                    # Update to 'completed' status
                    access_items_updates.append({
                        "item": item_name,  # Use original item name from DB
                        "status": "completed",
                    })
                    self._log_info(
                        "access_item_marked_for_completion",
                        user_email=user_email,
                        item=item_name,
                        jenkins_service=service_normalized_map[item_name_normalized],
                    )
            
            # Only update if there are items to update
            if not access_items_updates:
                self._log_warning(
                    "no_matching_access_items_for_update",
                    user_email=user_email,
                    services=services,
                    access_items=[item.get("item") for item in access_items_status],
                )
                return
            
            # Update user status
            user_service.update_user_status(
                emailid=user_email,
                status=None,  # Don't update overall status
                access_items_status=access_items_updates,
            )
            
            self._log_info(
                "access_items_status_updated",
                user_email=user_email,
                updated_items_count=len(access_items_updates),
                updated_items=[item["item"] for item in access_items_updates],
            )
            
        except UserServiceError as e:
            self._log_error(
                "user_service_error_updating_access_items",
                user_email=user_email,
                error=str(e),
            )
            raise
        except UserDBError as e:
            self._log_error(
                "user_db_error_updating_access_items",
                user_email=user_email,
                error=str(e),
            )
            raise
        except Exception as e:
            self._log_error(
                "unexpected_error_updating_access_items",
                user_email=user_email,
                error=str(e),
                error_type=type(e).__name__,
            )
            raise
    
    def _log_warning(self, message: str, **kwargs: Any) -> None:
        """Log a warning message."""
        self.logger.warning(message, **kwargs)

