from __future__ import annotations

import asyncio
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


class S3TraceSink:
    """Upload each trace record to S3-compatible storage (e.g., Supabase Storage).

    Objects are stored one-per-record at
    ``traces/<prompt-slug>/<year>/<month>/<day>/<timestamp>-<trace_id>.json``
    so concurrent serverless instances never clobber each other and the
    hierarchy is browsable per prompt and day.
    """

    def __init__(
        self,
        s3_endpoint: str,
        s3_region: str,
        s3_access_key: str,
        s3_secret_key: str,
        s3_bucket: str = "llm-traces",
    ):
        self.s3_endpoint = s3_endpoint
        self.s3_region = s3_region
        self.s3_access_key = s3_access_key
        self.s3_secret_key = s3_secret_key
        self.s3_bucket = s3_bucket

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
        asyncio.create_task(self._upload_async(object_path, body))
        return trace_id

    async def _upload_async(self, object_path: str, body: bytes) -> None:
        try:
            import aioboto3

            session = aioboto3.Session(
                aws_access_key_id=self.s3_access_key,
                aws_secret_access_key=self.s3_secret_key,
                region_name=self.s3_region,
            )
            async with session.client(
                "s3",
                endpoint_url=self.s3_endpoint,
            ) as client:
                await client.put_object(
                    Bucket=self.s3_bucket,
                    Key=object_path,
                    Body=body,
                    ContentType="application/json",
                )
        except Exception as exc:
            logger.warning("trace upload to S3 failed for %s: %s", object_path, exc)
