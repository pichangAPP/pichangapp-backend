from __future__ import annotations

from typing import TYPE_CHECKING, Optional
from datetime import datetime

from sqlalchemy import BigInteger, Boolean, ForeignKey, String, Text,DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.business import Business

if TYPE_CHECKING:  # pragma: no cover
    from app.models.campus import Campus
    from app.models.field import Field


class Image(Base):
    __tablename__ = "images"
    __table_args__ = {"schema": "booking"}

    id_image: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    name_image: Mapped[str] = mapped_column(String(100), nullable=False)
    image_url: Mapped[str] = mapped_column(Text, nullable=False)
    type: Mapped[str] = mapped_column(String(30), nullable=False)  # Ejemplo: "business" o "campus"
    category: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)  # Ejemplo: "logo", "interior", etc.
    creation_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), nullable=False)
    modification_date: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now(), nullable=False)
    state: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    id_campus: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("booking.campus.id_campus", ondelete="CASCADE"), nullable=True
    )
    id_business: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("booking.business.id_business", ondelete="CASCADE"), nullable=True
    )
    id_field: Mapped[Optional[int]] = mapped_column(
        BigInteger, ForeignKey("booking.field.id_field", ondelete="CASCADE"), nullable=True
    )

    campus: Mapped[Optional["Campus"]] = relationship("Campus", back_populates="images")
    business: Mapped[Optional["Business"]] = relationship("Business", back_populates="images")
    field: Mapped[Optional["Field"]] = relationship("Field", back_populates="images")

