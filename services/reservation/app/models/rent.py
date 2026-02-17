from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
    func,
    text,
)
from sqlalchemy.orm import relationship

from app.core.database import Base

class Rent(Base):

    __tablename__ = "rent"
    __table_args__ = {"schema": "reservation"}

    id_rent = Column(BigInteger, primary_key=True, index=True)
    period = Column(String(20), nullable=False)
    start_time = Column(DateTime(timezone=True), nullable=False)
    end_time = Column(DateTime(timezone=True), nullable=False)
    initialized = Column(DateTime(timezone=True), nullable=True)
    finished = Column(DateTime(timezone=True), nullable=True)
    status = Column(String(30), nullable=False)
    minutes = Column(Numeric(6, 2), nullable=False)
    mount = Column(Numeric(10, 2), nullable=False)
    date_log = Column(DateTime(timezone=True), nullable=False)
    date_create = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    payment_deadline = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP + INTERVAL '5 minutes'"),
    )
    capacity = Column(Integer, nullable=False)
    id_payment = Column(BigInteger, nullable=True)
    customer_full_name = Column(String(200), nullable=True)
    customer_phone = Column(String(20), nullable=True)
    customer_email = Column(String(200), nullable=True)
    customer_document = Column(String(30), nullable=True)
    customer_notes = Column(Text, nullable=True)
    id_schedule = Column(BigInteger, ForeignKey("reservation.schedule.id_schedule"), nullable=False)
    schedule = relationship("Schedule", back_populates="rents")

    def __repr__(self) -> str:
        return (
            f"<Rent(id_rent={self.id_rent}, status={self.status}, "
            f"start_time={self.start_time}, end_time={self.end_time}, "
            f"payment_deadline={self.payment_deadline})>"
        )
