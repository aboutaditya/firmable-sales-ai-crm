from __future__ import annotations

import argparse
from pathlib import Path

from sales_intelligence.config import Settings
from sales_intelligence.services.sync import DatabaseSyncService
from sales_intelligence.logging_config import configure_logging


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("sync", help="Sync qualified companies to PostgreSQL/Supabase")
    parser.add_argument("dataset", type=Path, nargs="?")
    parser.add_argument("--min-score", type=int, default=60)
    parser.add_argument("--dataset-version", default="unknown")
    parser.add_argument("--batch-size", type=int, default=1_000)


def run(args: argparse.Namespace) -> None:
    settings = Settings.from_env()
    configure_logging(settings.log_level)
    dataset = args.dataset or settings.analytical_dataset
    print(f"Starting sync: dataset={dataset} min_score={args.min_score} dataset_version={args.dataset_version} batch_size={args.batch_size}", flush=True)
    count = DatabaseSyncService().sync(
        dataset,
        settings.database_url or "",
        min_score=args.min_score,
        dataset_version=args.dataset_version,
        batch_size=args.batch_size,
    )
    print(f"Synchronized {count} qualified companies", flush=True)
