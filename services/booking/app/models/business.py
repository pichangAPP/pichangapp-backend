from __future__ import annotations

from typing import TYPE_CHECKING

from datetime import date

from sqlalchemy import BigInteger, Column, Date, ForeignKey, Integer, String, Text, Table, func
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base, engine

Table(
    "memberships",
    Base.metadata,
    Column("id_membership", Integer, primary_key=True),
    schema="payment",
    keep_existing=True, 
)


if TYPE_CHECKING:  # pragma: no cover
    from app.models.campus import Campus


class Business(Base):
    __tablename__ = "business"
    __table_args__ = {"schema": "booking"}

    id_business: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    ruc: Mapped[str | None] = mapped_column(String(30), nullable=True)
    email_contact: Mapped[str] = mapped_column(String(300), nullable=False)
    phone_contact: Mapped[str] = mapped_column(String(20), nullable=False)
    created_at: Mapped[date] = mapped_column(Date, server_default=func.current_date(), nullable=False)
    district: Mapped[str] = mapped_column(String(50), nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    id_membership: Mapped[int] = mapped_column(
        Integer, ForeignKey("payment.memberships.id_membership"), nullable=False
    )


    campuses: Mapped[list["Campus"]] = relationship(
        "Campus",
        back_populates="business",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )
