from sqlalchemy import Column, BigInteger, String, Boolean, ForeignKey, DateTime, func

from app.core.database import Base


class UserSession(Base):
    __tablename__ = "sessions"
    __table_args__ = {"schema": "auth"}

    id_session = Column(BigInteger, primary_key=True, index=True)
    id_user = Column(BigInteger, ForeignKey("auth.users.id_user"), nullable=False)
    access_token = Column(String, nullable=False)
    refresh_token = Column(String, nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    expires_at = Column(DateTime(timezone=True), nullable=True)
