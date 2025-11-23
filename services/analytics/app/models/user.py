from __future__ import annotations

from sqlalchemy import BigInteger, Column

from app.core.database import Base


class User(Base):
    """Representation of a user known to the analytics domain."""

    __tablename__ = "users"
    __table_args__ = {"schema": "auth"}

    id_user = Column(BigInteger, primary_key=True, index=True)


__all__ = ["User"]
