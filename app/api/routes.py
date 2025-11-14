from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, EmailStr, Field

from app.api.dependencies import get_orchestrator
from app.models.schemas import AgentDescriptor, TaskRequest, TaskResponse
from app.services.orchestrator import TaskExecutionError, TaskOrchestrator
from app.services.plan_validator import ALLOWED_ACTIONS
from app.utils.logging import get_logger

logger = get_logger("routes")

router = APIRouter()


@router.post("/execute_task", response_model=TaskResponse, status_code=status.HTTP_200_OK)
async def execute_task(
    request: TaskRequest,
    orchestrator: TaskOrchestrator = Depends(get_orchestrator),
) -> TaskResponse:
    """
    Execute a task by planning agent actions, executing them, and synthesizing results.

    Request body:
    - task: Natural language description of the task
    - context: Optional context hints (dict)

    Returns:
    - request_id: UUID for this request
    - plan: List of planned steps
    - trace: Execution trace with agent responses
    - final_result: LLM-synthesized result
    - warnings: List of warnings encountered
    """
    try:
        response = await orchestrator.execute(request)
        return response
    except TaskExecutionError as exc:
        logger.error("task_execution_failed", error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Task execution failed: {str(exc)}",
        ) from exc
    except Exception as exc:
        logger.error("unexpected_error", error=str(exc), error_type=type(exc).__name__)
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during task execution.",
        ) from exc


@router.get("/agents", response_model=Dict[str, AgentDescriptor], status_code=status.HTTP_200_OK)
async def list_agents() -> Dict[str, AgentDescriptor]:
    """
    List available agents and their capabilities.

    Returns a dictionary mapping agent names to their descriptors,
    including available actions.
    """
    agents: Dict[str, AgentDescriptor] = {}
    agent_descriptions = {
        "GithubAgent": "Read-only GitHub operations (PRs, commits, files)",
        "AWSAgent": "Read-only AWS operations (S3, EC2)",
        "JiraAgent": "Read-only JIRA operations (issues, search)",
        "JenkinsAgent": "User onboarding via Jenkins ProvideAccess-Pipeline (AWS, GitHub, Confluence, Database)",
        "EntraAgent": "Generate SSO-enabled company email addresses and create users in Microsoft Entra ID",
    }

    for agent_name, actions in ALLOWED_ACTIONS.items():
        agents[agent_name] = AgentDescriptor(
            name=agent_name,
            description=agent_descriptions.get(agent_name, "Access agent"),
            actions=list(actions.keys()),
        )

    return agents


class OnboardUserRequest(BaseModel):
    """Request model for user onboarding."""

    user_email: EmailStr = Field(..., description="Email address of the user to onboard")
    services: List[str] = Field(
        ...,
        min_items=1,
        description="List of services to provision (AWS, GitHub, Confluence, Database)",
    )
    cc_email: Optional[EmailStr] = Field(None, description="Optional CC email for notifications")
    task: Optional[str] = Field(
        None,
        description="Optional natural language task description. If not provided, will be auto-generated.",
    )


@router.post("/onboard_user", response_model=TaskResponse, status_code=status.HTTP_200_OK)
async def onboard_user(
    request: OnboardUserRequest,
    orchestrator: TaskOrchestrator = Depends(get_orchestrator),
) -> TaskResponse:
    """
    Onboard a new user by provisioning access to selected services via Jenkins pipeline.

    This is a convenience endpoint that automatically creates a task for the orchestrator.
    You can also use /api/execute_task with a natural language request.

    Request body:
    - user_email: Email address of the user to onboard
    - services: List of services to provision (must be subset of: AWS, GitHub, Confluence, Database)
    - cc_email: Optional CC email for notifications
    - task: Optional natural language task (auto-generated if not provided)

    Returns:
    - Standard TaskResponse with plan, trace, and final result
    """
    # Auto-generate task if not provided
    if not request.task:
        services_str = ", ".join(request.services)
        task = f"Onboard {request.user_email} with access to {services_str}"
    else:
        task = request.task

    # Create context with structured data for the LLM
    context: Dict[str, Any] = {
        "user_email": request.user_email,
        "services": request.services,
    }
    if request.cc_email:
        context["cc_email"] = request.cc_email

    # Create TaskRequest and execute
    task_request = TaskRequest(task=task, context=context)

    try:
        response = await orchestrator.execute(task_request)
        return response
    except TaskExecutionError as exc:
        logger.error("onboarding_failed", user_email=request.user_email, error=str(exc))
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"User onboarding failed: {str(exc)}",
        ) from exc
    except Exception as exc:
        logger.error(
            "unexpected_onboarding_error",
            user_email=request.user_email,
            error=str(exc),
            error_type=type(exc).__name__,
        )
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail="An unexpected error occurred during user onboarding.",
        ) from exc

