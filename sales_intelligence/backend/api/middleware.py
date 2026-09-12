from __future__ import annotations

import uuid
import logging
import time

from starlette.middleware.base import BaseHTTPMiddleware


class RequestIdMiddleware(BaseHTTPMiddleware):
    async def dispatch(self, request, call_next):
        request_id = request.headers.get("X-Request-ID") or str(uuid.uuid4())
        request.state.request_id = request_id
        started = time.perf_counter()
        response = await call_next(request)
        response.headers["X-Request-ID"] = request_id
        logging.getLogger("sales_intelligence.api").info(
            "request_completed", extra={"request_id": request_id, "method": request.method,
            "path": request.url.path, "status_code": response.status_code,
            "duration_ms": int((time.perf_counter() - started) * 1000)})
        return response
