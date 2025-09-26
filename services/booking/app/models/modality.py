from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import Integer, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:  # pragma: no cover
    from app.models.sport import Sport


class Modality(Base):
    __tablename__ = "modality"
    __table_args__ = {"schema": "reservation"}

    id_modality: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    modality_description: Mapped[str] = mapped_column(Text, nullable=False)
    players: Mapped[int] = mapped_column(Integer, nullable=False)
    team: Mapped[int] = mapped_column(Integer, nullable=False)

    sports: Mapped[list["Sport"]] = relationship("Sport", back_populates="modality")
