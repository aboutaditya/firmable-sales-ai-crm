from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock
from typing import Any, Protocol
from uuid import uuid4


class TraceSink(Protocol):
    def record(self, **event: Any) -> str: ...


class NullTraceSink:
    """No-op sink used by isolated services and unit tests."""

    def record(self, **_: Any) -> str:
        return str(uuid4())


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
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(row, sort_keys=True, default=str) + "\n")
        return trace_id
