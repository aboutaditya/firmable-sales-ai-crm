from __future__ import annotations

import time
from collections import defaultdict, deque
from threading import Lock

from fastapi import HTTPException, Request


class InMemoryRateLimiter:
    """Small single-process limiter; use a shared gateway for multi-worker deployments."""

    def __init__(self, limit: int):
        self.limit = limit
        self._events: dict[str, deque[float]] = defaultdict(deque)
        self._lock = Lock()

    def check(self, key: str) -> None:
        now = time.monotonic()
        with self._lock:
            events = self._events[key]
            while events and events[0] <= now - 60:
                events.popleft()
            if len(events) >= self.limit:
                raise HTTPException(status_code=429, detail="AI request rate limit exceeded")
            events.append(now)


def ai_rate_limit(request: Request) -> None:
    limiter: InMemoryRateLimiter = request.app.state.ai_rate_limiter
    client = request.client.host if request.client else "unknown"
    limiter.check(client)
