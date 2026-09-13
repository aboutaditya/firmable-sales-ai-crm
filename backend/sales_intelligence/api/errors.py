from __future__ import annotations

import logging
from fastapi import Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

logger = logging.getLogger("sales_intelligence.api")


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

    logger.warning(
        "http_exception",
        extra={
            "request_id": _request_id(request),
            "method": request.method,
            "path": request.url.path,
            "status_code": status,
            "detail": detail,
        },
        exc_info=True if status >= 500 else False
    )

    return JSONResponse(status_code=status, content=error_payload(request, detail, code=f"HTTP_{status}", details=details))


async def validation_exception_handler(request: Request, exc: RequestValidationError) -> JSONResponse:
    logger.warning(
        "validation_error",
        extra={
            "request_id": _request_id(request),
            "method": request.method,
            "path": request.url.path,
            "errors": len(exc.errors()),
        },
        exc_info=False
    )

    return JSONResponse(
        status_code=422,
        content=error_payload(request, "Request validation failed", code="VALIDATION_ERROR", details=exc.errors()),
    )


async def unhandled_exception_handler(request: Request, exc: Exception) -> JSONResponse:
    logger.error(
        "unhandled_exception",
        extra={
            "request_id": _request_id(request),
            "method": request.method,
            "path": request.url.path,
            "error_type": type(exc).__name__,
            "error_message": str(exc),
        },
        exc_info=True
    )

    return JSONResponse(
        status_code=500,
        content=error_payload(request, "Internal server error", code="INTERNAL_SERVER_ERROR"),
    )
