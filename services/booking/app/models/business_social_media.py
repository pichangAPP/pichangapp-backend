from __future__ import annotations

from typing import TYPE_CHECKING

from datetime import datetime

from sqlalchemy import BigInteger, Boolean, ForeignKey, String, Text, DateTime, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:  # pragma: no cover
    from app.models.business import Business


class BusinessSocialMedia(Base):
    __tablename__ = "business_social_media"
    __table_args__ = {"schema": "booking"}

    id_business_social_media: Mapped[int] = mapped_column(
        BigInteger, primary_key=True, index=True
    )
    id_business: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("booking.business.id_business", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )

    website_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    instagram_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    facebook_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    tiktok_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    youtube_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    x_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    linkedin_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    whatsapp_url: Mapped[str | None] = mapped_column(Text, nullable=True)
    google_maps_url: Mapped[str | None] = mapped_column(Text, nullable=True)

    instagram_handle: Mapped[str | None] = mapped_column(String(100), nullable=True)
    facebook_handle: Mapped[str | None] = mapped_column(String(100), nullable=True)
    tiktok_handle: Mapped[str | None] = mapped_column(String(100), nullable=True)
    youtube_handle: Mapped[str | None] = mapped_column(String(100), nullable=True)
    x_handle: Mapped[str | None] = mapped_column(String(100), nullable=True)
    linkedin_handle: Mapped[str | None] = mapped_column(String(100), nullable=True)

    is_public: Mapped[bool] = mapped_column(Boolean, nullable=False, server_default="true")
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), server_default=func.now(), nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )

    business: Mapped["Business"] = relationship("Business", back_populates="social_media")
