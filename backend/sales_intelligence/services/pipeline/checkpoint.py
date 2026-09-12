from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path

from sales_intelligence.pipeline import profile_to_state

from sales_intelligence.services.pipeline.files import atomic_json


class CheckpointStore:
    """Reads and writes the resumable ETL checkpoint file."""

    def __init__(self, path: str | Path | None):
        self.path = Path(path) if path else None

    @property
    def enabled(self) -> bool:
        return self.path is not None

    def load(self) -> dict | None:
        if not self.enabled or not self.path.exists():
            return None
        return json.loads(self.path.read_text(encoding="utf-8"))

    @staticmethod
    def should_resume(state: dict, *, max_records: int | None) -> bool:
        processed = int(state.get("processed_count", 0))
        return state.get("status") != "completed" or (
            max_records is not None and max_records > processed
        )

    def save_running(
        self,
        *,
        processed_count: int,
        profiles: list,
        run_id: str,
        source: str | Path,
        source_identity: str,
        dataset_version: str,
        score_version: str,
    ) -> None:
        if not self.enabled:
            return
        payload = {
            "status": "running",
            "run_id": run_id,
            "source": str(source),
            "source_checksum": source_identity,
            "dataset_version": dataset_version,
            "score_version": score_version,
            "processed_count": processed_count,
            "profiles": [profile_to_state(profile) for profile in profiles.values()],
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        atomic_json(self.path, payload)

    def save_completed(self, *, processed_count: int, profiles: list, manifest: dict) -> None:
        if not self.enabled:
            return
        self.path.parent.mkdir(parents=True, exist_ok=True)
        completed_state = {
            "status": "completed",
            **manifest,
            "profiles": [profile_to_state(profile) for profile in profiles],
        }
        atomic_json(self.path, completed_state)