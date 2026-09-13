from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import update
from sqlalchemy.orm import Session, sessionmaker

from sales_intelligence.models import DatasetRun


class DatasetRunService:
    """Persists the durable dataset manifest and current dataset pointer."""

    def __init__(self, session_factory: sessionmaker | None):
        self.session_factory = session_factory

    def start(
        self,
        *,
        run_id: str,
        dataset_name: str,
        dataset_version: str,
        source_url: str,
        source_checksum: str,
        output_uri: str | None,
        manifest_uri: str | None,
        checkpoint_uri: str | None,
        target_record: int | None,
        score_version: str,
        current_record: int = 0,
        company_count: int = 0,
    ) -> None:
        if self.session_factory is None:
            return
        with self.session_factory.begin() as session:
            run = session.get(DatasetRun, run_id)
            if run is None:
                run = DatasetRun(run_id=run_id)
                session.add(run)
            session.execute(
                update(DatasetRun)
                .where(DatasetRun.dataset_name == dataset_name, DatasetRun.is_current.is_(True), DatasetRun.run_id != run_id)
                .values(is_current=False)
            )
            run.dataset_name = dataset_name
            run.dataset_version = dataset_version
            run.source_url = source_url
            run.source_checksum = source_checksum
            run.output_uri = output_uri
            run.manifest_uri = manifest_uri
            run.checkpoint_uri = checkpoint_uri
            run.status = "running"
            run.current_record = current_record
            run.next_record = current_record + 1
            run.target_record = target_record
            run.processed_rows = current_record
            run.company_count = company_count
            run.score_version = score_version
            run.is_current = True
            run.error_message = None

    def progress(self, run_id: str, *, processed_rows: int, company_count: int) -> None:
        self._update(run_id, processed_rows=processed_rows, current_record=processed_rows, next_record=processed_rows + 1, company_count=company_count)

    def complete(self, run_id: str, *, processed_rows: int, company_count: int, metadata: dict | None = None) -> None:
        if self.session_factory is None:
            return
        with self.session_factory.begin() as session:
            run = session.get(DatasetRun, run_id)
            if run:
                session.execute(update(DatasetRun).where(DatasetRun.is_current.is_(True), DatasetRun.dataset_name == run.dataset_name).values(is_current=False))
                run.status = "completed"
                run.current_record = processed_rows
                run.next_record = processed_rows + 1
                run.processed_rows = processed_rows
                run.company_count = company_count
                run.is_current = True
                run.completed_at = datetime.now(timezone.utc)
                run.metadata_json = metadata or {}

    def fail(self, run_id: str, error_message: str, *, processed_rows: int = 0, company_count: int = 0) -> None:
        self._update(run_id, status="failed", error_message=error_message[:4000], processed_rows=processed_rows, current_record=processed_rows, next_record=processed_rows + 1, company_count=company_count)

    def _update(self, run_id: str, **values: object) -> None:
        if self.session_factory is None:
            return
        with self.session_factory.begin() as session:
            run = session.get(DatasetRun, run_id)
            if run:
                for key, value in values.items():
                    setattr(run, key, value)
