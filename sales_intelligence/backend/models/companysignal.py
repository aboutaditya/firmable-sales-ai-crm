from __future__ import annotations

from datetime import datetime

from sqlalchemy import Boolean, DateTime, ForeignKey, Integer, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from sales_intelligence.backend.models.base import Base


class CompanySignal(Base):
    __tablename__ = "company_signals"

    company_id: Mapped[str] = mapped_column(ForeignKey("companies.id", ondelete="CASCADE"), primary_key=True)
    asset_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unique_ip_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    unique_domain_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    vulnerability_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    critical_vulnerability_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    eol_product_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    exposed_rdp: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    exposed_database: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    exposed_exchange: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    security_tag_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    company: Mapped["Company"] = relationship(back_populates="signals")