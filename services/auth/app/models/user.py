from sqlalchemy import Column, Integer, BigInteger, String, Text, DateTime, ForeignKey, func
from app.core.database import Base

class User(Base):
    __tablename__ = "users"
    __table_args__ = {"schema": "auth"}  # 👈 importante

    id_user = Column(BigInteger, primary_key=True, index=True)
    name = Column(String(200), nullable=False)
    email = Column(String(255), unique=True, nullable=False, index=True)
    phone = Column(String(20), nullable=False)
    password_hash = Column(Text, nullable=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    status = Column(String(30), nullable=False, default="active")
    rol_id_role = Column(Integer, ForeignKey("auth.rol.id_role"), nullable=False)
