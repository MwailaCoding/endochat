"""Structured logging configuration."""

import logging
import sys
from typing import Optional

import structlog


def setup_logging(
    level: str = "INFO",
    json_format: bool = False,
) -> None:
    """Configure structured logging for the application."""
    # Set base log level
    log_level = getattr(logging, level.upper(), logging.INFO)

    # Configure structlog processors
    shared_processors = [
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        structlog.processors.TimeStamper(fmt="iso"),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.UnicodeDecoder(),
    ]

    if json_format:
        # JSON format for production
        processors = shared_processors + [
            structlog.processors.format_exc_info,
            structlog.processors.JSONRenderer(),
        ]
    else:
        # Console format for development
        processors = shared_processors + [
            structlog.dev.ConsoleRenderer(colors=True),
        ]

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.stdlib.BoundLogger,
        context_class=dict,
        logger_factory=structlog.stdlib.LoggerFactory(),
        cache_logger_on_first_use=True,
    )

    # Configure standard library logging
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=log_level,
    )

    # Reduce noise from third-party libraries
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("asyncio").setLevel(logging.WARNING)


def get_logger(name: Optional[str] = None) -> structlog.stdlib.BoundLogger:
    """Get a structured logger instance."""
    return structlog.get_logger(name)


class RequestContextLogger:
    """Logger that includes request context."""

    def __init__(self, request_id: str):
        self.logger = get_logger()
        self.request_id = request_id

    def bind(self, **kwargs):
        """Bind additional context to logger."""
        return self.logger.bind(request_id=self.request_id, **kwargs)

    def info(self, event: str, **kwargs):
        """Log info level message."""
        self.logger.info(event, request_id=self.request_id, **kwargs)

    def warning(self, event: str, **kwargs):
        """Log warning level message."""
        self.logger.warning(event, request_id=self.request_id, **kwargs)

    def error(self, event: str, **kwargs):
        """Log error level message."""
        self.logger.error(event, request_id=self.request_id, **kwargs)

    def debug(self, event: str, **kwargs):
        """Log debug level message."""
        self.logger.debug(event, request_id=self.request_id, **kwargs)
