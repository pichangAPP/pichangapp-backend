"""auth.user_devices — tokens FCM por usuario."""

from sqlalchemy import BigInteger, Boolean, Column, DateTime, ForeignKey, String, Text, func, text

from app.core.database import Base


class UserDevice(Base):
    __tablename__ = "user_devices"
    __table_args__ = {"schema": "auth"}

    id_device = Column(BigInteger, primary_key=True, autoincrement=True)
    id_user = Column(BigInteger, ForeignKey("auth.users.id_user"), nullable=False, index=True)
    push_token = Column(Text, nullable=False, index=True)
    platform = Column(String(20), nullable=False)
    device_name = Column(String(200), nullable=True)
    is_active = Column(Boolean, nullable=False, server_default=text("true"))
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    updated_at = Column(DateTime(timezone=True), onupdate=func.now())
