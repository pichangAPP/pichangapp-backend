"""SQLAlchemy models for the payment service."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import DateTime, Float, Integer, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base


class Membership(Base):
    """Represents a purchasable membership plan."""

    __tablename__ = "memberships"
    __table_args__ = {"schema": "payment"}

    id_membership: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    membership_name: Mapped[str] = mapped_column(String(100), nullable=False)
    price: Mapped[float] = mapped_column(Float, nullable=False)
    duration: Mapped[int] = mapped_column(Integer, nullable=False)
    creation_date: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    date_payments: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return (
            "Membership(id_membership={id}, membership_name={name!r}, price={price})"
        ).format(id=self.id_membership, name=self.membership_name, price=self.price)
