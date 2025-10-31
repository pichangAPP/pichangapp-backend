from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Numeric, String
from sqlalchemy.orm import relationship

from app.core.database import Base


class Schedule(Base):
    """Represents an available schedule for a sports field."""

    __tablename__ = "schedule"
    __table_args__ = {"schema": "reservation"}

    id_schedule = Column(BigInteger, primary_key=True, index=True)
    day_of_week = Column(String(30), nullable=False)
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(30), nullable=False)
    price = Column(Numeric(10, 2), nullable=False)
    id_field = Column(
        BigInteger, ForeignKey("booking.field.id_field"), nullable=True
    )
    id_user = Column(BigInteger, ForeignKey("auth.users.id_user"), nullable=True)

    rents = relationship("Rent", back_populates="schedule", cascade="all, delete-orphan")
    field = relationship("Field", lazy="joined")
    user = relationship("User", lazy="joined")

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return (
            "<Schedule(id_schedule={id}, day_of_week={day}, start_time={start}, end_time={end})>"
        ).format(
            id=self.id_schedule,
            day=self.day_of_week,
            start=self.start_time,
            end=self.end_time,
        )
