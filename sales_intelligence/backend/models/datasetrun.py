from __future__ import annotations

from datetime import datetime
from uuid import uuid4

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from sales_intelligence.backend.models.base import Base


class DatasetRun(Base):
    """Durable dataset artifact and resumable progress record."""

    __tablename__ = "dataset_runs"

    run_id: Mapped[str] = mapped_column(String, primary_key=True, default=lambda: str(uuid4()))
    dataset_name: Mapped[str] = mapped_column(String, nullable=False, default="companies")
    dataset_version: Mapped[str] = mapped_column(String, nullable=False)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    source_checksum: Mapped[str | None] = mapped_column(String)
    source_etag: Mapped[str | None] = mapped_column(String)
    output_uri: Mapped[str | None] = mapped_column(Text)
    manifest_uri: Mapped[str | None] = mapped_column(Text)
    checkpoint_uri: Mapped[str | None] = mapped_column(Text)
    status: Mapped[str] = mapped_column(String, nullable=False, default="running")
    current_record: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    next_record: Mapped[int] = mapped_column(Integer, nullable=False, default=1)
    target_record: Mapped[int | None] = mapped_column(Integer)
    processed_rows: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    company_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    score_version: Mapped[str] = mapped_column(String, nullable=False)
    is_current: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    metadata_json: Mapped[dict] = mapped_column(JSON, nullable=False, default=dict)
    started_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())
    completed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    error_message: Mapped[str | None] = mapped_column(Text)