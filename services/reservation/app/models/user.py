"""SQLAlchemy model mapping to the auth.users table."""

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String, Text
from sqlalchemy.sql import func

from app.core.database import Base


class User(Base):
    """Represents a user from the authentication service."""

    __tablename__ = "users"
    __table_args__ = {"schema": "auth"}

    id_user = Column(BigInteger, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    lastname = Column(String(200), nullable=False)
    email = Column(String(255), nullable=False, unique=True, index=True)
    phone = Column(String(20), nullable=False)
    imageurl = Column(Text, nullable=True)
    birthdate = Column(DateTime, nullable=False)
    gender = Column(String(10), nullable=False)
    city = Column(String(100), nullable=True)
    district = Column(String(100), nullable=True)
    password_hash = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
    status = Column(String(30), nullable=False, default="active")
    id_role = Column(Integer, ForeignKey("auth.rol.id_role"), nullable=False)

    def __repr__(self) -> str:  # pragma: no cover - debugging helper
        return f"<User(id_user={self.id_user}, email={self.email})>"
