from __future__ import annotations

import uuid
import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware

logger = logging.getLogger("sales_intelligence.api")


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        started = time.perf_counter()

        # Log request start
        logger.info(
            "request_started",
            extra={
                "request_id": request_id,
                "method": request.method,
                "path": request.url.path,
                "query": str(request.url.query),
            }
        )

        try:
            response = await call_next(request)
            duration_ms = int((time.perf_counter() - started) * 1000)

            # Log request completion
            logger.info(
                "request_completed",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "status_code": response.status_code,
                    "duration_ms": duration_ms,
                }
            )
            response.headers["X-Request-ID"] = request_id
            return response
        except Exception as e:
            duration_ms = int((time.perf_counter() - started) * 1000)
            logger.error(
                "request_error",
                extra={
                    "request_id": request_id,
                    "method": request.method,
                    "path": request.url.path,
                    "duration_ms": duration_ms,
                    "error": str(e),
                },
                exc_info=True
            )
            raise
