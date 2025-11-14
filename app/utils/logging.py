import logging
from typing import Any

import structlog  # type: ignore


def configure_logging(level: str = "INFO") -> None:
    """Configure structlog and standard logging."""
    logging.basicConfig(
        format="%(message)s",
        level=getattr(logging, level.upper(), logging.INFO),
    )

    structlog.configure(
        processors=[
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.JSONRenderer(),
        ],
        wrapper_class=structlog.make_filtering_bound_logger(logging.INFO),
        context_class=dict,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str, **initial_values: Any) -> structlog.stdlib.BoundLogger:
    """Return a structlog bound logger."""
    return structlog.get_logger(name).bind(**initial_values)

