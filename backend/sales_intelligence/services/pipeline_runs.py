from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy.orm import sessionmaker

from sales_intelligence.models import PipelineRun


class PipelineRunTracker:
    """Manages the lifecycle of a PipelineRun row (start, progress, complete, fail).

    Used by both the analytical ETL and the database sync service so run tracking
    stays a single responsibility instead of being reimplemented in each flow.
    """

    def __init__(self, session_factory: sessionmaker | None):
        self.session_factory = session_factory

    def start(
        self,
        *,
        run_type: str,
        dataset_version: str,
        score_version: str,
        source: str,
        status: str = "running",
    ) -> int | None:
        if self.session_factory is None:
            return None
        with self.session_factory.begin() as session:
            run = PipelineRun(
                run_type=run_type,
                dataset_version=dataset_version,
                score_version=score_version,
                source=source,
                status=status,
            )
            session.add(run)
            session.flush()
            return run.id

    def progress(self, run_id: int | None, processed_count: int) -> None:
        self._update(run_id, processed_count=processed_count, qualified_count=processed_count)

    def complete(self, run_id: int | None, *, processed_count: int, qualified_count: int) -> None:
        self._update(
            run_id,
            status="completed",
            processed_count=processed_count,
            qualified_count=qualified_count,
            completed_at=datetime.now(timezone.utc),
        )

    def fail(self, run_id: int | None, error: str) -> None:
        self._update(
            run_id,
            status="failed",
            error_message=error[:4000],
            completed_at=datetime.now(timezone.utc),
        )

    def _update(self, run_id: int | None, **values: object) -> None:
        if self.session_factory is None or run_id is None:
            return
        with self.session_factory.begin() as session:
            run = session.get(PipelineRun, run_id)
            if run:
                for key, value in values.items():
                    setattr(run, key, value)