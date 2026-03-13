"""Custom exception classes for the application."""

from typing import Optional, Dict, Any


class EndoChatException(Exception):
    """Base exception for EndoChat application."""

    def __init__(
        self,
        message: str,
        status_code: int = 500,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.message = message
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class APIClientError(EndoChatException):
    """Error when calling external APIs."""

    def __init__(
        self,
        message: str,
        api_name: str,
        status_code: int = 502,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.api_name = api_name
        super().__init__(message, status_code, details)


class DatabaseError(EndoChatException):
    """Error when interacting with database."""

    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.operation = operation
        super().__init__(message, 500, details)


class CacheError(EndoChatException):
    """Error when interacting with cache."""

    def __init__(
        self,
        message: str,
        operation: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.operation = operation
        super().__init__(message, 500, details)


class ValidationError(EndoChatException):
    """Error for request validation failures."""

    def __init__(
        self,
        message: str,
        field: Optional[str] = None,
        details: Optional[Dict[str, Any]] = None,
    ):
        self.field = field
        super().__init__(message, 400, details)


class RateLimitError(EndoChatException):
    """Error when rate limit is exceeded."""

    def __init__(
        self,
        message: str = "Rate limit exceeded",
        retry_after: int = 60,
    ):
        self.retry_after = retry_after
        super().__init__(message, 429, {"retry_after": retry_after})


class NotFoundError(EndoChatException):
    """Error when a resource is not found."""

    def __init__(
        self,
        message: str = "Resource not found",
        resource_type: Optional[str] = None,
        resource_id: Optional[str] = None,
    ):
        super().__init__(
            message,
            404,
            {"resource_type": resource_type, "resource_id": resource_id},
        )
