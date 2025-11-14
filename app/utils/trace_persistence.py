from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Dict
from uuid import UUID

from app.models.schemas import TaskResponse
from app.utils.logging import get_logger

logger = get_logger("trace_persistence")

# Ensure traces directory exists
TRACES_DIR = Path("traces")
TRACES_DIR.mkdir(exist_ok=True)


def save_trace(response: TaskResponse) -> None:
    """
    Save a minimal trace JSON file for post-hoc review.

    The trace file excludes raw LLM prompts and full tool outputs,
    only including summaries and truncation indicators.
    """
    try:
        trace_data: Dict[str, Any] = {
            "request_id": str(response.request_id),
            "task": response.task,
            "plan": [step.dict() for step in response.plan],
            "trace": [
                {
                    "step_id": entry.step_id,
                    "agent": entry.agent,
                    "action": entry.action,
                    "request": entry.request,
                    "response_summary": entry.response_summary,
                    "duration_ms": entry.duration_ms,
                    "truncated": entry.truncated,
                    "warnings": entry.warnings,
                }
                for entry in response.trace
            ],
            "final_result": {
                "type": response.final_result.type,
                "content": response.final_result.content,
            },
            "warnings": response.warnings,
        }

        trace_file = TRACES_DIR / f"{response.request_id}.json"
        with open(trace_file, "w") as f:
            json.dump(trace_data, f, indent=2, default=str)

        logger.info("trace_saved", request_id=str(response.request_id), trace_file=str(trace_file))
    except Exception as exc:
        logger.error("trace_save_failed", request_id=str(response.request_id), error=str(exc))
        # Don't raise - trace persistence is non-blocking


def load_trace(request_id: UUID) -> Dict[str, Any] | None:
    """
    Load a trace file by request_id.

    Returns None if the trace file doesn't exist.
    """
    trace_file = TRACES_DIR / f"{request_id}.json"
    if not trace_file.exists():
        return None

    try:
        with open(trace_file, "r") as f:
            return json.load(f)
    except Exception as exc:
        logger.error("trace_load_failed", request_id=str(request_id), error=str(exc))
        return None

