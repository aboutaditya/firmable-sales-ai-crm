from __future__ import annotations

import argparse
import json
from pathlib import Path

from sales_intelligence.query import query_companies


def add_parser(subparsers: argparse._SubParsersAction) -> None:
    parser = subparsers.add_parser("query", help="Query ranked company profiles")
    parser.add_argument("dataset", type=Path)
    parser.add_argument("--company-id")
    parser.add_argument("--country")
    parser.add_argument("--min-score", type=int)
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--offset", type=int, default=0)


def run(args: argparse.Namespace) -> None:
    rows = query_companies(
        args.dataset,
        company_id=args.company_id,
        country=args.country,
        min_score=args.min_score,
        limit=args.limit,
        offset=args.offset,
    )
    for row in rows:
        print(json.dumps(row, sort_keys=True, default=str))
