from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:  # pragma: no cover
    from app.models.campus import Campus


class Image(Base):
    __tablename__ = "images"
    __table_args__ = {"schema": "booking"}

    id_image: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    name_image: Mapped[str] = mapped_column(String(100), nullable=False)
    image_url: Mapped[str] = mapped_column(Text, nullable=False)
    state: Mapped[str] = mapped_column(String(30), nullable=False)
    deleted: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    id_campus: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("booking.campus.id_campus", ondelete="CASCADE"), nullable=False
    )

    campus: Mapped["Campus"] = relationship("Campus", back_populates="images")
