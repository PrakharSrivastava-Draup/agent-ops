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
        "Do not call any agent; only output the plan. Do not include any extra prose.\n\n"
        "For user onboarding tasks, use JenkinsAgent.trigger_provide_access with user_email "
        "and services list (AWS, GitHub, Confluence, Database). Extract the user email and "
        "requested services from the natural language request. Optional parameters: cc_email, "
        "aws_iam_user_group, github_team, env_name."
    )
    SYNTHESIS_SYSTEM_PROMPT = (
        "You are a synthesis assistant. Given the original task, the executed plan, and summarized "
        "agent step responses, produce a JSON object with a `final_result` field. "
        "The `final_result` must have exactly two fields:\n"
        "1. `type`: either \"text\" or \"structured\"\n"
        "2. `content`: a dictionary containing the result details\n\n"
        "Example format:\n"
        "{\n"
        '  "final_result": {\n'
        '    "type": "structured",\n'
        '    "content": {\n'
        '      "status": "success",\n'
        '      "message": "...",\n'
        '      "details": {...}\n'
        "    }\n"
        "  }\n"
        "}\n\n"
        "Return ONLY valid JSON, no markdown code blocks."
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
                {
                    "name": "JenkinsAgent",
                    "actions": ["trigger_provide_access"],
                    "description": "Triggers Jenkins ProvideAccess-Pipeline for user onboarding. Requires user_email (string) and services (list of: AWS, GitHub, Confluence, Database). Optional: cc_email, aws_iam_user_group, github_team, env_name (defaults to 'dev').",
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
        self.logger.info(
            "synthesis_start",
            task=task,
            plan_steps=len(plan),
            trace_entries=len(trace),
        )
        
        prepared_trace = self._prepare_trace(trace)
        structure = {
            "task": task,
            "plan": plan,
            "trace": prepared_trace,
        }
        user_prompt = json.dumps(structure, indent=2)
        
        self.logger.info(
            "synthesis_prompt_prepared",
            prompt_length=len(user_prompt),
            trace_entries_count=len(prepared_trace),
        )

        async with self._semaphore:
            response_text = await self.client.complete(
                system_prompt=self.SYNTHESIS_SYSTEM_PROMPT,
                user_prompt=user_prompt,
                temperature=0.1,
                max_output_tokens=1200,
            )
        
        self.logger.info(
            "synthesis_llm_response",
            response_length=len(response_text),
            response_preview=response_text[:200] if response_text else None,
        )

        # Strip markdown code blocks if present
        cleaned_response = response_text.strip()
        if cleaned_response.startswith("```"):
            # Remove opening ```json or ```
            lines = cleaned_response.split("\n")
            if lines[0].startswith("```"):
                lines = lines[1:]
            # Remove closing ```
            if lines and lines[-1].strip() == "```":
                lines = lines[:-1]
            cleaned_response = "\n".join(lines)
        
        self.logger.info(
            "synthesis_response_cleaned",
            original_length=len(response_text),
            cleaned_length=len(cleaned_response),
            was_wrapped=response_text.strip().startswith("```"),
        )

        try:
            parsed = json.loads(cleaned_response)
            self.logger.info(
                "synthesis_json_parsed",
                has_final_result="final_result" in parsed,
                keys=list(parsed.keys()) if isinstance(parsed, dict) else None,
            )
        except json.JSONDecodeError as exc:
            self.logger.error(
                "Invalid synthesis JSON",
                raw_output=response_text,
                error=str(exc),
                error_type=type(exc).__name__,
            )
            raise PlannerError(f"Synthesis returned invalid JSON: {str(exc)}") from exc

        if "final_result" not in parsed:
            self.logger.error(
                "synthesis_missing_final_result",
                parsed_keys=list(parsed.keys()) if isinstance(parsed, dict) else None,
                parsed_type=type(parsed).__name__,
            )
            raise PlannerError(
                f"Synthesis response missing `final_result`. Got keys: {list(parsed.keys()) if isinstance(parsed, dict) else 'not a dict'}"
            )
        self.logger.info("planner_synthesis_generated", final_result_type=type(parsed["final_result"]).__name__)
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

