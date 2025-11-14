"""
API routes for Jenkins pipeline operations.
"""

from __future__ import annotations

from typing import Any, Dict, Optional

from fastapi import APIRouter, Body, Depends, HTTPException, status
from pydantic import BaseModel

from app.api.dependencies import get_app_settings
from app.config import Settings
from app.services.jenkins_service import JenkinsService, JenkinsServiceError
from app.utils.logging import get_logger

logger = get_logger("jenkins_routes")

router = APIRouter()


class JenkinsTriggerRequest(BaseModel):
    """Request model for Jenkins trigger endpoint."""
    
    parameters: Optional[Dict[str, Any]] = None


def get_jenkins_service(settings: Settings = Depends(get_app_settings)) -> JenkinsService:
    """Create and return JenkinsService instance."""
    return JenkinsService(
        aws_region=getattr(settings, "aws_region", "us-east-2"),
        ssm_parameter_name=getattr(settings, "jenkins_ssm_parameter", "jenkins"),
        aws_access_key_id=settings.aws_access_key_id,
        aws_secret_access_key=settings.aws_secret_access_key,
        aws_session_token=getattr(settings, "aws_session_token", None),
    )


@router.post("/trigger", status_code=status.HTTP_200_OK)
async def trigger_jenkins_job(
    jenkins_url: str,
    request: Optional[JenkinsTriggerRequest] = Body(None),
    jenkins_service: JenkinsService = Depends(get_jenkins_service),
) -> Dict[str, Any]:
    """
    Trigger a Jenkins pipeline job.

    Args:
        jenkins_url: Full URL to the Jenkins job (e.g., https://jenkins.example.com/job/MyJob/)
        request: Optional request body with parameters dict

    Returns:
        dict: Response with success status, message, and optional queue_url

    Example:
        POST /api/jenkins/trigger?jenkins_url=https://jenkins.example.com/job/MyJob/
        Body: {
            "parameters": {
                "Option": ["AWS", "GitHub"],
                "userEmail": "user@example.com",
                "cc_email": "user@example.com",
                "awsIAMUserGroup": "AWS",
                "githubTeam": "GitHub",
                "env_name": "dev"
            }
        }
    """
    try:
        # Extract parameters from request body
        parameters = request.parameters if request else None
        build_with_params = parameters is not None and len(parameters) > 0
        
        logger.info(
            "trigger_jenkins_job_received",
            jenkins_url=jenkins_url,
            has_parameters=bool(parameters),
            parameter_keys=list(parameters.keys()) if parameters else [],
        )
        
        result = jenkins_service.trigger_jenkins_job(
            jenkins_url=jenkins_url,
            build_with_params=build_with_params,
            parameters=parameters,
        )
        return result
    except JenkinsServiceError as e:
        logger.error("jenkins_trigger_failed", error=str(e))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to trigger Jenkins job: {str(e)}",
        ) from e
    except Exception as e:
        logger.error("unexpected_error", error=str(e), error_type=type(e).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred while triggering Jenkins job.",
        ) from e

