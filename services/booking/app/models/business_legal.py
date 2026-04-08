from __future__ import annotations

from typing import TYPE_CHECKING

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, ForeignKey, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:  # pragma: no cover
    from app.models.business import Business


class BusinessLegal(Base):
    __tablename__ = "business_legal"
    __table_args__ = {"schema": "booking"}

    id_business_legal: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    id_business: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("booking.business.id_business", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    terms_and_conditions: Mapped[str | None] = mapped_column(Text, nullable=True)
    terms_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    privacy_policy: Mapped[str | None] = mapped_column(Text, nullable=True)
    privacy_policy_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    cookies_policy: Mapped[str | None] = mapped_column(Text, nullable=True)
    cookies_policy_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    refund_policy: Mapped[str | None] = mapped_column(Text, nullable=True)
    refund_policy_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    version: Mapped[str | None] = mapped_column(String(30), nullable=True)
    effective_from: Mapped[date | None] = mapped_column(Date, nullable=True)
    last_reviewed_at: Mapped[date | None] = mapped_column(Date, nullable=True)

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    business: Mapped["Business"] = relationship("Business", back_populates="legal")
