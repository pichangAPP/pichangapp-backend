from __future__ import annotations

from typing import TYPE_CHECKING

from sqlalchemy import BigInteger, Boolean
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

if TYPE_CHECKING:  # pragma: no cover
    from app.models.campus import Campus


class Characteristic(Base):
    __tablename__ = "characteristic"
    __table_args__ = {"schema": "booking"}

    id_characteristic: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    lights: Mapped[bool] = mapped_column(Boolean, nullable=False)
    toilets: Mapped[bool] = mapped_column(Boolean, nullable=False)
    parking: Mapped[bool] = mapped_column(Boolean, nullable=False)
    jerseys: Mapped[bool] = mapped_column(Boolean, nullable=False)
    store: Mapped[bool] = mapped_column(Boolean, nullable=False)
    coffee: Mapped[bool] = mapped_column(Boolean, nullable=False)
    restaurant: Mapped[bool] = mapped_column(Boolean, nullable=False)
    arbitration: Mapped[bool] = mapped_column(Boolean, nullable=False)
    emergency_kit: Mapped[bool] = mapped_column(Boolean, nullable=False)
    streaming: Mapped[bool] = mapped_column(Boolean, nullable=False)
    rest_area: Mapped[bool] = mapped_column(Boolean, nullable=False)
    scoreboard: Mapped[bool] = mapped_column(Boolean, nullable=False)
    spectator_area: Mapped[bool] = mapped_column(Boolean, nullable=False)
    wifi: Mapped[bool] = mapped_column(Boolean, nullable=False)
    tournaments: Mapped[bool] = mapped_column(Boolean, nullable=False)
    coporative_event: Mapped[bool] = mapped_column(Boolean, nullable=False)
    recreational_act: Mapped[bool] = mapped_column(Boolean, nullable=False)

    campus: Mapped["Campus" | None] = relationship(
        "Campus", back_populates="characteristic", uselist=False
    )
