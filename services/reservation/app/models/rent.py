from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    BigInteger,
    Table,
    func,
    text,
)
from sqlalchemy.orm import relationship
from typing import TYPE_CHECKING

from app.core.database import Base

Table(
    "memberships",
    Base.metadata,
    Column("id_membership", Integer, primary_key=True),
    schema="payment",
    keep_existing=True, 
)

class Rent(Base):

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
    payment_deadline = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=text("CURRENT_TIMESTAMP + INTERVAL '5 minutes'"),
    )
    capacity = Column(Integer, nullable=False)
    id_payment = Column(BigInteger, ForeignKey("payment.payment.id_payment"), nullable=True)
    id_schedule = Column(BigInteger, ForeignKey("reservation.schedule.id_schedule"), nullable=False)
    #Límite de pago
    payment_deadline = Column(DateTime(timezone=True), server_default=func.now())

    schedule = relationship("Schedule", back_populates="rents")

    def __repr__(self) -> str:
        return (
            f"<Rent(id_rent={self.id_rent}, status={self.status}, "
            f"start_time={self.start_time}, end_time={self.end_time}, "
            f"payment_deadline={self.payment_deadline})>"
        )
