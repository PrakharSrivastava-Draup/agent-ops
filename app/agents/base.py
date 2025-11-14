from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from app.utils.logging import get_logger


class AgentError(Exception):
    """Base exception for agent failures."""


@dataclass
class AgentResponse:
    """Structured agent response."""

    data: Any
    truncated: bool = False
    warnings: list[str] | None = None


class BaseAgent:
    """Common functionality for access agents."""

    def __init__(self, name: str) -> None:
        self.name = name
        self.logger = get_logger(name)

    def _log_debug(self, message: str, **kwargs: Any) -> None:
        self.logger.debug(message, **kwargs)

    def _log_info(self, message: str, **kwargs: Any) -> None:
        self.logger.info(message, **kwargs)

    def _log_error(self, message: str, **kwargs: Any) -> None:
        self.logger.error(message, **kwargs)


