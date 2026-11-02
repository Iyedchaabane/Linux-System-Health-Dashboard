"""API error handling for the Linux System Health Dashboard."""

from __future__ import annotations

import uuid

from fastapi import FastAPI, HTTPException, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse

from monitor.presentation.api.schemas import ErrorDetail, ErrorResponse


class ApiError(Exception):
    """Application error with a stable machine-readable code."""

    def __init__(self, code: str, message: str, status_code: int) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.status_code = status_code


def _request_id(request: Request) -> str:
    """Return the request correlation id when available."""
    value = getattr(request.state, "request_id", None)
    if isinstance(value, str) and value:
        return value
    return uuid.uuid4().hex


def _error_response(status_code: int, code: str, message: str, request_id: str) -> JSONResponse:
    """Build the canonical error envelope response."""
    error = ErrorDetail(code=code, message=message, request_id=request_id)
    return JSONResponse(
        status_code=status_code,
        content=ErrorResponse(error=error).model_dump(mode="json"),
    )


async def api_error_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return application errors in the canonical error envelope."""
    if not isinstance(exc, ApiError):
        raise TypeError("Unreachable handler for ApiError")
    return _error_response(exc.status_code, exc.code, exc.message, _request_id(request))


async def validation_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return request validation failures in the canonical error envelope."""
    if not isinstance(exc, RequestValidationError):
        raise TypeError("Unreachable handler for validation error")
    return _error_response(422, "INVALID_REQUEST", "Invalid request", _request_id(request))


async def http_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    """Return Starlette HTTP exceptions in the canonical error envelope."""
    if not isinstance(exc, HTTPException):
        raise TypeError("Unreachable handler for HTTP exception")
    code = exc.detail if isinstance(exc.detail, str) else "INVALID_REQUEST"
    return _error_response(exc.status_code, code, str(exc.detail), _request_id(request))


async def generic_exception_handler(request: Request, _exc: Exception) -> JSONResponse:
    """Return unexpected failures without leaking internals."""
    return _error_response(500, "INTERNAL_ERROR", "Internal server error", _request_id(request))


def register_error_handlers(app: FastAPI) -> None:
    """Register canonical API exception handlers on the FastAPI app."""
    app.add_exception_handler(ApiError, api_error_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
    app.add_exception_handler(HTTPException, http_exception_handler)
    app.add_exception_handler(Exception, generic_exception_handler)
