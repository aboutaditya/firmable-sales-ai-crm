"""Profile export to JSONL or Parquet."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Iterable

from sales_intelligence.pipeline.models import CompanyProfile


class ProfileWriter:
    """Writes company profiles to JSONL or Parquet output."""

    @staticmethod
    def write(
        profiles: Iterable[CompanyProfile],
        output: str | Path,
        format: str = "jsonl",
    ) -> Path:
        output = Path(output)
        output.parent.mkdir(parents=True, exist_ok=True)
        profiles = list(profiles)
        if format == "parquet":
            try:
                import pyarrow as pa
                import pyarrow.parquet as pq
            except ImportError as exc:
                raise RuntimeError("Parquet output requires: pip install -e '.[analytics]'") from exc
            table = pa.Table.from_pylist([profile.to_dict() for profile in profiles])
            pq.write_table(table, output)
        elif format == "jsonl":
            with output.open("w", encoding="utf-8") as stream:
                for profile in profiles:
                    stream.write(json.dumps(profile.to_dict(), sort_keys=True) + "\n")
        else:
            raise ValueError("format must be 'jsonl' or 'parquet'")
        return output