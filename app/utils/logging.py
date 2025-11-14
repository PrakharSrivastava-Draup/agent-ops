import logging
from pathlib import Path
from typing import Any, Optional

import structlog  # type: ignore
from logging.handlers import RotatingFileHandler


def configure_logging(
    level: str = "INFO",
    log_file: Optional[str] = "logs/app.log",
    log_max_bytes: int = 10485760,  # 10MB
    log_backup_count: int = 5,
) -> None:
    """
    Configure structlog and standard logging with both console and file output.
    
    Args:
        level: Logging level (DEBUG, INFO, WARNING, ERROR, CRITICAL)
        log_file: Path to log file (relative to workspace root)
        log_max_bytes: Maximum size of log file before rotation (default: 10MB)
        log_backup_count: Number of backup log files to keep (default: 5)
    """
    log_level = getattr(logging, level.upper(), logging.INFO)
    
    # Create logs directory if it doesn't exist
    if log_file:
        # Resolve path relative to workspace root (where the app is run from)
        log_path = Path(log_file)
        if not log_path.is_absolute():
            # If relative, make it relative to current working directory
            log_path = Path.cwd() / log_file
        log_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Set up file handler with rotation
        file_handler = RotatingFileHandler(
            str(log_path),
            maxBytes=log_max_bytes,
            backupCount=log_backup_count,
            encoding="utf-8",
        )
        file_handler.setLevel(log_level)
        file_handler.setFormatter(logging.Formatter("%(message)s"))
    
    # Set up console handler
    console_handler = logging.StreamHandler()
    console_handler.setLevel(log_level)
    console_handler.setFormatter(logging.Formatter("%(message)s"))
    
    # Configure root logger with both handlers
    root_logger = logging.getLogger()
    root_logger.setLevel(log_level)
    root_logger.handlers.clear()  # Clear any existing handlers
    
    if log_file:
        root_logger.addHandler(file_handler)
    root_logger.addHandler(console_handler)

    # Configure structlog to use standard logging
    structlog.configure(
        processors=[
            structlog.stdlib.filter_by_level,
            structlog.stdlib.add_logger_name,
            structlog.stdlib.add_log_level,
            structlog.stdlib.PositionalArgumentsFormatter(),
            structlog.processors.TimeStamper(fmt="iso"),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            structlog.processors.UnicodeDecoder(),
            structlog.processors.JSONRenderer(),
        ],
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )


def get_logger(name: str, **initial_values: Any) -> structlog.stdlib.BoundLogger:
    """Return a structlog bound logger."""
    return structlog.get_logger(name).bind(**initial_values)

