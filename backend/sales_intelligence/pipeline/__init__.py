"""Company aggregation pipeline: source streaming, normalization, scoring, and export.

The heavy lifting lives in the class-based components in this package
(:class:`RecordSource`, :class:`CompaniesAggregator`, :class:`ProfileWriter`,
:class:`CompanyProfile`). The module-level functions below are thin wrappers
that keep the original ``sales_intelligence.pipeline`` API working.
"""

from __future__ import annotations

from pathlib import Path
from typing import Callable, Iterable, Iterator

from sales_intelligence.pipeline.aggregator import (
    CompaniesAggregator,
    company_id_for,
    normalize_domain,
)
from sales_intelligence.pipeline.models import CompanyProfile
from sales_intelligence.pipeline.sources import RecordSource
from sales_intelligence.pipeline.writer import ProfileWriter
from sales_intelligence.scoring import DEFAULT_SCORING_CONFIG, ScoringConfig

__all__ = [
    "CompanyProfile",
    "CompaniesAggregator",
    "ProfileWriter",
    "RecordSource",
    "aggregate",
    "company_id_for",
    "iter_records",
    "normalize_domain",
    "profile_from_state",
    "profile_to_state",
    "source_checksum",
    "write_profiles",
]


def aggregate(
    records: Iterable[dict],
    *,
    initial_profiles: Iterable[CompanyProfile] | None = None,
    on_record: Callable[[int, dict[str, CompanyProfile]], None] | None = None,
    scoring_config: ScoringConfig = DEFAULT_SCORING_CONFIG,
) -> list[CompanyProfile]:
    """Legacy functional API for :meth:`CompaniesAggregator.run`."""
    aggregator = CompaniesAggregator(
        scoring_config=scoring_config, initial_profiles=initial_profiles
    )
    return aggregator.run(records, on_record=on_record)


def iter_records(source: str | Path) -> Iterator[dict]:
    """Stream JSONL records from a local file or HTTP(S) object URL."""
    return RecordSource(source).records()


def source_checksum(source: str | Path) -> str:
    """Return a reproducible checksum for a local source, or its URL identity."""
    return RecordSource(source).checksum()


def write_profiles(
    profiles: Iterable[CompanyProfile],
    output: str | Path,
    format: str = "jsonl",
) -> Path:
    """Write company profiles to JSONL or Parquet output."""
    return ProfileWriter.write(profiles, output, format=format)


def profile_to_state(profile: CompanyProfile) -> dict:
    """Serialize a profile for checkpoint storage, including private sets."""
    return profile.to_state()


def profile_from_state(state: dict) -> CompanyProfile:
    """Rebuild a profile from a checkpoint state dict."""
    return CompanyProfile.from_state(state)