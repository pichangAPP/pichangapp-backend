from sqlalchemy import Column, Integer, String, Text, DateTime, func

from app.core.database import Base


class Role(Base):
    __tablename__ = "rol"
    __table_args__ = {"schema": "auth"}

    id_role = Column(Integer, primary_key=True, index=True)
    role_name = Column(String(100), unique=True, nullable=False)
    description = Column(Text, nullable=True)
    status = Column(String(30), nullable=False, default="active")
