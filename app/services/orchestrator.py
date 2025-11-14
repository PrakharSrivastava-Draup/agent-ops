from __future__ import annotations

import inspect
import json
import time
from copy import deepcopy
from typing import Any, Dict, List
from uuid import UUID, uuid4

from app.agents import AgentError, AgentResponse, BaseAgent
from app.models.schemas import FinalResult, PlanStep, TaskRequest, TaskResponse, TraceEntry
from app.services.llm_planner import LLMPlanner, PlannerError
from app.services.plan_validator import PlanValidationError, PlanValidator
from app.utils.logging import get_logger
from app.utils.trace_persistence import save_trace


class TaskExecutionError(Exception):
    """Raised when orchestration fails to complete."""

    def __init__(self, message: str, *, trace_entry: TraceEntry | None = None) -> None:
        super().__init__(message)
        self.trace_entry = trace_entry


class TaskOrchestrator:
    """Coordinate planning, validation, agent execution, and synthesis."""

    def __init__(
        self,
        *,
        planner: LLMPlanner,
        validator: PlanValidator,
        agents: Dict[str, BaseAgent],
    ) -> None:
        self.planner = planner
        self.validator = validator
        self.agents = agents
        self.logger = get_logger("TaskOrchestrator")

    async def execute(self, request: TaskRequest) -> TaskResponse:
        """Execute a task end-to-end."""
        request_id = uuid4()
        self.logger.info("orchestrator_start", request_id=str(request_id), task=request.task)
        raw_plan = await self._generate_plan(request)
        try:
            plan_steps = self.validator.validate(raw_plan)
        except PlanValidationError as exc:
            self.logger.error("plan_validation_failed", error=str(exc))
            raise TaskExecutionError("Plan validation failed.") from exc
        trace_entries: List[TraceEntry] = []
        warnings: List[str] = []

        for step in plan_steps:
            try:
                trace_entry, step_warnings = await self._execute_step(request_id, step)
                trace_entries.append(trace_entry)
                warnings.extend(step_warnings)
            except TaskExecutionError as exc:
                if exc.trace_entry:
                    trace_entries.append(exc.trace_entry)
                warnings.append(str(exc))
                raise

        synthesis = await self._synthesize(request, plan_steps, trace_entries)

        final_result = FinalResult.parse_obj(synthesis["final_result"])
        synthesis_warnings = synthesis.get("warnings", [])
        if isinstance(synthesis_warnings, list):
            warnings.extend(str(item) for item in synthesis_warnings)

        response = TaskResponse(
            request_id=UUID(str(request_id)),
            task=request.task,
            plan=plan_steps,
            trace=trace_entries,
            final_result=final_result,
            warnings=warnings,
        )
        self.logger.info("orchestrator_complete", request_id=str(request_id))
        # Save trace for post-hoc review
        try:
            save_trace(response)
        except Exception as exc:
            self.logger.warning("trace_save_failed", request_id=str(request_id), error=str(exc))
        return response

    async def _generate_plan(self, request: TaskRequest) -> List[dict[str, Any]]:
        try:
            return await self.planner.plan(task=request.task, context=request.context)
        except PlannerError as exc:
            self.logger.error("plan_generation_failed", error=str(exc))
            raise TaskExecutionError("Planning step failed.") from exc

    async def _execute_step(self, request_id: UUID, step: PlanStep) -> tuple[TraceEntry, list[str]]:
        agent = self.agents.get(step.agent)
        if not agent:
            raise TaskExecutionError(f"Agent `{step.agent}` is not available.")
        action = getattr(agent, step.action, None)
        if not action:
            raise TaskExecutionError(f"Action `{step.action}` is not available on agent `{step.agent}`.")

        args = deepcopy(step.args)
        start = time.perf_counter()
        self.logger.info(
            "agent_step_start",
            request_id=str(request_id),
            step_id=step.step_id,
            agent=step.agent,
            action=step.action,
        )

        try:
            result = action(**args)
            if inspect.isawaitable(result):
                result = await result
            if isinstance(result, AgentResponse):
                response_data = result.data
                truncated = result.truncated
                step_warnings = result.warnings or []
            else:
                response_data = result
                truncated = False
                step_warnings = []
        except AgentError as exc:
            duration_ms = self._calculate_duration_ms(start)
            trace_entry = TraceEntry(
                step_id=step.step_id,
                agent=step.agent,
                action=step.action,
                request=args,
                response_summary=str(exc),
                duration_ms=duration_ms,
                truncated=False,
                warnings=[str(exc)],
            )
            self.logger.error(
                "agent_step_failed",
                request_id=str(request_id),
                step_id=step.step_id,
                agent=step.agent,
                action=step.action,
                error=str(exc),
                duration_ms=duration_ms,
            )
            raise TaskExecutionError(
                f"Agent step `{step.agent}.{step.action}` failed.",
                trace_entry=trace_entry,
            ) from exc

        duration_ms = self._calculate_duration_ms(start)
        response_summary, summary_truncated = self._summarize_response(response_data)

        trace_entry = TraceEntry(
            step_id=step.step_id,
            agent=step.agent,
            action=step.action,
            request=args,
            response_summary=response_summary,
            duration_ms=duration_ms,
            truncated=truncated or summary_truncated,
            warnings=[str(w) for w in step_warnings],
        )

        self.logger.info(
            "agent_step_complete",
            request_id=str(request_id),
            step_id=step.step_id,
            agent=step.agent,
            action=step.action,
            duration_ms=duration_ms,
        )

        warning_messages = [str(w) for w in step_warnings if w]
        return trace_entry, warning_messages

    async def _synthesize(
        self,
        request: TaskRequest,
        plan_steps: List[PlanStep],
        trace_entries: List[TraceEntry],
    ) -> Dict[str, Any]:
        try:
            return await self.planner.synthesize(
                task=request.task,
                plan=[step.dict() for step in plan_steps],
                trace=[entry.dict() for entry in trace_entries],
            )
        except PlannerError as exc:
            self.logger.error("synthesis_failed", error=str(exc))
            raise TaskExecutionError("Failed to synthesize final result.") from exc

    @staticmethod
    def _calculate_duration_ms(start_time: float) -> int:
        return int((time.perf_counter() - start_time) * 1000)

    @staticmethod
    def _summarize_response(data: Any, limit: int = 1200) -> tuple[str, bool]:
        """Return a truncated JSON summary of the agent response."""
        try:
            serialized = json.dumps(data, default=str) if data is not None else "{}"
        except (TypeError, ValueError):
            serialized = str(data)
        if len(serialized) <= limit:
            return serialized, False
        return serialized[:limit] + "...TRUNCATED...", True

