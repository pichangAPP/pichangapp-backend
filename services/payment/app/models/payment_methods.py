"""SQLAlchemy model for business/campus payment method configuration."""

from __future__ import annotations

from sqlalchemy import (
    BigInteger,
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Identity,
    String,
    Text,
    UniqueConstraint,
    func,
)
from sqlalchemy.dialects.postgresql import JSONB

from app.core.database import Base


class PaymentMethods(Base):
    """Configurable payment methods for a business and campus."""

    __tablename__ = "payment_methods"
    __table_args__ = (
        UniqueConstraint(
            "id_business",
            "id_campus",
            name="uq_payment_methods_business_campus",
        ),
        {"schema": "payment"},
    )

    id_payment_methods = Column(
        BigInteger,
        primary_key=True,
        index=True,
        server_default=Identity(always=True),
    )

    id_business = Column(
        BigInteger,
        ForeignKey("booking.business.id_business", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    id_campus = Column(
        BigInteger,
        ForeignKey("booking.campus.id_campus", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    uses_cash = Column(Boolean, nullable=False, server_default="false")

    uses_yape = Column(Boolean, nullable=False, server_default="false")
    yape_phone = Column(String(20), nullable=True)
    yape_qr_url = Column(Text, nullable=True)

    uses_plin = Column(Boolean, nullable=False, server_default="false")
    plin_phone = Column(String(20), nullable=True)
    plin_qr_url = Column(Text, nullable=True)

    uses_bank_transfer = Column(Boolean, nullable=False, server_default="false")
    bank_name = Column(String(100), nullable=True)
    account_currency = Column(String(10), nullable=True)
    account_number = Column(String(50), nullable=True)
    cci = Column(String(50), nullable=True)
    account_holder_name = Column(String(200), nullable=True)
    account_holder_doc = Column(String(30), nullable=True)

    uses_card = Column(Boolean, nullable=False, server_default="false")
    card_provider = Column(String(60), nullable=True)
    merchant_id = Column(String(100), nullable=True)
    terminal_id = Column(String(100), nullable=True)
    public_key = Column(String(200), nullable=True)

    uses_pos = Column(Boolean, nullable=False, server_default="false")
    pos_provider = Column(String(60), nullable=True)
    pos_detail = Column(Text, nullable=True)

    uses_apple_pay = Column(Boolean, nullable=False, server_default="false")
    apple_pay_provider = Column(String(60), nullable=True)
    apple_pay_merchant_id = Column(String(120), nullable=True)

    uses_google_pay = Column(Boolean, nullable=False, server_default="false")
    google_pay_provider = Column(String(60), nullable=True)
    google_pay_merchant_id = Column(String(120), nullable=True)

    uses_invoice = Column(Boolean, nullable=False, server_default="false")
    invoice_detail = Column(Text, nullable=True)

    extra = Column(JSONB, nullable=True)

    status = Column(String(30), nullable=False, server_default="active")
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    updated_at = Column(
        DateTime(timezone=True),
        nullable=False,
        server_default=func.now(),
        onupdate=func.now(),
    )


__all__ = ["PaymentMethods"]
