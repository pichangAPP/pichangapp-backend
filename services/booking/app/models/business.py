from __future__ import annotations

from typing import TYPE_CHECKING

from datetime import date, datetime

from sqlalchemy import BigInteger, Date, DateTime, Integer, Numeric, String, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:  # pragma: no cover
    from app.models.business_legal import BusinessLegal
    from app.models.campus import Campus
    from app.models.image import Image
    from app.models.business_social_media import BusinessSocialMedia


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
    updated_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        onupdate=func.now(),
        nullable=True,
    )
    district: Mapped[str] = mapped_column(String(50), nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    imageurl: Mapped[str | None] = mapped_column(Text, nullable=True)
    min_price: Mapped[float | None] = mapped_column(Numeric(10, 2), nullable=True)
    id_membership: Mapped[int] = mapped_column(Integer, nullable=False)
    id_manager: Mapped[int | None] = mapped_column(BigInteger, nullable=True)

    campuses: Mapped[list["Campus"]] = relationship(
        "Campus",
        back_populates="business",
        cascade="all, delete-orphan",
        passive_deletes=True,
    )

    images: Mapped[list["Image"]] = relationship(
        "Image", back_populates="business", cascade="all, delete-orphan", passive_deletes=True
    )

    social_media: Mapped["BusinessSocialMedia | None"] = relationship(
        "BusinessSocialMedia",
        back_populates="business",
        cascade="all, delete-orphan",
        single_parent=True,
        uselist=False,
        passive_deletes=True,
    )

    legal: Mapped["BusinessLegal | None"] = relationship(
        "BusinessLegal",
        back_populates="business",
        cascade="all, delete-orphan",
        single_parent=True,
        uselist=False,
        passive_deletes=True,
    )
