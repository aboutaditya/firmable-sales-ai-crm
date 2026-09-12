from __future__ import annotations

from collections.abc import Iterator
import logging
import time
from pathlib import Path

from sqlalchemy import update
from sqlalchemy.orm import Session

from sales_intelligence.models import Company, CompanySignal
from sales_intelligence.db.session import create_session_factory
from sales_intelligence.services.audit import AuditService
from sales_intelligence.services.pipeline_runs import PipelineRunTracker
from sales_intelligence.query import query_companies
from sales_intelligence.scoring import DEFAULT_SCORING_CONFIG

logger = logging.getLogger(__name__)


def iter_qualified_companies(dataset_path: str | Path, *, min_score: int, batch_size: int) -> Iterator[list[dict]]:
    offset = 0
    batch_number = 0
    while True:
        batch_number += 1
        logger.info("sync_batch_query_started", extra={"batch_number": batch_number, "offset": offset, "batch_size": batch_size, "min_score": min_score})
        batch = query_companies(dataset_path, min_score=min_score, limit=batch_size, offset=offset)
        if not batch:
            logger.info("sync_batch_query_empty", extra={"batch_number": batch_number, "offset": offset})
            return
        logger.info("sync_batch_query_completed", extra={"batch_number": batch_number, "offset": offset, "row_count": len(batch)})
        yield batch
        offset += len(batch)
        if len(batch) < batch_size:
            return


class DatabaseSyncService:
    """Sync qualified analytical rows using typed SQLAlchemy ORM models."""

    def sync(
        self,
        dataset_path: str | Path,
        database_url: str,
        *,
        min_score: int = 0,
        dataset_version: str = "unknown",
        batch_size: int = 1_000,
        source: str = "parquet",
    ) -> int:
        self._validate(database_url, min_score, batch_size)
        logger.info("sync_database_connecting", extra={"dataset_path": str(dataset_path), "dataset_version": dataset_version, "min_score": min_score, "batch_size": batch_size})
        session_factory = create_session_factory(database_url)
        run_tracker = PipelineRunTracker(session_factory)
        run_id = run_tracker.start(run_type="sync", dataset_version=dataset_version, score_version=DEFAULT_SCORING_CONFIG.score_version, source=source)
        logger.info("sync_pipeline_run_started", extra={"run_id": run_id, "dataset_version": dataset_version})
        processed = 0
        synced_ids: list[str] = []
        try:
            for batch_number, batch in enumerate(iter_qualified_companies(dataset_path, min_score=min_score, batch_size=batch_size), start=1):
                logger.info("sync_batch_upsert_started", extra={"run_id": run_id, "batch_number": batch_number, "row_count": len(batch), "processed_before": processed})
                with session_factory.begin() as session:
                    for row_number, row in enumerate(batch, start=1):
                        row_started = time.perf_counter()
                        logger.info("sync_row_upsert_started", extra={"run_id": run_id, "batch_number": batch_number, "row_number": row_number, "company_id": row["company_id"]})
                        self._upsert_company(session, row, dataset_version)
                        synced_ids.append(row["company_id"])
                        processed += 1
                        logger.info("sync_row_upsert_completed", extra={"run_id": run_id, "batch_number": batch_number, "row_number": row_number, "company_id": row["company_id"], "processed_count": processed, "duration_ms": int((time.perf_counter() - row_started) * 1000)})
                logger.info("sync_batch_upsert_completed", extra={"run_id": run_id, "batch_number": batch_number, "row_count": len(batch), "processed_count": processed})
                run_tracker.progress(run_id, processed)
                logger.info("sync_pipeline_run_progress", extra={"run_id": run_id, "processed_count": processed})

            logger.info("sync_deactivation_started", extra={"run_id": run_id, "dataset_version": dataset_version, "synced_count": len(synced_ids)})
            with session_factory.begin() as session:
                self._deactivate_missing(session, dataset_version, synced_ids)
            logger.info("sync_deactivation_completed", extra={"run_id": run_id})
            run_tracker.complete(run_id, processed_count=processed, qualified_count=processed)
            logger.info("sync_pipeline_run_completed", extra={"run_id": run_id, "processed_count": processed})
            AuditService(session_factory).record(
                user_id="system", role="system", action="sync_completed",
                resource_type="pipeline_run", resource_id=str(run_id),
                metadata={"dataset_version": dataset_version, "qualified_count": processed},
            )
            return processed
        except Exception as exc:
            logger.exception("sync_failed", extra={"run_id": run_id, "processed_count": processed})
            run_tracker.fail(run_id, str(exc))
            AuditService(session_factory).record(
                user_id="system", role="system", action="sync_failed",
                resource_type="pipeline_run", resource_id=str(run_id),
                metadata={"dataset_version": dataset_version, "error": str(exc)[:1000]},
            )
            raise

    @staticmethod
    def _validate(database_url: str, min_score: int, batch_size: int) -> None:
        if not database_url:
            raise ValueError("database_url is required")
        if not 0 <= min_score <= 100:
            raise ValueError("min_score must be between 0 and 100")
        if not 1 <= batch_size <= 10_000:
            raise ValueError("batch_size must be between 1 and 10000")

    @staticmethod
    def _upsert_company(session: Session, row: dict, dataset_version: str) -> None:
        company = session.get(Company, row["company_id"])
        if company is None:
            company = Company(id=row["company_id"])
            session.add(company)
        for field in ("domain", "organization", "country", "city", "industry", "employee_count", "security_score", "score_version"):
            setattr(company, field, row.get(field))
        company.dataset_version = dataset_version
        company.is_active = True

        signal = session.get(CompanySignal, row["company_id"])
        if signal is None:
            signal = CompanySignal(company_id=row["company_id"])
            session.add(signal)
        for field in (
            "asset_count", "unique_ip_count", "unique_domain_count", "vulnerability_count",
            "critical_vulnerability_count", "eol_product_count", "exposed_rdp",
            "exposed_database", "exposed_exchange", "security_tag_count",
        ):
            setattr(signal, field, row[field])

    @staticmethod
    def _deactivate_missing(session: Session, dataset_version: str, synced_ids: list[str]) -> None:
        statement = update(Company).where(Company.dataset_version == dataset_version)
        if synced_ids:
            statement = statement.where(Company.id.not_in(synced_ids))
        session.execute(statement.values(is_active=False))
