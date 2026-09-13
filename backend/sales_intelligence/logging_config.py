from __future__ import annotations

import json
import logging
import sys
import traceback
from datetime import datetime, timezone


class JsonFormatter(logging.Formatter):
    def format(self, record: logging.LogRecord) -> str:
        payload = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
        }

        # Add all extra fields
        for key in (
            "request_id", "method", "path", "query", "status_code", "duration_ms",
            "dataset_version", "processed_count", "company_count", "run_id",
            "batch_number", "batch_size", "offset", "row_count", "min_score",
            "synced_count", "row_number", "company_id", "detail", "error",
            "error_type", "error_message", "errors", "cached", "feature",
            "user_id", "role", "action", "resource_type", "resource_id",
        ):
            if hasattr(record, key):
                payload[key] = getattr(record, key)

        # Add exception info if present
        if record.exc_info:
            payload["exception"] = "".join(traceback.format_exception(*record.exc_info))

        return json.dumps(payload, default=str)


def configure_logging(level: str = "INFO") -> None:
    handler = logging.StreamHandler(sys.stdout)
    handler.setFormatter(JsonFormatter())
    logging.basicConfig(level=getattr(logging, level.upper(), logging.INFO), handlers=[handler], force=True)
