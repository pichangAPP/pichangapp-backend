"""SQLAlchemy model representing a payment record accessible to the reservation service."""

from sqlalchemy import (
    BigInteger,
    Column,
    DateTime,
    ForeignKey,
    Identity,
    Integer,
    Numeric,
    String,
    Text,
    func,
)

from app.core.database import Base


class Payment(Base):
    """Represents a payment registered in the payment service."""

    __tablename__ = "payment"
    __table_args__ = {"schema": "payment"}

    id_payment = Column(
        BigInteger,
        primary_key=True,
        index=True,
        server_default=Identity(always=True),
    )
    amount = Column(Numeric(10, 2), nullable=False)
    currency = Column(String(30), nullable=False)
    method = Column(String(100), nullable=False)
    transaction_id = Column(
        BigInteger,
        nullable=False,
        server_default=Identity(always=True),
    )
    status = Column(String(30), nullable=False)
    type = Column(String(30), nullable=False)
    paid_at = Column(
        DateTime(timezone=True), nullable=False, server_default=func.now()
    )
    memberships_id_membership = Column(
        Integer,
        ForeignKey("payment.memberships.id_membership"),
        nullable=False,
    )
    reference = Column(String(100), nullable=True)
    additional_data = Column(Text, nullable=True)


__all__ = ["Payment"]
