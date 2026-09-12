from __future__ import annotations

import json
import logging
import re
import urllib.request
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
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with self.path.open("a", encoding="utf-8") as stream:
                stream.write(json.dumps(row, sort_keys=True, default=str) + "\n")
        return trace_id


def _prompt_slug(event: dict[str, Any]) -> str:
    name = event.get("prompt_version") or event.get("feature") or "llm"
    slug = re.sub(r"[^A-Za-z0-9]+", "-", str(name)).strip("-").lower()
    return slug or "llm"


class SupabaseStorageTraceSink:
    """Upload each trace record to a Supabase Storage bucket.

    Objects are stored one-per-record at
    ``traces/<prompt-slug>/<year>/<month>/<day>/<timestamp>-<trace_id>.json``
    so concurrent serverless instances never clobber each other and the
    hierarchy is browsable per prompt and day.
    """

    def __init__(self, storage_url: str, service_role_key: str, bucket: str = "llm-traces", timeout: float = 10.0):
        self.base_url = storage_url.rstrip("/")
        self.bucket = bucket
        self.service_role_key = service_role_key
        self.timeout = timeout
        self._lock = Lock()

    def _upload(self, object_path: str, body: bytes) -> None:
        request = urllib.request.Request(
            f"{self.base_url}/storage/v1/object/{self.bucket}/{object_path}",
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {self.service_role_key}",
                "Content-Type": "application/json",
            },
        )
        with urllib.request.urlopen(request, timeout=self.timeout) as response:
            if response.status >= 400:
                raise RuntimeError(f"Supabase Storage upload failed with HTTP {response.status}")

    def record(self, **event: Any) -> str:
        trace_id = str(event.pop("trace_id", uuid4()))
        row = {
            "trace_id": trace_id,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            **event,
        }
        now = datetime.now(timezone.utc)
        object_path = (
            f"traces/{_prompt_slug(row)}/{now:%Y}/{now:%m}/{now:%d}/"
            f"{now:%Y%m%dT%H%M%S}-{trace_id}.json"
        )
        body = json.dumps(row, sort_keys=True, default=str).encode("utf-8")
        with self._lock:
            try:
                self._upload(object_path, body)
            except Exception as exc:
                logger.warning("trace upload to Supabase Storage failed for %s: %s", object_path, exc)
        return trace_id
