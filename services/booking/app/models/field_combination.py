from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import BigInteger, DateTime, ForeignKey, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.field import Field


class FieldCombination(Base):
    __tablename__ = "field_combination"
    __table_args__ = {"schema": "booking"}

    id_combination: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    id_campus: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("booking.campus.id_campus", ondelete="CASCADE"), nullable=False
    )
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, server_default="active")
    price_per_hour: Mapped[Decimal] = mapped_column(Numeric(10, 2), nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True), onupdate=func.now(), nullable=True
    )

    members: Mapped[list["FieldCombinationMember"]] = relationship(
        "FieldCombinationMember",
        back_populates="combination",
        cascade="all, delete-orphan",
        order_by="FieldCombinationMember.sort_order",
    )


class FieldCombinationMember(Base):
    __tablename__ = "field_combination_member"
    __table_args__ = {"schema": "booking"}

    id_combination: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("booking.field_combination.id_combination", ondelete="CASCADE"),
        primary_key=True,
    )
    id_field: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("booking.field.id_field", ondelete="CASCADE"),
        primary_key=True,
    )
    sort_order: Mapped[int] = mapped_column(Integer, nullable=False, server_default="0")

    combination: Mapped["FieldCombination"] = relationship(
        "FieldCombination", back_populates="members"
    )
    field: Mapped["Field"] = relationship("Field")
