from __future__ import annotations

from typing import Dict

from fastapi import APIRouter, Depends, HTTPException, status

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
    }

    for agent_name, actions in ALLOWED_ACTIONS.items():
        agents[agent_name] = AgentDescriptor(
            name=agent_name,
            description=agent_descriptions.get(agent_name, "Access agent"),
            actions=list(actions.keys()),
        )

    return agents

