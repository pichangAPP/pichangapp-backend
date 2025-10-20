from __future__ import annotations

from typing import TYPE_CHECKING

from datetime import time

from sqlalchemy import BigInteger, Column, ForeignKey, Integer, Numeric, String, Table, Text, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base

Table(
    "users",
    Base.metadata,
    Column("id_user", BigInteger, primary_key=True),
    schema="auth",
    keep_existing=True,
)

if TYPE_CHECKING:  # pragma: no cover
    from app.models.business import Business
    from app.models.characteristic import Characteristic
    from app.models.field import Field
    from app.models.image import Image
    from auth.app.models.user import User 

class Campus(Base):
    __tablename__ = "campus"
    __table_args__ = {"schema": "booking"}

    id_campus: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str] = mapped_column(Text, nullable=False)
    address: Mapped[str] = mapped_column(Text, nullable=False)
    district: Mapped[str] = mapped_column(String(200), nullable=False)
    opentime: Mapped[time] = mapped_column(Time, nullable=False)
    closetime: Mapped[time] = mapped_column(Time, nullable=False)
    status: Mapped[str] = mapped_column(String(30), nullable=False)
    rating: Mapped[float] = mapped_column(Numeric(3, 1), nullable=False)
    count_fields: Mapped[int] = mapped_column(Integer, nullable=False)
    coords_x: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    coords_y: Mapped[float] = mapped_column(Numeric(9, 6), nullable=False)
    id_business: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("booking.business.id_business", ondelete="CASCADE"),
        nullable=False,
    )
    id_characteristic: Mapped[int] = mapped_column(
        BigInteger,
        ForeignKey("booking.characteristic.id_characteristic", ondelete="CASCADE"),
        nullable=False,
        unique=True,
    )
    id_manager: Mapped[int | None] = mapped_column(
        BigInteger,
        ForeignKey("auth.users.id_user", ondelete="SET NULL"),
        nullable=True,
    )
    

    business: Mapped["Business"] = relationship("Business", back_populates="campuses")
    characteristic: Mapped["Characteristic"] = relationship(
        "Characteristic",
        back_populates="campus",
        cascade="all, delete-orphan",
        single_parent=True,
    )
    fields: Mapped[list["Field"]] = relationship(
        "Field", back_populates="campus", cascade="all, delete-orphan", passive_deletes=True
    )
    images: Mapped[list["Image"]] = relationship(
        "Image", back_populates="campus", cascade="all, delete-orphan", passive_deletes=True
    )
    manager: Mapped["User"] = relationship(
        "auth.app.models.user.User",  # ruta absoluta al modelo User
        back_populates="campuses",
        lazy="joined"
    )
