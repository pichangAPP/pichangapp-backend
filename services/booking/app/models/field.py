from __future__ import annotations

from __future__ import annotations

from typing import TYPE_CHECKING

from datetime import time

from sqlalchemy import BigInteger, ForeignKey, Integer, Numeric, String, Text, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:  # pragma: no cover
    from app.models.campus import Campus
    from app.models.sport import Sport
    from app.models.image import Image


class Field(Base):
    __tablename__ = "field"
    __table_args__ = {"schema": "booking"}

    id_field: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    field_name: Mapped[str] = mapped_column(String(200), nullable=False)
    capacity: Mapped[int] = mapped_column(Integer, nullable=False)
    surface: Mapped[str] = mapped_column(String(100), nullable=False)
    measurement: Mapped[str] = mapped_column(Text, nullable=False)
    price_per_hour: Mapped[float] = mapped_column(Numeric(10, 2), nullable=False)
    status: Mapped[str] = mapped_column(String(100), nullable=False)
    open_time: Mapped[time] = mapped_column(Time, nullable=False)
    close_time: Mapped[time] = mapped_column(Time, nullable=False)
    minutes_wait: Mapped[float] = mapped_column(Numeric(6, 2), nullable=False)
    id_sport: Mapped[int] = mapped_column(Integer, ForeignKey("booking.sports.id_sport"), nullable=False)
    id_campus: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("booking.campus.id_campus", ondelete="CASCADE"), nullable=False
    )

    campus: Mapped["Campus"] = relationship("Campus", back_populates="fields")
    sport: Mapped["Sport"] = relationship("Sport", back_populates="fields")
    images: Mapped[list["Image"]] = relationship(
        "Image", back_populates="field", cascade="all, delete-orphan", passive_deletes=True
    )