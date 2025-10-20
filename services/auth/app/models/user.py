from typing import TYPE_CHECKING
from sqlalchemy import Column, Integer, BigInteger, String, Text, DateTime, ForeignKey, func
from app.core.database import Base
from sqlalchemy.orm import relationship, Mapped


if TYPE_CHECKING:  # pragma: no cover
    from booking.app.models.campus import Campus

class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "auth"}  # 👈 importante

    id_user = Column(BigInteger, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    lastname = Column(String(200), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
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

