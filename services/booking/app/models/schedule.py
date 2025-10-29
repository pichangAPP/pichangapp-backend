from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Schedule(Base):
    """Lightweight schedule model mapped to the reservation schema."""

    __tablename__ = "schedule"
    __table_args__ = {"schema": "reservation"}

    id_schedule: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    day_of_week: Mapped[str] = mapped_column(String(30), nullable=False)
    start_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    end_time: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    price: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    id_field: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("booking.field.id_field", ondelete="CASCADE"), nullable=False
    )
    id_user: Mapped[int] = mapped_column(BigInteger, ForeignKey("auth.users.id_user"), nullable=False)

    # Relationships are intentionally omitted because this model is only
    # used to read schedule metadata for response composition.
