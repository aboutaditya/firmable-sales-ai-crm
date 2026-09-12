from __future__ import annotations

from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException


def _request_id(request: Request) -> str:
    return getattr(request.state, "request_id", "unknown")


def error_payload(request: Request, message: str, *, code: str, details: object = None) -> dict:
    return {
        "error": code,
        "message": message,
        "request_id": _request_id(request),
        "details": details,
    }


async def http_exception_handler(request: Request, exc: StarletteHTTPException) -> JSONResponse:
    status = exc.status_code
    detail = exc.detail if isinstance(exc.detail, str) else "Request failed"
    details = None if isinstance(exc.detail, str) else exc.detail
    return JSONResponse(status_code=status, content=error_payload(request, detail, code=f"HTTP_{status}", details=details))


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    return JSONResponse(
        status_code=422,
        content=error_payload(request, "Request validation failed", code="VALIDATION_ERROR", details=exc.errors()),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=500,
        content=error_payload(request, "Internal server error", code="INTERNAL_SERVER_ERROR"),
    )
