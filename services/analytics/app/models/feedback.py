from __future__ import annotations

from sqlalchemy import BigInteger, Column, DateTime, Numeric, Text
from sqlalchemy.sql import func

from app.core.database import Base


class Feedback(Base):
    """Represents user feedback for completed rents."""

    __tablename__ = "feedback"
    __table_args__ = {"schema": "analytics"}

    id_feedback = Column(BigInteger, primary_key=True, index=True)
    rating = Column(Numeric(3, 1), nullable=True)
    comment = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), nullable=False, server_default=func.now())
    # External ids are stored as plain values to avoid cross-service ORM coupling.
    id_user = Column(BigInteger, nullable=False)
    id_rent = Column(BigInteger, nullable=False)


__all__ = ["Feedback"]
