from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sales_intelligence.backend.models.base import Base


class CompanyAssignment(Base):
    __tablename__ = "company_assignments"

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True)
    user_id: Mapped[str] = mapped_column(String, primary_key=True)
    team_id: Mapped[str | None] = mapped_column(String)
    assigned_by: Mapped[str] = mapped_column(String, nullable=False)
    status: Mapped[str] = mapped_column(String, nullable=False, default="assigned")
    disposition: Mapped[str | None] = mapped_column(String)
    claimed_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    last_contacted_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    next_follow_up_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True))
    notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    company: Mapped["Company"] = relationship(back_populates="assignments")