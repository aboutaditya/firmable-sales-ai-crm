from __future__ import annotations

import argparse
from pathlib import Path

from sales_intelligence.config import Settings
from sales_intelligence.db.session import create_session_factory
from sales_intelligence.services.audit import AuditService
from sales_intelligence.services.pipeline import PipelineService
from sales_intelligence.scoring import load_scoring_config


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("etl", help="Aggregate raw observations")
    parser.add_argument(
        "source",
        nargs="?",
        help="Optional local path; remote source defaults to RAW_DATASET_URL",
    )
    parser.add_argument(
        "--output", type=Path, default=Path("data/processed/companies.parquet")
    )
    parser.add_argument("--format", choices=("jsonl", "parquet"), default="parquet")
    parser.add_argument("--max-records", type=int)
    parser.add_argument("--dataset-version", help="Stable identifier; defaults to source checksum")
    parser.add_argument("--checkpoint", type=Path, help="Checkpoint file for resumable ETL")
    parser.add_argument("--checkpoint-interval", type=int, default=10_000)
    parser.add_argument("--dataset-runs-dir", type=Path, help="Directory for dataset run manifests and current pointer")
    parser.add_argument("--dataset-name", default="companies")
    parser.add_argument("--scoring-config", type=Path, help="JSON file overriding scoring weights; defaults to SCORING_CONFIG_PATH or built-in v1")


def run(args: argparse.Namespace) -> None:
    settings = Settings.from_env()
    source = args.source or settings.raw_dataset_url
    if not source:
        raise SystemExit("Set RAW_DATASET_URL in .env or provide a local source path")
    session_factory = create_session_factory(settings.database_url) if settings.database_url else None
    output = PipelineService().run(
        source,
        args.output,
        output_format=args.format,
        max_records=args.max_records,
        session_factory=session_factory,
        dataset_version=args.dataset_version,
        checkpoint_path=args.checkpoint,
        checkpoint_interval=args.checkpoint_interval,
        dataset_runs_dir=args.dataset_runs_dir,
        dataset_name=args.dataset_name,
        scoring_config=load_scoring_config(args.scoring_config),
    )
    AuditService(
        session_factory
    ).record(
        user_id="system",
        role="system",
        action="etl_completed",
        resource_type="analytical_dataset",
        resource_id=str(output),
        metadata={"source": source, "format": args.format, "max_records": args.max_records},
    )
    print(f"Wrote analytical dataset to {output}")
