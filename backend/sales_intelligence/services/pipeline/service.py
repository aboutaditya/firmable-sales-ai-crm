from __future__ import annotations

import itertools
import json
import logging
from datetime import datetime, timezone
from pathlib import Path

from sales_intelligence.pipeline import (
    aggregate,
    iter_records,
    profile_from_state,
    source_checksum,
    write_profiles,
)
from sales_intelligence.scoring import DEFAULT_SCORING_CONFIG, ScoringConfig
from sales_intelligence.services.dataset_runs import DatasetRunService
from sales_intelligence.services.pipeline.checkpoint import CheckpointStore
from sales_intelligence.services.pipeline.manifest import RunManifest
from sales_intelligence.services.pipeline_runs import PipelineRunTracker

logger = logging.getLogger(__name__)


class PipelineService:
    def run(
        self,
        source: str | Path,
        output: str | Path,
        *,
        output_format: str = "parquet",
        max_records: int | None = None,
        session_factory=None,
        dataset_version: str | None = None,
        checkpoint_path: str | Path | None = None,
        checkpoint_interval: int = 10_000,
        dataset_runs_dir: str | Path | None = None,
        dataset_name: str = "companies",
        scoring_config: ScoringConfig = DEFAULT_SCORING_CONFIG,
    ) -> Path:
        if checkpoint_interval < 1:
            raise ValueError("checkpoint_interval must be greater than zero")
        source_identity = source_checksum(source)
        dataset_version = dataset_version or source_identity
        checkpoint_store = CheckpointStore(checkpoint_path)
        output_path = Path(output)
        runs_dir = Path(dataset_runs_dir) if dataset_runs_dir else output_path.parent / "dataset_runs"
        runs_dir.mkdir(parents=True, exist_ok=True)
        dataset_run_id = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S.%fZ")
        resumed_count = 0
        initial_profiles: list = []
        checkpoint_state = checkpoint_store.load()
        if checkpoint_state:
            state_processed_count = int(checkpoint_state.get("processed_count", 0))
            if checkpoint_store.should_resume(checkpoint_state, max_records=max_records):
                if checkpoint_state.get("source_checksum") != source_identity:
                    raise ValueError("checkpoint source does not match the current source")
                if checkpoint_state.get("dataset_version") != dataset_version:
                    raise ValueError("checkpoint dataset_version does not match the current run")
                if "score_version" in checkpoint_state and checkpoint_state.get("score_version") != scoring_config.score_version:
                    raise ValueError("checkpoint score_version does not match the current scoring config")
                dataset_run_id = checkpoint_state.get("run_id", dataset_run_id)
                resumed_count = state_processed_count
                initial_profiles = [profile_from_state(row) for row in checkpoint_state.get("profiles", [])]
                logger.info("etl_checkpoint_resuming", extra={"processed_count": resumed_count, "company_count": len(initial_profiles), "checkpoint": str(checkpoint_store.path), "status": checkpoint_state.get("status")})
        started = datetime.now(timezone.utc)
        manifest = RunManifest(
            runs_dir,
            dataset_run_id,
            source=source,
            source_identity=source_identity,
            dataset_version=dataset_version,
            output_path=output_path,
            checkpoint=checkpoint_store.path,
            max_records=max_records,
            started=started,
            score_version=scoring_config.score_version,
        )
        last_processed = resumed_count
        last_company_count = len(initial_profiles)

        manifest.write("running", resumed_count, len(initial_profiles))
        logger.info("etl_dataset_run_started", extra={"dataset_run_id": dataset_run_id, "source": str(source), "dataset_version": dataset_version, "processed_count": resumed_count})
        run_tracker = PipelineRunTracker(session_factory)
        run_id = None
        dataset_run_service = DatasetRunService(session_factory)
        try:
            dataset_run_service.start(
                run_id=dataset_run_id, dataset_name=dataset_name, dataset_version=dataset_version,
                source_url=str(source), source_checksum=source_identity, output_uri=str(output_path),
                manifest_uri=str(output_path.with_suffix(output_path.suffix + ".manifest.json")),
                checkpoint_uri=str(checkpoint_store.path) if checkpoint_store.enabled else None,
                target_record=max_records,
                score_version=scoring_config.score_version, current_record=resumed_count,
                company_count=len(initial_profiles),
            )
            run_id = run_tracker.start(run_type="etl", dataset_version=dataset_version, score_version=scoring_config.score_version, source=str(source))
        except Exception as exc:
            dataset_run_service.fail(dataset_run_id, str(exc), processed_rows=resumed_count, company_count=len(initial_profiles))
            manifest.write("failed", resumed_count, len(initial_profiles), error_message=str(exc)[:4000])
            logger.exception("etl_pipeline_run_start_failed", extra={"source": str(source), "dataset_run_id": dataset_run_id})
            raise

        records = iter_records(source)
        if resumed_count:
            records = itertools.islice(records, resumed_count, None)
        if max_records is not None:
            if max_records < 1:
                raise ValueError("max_records must be greater than zero")
            remaining = max_records - resumed_count
            records = itertools.islice(records, max(remaining, 0))
        try:

            def save_checkpoint(processed: int, companies: dict) -> None:
                nonlocal last_processed, last_company_count
                total_processed = resumed_count + processed
                last_processed = total_processed
                last_company_count = len(companies)
                if not checkpoint_store.enabled or total_processed % checkpoint_interval != 0:
                    return
                checkpoint_store.save_running(
                    processed_count=total_processed,
                    profiles=companies,
                    run_id=dataset_run_id,
                    source=source,
                    source_identity=source_identity,
                    dataset_version=dataset_version,
                    score_version=scoring_config.score_version,
                )
                dataset_run_service.progress(dataset_run_id, processed_rows=total_processed, company_count=len(companies))
                manifest.write("running", total_processed, len(companies))
                logger.info("etl_checkpoint_saved", extra={"processed_count": total_processed, "company_count": len(companies), "checkpoint": str(checkpoint_store.path)})

            profiles = aggregate(records, initial_profiles=initial_profiles, on_record=save_checkpoint, scoring_config=scoring_config)
            result = write_profiles(profiles, output_path, format=output_format)
            processed_count = sum(profile.asset_count for profile in profiles)
            result_manifest = {
                "run_id": dataset_run_id, "dataset_version": dataset_version,
                "score_version": scoring_config.score_version, "source": str(source),
                "source_checksum": source_identity, "output": str(result),
                "format": output_format, "processed_count": processed_count,
                "company_count": len(profiles), "created_at": datetime.now(timezone.utc).isoformat(),
            }
            result.with_suffix(result.suffix + ".manifest.json").write_text(json.dumps(result_manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
            checkpoint_store.save_completed(processed_count=processed_count, profiles=profiles, manifest=result_manifest)
            dataset_run_service.complete(dataset_run_id, processed_rows=processed_count, company_count=len(profiles), metadata=result_manifest)
            manifest.write("completed", processed_count, len(profiles), completed_at=datetime.now(timezone.utc).isoformat())
            run_tracker.complete(run_id, processed_count=processed_count, qualified_count=len(profiles))
            logger.info("etl_completed", extra={"dataset_version": dataset_version, "processed_count": processed_count, "company_count": len(profiles), "duration_ms": int((datetime.now(timezone.utc) - started).total_seconds() * 1000)})
            return result
        except Exception as exc:
            dataset_run_service.fail(dataset_run_id, str(exc), processed_rows=last_processed, company_count=last_company_count)
            manifest.write("failed", last_processed, last_company_count, error_message=str(exc)[:4000])
            run_tracker.fail(run_id, str(exc))
            logger.exception("etl_failed", extra={"source": str(source)})
            raise