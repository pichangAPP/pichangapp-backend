from sqlalchemy import BigInteger, Boolean, Column, ForeignKey, text
from sqlalchemy.orm import relationship

from app.core.database import Base


class RentSchedule(Base):
    """Links a rent to one or more schedules (e.g. combined fields)."""

    __tablename__ = "rent_schedule"
    __table_args__ = {"schema": "reservation"}

    id_rent = Column(BigInteger, ForeignKey("reservation.rent.id_rent", ondelete="CASCADE"), primary_key=True)
    id_schedule = Column(
        BigInteger,
        ForeignKey("reservation.schedule.id_schedule", ondelete="CASCADE"),
        primary_key=True,
    )
    is_primary = Column(Boolean, nullable=False, default=False, server_default=text("false"))

    rent = relationship("Rent", back_populates="schedule_links")
    schedule = relationship("Schedule", back_populates="rent_links")
