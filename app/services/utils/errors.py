"""Error handling utilities."""

from typing import Optional, Dict, Any
from fastapi import HTTPException
from fastapi.responses import JSONResponse

from app.core.exceptions import (
    EndoChatException,
    APIClientError,
    DatabaseError,
    CacheError,
    ValidationError,
    RateLimitError,
    NotFoundError,
)
from app.services.utils.logging import get_logger

logger = get_logger(__name__)


class APIError(EndoChatException):
    """API-level error for HTTP responses."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        error_code: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        super().__init__(message, status_code, details)
        self.error_code = error_code or f"ERR_{status_code}"


def create_error_response(
    status_code: int,
    message: str,
    error_code: Optional[str] = None,
    details: Optional[Dict[str, Any]] = None,
) -> JSONResponse:
    """Create a standardized error response."""
    content = {
        "error": True,
        "message": message,
        "error_code": error_code or f"ERR_{status_code}",
    }

    if details:
        content["details"] = details

    return JSONResponse(status_code=status_code, content=content)


def handle_exception(exc: Exception) -> JSONResponse:
    """Handle exceptions and convert to appropriate responses."""
    if isinstance(exc, EndoChatException):
        logger.warning(
            "handled_exception",
            error_type=type(exc).__name__,
            message=exc.message,
            status_code=exc.status_code,
        )
        return create_error_response(
            status_code=exc.status_code,
            message=exc.message,
            details=exc.details,
        )

    elif isinstance(exc, HTTPException):
        return create_error_response(
            status_code=exc.status_code,
            message=exc.detail,
        )

    else:
        logger.error(
            "unhandled_exception",
            error_type=type(exc).__name__,
            message=str(exc),
            exc_info=True,
        )
        return create_error_response(
            status_code=500,
            message="An unexpected error occurred",
            error_code="ERR_INTERNAL",
        )


def log_and_raise(
    message: str,
    status_code: int = 500,
    error_code: Optional[str] = None,
    **log_context,
) -> None:
    """Log error and raise HTTP exception."""
    logger.error(message, status_code=status_code, **log_context)
    raise HTTPException(status_code=status_code, detail=message)


def safe_execute(func, default=None, log_errors: bool = True):
    """Execute function safely, returning default on error."""
    async def wrapper(*args, **kwargs):
        try:
            return await func(*args, **kwargs)
        except Exception as e:
            if log_errors:
                logger.warning(
                    "safe_execute_error",
                    function=func.__name__,
                    error=str(e),
                )
            return default

    return wrapper
