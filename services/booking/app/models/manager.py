from __future__ import annotations

from datetime import datetime
from typing import Optional

from sqlalchemy import BigInteger, Column, DateTime, ForeignKey, Integer, String, Table, Text, func
from sqlalchemy.orm import Mapped, mapped_column

from app.core.database import Base
Table(
    "rol",
    Base.metadata,
    Column("id_role", Integer, primary_key=True),
    schema="auth",
    keep_existing=True, 
)

class Manager(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "auth"}

    id_user: Mapped[int] = mapped_column(BigInteger, primary_key=True, index=True)
    name: Mapped[str] = mapped_column(String(200), nullable=False)
    lastname: Mapped[str] = mapped_column(String(200), nullable=False)
    email: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    phone: Mapped[str] = mapped_column(String(20), nullable=False)
    imageurl: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    birthdate: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    gender: Mapped[str] = mapped_column(String(10), nullable=False)
    city: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    district: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    password_hash: Mapped[str] = mapped_column(Text, nullable=False)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[Optional[datetime]] = mapped_column(DateTime(timezone=True), onupdate=func.now())
    status: Mapped[str] = mapped_column(String(30), nullable=False, default="active")
    id_role: Mapped[int] = mapped_column(Integer, ForeignKey("auth.rol.id_role"), nullable=False)