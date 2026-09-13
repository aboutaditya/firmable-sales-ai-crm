from __future__ import annotations

import json
import logging
import re
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Protocol
from uuid import uuid4

logger = logging.getLogger(__name__)


class TraceSink(Protocol):
    def record(self, **event: Any) -> str: ...


class NullTraceSink:
    """No-op sink used by isolated services and unit tests."""

    def record(self, **_: Any) -> str:
        return str(uuid4())


class CompositeTraceSink:
    """Fan a trace event out to multiple sinks; best-effort per child."""

    def __init__(self, sinks: list[TraceSink]):
        self.sinks = sinks

    def record(self, **event: Any) -> str:
        trace_id = str(event.get("trace_id", uuid4()))
        for sink in self.sinks:
            try:
                sink.record(**event)
            except Exception as exc:  # pragma: no cover - defensive
                logger.warning("trace sink %s failed: %s", type(sink).__name__, exc)
        return trace_id


class JsonlTraceSink:
    """Append one structured record for every LLM attempt."""

    def __init__(self, path: str | Path):
        self.path = Path(path)
        self._lock = Lock()

    def record(self, **event: Any) -> str:
        trace_id = str(event.pop("trace_id", uuid4()))
        row = {
            "trace_id": trace_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **event,
        }
        with self._lock:
            try:
                self.path.parent.mkdir(parents=True, exist_ok=True)
                with self.path.open("a", encoding="utf-8") as stream:
                    stream.write(json.dumps(row, sort_keys=True, default=str) + "\n")
            except OSError as exc:
                logger.warning("unable to write trace to %s: %s (tracing disabled)", self.path, exc)
        return trace_id


def _prompt_slug(event: dict[str, Any]) -> str:
    name = event.get("prompt_version") or event.get("feature") or "llm"
    slug = re.sub(r"[^A-Za-z0-9]+", "-", str(name)).strip("-").lower()
    return slug or "llm"


