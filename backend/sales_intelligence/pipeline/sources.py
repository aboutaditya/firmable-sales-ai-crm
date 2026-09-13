"""Streaming JSONL record sources: local files and HTTP(S) object URLs."""

from __future__ import annotations

import gzip
import hashlib
import io
import json
import urllib.request
from pathlib import Path
from typing import Iterator, TextIO
from urllib.parse import urlparse


class RecordSource:
    """Stream JSONL records from a local file or HTTP(S) object URL."""

    def __init__(self, source: str | Path):
        self.source = str(source)
        self._parsed = urlparse(self.source)

    @property
    def is_url(self) -> bool:
        return self._parsed.scheme in {"http", "https"}

    @property
    def name(self) -> str:
        return self._parsed.path if self.is_url else self.source

    @property
    def suffix(self) -> str:
        return Path(self.name).suffix.lower()

    def __iter__(self) -> Iterator[dict]:
        return self.records()

    def records(self) -> Iterator[dict]:
        """Stream parsed JSONL records from the source."""
        if self.is_url:
            yield from self._records_from_url()
            return
        suffix = self.suffix
        path = Path(self.source)
        if suffix == ".gz":
            with gzip.open(path, "rt", encoding="utf-8") as stream:
                yield from _iter_json_lines(stream)
            return
        if suffix == ".zst":
            try:
                import zstandard
            except ImportError as exc:
                raise RuntimeError("Reading .zst files requires: pip install zstandard") from exc
            with path.open("rb") as raw:
                with zstandard.ZstdDecompressor().stream_reader(raw) as decompressed:
                    stream = io.TextIOWrapper(decompressed)
                    yield from _iter_json_lines(stream)
            return
        with path.open("rt", encoding="utf-8") as stream:
            yield from _iter_json_lines(stream)

    def checksum(self) -> str:
        """Return a reproducible checksum for a local source, or its URL identity."""
        digest = hashlib.sha256()
        if self.is_url:
            digest.update(self.source.encode("utf-8"))
            return digest.hexdigest()
        with Path(self.source).open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                digest.update(chunk)
        return digest.hexdigest()

    def _records_from_url(self) -> Iterator[dict]:
        response = urllib.request.urlopen(self.source, timeout=120)
        stream: TextIO | None = None
        try:
            suffix = self.suffix
            remote_name = response.headers.get("x-bz-file-name", "")
            content_type = response.headers.get("content-type", "").lower()
            if remote_name.endswith(".zst") or "zstd" in content_type:
                suffix = ".zst"
            elif remote_name.endswith(".gz") or "gzip" in content_type:
                suffix = ".gz"
            binary_stream = response
            if suffix == ".zst":
                try:
                    import zstandard
                except ImportError as exc:
                    raise RuntimeError("Reading .zst files requires: pip install zstandard") from exc
                binary_stream = zstandard.ZstdDecompressor().stream_reader(response)
            elif suffix == ".gz":
                binary_stream = gzip.GzipFile(fileobj=response)
            stream = io.TextIOWrapper(binary_stream)
            yield from _iter_json_lines(stream)
        finally:
            if stream is not None:
                stream.close()
            response.close()


def _iter_json_lines(stream: TextIO) -> Iterator[dict]:
    for line_number, line in enumerate(stream, start=1):
        if not line.strip():
            continue
        try:
            record = json.loads(line)
        except json.JSONDecodeError as exc:
            raise ValueError(f"Invalid JSON on line {line_number}") from exc
        if not isinstance(record, dict):
            raise ValueError(f"Expected an object on line {line_number}")
        yield record