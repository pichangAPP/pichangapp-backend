from __future__ import annotations

from sqlalchemy import BigInteger, Column

from app.core.database import Base


class Rent(Base):
    """Lightweight mapping for reservation rents used in analytics FKs."""

    __tablename__ = "rent"
    __table_args__ = {"schema": "reservation"}

    id_rent = Column(BigInteger, primary_key=True, index=True)


__all__ = ["Rent"]
