"""Recurring weekly windows when reservations are not allowed."""

from __future__ import annotations

from datetime import datetime, time

from sqlalchemy import BigInteger, Boolean, DateTime, ForeignKey, SmallInteger, String, Time, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class WeeklyScheduleClosure(Base):
    """Campus-wide or field-specific weekly closure (e.g. closed Wednesdays)."""

    __tablename__ = "weekly_schedule_closure"
    __table_args__ = {"schema": "booking"}

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    id_campus: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("booking.campus.id_campus", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    id_field: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("booking.field.id_field", ondelete="CASCADE"),
        nullable=True,
        index=True,
    )
    weekday: Mapped[int] = mapped_column(SmallInteger, nullable=False)
    local_start_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    local_end_time: Mapped[time | None] = mapped_column(Time, nullable=True)
    reason: Mapped[str | None] = mapped_column(String(500), nullable=True)
    is_active: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
    )
