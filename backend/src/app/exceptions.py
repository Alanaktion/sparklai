"""Domain exceptions, adapted from the vendored `fastapi-exceptions` skill (trimmed: no
correlation-id middleware for this pass — see BACKEND_MIGRATION.md for what's still deferred)."""

from typing import Any


class AppException(Exception):
    """Base exception for all application errors; carries enough to render a JSON response."""

    def __init__(
        self,
        message: str,
        error_code: str,
        status_code: int = 500,
        details: dict[str, Any] | None = None,
    ):
        self.message = message
        self.error_code = error_code
        self.status_code = status_code
        self.details = details or {}
        super().__init__(self.message)


class NotFoundError(AppException):
    def __init__(self, resource: str, id: int | str | None = None):
        message = f"{resource} not found" if id is None else f"{resource} with id '{id}' not found"
        super().__init__(message, "NOT_FOUND", 404, {"resource": resource})


class ConflictError(AppException):
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, "CONFLICT", 409, details)


class ValidationError(AppException):
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, "VALIDATION_ERROR", 422, details)


class UnauthorizedError(AppException):
    def __init__(self, message: str = "No active creator"):
        super().__init__(message, "UNAUTHORIZED", 401)


class ForbiddenError(AppException):
    def __init__(self, message: str = "You do not have permission to perform this action"):
        super().__init__(message, "FORBIDDEN", 403)


class BadRequestError(AppException):
    def __init__(self, message: str, details: dict[str, Any] | None = None):
        super().__init__(message, "BAD_REQUEST", 400, details)
