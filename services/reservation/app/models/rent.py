"""SQLAlchemy model for reservation rents."""

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    BigInteger,
    func,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


class Rent(Base):
    """Represents a rent/booking for a schedule."""

    __tablename__ = "rent"
    __table_args__ = {"schema": "reservation"}

    id_rent = Column(BigInteger, primary_key=True, index=True)
    period = Column(String(20), nullable=False)
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    initialized = Column(DateTime(timezone=True), nullable=False)
    finished = Column(DateTime(timezone=True), nullable=False)
    status = Column(String(30), nullable=False)
    minutes = Column(Numeric(6, 2), nullable=False)
    mount = Column(Numeric(10, 2), nullable=False)
    date_log = Column(DateTime(timezone=True), nullable=False)
    date_create = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    capacity = Column(Integer, nullable=False)
    id_payment = Column(BigInteger, ForeignKey("payment.payment.id_payment"), nullable=False)
    id_schedule = Column(BigInteger, ForeignKey("reservation.schedule.id_schedule"), nullable=False)

    schedule = relationship("Schedule", back_populates="rents")

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return (
            "<Rent(id_rent={id}, status={status}, start_time={start}, end_time={end})>"
        ).format(
            id=self.id_rent,
            status=self.status,
            start=self.start_time,
            end=self.end_time,
        )
