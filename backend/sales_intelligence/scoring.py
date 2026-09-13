"""Deterministic exposure scoring: weights and thresholds are configuration."""

from __future__ import annotations

import json
import os
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .pipeline import CompanyProfile


SCORE_VERSION = "v1"


@dataclass(frozen=True)
class ScoringConfig:
    """All tuning knobs for the deterministic exposure score.

    Defaults match the shipped v1 scoring model exactly. Override any field via
    a JSON config file (see :func:`load_scoring_config`) so weights can change
    without code edits.
    """

    score_version: str = SCORE_VERSION
    max_score: int = 100

    critical_vulnerability_points: int = 20
    vulnerability_points: int = 10
    vulnerability_count_threshold: int = 2

    exposed_rdp_points: int = 15
    exposed_database_points: int = 15
    exposed_exchange_points: int = 0

    eol_product_points: int = 10
    ip_threshold: int = 25
    ip_points: int = 10
    security_tag_points: int = 5

    @classmethod
    def from_dict(cls, data: dict) -> "ScoringConfig":
        defaults = asdict(DEFAULT_SCORING_CONFIG)
        for key, value in data.items():
            if key not in defaults:
                raise ValueError(f"unknown scoring config field: {key}")
            defaults[key] = value
        return cls(**defaults)

    @classmethod
    def from_json(cls, path: str | Path) -> "ScoringConfig":
        return cls.from_dict(json.loads(Path(path).read_text(encoding="utf-8")))


DEFAULT_SCORING_CONFIG = ScoringConfig()


def load_scoring_config(path: str | Path | None = None) -> ScoringConfig:
    """Load a scoring config from ``SCORING_CONFIG_PATH`` (or an explicit path).

    The JSON file may override any subset of :class:`ScoringConfig` fields;
    unset fields keep the defaults. Returns the defaults when no path is set.
    """
    configured = Path(path) if path else os.getenv("SCORING_CONFIG_PATH")
    if not configured:
        return DEFAULT_SCORING_CONFIG
    return ScoringConfig.from_json(configured)


def score(company: "CompanyProfile", config: ScoringConfig = DEFAULT_SCORING_CONFIG) -> int:
    points = 0
    points += config.critical_vulnerability_points if company.critical_vulnerability_count else 0
    if company.vulnerability_count >= config.vulnerability_count_threshold:
        points += config.vulnerability_points
    points += config.exposed_rdp_points if company.exposed_rdp else 0
    points += config.exposed_database_points if company.exposed_database else 0
    points += config.exposed_exchange_points if company.exposed_exchange else 0
    points += config.eol_product_points if company.eol_product_count else 0
    if company.unique_ip_count >= config.ip_threshold:
        points += config.ip_points
    points += config.security_tag_points if company.security_tag_count else 0
    return min(points, config.max_score)