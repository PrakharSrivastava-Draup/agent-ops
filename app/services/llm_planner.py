from __future__ import annotations

import json
from typing import Any
from app.services.llm_client import AsyncSemaphore, LLMClient
from app.utils.logging import get_logger


class PlannerError(Exception):
    """Raised when the planning LLM returns invalid output."""


class LLMPlanner:
    """LLM-backed planner responsible for orchestrating agent calls."""

    PLAN_SYSTEM_PROMPT = (
        "You are a deterministic planning assistant. Given a user task and available agent "
        "capabilities, return a JSON array named `plan` where each element is "
        "`{step_id, agent, action, args}`. Only use provided agent actions. "
        "Do not call any agent; only output the plan. Do not include any extra prose."
    )
    SYNTHESIS_SYSTEM_PROMPT = (
        "You are a synthesis assistant. Given the original task, the executed plan, and summarized "
        "agent step responses, produce a final JSON `final_result` that answers the task and lists "
        "recommended next steps and any uncertainty or warnings."
    )

    def __init__(self, client: LLMClient) -> None:
        self.client = client
        self.logger = get_logger("LLMPlanner")
        self._semaphore = AsyncSemaphore(value=1)

    async def plan(self, task: str, context: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        """Produce a structured plan for the task."""
        payload = {
            "task": task,
            "context": context or {},
            "available_agents": [
                {
                    "name": "GithubAgent",
                    "actions": ["get_pr", "list_recent_commits", "get_file"],
                },
                {
                    "name": "AWSAgent",
                    "actions": ["list_s3_buckets", "describe_ec2_instances", "get_s3_object_head"],
                },
                {
                    "name": "JiraAgent",
                    "actions": ["get_issue", "search_issues"],
                },
            ],
        }
        user_prompt = json.dumps(payload, indent=2)

        async with self._semaphore:
            response_text = await self.client.complete(
                system_prompt=self.PLAN_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                temperature=0.0,
                max_output_tokens=800,
            )

        try:
            parsed = json.loads(response_text)
        except json.JSONDecodeError as exc:
            self.logger.error("Invalid planner JSON", raw_output=response_text)
            raise PlannerError("Planner returned invalid JSON.") from exc

        if isinstance(parsed, dict):
            plan = parsed.get("plan")
        else:
            plan = parsed
        if not isinstance(plan, list):
            raise PlannerError("Planner response must be a list of steps.")

        # Basic validation: ensure each step contains required keys.
        for index, step in enumerate(plan):
            if not isinstance(step, dict):
                raise PlannerError(f"Plan step {index} must be an object.")
            for field in ("step_id", "agent", "action", "args"):
                if field not in step:
                    raise PlannerError(f"Plan step {index} missing field '{field}'.")

        self.logger.info("planner_plan_generated", steps=len(plan))
        return plan

    async def synthesize(
        self,
        task: str,
        plan: list[dict[str, Any]],
        trace: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Synthesize final result based on plan execution trace."""
        structure = {
            "task": task,
            "plan": plan,
            "trace": self._prepare_trace(trace),
        }
        user_prompt = json.dumps(structure, indent=2)

        async with self._semaphore:
            response_text = await self.client.complete(
                system_prompt=self.SYNTHESIS_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                temperature=0.1,
                max_output_tokens=1200,
            )

        try:
            parsed = json.loads(response_text)
        except json.JSONDecodeError as exc:
            self.logger.error("Invalid synthesis JSON", raw_output=response_text)
            raise PlannerError("Synthesis returned invalid JSON.") from exc

        if "final_result" not in parsed:
            raise PlannerError("Synthesis response missing `final_result`.")
        self.logger.info("planner_synthesis_generated")
        return parsed

    def _prepare_trace(self, trace: list[dict[str, Any]]) -> list[dict[str, Any]]:
        """Truncate and sanitize trace records for LLM consumption."""
        prepared: list[dict[str, Any]] = []
        for entry in trace:
            truncated_summary, truncated = self._truncate_text(entry.get("response_summary", ""), 1200)
            prepared.append(
                {
                    "step_id": entry.get("step_id"),
                    "agent": entry.get("agent"),
                    "action": entry.get("action"),
                    "response_summary": truncated_summary,
                    "truncated": truncated or entry.get("truncated", False),
                    "duration_ms": entry.get("duration_ms"),
                }
            )
        return prepared

    @staticmethod
    def _truncate_text(text: str, limit: int) -> tuple[str, bool]:
        if len(text) <= limit:
            return text, False
        return text[:limit] + "...TRUNCATED...", True

