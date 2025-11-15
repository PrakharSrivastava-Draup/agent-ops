from __future__ import annotations

from typing import Any, Dict, List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, validator


AgentName = Literal["GithubAgent", "AWSAgent", "JiraAgent", "JenkinsAgent", "EntraAgent"]


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


# User Management Schemas


class AccessItemStatus(BaseModel):
    """Access item status entry."""

    item: str
    status: str  # pending, in progress, completed
    timestamp: Optional[int] = None  # Unix timestamp in milliseconds


class OnboardUserRequest(BaseModel):
    """Request model for user onboarding."""

    name: str
    emailid: str
    contact_no: str
    location: str
    date_of_joining: str
    level: str
    team: str
    manager: str


class AILiveReasoningEntry(BaseModel):
    """Single entry in ai_live_reasoning array."""

    message: str
    timestamp: int  # Unix timestamp in milliseconds


class UserResponse(BaseModel):
    """User response model."""

    id: int
    name: str
    emailid: str
    contact_no: str
    location: str
    date_of_joining: str
    level: str
    team: str
    manager: str
    status: str
    access_items_status: List[AccessItemStatus]
    ai_live_reasoning: List[AILiveReasoningEntry] = Field(default_factory=list, description="AI live reasoning array with message and timestamp")


class POCConfigEntry(BaseModel):
    """Single POC config entry."""

    role: str
    team: str
    access_items: List[str]
    poc_id: str


class UpdateUserStatusRequest(BaseModel):
    """Request model for updating user status and access items."""

    emailid: str = Field(..., description="User email to identify the user")
    status: Optional[str] = Field(None, description="Overall user status (optional)")
    access_items_status: List[Dict[str, str]] = Field(
        ...,
        description="List of access items to update with format [{'item': 'item_name', 'status': 'pending|in progress|completed'}]",
    )
