from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:  # pragma: no cover
    from app.models.field import Field
    from app.models.modality import Modality


class Sport(Base):
    __tablename__ = "sports"
    __table_args__ = {"schema": "reservation"}

    id_sport: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    sport_name: Mapped[str] = mapped_column(String(100), nullable=False)
    sport_type: Mapped[str] = mapped_column(String(100), nullable=False)
    id_modality: Mapped[int] = mapped_column(
        Integer, ForeignKey("reservation.modality.id_modality"), nullable=False
    )

    modality: Mapped["Modality"] = relationship("Modality", back_populates="sports")
    fields: Mapped[list["Field"]] = relationship("Field", back_populates="sport")
