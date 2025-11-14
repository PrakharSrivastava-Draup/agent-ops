from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, validator


AgentName = Literal["GithubAgent", "AWSAgent", "JiraAgent"]


class TaskRequest(BaseModel):
    """Incoming task payload."""

    task: str = Field(..., min_length=1, description="Natural language task to execute")
    context: Dict[str, Any] = Field(default_factory=dict)


class PlanStep(BaseModel):
    """Validated plan step from the LLM planner."""

    step_id: int
    agent: AgentName
    action: str
    args: Dict[str, Any] = Field(default_factory=dict)

    @validator("step_id")
    def validate_step_id(cls, value: int) -> int:
        if value < 0:
            raise ValueError("step_id must be non-negative.")
        return value


class TraceEntry(BaseModel):
    """Execution trace step summary."""

    step_id: int
    agent: AgentName
    action: str
    request: Dict[str, Any]
    response_summary: str
    duration_ms: int
    truncated: bool = False
    warnings: List[str] = Field(default_factory=list)


class FinalResult(BaseModel):
    """LLM synthesized final result."""

    type: Literal["text", "structured"]
    content: Dict[str, Any]


class TaskResponse(BaseModel):
    """API response payload."""

    request_id: UUID
    task: str
    plan: List[PlanStep]
    trace: List[TraceEntry]
    final_result: FinalResult
    warnings: List[str] = Field(default_factory=list)


class AgentDescriptor(BaseModel):
    """Metadata describing available agents."""

    name: AgentName
    description: str
    actions: List[str]


