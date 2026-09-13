"""Operational command-line interface for the backend."""

from __future__ import annotations

import argparse

from .etl import add_parser as add_etl_parser
from .etl import run as run_etl
from .query import add_parser as add_query_parser
from .query import run as run_query
from .sync import add_parser as add_sync_parser
from .sync import run as run_sync


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="sales-intelligence")
    subparsers = parser.add_subparsers(dest="command", required=True)
    add_etl_parser(subparsers)
    add_query_parser(subparsers)
    add_sync_parser(subparsers)
    return parser


def main() -> None:
    args = build_parser().parse_args()
    if args.command == "etl":
        run_etl(args)
    elif args.command == "query":
        run_query(args)
    elif args.command == "sync":
        run_sync(args)


__all__ = ["build_parser", "main"]
