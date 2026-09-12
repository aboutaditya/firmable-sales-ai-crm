from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path

from sales_intelligence.pipeline import SCORE_VERSION

from sales_intelligence.backend.services.pipeline.files import atomic_json


class RunManifest:
    """Writes the durable run manifest and the current dataset pointer."""

    def __init__(
        self,
        runs_dir: Path,
        run_id: str,
        *,
        source: str | Path,
        source_identity: str,
        dataset_version: str,
        output_path: Path,
        checkpoint: Path | None,
        max_records: int | None,
        started: datetime,
    ):
        self.runs_dir = runs_dir
        self.run_id = run_id
        self.source = source
        self.source_identity = source_identity
        self.dataset_version = dataset_version
        self.output_path = output_path
        self.checkpoint = checkpoint
        self.max_records = max_records
        self.started = started

    @property
    def path(self) -> Path:
        return self.runs_dir / f"{self.run_id}.json"

    def write(self, status: str, processed_count: int, company_count: int, **extra: object) -> None:
        metadata = {
            "run_id": self.run_id,
            "status": status,
            "source": str(self.source),
            "source_checksum": self.source_identity,
            "dataset_version": self.dataset_version,
            "score_version": SCORE_VERSION,
            "output": str(self.output_path),
            "checkpoint": str(self.checkpoint) if self.checkpoint else None,
            "processed_count": processed_count,
            "requested_max_records": self.max_records,
            "company_count": company_count,
            "started_at": self.started.isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            **extra,
        }
        atomic_json(self.path, metadata)
        atomic_json(self.runs_dir / "current.json", {
            "run_id": self.run_id,
            "manifest": str(self.path),
            "checkpoint": str(self.checkpoint) if self.checkpoint else None,
            "status": status,
            "dataset_version": self.dataset_version,
            "source": str(self.source),
            "processed_count": processed_count,
            "next_record": processed_count + 1,
            "updated_at": metadata["updated_at"],
        })